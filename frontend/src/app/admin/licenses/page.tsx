'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Key, Shield, ShieldAlert, Loader2, Copy, Trash2, Download, Edit2, X } from 'lucide-react';
import api from '@/lib/api';

export default function LicensesPage() {
  const queryClient = useQueryClient();
  const [editingLicense, setEditingLicense] = useState<any>(null);
  
  const { data: licenses = [], isLoading, error } = useQuery({
    queryKey: ['admin-licenses'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/licenses');
      return data;
    }
  });

    const updateLicenseMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await api.put(`/api/v1/licenses/${data.id}`, {
        mt5_id: data.mt5_id,
        status: data.status,
        expiry_date: data.expiry_date ? new Date(data.expiry_date).toISOString() : null,
        purchase_date: data.purchase_date ? new Date(data.purchase_date).toISOString() : null,
        download_count: parseInt(data.download_count, 10),
        renew_count: parseInt(data.renew_count, 10)
      });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-licenses'] });
      setEditingLicense(null);
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || "Failed to update license");
    }
  });

  const deleteLicenseMutation = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.delete(`/api/v1/licenses/${id}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-licenses'] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.detail || "Failed to delete license");
    }
  });

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  const handleDownloadCsv = () => {
    window.open(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/licenses/export/csv`, '_blank');
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-blue-500" size={32} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-4 rounded-lg">
        Failed to load licenses.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Licenses</h1>
          <p className="text-neutral-400 mt-1">Manage active MT4/MT5 product licenses.</p>
        </div>
        <button
          onClick={handleDownloadCsv}
          className="flex items-center px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-medium transition-colors"
        >
          <Download size={18} className="mr-2" />
          Download CSV
        </button>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-neutral-400 bg-neutral-900/50 uppercase border-b border-neutral-800">
              <tr>
                <th className="px-6 py-4 whitespace-nowrap">License Key</th>
                <th className="px-6 py-4 whitespace-nowrap">Customer ID</th>
                <th className="px-6 py-4 whitespace-nowrap">MT4/MT5 ID</th>
                <th className="px-6 py-4 whitespace-nowrap">Type</th>
                <th className="px-6 py-4 whitespace-nowrap">Status</th>
                <th className="px-6 py-4 whitespace-nowrap">Expiry Date</th>
                <th className="px-6 py-4 text-right whitespace-nowrap">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {licenses.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-neutral-500">
                    No licenses found.
                  </td>
                </tr>
              ) : (
                licenses.map((license: any) => {
                  const expiryDate = license.expiry_date ? new Date(license.expiry_date) : null;
                  const now = new Date();
                  const daysExpired = expiryDate ? (now.getTime() - expiryDate.getTime()) / (1000 * 3600 * 24) : 0;
                  const canDelete = true;

                  return (
                    <tr key={license.id} className="hover:bg-neutral-800/30 transition-colors">
                      <td className="px-6 py-4 font-mono text-xs text-neutral-300 flex items-center space-x-2 whitespace-nowrap">
                        <Key size={14} className="text-indigo-400" />
                        <span>{license.id || license.key}</span>
                      </td>
                      <td className="px-6 py-4 text-neutral-400 whitespace-nowrap">{license.user_id || 'Guest'}</td>
                      <td className="px-6 py-4 font-mono text-xs text-white whitespace-nowrap">{license.mt5_id || 'N/A'}</td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {license.license_type === 'trial' ? (
                          <span className="bg-purple-500/20 text-purple-400 text-xs px-2 py-1 rounded-full font-medium">Trial</span>
                        ) : (
                          <span className="bg-blue-500/20 text-blue-400 text-xs px-2 py-1 rounded-full font-medium">Paid</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {license.status === 'active' || license.status === 'valid' ? (
                          <span className="flex items-center space-x-1 text-emerald-400 text-xs font-medium">
                            <Shield size={14} />
                            <span>Active</span>
                          </span>
                        ) : (
                          <span className="flex items-center space-x-1 text-red-400 text-xs font-medium">
                            <ShieldAlert size={14} />
                            <span>{license.status || 'Expired'}</span>
                          </span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-neutral-400">
                        {expiryDate ? expiryDate.toLocaleDateString() : 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-right space-x-2">
                        <button 
                          onClick={() => copyToClipboard(license.id || license.key)}
                          className="p-2 text-neutral-400 hover:text-white hover:bg-neutral-700 rounded transition-colors"
                          title="Copy Key"
                        >
                          <Copy size={16} />
                        </button>
                        <button 
                          onClick={() => setEditingLicense(license)}
                          className="p-2 text-neutral-400 hover:text-white hover:bg-neutral-700 rounded transition-colors"
                          title="Edit License"
                        >
                          <Edit2 size={16} />
                        </button>
                        <button 
                          onClick={() => {
                            if (confirm('Are you sure you want to delete this expired license?')) {
                              deleteLicenseMutation.mutate(license.id);
                            }
                          }}
                          disabled={!canDelete}
                          className={`p-2 rounded transition-colors ${canDelete ? 'text-red-400 hover:bg-red-500/10 hover:text-red-300 cursor-pointer' : 'text-neutral-600 cursor-not-allowed'}`}
                          title="Delete License"
                        >
                          <Trash2 size={16} />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
      
      {/* Edit Modal */}
      {editingLicense && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl max-w-md w-full overflow-hidden shadow-2xl overflow-y-auto max-h-[90vh]">
            <div className="flex items-center justify-between p-4 border-b border-neutral-800 sticky top-0 bg-neutral-900 z-10">
              <h2 className="font-semibold text-white">Edit License</h2>
              <button 
                onClick={() => setEditingLicense(null)}
                className="text-neutral-400 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            
            <form 
              onSubmit={(e) => {
                e.preventDefault();
                updateLicenseMutation.mutate(editingLicense);
              }}
              className="p-4 space-y-4"
            >
              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">MT5 ID</label>
                <input
                  type="text"
                  required
                  value={editingLicense.mt5_id || ''}
                  onChange={(e) => setEditingLicense({...editingLicense, mt5_id: e.target.value})}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">Status</label>
                <select
                  value={editingLicense.status || 'active'}
                  onChange={(e) => setEditingLicense({...editingLicense, status: e.target.value})}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                >
                  <option value="active">Active</option>
                  <option value="expired">Expired</option>
                  <option value="generating">Generating</option>
                  <option value="failed">Failed</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">Purchase Date</label>
                <input
                  type="date"
                  value={editingLicense.purchase_date ? editingLicense.purchase_date.split('T')[0] : ''}
                  onChange={(e) => setEditingLicense({...editingLicense, purchase_date: e.target.value})}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">Expiry Date</label>
                <input
                  type="date"
                  value={editingLicense.expiry_date ? editingLicense.expiry_date.split('T')[0] : ''}
                  onChange={(e) => setEditingLicense({...editingLicense, expiry_date: e.target.value})}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-neutral-400 mb-1">Download Count</label>
                  <input
                    type="number"
                    min="0"
                    value={editingLicense.download_count ?? 0}
                    onChange={(e) => setEditingLicense({...editingLicense, download_count: e.target.value})}
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-400 mb-1">Renew Count</label>
                  <input
                    type="number"
                    min="0"
                    value={editingLicense.renew_count ?? 0}
                    onChange={(e) => setEditingLicense({...editingLicense, renew_count: e.target.value})}
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-3 pt-4 sticky bottom-0 bg-neutral-900 pb-2">
                <button
                  type="button"
                  onClick={() => setEditingLicense(null)}
                  className="px-4 py-2 text-neutral-400 hover:text-white transition-colors font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={updateLicenseMutation.isPending}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium transition-colors disabled:opacity-50 flex items-center"
                >
                  {updateLicenseMutation.isPending && <Loader2 size={16} className="animate-spin mr-2" />}
                  Save Changes
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
