'use client';

import { useQuery } from '@tanstack/react-query';
import { 
  Users, 
  ShoppingCart, 
  Activity, 
  DollarSign, 
  ArrowUpRight, 
  ArrowDownRight,
  Loader2
} from 'lucide-react';
import api from '@/lib/api';

const StatCard = ({ title, value, icon: Icon, trend }: { title: string, value: string | number, icon: any, trend?: { value: string, isPositive: boolean } }) => (
  <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
    <div className="flex items-center justify-between">
      <div>
        <p className="text-sm font-medium text-neutral-400 mb-1">{title}</p>
        <h3 className="text-2xl font-bold text-white">{value}</h3>
      </div>
      <div className="p-3 bg-neutral-800/50 rounded-lg">
        <Icon className="text-blue-400" size={24} />
      </div>
    </div>
    {trend && (
      <div className={`mt-4 flex items-center text-sm ${trend.isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
        {trend.isPositive ? <ArrowUpRight size={16} className="mr-1" /> : <ArrowDownRight size={16} className="mr-1" />}
        <span className="font-medium">{trend.value}</span>
        <span className="text-neutral-500 ml-2">vs last month</span>
      </div>
    )}
  </div>
);

export default function DashboardPage() {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: async () => {
      const { data } = await api.get('/api/v1/admin/stats');
      return data;
    }
  });

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
        Failed to load dashboard statistics.
      </div>
    );
  }

  // Map snake_case API response to display values
  const displayStats = stats ? {
    totalRevenue: stats.total_revenue || 0,
    totalOrders: stats.total_orders || 0,
    activeLicenses: stats.active_licenses || 0,
    totalUsers: stats.total_users || 0
  } : {
    totalRevenue: 0,
    totalOrders: 0,
    activeLicenses: 0,
    totalUsers: 0
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">Overview</h1>
        <p className="text-neutral-400 mt-1">Welcome back, here's what's happening today.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total Revenue"
          value={`₹${(displayStats.totalRevenue || 0).toLocaleString()}`}
          icon={DollarSign}
          trend={{ value: "+12.5%", isPositive: true }}
        />
        <StatCard
          title="Total Orders"
          value={displayStats.totalOrders}
          icon={ShoppingCart}
          trend={{ value: "+5.2%", isPositive: true }}
        />
        <StatCard
          title="Active Licenses"
          value={displayStats.activeLicenses}
          icon={Activity}
          trend={{ value: "+18.1%", isPositive: true }}
        />
        <StatCard
          title="Total Users"
          value={displayStats.totalUsers}
          icon={Users}
          trend={{ value: "-2.4%", isPositive: false }}
        />
      </div>
    </div>
  );
}
