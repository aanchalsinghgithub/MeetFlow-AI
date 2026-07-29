import { FormEvent, useState } from 'react';
import { Bot, LogIn } from 'lucide-react';
import { useAuth } from '../auth';

export function Login({ onShowSignup, onBack }: { onShowSignup: () => void; onBack?: () => void }) {
  const auth = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await auth.login({ email, password });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in');
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthFrame title="Sign in" subtitle="Use your company account to access isolated meeting intelligence." onBack={onBack}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email" type="email" value={email} onChange={setEmail} />
        <Field label="Password" type="password" value={password} onChange={setPassword} />
        {error && <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        <button className="inline-flex h-11 w-full items-center justify-center gap-2 rounded bg-ocean px-4 text-sm font-medium text-white hover:bg-[#0b5d56]" disabled={loading}>
          <LogIn size={18} />
          {loading ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
      <button className="mt-4 text-sm font-medium text-ocean hover:underline" onClick={onShowSignup}>
        Create a company workspace
      </button>
    </AuthFrame>
  );
}

export function AuthFrame({
  title,
  subtitle,
  children,
  onBack
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
  onBack?: () => void;
}) {
  return (
    <div className="grid min-h-screen bg-[#f7f8f5] text-ink lg:grid-cols-[1.1fr_0.9fr]">
      <section className="relative hidden overflow-hidden bg-ocean p-10 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 rounded-full bg-white/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 -left-16 h-96 w-96 rounded-full bg-coral/20 blur-3xl" />
        <button
          className="relative flex items-center gap-3 text-left"
          onClick={onBack}
          disabled={!onBack}
        >
          <div className="grid h-11 w-11 place-items-center rounded bg-white text-ocean">
            <Bot size={23} />
          </div>
          <div>
            <div className="text-xl font-semibold">MeetFlow AI</div>
            <div className="text-sm text-white/70">Multi-tenant meeting automation</div>
          </div>
        </button>
        <div className="relative">
          <h1 className="max-w-xl text-5xl font-semibold leading-tight">One deployment. Fully isolated company workspaces.</h1>
          <p className="mt-5 max-w-lg text-white/75">
            Connect Google Calendar, auto-join meetings, extract tasks, and route approvals without exposing another company&apos;s data.
          </p>
        </div>
      </section>
      <section className="flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          {onBack && (
            <button
              className="mb-4 flex items-center gap-2 text-sm font-medium text-stone-500 hover:text-ocean lg:hidden"
              onClick={onBack}
            >
              <Bot size={16} />
              MeetFlow AI
            </button>
          )}
          <div className="rounded border border-stone-200 bg-white p-6 shadow-sm">
            <h2 className="text-2xl font-semibold">{title}</h2>
            <p className="mt-2 text-sm text-stone-500">{subtitle}</p>
            <div className="mt-6">{children}</div>
          </div>
        </div>
      </section>
    </div>
  );
}

export function Field({
  label,
  type = 'text',
  value,
  onChange
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-stone-700">{label}</span>
      <input
        className="mt-2 h-11 w-full rounded border border-stone-300 px-3 text-sm outline-none focus:border-ocean focus:ring-2 focus:ring-ocean/20"
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        required
      />
    </label>
  );
}
