/// <reference types="vite/client" />

interface Window {
  electronAPI?: {
    getAuthToken?: () => Promise<string | null>;
    setAuthToken?: (token: string) => Promise<{ ok: boolean }>;
    clearAuthToken?: () => Promise<{ ok: boolean }>;
    onSignOut?: (callback: () => void) => () => void;
  };
}
