import { useState } from 'react';
import { api } from '../services/api';

export default function Login({ onAuthenticated, onShowSignup }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await api.login({ email, password });
      await window.electronAPI?.setAuthToken?.(data.access_token);
      onAuthenticated(data.access_token);
    } catch (err) {
      // api.js throws `POST /api/auth/login -> 401: {"detail":"..."}`
      // Pull the detail out if present, otherwise fall back to the raw message.
      let message = err.message || 'Could not sign in';
      const match = message.match(/"detail":"([^"]+)"/);
      if (match) message = match[1];
      else if (message.includes('401')) message = 'Incorrect email or password';
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.wrap}>
      <div style={styles.card}>
        <div style={styles.logo}>⚡ MeetFlow Desktop</div>
        <div style={styles.subtitle}>Sign in to your company workspace</div>

        <form onSubmit={submit} style={styles.form}>
          <label style={styles.label}>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />
          </label>
          <label style={styles.label}>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>

          {error && <div style={styles.error}>⚠ {error}</div>}

          <button className="primary" type="submit" disabled={loading} style={styles.submitBtn}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <button className="ghost" onClick={onShowSignup} style={styles.switchBtn}>
          Create a company workspace
        </button>
      </div>
    </div>
  );
}

const styles = {
  wrap: {
    height: '100%',
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'var(--bg)',
  },
  card: {
    width: 340,
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: 24,
  },
  logo: { fontWeight: 700, fontSize: 16, marginBottom: 4 },
  subtitle: { color: 'var(--muted)', fontSize: 12, marginBottom: 20 },
  form: { display: 'flex', flexDirection: 'column', gap: 14 },
  label: { display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: 'var(--muted)' },
  error: { color: 'var(--danger)', fontSize: 12 },
  submitBtn: { width: '100%', padding: '9px 0', marginTop: 4 },
  switchBtn: { width: '100%', marginTop: 16, padding: '8px 0' },
};
