/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import apiClient from '../services/api';

interface User {
  id: string;
  username: string;
  role: string;
  organizationId: string | null;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isAuthenticated: boolean;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const AUTH_STORAGE_KEY = 'auth_state';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore auth state from localStorage on mount
  useEffect(() => {
    const storedAuth = localStorage.getItem(AUTH_STORAGE_KEY);
    if (storedAuth) {
      try {
        const { user: storedUser, token: storedToken } = JSON.parse(storedAuth);
        if (storedUser && storedToken) {
          setUser(storedUser);
          setToken(storedToken);
          apiClient.setToken(storedToken);
        }
      } catch (error) {
        console.error('Failed to restore auth state:', error);
        localStorage.removeItem(AUTH_STORAGE_KEY);
      }
    }
    setIsLoading(false);
  }, []);

  // Persist auth state to localStorage whenever it changes
  useEffect(() => {
    if (!isLoading) {
      if (user && token) {
        localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ user, token }));
      } else {
        localStorage.removeItem(AUTH_STORAGE_KEY);
      }
    }
  }, [user, token, isLoading]);

  const login = async (username: string, password: string) => {
    try {
      const response = await apiClient.login({ username, password });

      // Set token in API client
      apiClient.setToken(response.access_token);

      // Store token and user info
      setToken(response.access_token);
      setUser({
        id: response.user_id,
        username,
        role: response.role,
        organizationId: response.organization_id,
      });
    } catch (error) {
      // Clear any existing auth state on login failure
      apiClient.setToken(null);
      setToken(null);
      setUser(null);
      throw error;
    }
  };

  const logout = () => {
    apiClient.setToken(null);
    setUser(null);
    setToken(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        logout,
        isAuthenticated: !!user && !!token,
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
