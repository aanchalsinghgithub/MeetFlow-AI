import { useState } from 'react';
import { api } from '../services/api';

export default function Signup({ onAuthenticated, onShowLogin }) {
  const [companyName, setCompanyName] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await api.register({
        company_name: companyName,
        full_name: fullName,
        email,
        password,
      });
      await window.electronAPI?.setAuthToken?.(data.access_token);
      onAuthenticated(data.access_token);
    } catch (err) {
      let message = err.message || 'Could not create workspace';
      const match = message.match(/"detail":"([^"]+)"/);
      if (match) message = match[1];
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.wrap}>
      <div style={styles.card}>
        <div style={styles.logo}>⚡ MeetFlow Desktop</div>
        <div style={styles.subtitle}>Register a company and its first manager account</div>

        <form onSubmit={submit} style={styles.form}>
          <label style={styles.label}>
            Company name
            <input
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              required
              autoFocus
            />
          </label>
          <label style={styles.label}>
            Full name
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </label>
          <label style={styles.label}>
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
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
            {loading ? 'Creating…' : 'Create workspace'}
          </button>
        </form>

        <button className="ghost" onClick={onShowLogin} style={styles.switchBtn}>
          Already have an account? Sign in
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
