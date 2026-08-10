import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bot, CheckCircle2, Trash2, UploadCloud } from 'lucide-react';
import { useState } from 'react';
import { api, BotSessionStatus, clearBotSession, uploadBotSessionCookiesFile } from '../api';

// Lets an org admin connect the meeting bot's Google account entirely from
// the browser — no codebase, terminal, or Python required on their end.
// Anonymous guest joins get blocked by Google as automated traffic; a real
// logged-in account joining is far more reliable. See CHANGES.md for the
// full story on why this has to be a *cookie export*, not a scripted login
// (Google detects and blocks any automated browser touching its sign-in
// flow, even a real Chrome profile driven by Playwright).
export function BotAccountSettings() {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const status = useQuery({
    queryKey: ['bot-session-status'],
    queryFn: async () => (await api.get<BotSessionStatus>('/api/organizations/google-bot-session')).data
  });

  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Choose the cookies.txt file you exported first.');
      if (!email) throw new Error('Enter the Google account email the bot logged in as.');
      return uploadBotSessionCookiesFile(email, file);
    },
    onSuccess: () => {
      setFormError(null);
      setFile(null);
      setEmail('');
      queryClient.invalidateQueries({ queryKey: ['bot-session-status'] });
    },
    onError: (err: any) => {
      setFormError(err?.response?.data?.detail ?? err?.message ?? 'Upload failed.');
    }
  });

  const clear = useMutation({
    mutationFn: clearBotSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['bot-session-status'] })
  });

  return (
    <div className="rounded border border-stone-200 bg-white p-4">
      <div className="mb-2 flex items-center gap-2 font-semibold">
        <Bot size={18} />
        Meeting Bot Google Account
      </div>

      {status.data?.configured ? (
        <div className="mb-4 flex items-center justify-between rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
          <span className="flex items-center gap-2">
            <CheckCircle2 size={16} />
            Bot joins meetings as <strong>{status.data.email}</strong>
          </span>
          <button
            className="inline-flex items-center gap-1 rounded border border-emerald-300 px-2 py-1 text-xs font-medium hover:bg-emerald-100 disabled:opacity-50"
            onClick={() => clear.mutate()}
            disabled={clear.isPending}
          >
            <Trash2 size={14} />
            {clear.isPending ? 'Removing...' : 'Remove'}
          </button>
        </div>
      ) : (
        <p className="mb-4 text-sm text-stone-600">
          Not configured yet — the bot currently joins meetings as an anonymous guest, which Google is
          more likely to block. Connect a real Google account below instead.
        </p>
      )}

      <ol className="mb-4 list-decimal space-y-1 pl-5 text-sm text-stone-600">
        <li>
          Install{' '}
          <a
            className="text-ocean hover:underline"
            href="https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc"
            target="_blank"
            rel="noreferrer"
          >
            Get cookies.txt LOCALLY
          </a>{' '}
          from the Chrome Web Store.
        </li>
        <li>Sign in normally to the Google account you want the bot to use.</li>
        <li>
          Go to <code className="rounded bg-stone-100 px-1">meet.google.com</code> while signed in.
        </li>
        <li>Click the extension icon → Export → save the file.</li>
        <li>Upload that file below.</li>
      </ol>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <input
          type="email"
          placeholder="bot@example.com"
          className="h-10 flex-1 rounded border border-stone-300 px-3 text-sm"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <input
          type="file"
          accept=".txt"
          className="h-10 flex-1 rounded border border-stone-300 px-3 py-2 text-sm file:mr-2 file:rounded file:border-0 file:bg-stone-100 file:px-2 file:py-1 file:text-xs"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)}
        />
        <button
          className="inline-flex h-10 items-center gap-2 rounded bg-ocean px-4 text-sm font-medium text-white hover:bg-[#0c5f59] disabled:opacity-50"
          onClick={() => upload.mutate()}
          disabled={upload.isPending}
        >
          <UploadCloud size={16} />
          {upload.isPending ? 'Uploading...' : 'Upload'}
        </button>
      </div>

      {formError && <p className="mt-2 text-sm text-red-600">{formError}</p>}
    </div>
  );
}
