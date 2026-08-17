'use client';

import { useState, useEffect, useRef } from 'react';
import {
  FileCode2,
  UploadCloud,
  CheckCircle2,
  Download,
  Trash2,
  Clock,
  History,
  ShieldCheck,
} from 'lucide-react';
import api from '@/lib/api';

interface EaTemplateSummary {
  id: number;
  version_label: string | null;
  filename: string | null;
  file_size: number;
  is_active: boolean;
  notes: string | null;
  uploaded_by: string | null;
  created_at: string | null;
}

export default function EaTemplatePage() {
  const [versions, setVersions] = useState<EaTemplateSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [versionLabel, setVersionLabel] = useState('');
  const [notes, setNotes] = useState('');
  const [uploadedBy, setUploadedBy] = useState('');
  const [activateOnUpload, setActivateOnUpload] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchVersions();
  }, []);

  const fetchVersions = async () => {
    try {
      const { data } = await api.get('/api/v1/ea-templates/admin/list');
      setVersions(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const activeVersion = versions.find(v => v.is_active);

  const handleUpload = async () => {
    if (!selectedFile) {
      setErr('Choose a .mq5 file first');
      return;
    }
    setUploading(true);
    setErr('');
    setMsg('');
    try {
      const form = new FormData();
      form.append('file', selectedFile);
      if (versionLabel) form.append('version_label', versionLabel);
      if (notes) form.append('notes', notes);
      if (uploadedBy) form.append('uploaded_by', uploadedBy);
      form.append('activate', String(activateOnUpload));

      await api.post('/api/v1/ea-templates/admin/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setMsg('EA template uploaded successfully!');
      setSelectedFile(null);
      setVersionLabel('');
      setNotes('');
      setUploadedBy('');
      if (fileInputRef.current) fileInputRef.current.value = '';
      await fetchVersions();
      setTimeout(() => setMsg(''), 3000);
    } catch (e: any) {
      console.error(e);
      setErr(e?.response?.data?.detail || 'Failed to upload EA template');
    } finally {
      setUploading(false);
    }
  };

  const handleActivate = async (id: number) => {
    setErr('');
    try {
      await api.post(`/api/v1/ea-templates/admin/${id}/activate`);
      await fetchVersions();
    } catch (e: any) {
      console.error(e);
      setErr(e?.response?.data?.detail || 'Failed to activate version');
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this EA template version? This cannot be undone.')) return;
    setErr('');
    try {
      await api.delete(`/api/v1/ea-templates/admin/${id}`);
      await fetchVersions();
    } catch (e: any) {
      console.error(e);
      setErr(e?.response?.data?.detail || 'Failed to delete version');
    }
  };

  const handleDownload = async (id: number, filename: string | null) => {
    try {
      const { data } = await api.get(`/api/v1/ea-templates/admin/${id}`);
      const blob = new Blob([data.source_code], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename || `ea-template-${id}.mq5`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      setErr('Failed to download version');
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    return `${(bytes / 1024).toFixed(1)} KB`;
  };

  if (loading) return <div className="text-white">Loading EA template versions...</div>;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <FileCode2 className="text-blue-500" size={32} />
            EA File / Version Management
          </h1>
          <p className="text-neutral-400 mt-1">
            Upload a new EA source (.mq5) file to replace what the compiler worker builds for customers — no code changes needed.
          </p>
        </div>
      </div>

      {activeVersion ? (
        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-5 flex items-center gap-4">
          <ShieldCheck className="text-emerald-400 shrink-0" size={28} />
          <div>
            <p className="text-emerald-400 font-medium">
              Active version: {activeVersion.version_label || `#${activeVersion.id}`} ({activeVersion.filename})
            </p>
            <p className="text-emerald-400/70 text-sm">
              This is what the compiler worker will fetch and build for the next order.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-yellow-500/10 border border-yellow-500/20 text-yellow-400 rounded-xl p-5">
          No active EA template configured yet. Upload one below to get started.
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Upload Card */}
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
          <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
            <UploadCloud size={20} className="text-blue-400" />
            Upload New EA File
          </h2>

          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-white block mb-1">EA Source File (.mq5)</label>
              <input
                ref={fileInputRef}
                type="file"
                accept=".mq5,.mqh,.txt"
                onChange={e => setSelectedFile(e.target.files?.[0] || null)}
                className="w-full text-sm text-neutral-300 bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 file:mr-4 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:bg-blue-600 file:text-white file:text-sm hover:file:bg-blue-700 file:cursor-pointer"
              />
              {selectedFile && (
                <p className="text-xs text-neutral-500 mt-1">
                  {selectedFile.name} ({formatSize(selectedFile.size)})
                </p>
              )}
            </div>

            <div>
              <label className="text-sm font-medium text-white block mb-1">Version Label</label>
              <input
                type="text"
                placeholder="e.g. v2.3 - fixed trailing stop"
                value={versionLabel}
                onChange={e => setVersionLabel(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-white block mb-1">Notes</label>
              <textarea
                placeholder="What changed in this version?"
                value={notes}
                onChange={e => setNotes(e.target.value)}
                rows={2}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 resize-none"
              />
            </div>

            <div>
              <label className="text-sm font-medium text-white block mb-1">Uploaded By</label>
              <input
                type="text"
                placeholder="e.g. your name"
                value={uploadedBy}
                onChange={e => setUploadedBy(e.target.value)}
                className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500"
              />
            </div>

            <div className="flex items-center justify-between pt-1">
              <div>
                <label className="text-sm font-medium text-white block">Activate Immediately</label>
                <span className="text-xs text-neutral-400">Next compile job uses this version right away</span>
              </div>
              <button
                onClick={() => setActivateOnUpload(!activateOnUpload)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                  activateOnUpload ? 'bg-green-500' : 'bg-neutral-600'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    activateOnUpload ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>

            <div className="pt-4 border-t border-neutral-800">
              <button
                onClick={handleUpload}
                disabled={uploading || !selectedFile}
                className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
              >
                <UploadCloud size={18} />
                {uploading ? 'Uploading...' : 'Upload EA File'}
              </button>
              {msg && (
                <p className="text-green-400 text-sm mt-2 text-center flex items-center justify-center gap-1">
                  <CheckCircle2 size={14} /> {msg}
                </p>
              )}
              {err && <p className="text-red-400 text-sm mt-2 text-center">{err}</p>}
            </div>
          </div>
        </div>

        {/* How it works Card */}
        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
          <h2 className="text-xl font-semibold text-white mb-6 flex items-center gap-2">
            <FileCode2 size={20} className="text-indigo-400" />
            How This Works
          </h2>
          <ol className="space-y-4 text-sm text-neutral-400 list-decimal list-inside">
            <li>Upload the new <code className="text-neutral-300">.mq5</code> source file the client sends you.</li>
            <li>It's saved as a new version here — nothing is overwritten, old versions stay available.</li>
            <li>Mark it "Active" (or check the box on upload) to make it the live template.</li>
            <li>The compiler worker automatically pulls the active version before every compile job — no manual file copying, no code edits.</li>
            <li>If something looks wrong, just activate a previous version from the history below.</li>
          </ol>
        </div>
      </div>

      {/* Version History */}
      <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
        <div className="p-6 pb-0">
          <h2 className="text-xl font-semibold text-white mb-1 flex items-center gap-2">
            <History size={20} className="text-neutral-400" />
            Version History
          </h2>
          <p className="text-neutral-500 text-sm mb-4">All uploaded EA source versions, most recent first.</p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-neutral-400 bg-neutral-900/50 uppercase border-b border-neutral-800">
              <tr>
                <th className="px-6 py-3">Version</th>
                <th className="px-6 py-3">File</th>
                <th className="px-6 py-3">Size</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Uploaded</th>
                <th className="px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {versions.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-neutral-500">
                    No EA template versions uploaded yet.
                  </td>
                </tr>
              ) : (
                versions.map(v => (
                  <tr key={v.id} className="hover:bg-neutral-800/30 transition-colors">
                    <td className="px-6 py-4 text-neutral-300">
                      {v.version_label || `#${v.id}`}
                      {v.notes && <p className="text-xs text-neutral-500 mt-0.5 max-w-xs truncate">{v.notes}</p>}
                    </td>
                    <td className="px-6 py-4 text-neutral-400 font-mono text-xs">{v.filename}</td>
                    <td className="px-6 py-4 text-neutral-400">{formatSize(v.file_size)}</td>
                    <td className="px-6 py-4">
                      {v.is_active ? (
                        <span className="flex items-center gap-1 text-emerald-400 text-xs font-medium">
                          <CheckCircle2 size={14} /> Active
                        </span>
                      ) : (
                        <span className="text-neutral-500 text-xs">Inactive</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-neutral-400 text-xs flex items-center gap-1">
                      <Clock size={12} />
                      {v.created_at ? new Date(v.created_at).toLocaleString() : '—'}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-end gap-2">
                        {!v.is_active && (
                          <button
                            onClick={() => handleActivate(v.id)}
                            className="text-xs px-3 py-1.5 rounded-lg bg-blue-600/10 text-blue-400 hover:bg-blue-600/20 transition-colors"
                          >
                            Activate
                          </button>
                        )}
                        <button
                          onClick={() => handleDownload(v.id, v.filename)}
                          className="p-1.5 rounded-lg text-neutral-400 hover:text-white hover:bg-neutral-800 transition-colors"
                          title="Download"
                        >
                          <Download size={16} />
                        </button>
                        {!v.is_active && (
                          <button
                            onClick={() => handleDelete(v.id)}
                            className="p-1.5 rounded-lg text-neutral-400 hover:text-red-400 hover:bg-red-500/10 transition-colors"
                            title="Delete"
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
