import { FormEvent, useState } from 'react';
import { UserPlus } from 'lucide-react';
import { useAuth } from '../auth';
import { AuthFrame, Field } from './Login';

export function Signup({ onShowLogin, onBack }: { onShowLogin: () => void; onBack?: () => void }) {
  const auth = useAuth();
  const [companyName, setCompanyName] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await auth.signup({
        company_name: companyName,
        full_name: fullName,
        email,
        password
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create workspace');
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthFrame title="Create workspace" subtitle="Register a company and its first manager account." onBack={onBack}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Company name" value={companyName} onChange={setCompanyName} />
        <Field label="Full name" value={fullName} onChange={setFullName} />
        <Field label="Email" type="email" value={email} onChange={setEmail} />
        <Field label="Password" type="password" value={password} onChange={setPassword} />
        {error && <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        <button className="inline-flex h-11 w-full items-center justify-center gap-2 rounded bg-ocean px-4 text-sm font-medium text-white hover:bg-[#0b5d56]" disabled={loading}>
          <UserPlus size={18} />
          {loading ? 'Creating...' : 'Create workspace'}
        </button>
      </form>
      <button className="mt-4 text-sm font-medium text-ocean hover:underline" onClick={onShowLogin}>
        Already have an account? Sign in
      </button>
    </AuthFrame>
  );
}
