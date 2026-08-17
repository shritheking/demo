'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Server, Check, X, Loader2 } from 'lucide-react';
import api from '@/lib/api';

export default function VpsOrdersPage() {
  const queryClient = useQueryClient();
  const [selectedOrder, setSelectedOrder] = useState<any>(null);
  const [ip, setIp] = useState('');
  const [username, setUsername] = useState('Administrator');
  const [password, setPassword] = useState('');

  const { data: vpsOrders = [], isLoading, error } = useQuery({
    queryKey: ['admin-vps-orders'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/admin/vps-orders');
      return data;
    }
  });

  const provisionMutation = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.post(`/api/v1/admin/vps-orders/${selectedOrder.id}/provision`, payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-vps-orders'] });
      closeModal();
    }
  });

  const openModal = (order: any) => {
    setSelectedOrder(order);
    setIp('');
    setUsername('Administrator');
    setPassword('');
  };

  const closeModal = () => {
    setSelectedOrder(null);
  };

  const handleProvision = (e: React.FormEvent) => {
    e.preventDefault();
    provisionMutation.mutate({ ip, username, password });
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
        Failed to load VPS orders.
      </div>
    );
  }

  return (
    <div className="space-y-6 relative">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">VPS Provisioning</h1>
          <p className="text-neutral-400 mt-1">Manage and provision VPS servers for customers.</p>
        </div>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-neutral-400 bg-neutral-900/50 uppercase border-b border-neutral-800">
              <tr>
                <th className="px-6 py-4">Order ID</th>
                <th className="px-6 py-4">Customer</th>
                <th className="px-6 py-4">Plan</th>
                <th className="px-6 py-4">Terminals</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {vpsOrders.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-neutral-500">
                    No VPS orders found.
                  </td>
                </tr>
              ) : (
                vpsOrders.map((order: any) => (
                  <tr key={order.id} className="hover:bg-neutral-800/30 transition-colors">
                    <td className="px-6 py-4 font-medium text-neutral-300">#{order.id}</td>
                    <td className="px-6 py-4 text-white">{order.customer || 'Guest'}</td>
                    <td className="px-6 py-4 text-neutral-400">{order.plan_name || 'Standard'}</td>
                    <td className="px-6 py-4 text-neutral-400">{order.terminals_allowed || 2}</td>
                    <td className="px-6 py-4">
                      {order.status === 'active' || order.status === 'provisioned' ? (
                        <span className="px-2 py-1 bg-emerald-500/10 text-emerald-400 rounded text-xs font-medium border border-emerald-500/20">Provisioned</span>
                      ) : (
                        <span className="px-2 py-1 bg-yellow-500/10 text-yellow-400 rounded text-xs font-medium border border-yellow-500/20">Pending</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right">
                      {order.status !== 'provisioned' && order.status !== 'active' && (
                        <button 
                          onClick={() => openModal(order)}
                          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-medium transition-colors"
                        >
                          Provision
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Provisioning Modal */}
      {selectedOrder && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl w-full max-w-md shadow-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-neutral-800 flex items-center justify-between">
              <h3 className="text-lg font-bold text-white flex items-center">
                <Server size={18} className="mr-2 text-blue-400" />
                Provision VPS #{selectedOrder.id}
              </h3>
              <button 
                onClick={closeModal}
                className="text-neutral-500 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleProvision} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">Server IP Address</label>
                <input 
                  type="text" 
                  required
                  value={ip}
                  onChange={(e) => setIp(e.target.value)}
                  placeholder="e.g. 192.168.1.100"
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">Username</label>
                <input 
                  type="text" 
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">Password</label>
                <input 
                  type="password" 
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
              
              <div className="pt-4 flex justify-end space-x-3">
                <button 
                  type="button"
                  onClick={closeModal}
                  className="px-4 py-2 text-neutral-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={provisionMutation.isPending}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg font-medium flex items-center transition-colors"
                >
                  {provisionMutation.isPending ? (
                    <>
                      <Loader2 size={16} className="animate-spin mr-2" />
                      Provisioning...
                    </>
                  ) : (
                    <>
                      <Check size={16} className="mr-2" />
                      Complete Provisioning
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
