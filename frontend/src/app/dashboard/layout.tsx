'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Phone, LayoutDashboard, Settings, LogOut, BookOpen, BarChart2, Calendar } from 'lucide-react';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading, logout } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) router.push('/auth/login');
  }, [user, isLoading, router]);

  if (isLoading || !user) return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" /></div>;

  return (
    <div className="min-h-screen flex">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r flex flex-col">
        <div className="p-6 border-b">
          <span className="text-xl font-bold text-primary">Zylinn</span>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {[
            { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
            { href: '/dashboard/appointments', icon: Calendar, label: 'Appointments' },
            { href: '/dashboard/agents', icon: Settings, label: 'Receptionists' },
            { href: '/dashboard/calls', icon: Phone, label: 'Call History' },
            { href: '/dashboard/knowledge', icon: BookOpen, label: 'Knowledge Base' },
            { href: '/dashboard/billing', icon: BarChart2, label: 'Usage & Billing' },
          ].map(({ href, icon: Icon, label }) => (
            <Link key={href} href={href} className="flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-100 hover:text-primary transition-colors">
              <Icon size={18} />{label}
            </Link>
          ))}
        </nav>
        <div className="p-4 border-t">
          <Button variant="ghost" className="w-full justify-start gap-3 text-gray-600" onClick={logout}>
            <LogOut size={18} />Sign out
          </Button>
        </div>
      </aside>
      {/* Main */}
      <main className="flex-1 overflow-auto bg-gray-50">{children}</main>
    </div>
  );
}
