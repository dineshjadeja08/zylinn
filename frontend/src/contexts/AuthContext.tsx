'use client';
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authApi } from '@/lib/api';

interface User {
  id: number;
  email: string;
  full_name?: string;
  role: string;
  customer_id: string;
}

interface Customer {
  customer_id: string;
  company_name: string;
  plan_type: string;
  calls_this_month: number;
  max_calls_per_month: number;
  status: string;
}

interface AuthState {
  user: User | null;
  customer: Customer | null;
  token: string | null;
  isLoading: boolean;
}

interface AuthContextType extends AuthState {
  login: (token: string, user: User) => void;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null, customer: null, token: null, isLoading: true,
  });

  useEffect(() => {
    const token = localStorage.getItem('zylinn_token');
    if (token) {
      authApi.me()
        .then(res => setState({ user: res.data.user, customer: res.data.customer, token, isLoading: false }))
        .catch(() => { localStorage.removeItem('zylinn_token'); setState(s => ({ ...s, isLoading: false })); });
    } else {
      setState(s => ({ ...s, isLoading: false }));
    }
  }, []);

  const login = (token: string, user: User) => {
    localStorage.setItem('zylinn_token', token);
    setState(s => ({ ...s, user, token }));
    authApi.me().then(res => setState(s => ({ ...s, customer: res.data.customer }))).catch(() => {});
  };

  const logout = () => {
    localStorage.removeItem('zylinn_token');
    setState({ user: null, customer: null, token: null, isLoading: false });
    window.location.href = '/auth/login';
  };

  const refreshUser = async () => {
    const res = await authApi.me();
    setState(s => ({ ...s, user: res.data.user, customer: res.data.customer }));
  };

  return <AuthContext.Provider value={{ ...state, login, logout, refreshUser }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
