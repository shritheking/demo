'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Package, Plus, Loader2, Edit, Trash2, X, Check } from 'lucide-react';
import api from '@/lib/api';

export default function ProductsPage() {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingProductId, setEditingProductId] = useState<number | null>(null);
  
  // Form State
  const [name, setName] = useState('');
  const [type, setType] = useState('EA');
  const [price, setPrice] = useState('');
  const [duration, setDuration] = useState('1');
  const [description, setDescription] = useState('');

  const { data: products = [], isLoading, error } = useQuery({
    queryKey: ['admin-products'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/products');
      return data;
    }
  });

  const createProductMutation = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.post('/api/v1/products/', payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-products'] });
      closeModal();
    }
  });

  const updateProductMutation = useMutation({
    mutationFn: async (payload: any) => {
      const { data } = await api.put(`/api/v1/products/${editingProductId}`, payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-products'] });
      closeModal();
    }
  });

  const deleteProductMutation = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await api.delete(`/api/v1/products/${id}`);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-products'] });
    }
  });

  const openModal = (product: any = null) => {
    if (product) {
      setEditingProductId(product.id);
      setName(product.name);
      setType(product.type);
      setPrice(product.price.toString());
      setDuration(product.duration.toString());
      setDescription(product.description || '');
    } else {
      setEditingProductId(null);
      setName('');
      setType('EA');
      setPrice('');
      setDuration('1');
      setDescription('');
    }
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      name,
      type,
      price: parseFloat(price),
      duration: parseInt(duration, 10),
      description,
      active: true
    };
    
    if (editingProductId) {
      updateProductMutation.mutate(payload);
    } else {
      createProductMutation.mutate(payload);
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
        Failed to load products.
      </div>
    );
  }

  return (
    <div className="space-y-6 relative">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Products</h1>
          <p className="text-neutral-400 mt-1">Manage trading bots and VPS packages.</p>
        </div>
        <button 
          onClick={openModal}
          className="flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors"
        >
          <Plus size={18} className="mr-2" />
          Add Product
        </button>
      </div>

      <div className="bg-neutral-900 border border-neutral-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-neutral-400 bg-neutral-900/50 uppercase border-b border-neutral-800">
              <tr>
                <th className="px-6 py-4">Name</th>
                <th className="px-6 py-4">Type</th>
                <th className="px-6 py-4">Price (₹)</th>
                <th className="px-6 py-4">Duration</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {products.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-neutral-500">
                    No products found. Click "Add Product" to create one.
                  </td>
                </tr>
              ) : (
                products.map((product: any) => (
                  <tr key={product.id} className="hover:bg-neutral-800/30 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center">
                        <div className="h-8 w-8 rounded bg-neutral-800 flex items-center justify-center mr-3">
                          <Package size={16} className="text-neutral-400" />
                        </div>
                        <span className="font-medium text-white">{product.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-neutral-400 capitalize">{product.type}</td>
                    <td className="px-6 py-4 text-neutral-300">₹{product.price?.toLocaleString() || 0}</td>
                    <td className="px-6 py-4 text-neutral-400">{product.duration} Months</td>
                    <td className="px-6 py-4">
                      {product.active ? (
                        <span className="px-2 py-1 bg-emerald-500/10 text-emerald-400 rounded text-xs font-medium border border-emerald-500/20">
                          Active
                        </span>
                      ) : (
                        <span className="px-2 py-1 bg-neutral-500/10 text-neutral-400 rounded text-xs font-medium border border-neutral-500/20">
                          Inactive
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button 
                        onClick={() => openModal(product)}
                        className="p-2 text-neutral-400 hover:text-white hover:bg-neutral-700 rounded transition-colors" title="Edit"
                      >
                        <Edit size={16} />
                      </button>
                      <button 
                        onClick={() => {
                          if (confirm('Are you sure you want to delete this product?')) {
                            deleteProductMutation.mutate(product.id);
                          }
                        }}
                        className="p-2 text-neutral-400 hover:text-red-400 hover:bg-red-500/10 rounded transition-colors" title="Delete"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Product Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-xl w-full max-w-md shadow-2xl overflow-hidden">
            <div className="px-6 py-4 border-b border-neutral-800 flex items-center justify-between">
              <h3 className="text-lg font-bold text-white flex items-center">
                {editingProductId ? (
                  <>
                    <Edit size={18} className="mr-2 text-blue-400" />
                    Edit Product
                  </>
                ) : (
                  <>
                    <Plus size={18} className="mr-2 text-blue-400" />
                    Add New Product
                  </>
                )}
              </h3>
              <button 
                onClick={closeModal}
                className="text-neutral-500 hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>
            
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">Product Name</label>
                <input 
                  type="text" 
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. EA Basic Plan"
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-neutral-400 mb-1">Product Type</label>
                  <select
                    value={type}
                    onChange={(e) => setType(e.target.value)}
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="EA">EA License</option>
                    <option value="VPS">VPS Hosting</option>
                  </select>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-neutral-400 mb-1">Price (₹)</label>
                  <input 
                    type="number" 
                    required
                    min="0"
                    step="0.01"
                    value={price}
                    onChange={(e) => setPrice(e.target.value)}
                    placeholder="500"
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">Duration (Months)</label>
                <input 
                  type="number" 
                  required
                  min="1"
                  value={duration}
                  onChange={(e) => setDuration(e.target.value)}
                  placeholder="1"
                  className="w-full bg-neutral-950 border border-neutral-800 rounded-lg px-4 py-2 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-neutral-400 mb-1">Description (Optional)</label>
                <textarea 
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Brief description of the plan..."
                  rows={2}
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
                  disabled={createProductMutation.isPending || updateProductMutation.isPending}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg font-medium flex items-center transition-colors"
                >
                  {createProductMutation.isPending || updateProductMutation.isPending ? (
                    <>
                      <Loader2 size={16} className="animate-spin mr-2" />
                      {editingProductId ? 'Updating...' : 'Creating...'}
                    </>
                  ) : (
                    <>
                      <Check size={16} className="mr-2" />
                      {editingProductId ? 'Update Product' : 'Create Product'}
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
