'use client';
import { useAuth } from '@/contexts/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Phone, Clock, TrendingUp, Bot } from 'lucide-react';

export default function DashboardPage() {
  const { user, customer } = useAuth();

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Welcome back{user?.full_name ? `, ${user.full_name}` : ''}!</h1>
        <p className="text-gray-500 mt-1">{customer?.company_name} · {customer?.plan_type} plan</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Calls This Month</CardTitle>
            <Phone size={16} className="text-gray-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{customer?.calls_this_month ?? 0}</div>
            <p className="text-xs text-gray-500 mt-1">of {customer?.max_calls_per_month ?? 100} included</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Avg Call Duration</CardTitle>
            <Clock size={16} className="text-gray-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">—</div>
            <p className="text-xs text-gray-500 mt-1">Available after first call</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Appointments Booked</CardTitle>
            <TrendingUp size={16} className="text-gray-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">—</div>
            <p className="text-xs text-gray-500 mt-1">This month</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-gray-500">Active Receptionists</CardTitle>
            <Bot size={16} className="text-gray-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">—</div>
            <p className="text-xs text-gray-500 mt-1">Configure in Receptionists</p>
          </CardContent>
        </Card>
      </div>
      <div className="mt-8 p-6 bg-primary/5 border border-primary/20 rounded-lg">
        <h2 className="text-lg font-semibold text-primary mb-2">🚀 Get started</h2>
        <ol className="list-decimal list-inside space-y-2 text-sm text-gray-700">
          <li>Go to <strong>Receptionists</strong> and create your first AI receptionist</li>
          <li>Add knowledge from your website or FAQ in <strong>Knowledge Base</strong></li>
          <li>Test your agent using the browser test console</li>
          <li>Request a phone number to receive real inbound calls</li>
        </ol>
      </div>
    </div>
  );
}
