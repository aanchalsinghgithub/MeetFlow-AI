import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // Loads .env / .env.local etc. for the current mode (3rd arg '' means
  // load all vars, not just VITE_-prefixed ones, so plain PORT also works)
  const env = loadEnv(mode, process.cwd(), '');

  return {
    plugins: [react],
    server: {
      port: Number(env.VITE_PORT) || 5173
    }
  };
});
