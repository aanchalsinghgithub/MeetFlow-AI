import { useEffect, useState } from 'react';

const TOKEN_KEY = 'meetflow.access_token';
const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

let memoryToken: string | null = localStorage.getItem(TOKEN_KEY);
const listeners = new Set<() => void>();

type AuthResponse = {
  access_token: string;
  token_type: string;
};

type LoginPayload = {
  email: string;
  password: string;
};

type SignupPayload = LoginPayload & {
  company_name: string;
  full_name: string;
};

function emit() {
  listeners.forEach((listener) => listener());
}

async function requestToken(path: string, payload: LoginPayload | SignupPayload): Promise<string> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Authentication failed' }));
    throw new Error(error.detail ?? 'Authentication failed');
  }
  const data = (await response.json()) as AuthResponse;
  setAuthToken(data.access_token);
  return data.access_token;
}

export function getAuthToken() {
  return memoryToken;
}

export function setAuthToken(token: string | null) {
  memoryToken = token;
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
    void window.electronAPI?.setAuthToken?.(token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
    void window.electronAPI?.clearAuthToken?.();
  }
  emit();
}

export function useAuth() {
  const [token, setToken] = useState(memoryToken);

  useEffect(() => {
    let mounted = true;
    window.electronAPI?.getAuthToken?.().then((storedToken: string | null) => {
      if (mounted && storedToken && storedToken !== memoryToken) {
        setAuthToken(storedToken);
      }
    });
    const listener = () => setToken(memoryToken);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  return {
    token,
    isAuthenticated: Boolean(token),
    login: (payload: LoginPayload) => requestToken('/api/auth/login', payload),
    signup: (payload: SignupPayload) => requestToken('/api/auth/register', payload),
    logout: () => setAuthToken(null)
  };
}
