'use client';

import { useQuery } from '@tanstack/react-query';
import { Eye, Loader2 } from 'lucide-react';
import api from '@/lib/api';

export default function OrdersPage() {
  const { data: orders = [], isLoading, error } = useQuery({
    queryKey: ['admin-orders'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/admin/all_orders');
      return data;
    }
  });

  const getStatusBadge = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'paid':
        return <span className="px-2 py-1 bg-emerald-500/10 text-emerald-400 rounded text-xs font-medium border border-emerald-500/20">Paid</span>;
      case 'pending':
        return <span className="px-2 py-1 bg-yellow-500/10 text-yellow-400 rounded text-xs font-medium border border-yellow-500/20">Pending</span>;
      case 'failed':
        return <span className="px-2 py-1 bg-red-500/10 text-red-400 rounded text-xs font-medium border border-red-500/20">Failed</span>;
      default:
        return <span className="px-2 py-1 bg-neutral-500/10 text-neutral-400 rounded text-xs font-medium border border-neutral-500/20">{status || 'Unknown'}</span>;
    }
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
        Failed to load orders.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Orders</h1>
          <p className="text-neutral-400 mt-1">Manage and view all customer orders.</p>
        </div>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-neutral-400 bg-neutral-900/50 uppercase border-b border-neutral-800">
              <tr>
                <th className="px-6 py-4">Order ID</th>
                <th className="px-6 py-4">Product</th>
                <th className="px-6 py-4">Customer</th>
                <th className="px-6 py-4">Amount (₹)</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Date</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {orders.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-8 text-center text-neutral-500">
                    No orders found.
                  </td>
                </tr>
              ) : (
                orders.map((order: any) => (
                  <tr key={order.id} className="hover:bg-neutral-800/30 transition-colors">
                    <td className="px-6 py-4 font-medium text-neutral-300">#{order.id}</td>
                    <td className="px-6 py-4 text-white">{order.product || 'Unknown'}</td>
                    <td className="px-6 py-4 text-neutral-400">{order.customer || 'Guest'}</td>
                    <td className="px-6 py-4 text-neutral-300">₹{order.amount?.toLocaleString() || 0}</td>
                    <td className="px-6 py-4">{getStatusBadge(order.status)}</td>
                    <td className="px-6 py-4 text-neutral-400">{new Date(order.date || Date.now()).toLocaleDateString()}</td>
                    <td className="px-6 py-4 text-right">
                      <button className="p-2 text-neutral-400 hover:text-white hover:bg-neutral-700 rounded transition-colors" title="View Details">
                        <Eye size={16} />
                      </button>
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
