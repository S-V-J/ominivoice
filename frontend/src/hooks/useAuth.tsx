import { createContext, useContext, useEffect, ReactNode } from 'react';
import { useAuthStore } from '../store/authStore';
import { api } from '../services/api';

interface AuthContextType {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { setTokens, setUser, logout: logoutStore, setLoading } = useAuthStore();

  const refreshUser = async () => {
    const token = useAuthStore.getState().accessToken;
    if (!token) return;

    try {
      const user = await api.getMe();
      setUser(user);
    } catch {
      logoutStore();
    } finally {
      setLoading(false);
    }
  };

  // Initialize auth on mount
  useEffect(() => {
    const { isAuthenticated, accessToken } = useAuthStore.getState();
    if (isAuthenticated && accessToken) {
      refreshUser();
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const { access_token, refresh_token } = await api.login(email, password);
    setTokens(access_token, refresh_token);
    await refreshUser();
  };

  const register = async (email: string, password: string) => {
    const { access_token, refresh_token } = await api.register(email, password);
    setTokens(access_token, refresh_token);
    await refreshUser();
  };

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      logoutStore();
    }
  };

  return (
    <AuthContext.Provider value={{ login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}