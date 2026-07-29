import { useEffect, useState } from 'react';
import {
  Bot,
  CalendarClock,
  ClipboardCheck,
  Mic,
  ShieldCheck,
  Send,
  ArrowRight,
  Users,
  Lock,
  Building2,
  ToggleRight,
  Sparkles,
  Star,
  Download,
  Link2,
  ListChecks,
  Play
} from 'lucide-react';

// Replace with your own GitHub repo's Releases page - the download button
// below sends people to whatever .exe is attached to your latest release
// (see: Settings/README "Step 3 - GitHub pe upload karna").
const DESKTOP_APP_RELEASES_URL = 'https://github.com/aanchalsinghgithub/MeetFlow-AI/releases/latest';

const pipeline = [
  { icon: CalendarClock, label: 'Auto-join meeting' },
  { icon: Mic, label: 'Transcribe & ID speakers' },
  { icon: ClipboardCheck, label: 'Extract action items' },
  { icon: ShieldCheck, label: 'Route for approval' },
  { icon: Send, label: 'Notify the owner' }
];

const features = [
  {
    icon: CalendarClock,
    title: 'Joins meetings for you',
    body: 'Connects to Google Calendar and drops into every call automatically - no one has to remember to hit record.'
  },
  {
    icon: Mic,
    title: 'Transcribes with speaker ID',
    body: 'Every line is attributed to the person who said it, so "who owns this" is never a guessing game afterward.'
  },
  {
    icon: ClipboardCheck,
    title: 'Turns talk into tasks',
    body: 'Action items, owners, deadlines, and priority are pulled straight out of the discussion - not typed up by hand.'
  },
  {
    icon: Users,
    title: 'Built for whole companies',
    body: 'Every organization gets its own isolated workspace, logins, and data - nothing crosses between companies.'
  }
];

const steps = [
  {
    icon: Building2,
    title: 'Create your workspace',
    body: 'Sign up with your work email. Your organization gets its own isolated workspace - separate logins, separate data, from every other company on MeetFlow.'
  },
  {
    icon: CalendarClock,
    title: 'Connect Google Calendar',
    body: 'Open the Meetings tab and click "Connect Google Calendar." Sign in with Google and allow read-only calendar access - it takes about ten seconds and nothing is ever written back to your calendar.'
  },
  {
    icon: ToggleRight,
    title: 'Turn on Auto Join',
    body: 'Every upcoming Google Meet call from your calendar shows up automatically. Flip the Auto Join switch on any of them and the bot joins on its own, records, and transcribes with speaker names.'
  },
  {
    icon: Send,
    title: 'The right people get emailed - automatically',
    body: 'Attendee addresses come straight from the calendar invite\u2019s guest list, so there\u2019s nothing to type. Approve a task and its owner is emailed; the meeting recap goes out to everyone who was on the call.'
  }
];

const desktopSteps = [
  {
    icon: Download,
    title: 'Download & install',
    body: 'Grab the Windows installer and run it - takes under a minute, no admin setup required.'
  },
  {
    icon: Link2,
    title: 'Connect it to your workspace',
    body: 'Open the app, paste your workspace URL into the "Backend" box at the top, and click Connect.'
  },
  {
    icon: CalendarClock,
    title: 'Connect Google Calendar',
    body: 'One-time step, done from the web dashboard\u2019s Meetings tab - sign in with Google and allow read-only access. Takes about ten seconds, and every upcoming call then shows up in the desktop app too.'
  },
  {
    icon: ListChecks,
    title: 'Pick the meeting',
    body: 'Your upcoming Google Meet calls show up automatically under the Meetings tab - select the one you\u2019re on.'
  },
  {
    icon: Play,
    title: 'Start Capture',
    body: 'Click Start Capture to record system audio in 15-second chunks - it\u2019s transcribed live. Click Stop Capture when the meeting ends.'
  }
];

const stats = [
  { label: 'Meetings automated / mo', value: '40k+' },
  { label: 'Avg. minutes saved per meeting', value: '18' },
  { label: 'Task extraction accuracy', value: '91%' },
  { label: 'Isolated company workspaces', value: '100%' }
];

export function Welcome({ onLogin, onSignup }: { onLogin: () => void; onSignup: () => void }) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#f7f8f5] text-ink">
      <header
        className={`sticky top-0 z-20 transition-all ${
          scrolled ? 'border-b border-stone-200 bg-white/80 backdrop-blur-md' : 'border-b border-transparent bg-transparent'
        }`}
      >
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded bg-ocean text-white shadow-sm">
              <Bot size={22} />
            </div>
            <span className="text-lg font-semibold">MeetFlow AI</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              className="inline-flex h-10 items-center rounded px-4 text-sm font-medium text-stone-600 transition hover:bg-stone-100"
              onClick={onLogin}
            >
              Log in
            </button>
            <button
              className="group inline-flex h-10 items-center gap-2 rounded bg-ocean px-4 text-sm font-medium text-white shadow-sm transition hover:bg-[#0b5d56] hover:shadow"
              onClick={onSignup}
            >
              Sign up
              <ArrowRight size={16} className="transition group-hover:translate-x-0.5" />
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6">
        <section className="relative grid gap-10 py-16 lg:grid-cols-[1.1fr_0.9fr] lg:items-center lg:py-24">
          {/* Decorative gradient accents - purely visual, sit behind content */}
          <div className="pointer-events-none absolute -top-20 left-1/3 -z-10 h-72 w-72 rounded-full bg-ocean/10 blur-3xl" />
          <div className="pointer-events-none absolute -right-10 top-40 -z-10 h-72 w-72 rounded-full bg-coral/10 blur-3xl" />

          <div>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-ocean/10 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-ocean">
              <Sparkles size={12} />
              Meeting automation
            </span>
            <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-tight sm:text-5xl lg:text-6xl">
              Every meeting turns into{' '}
              <span className="bg-gradient-to-r from-ocean to-emerald-500 bg-clip-text text-transparent">
                finished work
              </span>{' '}
              automatically.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-stone-600">
              MeetFlow AI joins your calls, transcribes what was said, and turns the discussion into
              assigned, approved tasks - so nothing said in a meeting gets lost the moment it ends.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <button
                className="group inline-flex h-12 items-center gap-2 rounded bg-coral px-6 text-sm font-medium text-white shadow-sm transition hover:bg-[#c94e34] hover:shadow-md"
                onClick={onSignup}
              >
                Get started free
                <ArrowRight size={18} className="transition group-hover:translate-x-0.5" />
              </button>
              <button
                className="inline-flex h-12 items-center rounded border border-stone-300 bg-white px-6 text-sm font-medium transition hover:border-stone-400 hover:bg-stone-50"
                onClick={onLogin}
              >
                Sign in
              </button>
            </div>
            <p className="mt-4 flex items-center gap-2 text-xs text-stone-500">
              <Lock size={14} />
              Every company gets its own isolated, private workspace.
            </p>

            <div className="mt-10 grid grid-cols-2 gap-6 border-t border-stone-200 pt-8 sm:grid-cols-4">
              {stats.map((stat) => (
                <div key={stat.label}>
                  <div className="text-2xl font-semibold text-ink">{stat.value}</div>
                  <div className="mt-1 text-xs text-stone-500">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Signature element: the product's actual 5-stage pipeline, not a
              decorative graphic - this is literally what happens to every
              meeting, in order. */}
          <div className="rounded border border-stone-200 bg-white p-6 shadow-lg shadow-stone-200/50 transition hover:shadow-xl hover:shadow-stone-200/60">
            <div className="text-xs font-semibold uppercase tracking-widest text-stone-400">
              What happens to every meeting
            </div>
            <div className="mt-6 flex flex-col">
              {pipeline.map((stage, i) => {
                const Icon = stage.icon;
                const isLast = i === pipeline.length - 1;
                return (
                  <div key={stage.label} className="flex gap-4">
                    <div className="flex flex-col items-center">
                      <div
                        className={`grid h-10 w-10 shrink-0 place-items-center rounded-full ${
                          isLast ? 'bg-coral text-white' : 'border-2 border-ocean text-ocean'
                        }`}
                      >
                        <Icon size={18} />
                      </div>
                      {!isLast && <div className="w-px flex-1 bg-stone-200" style={{ minHeight: 28 }} />}
                    </div>
                    <div className={`pb-7 pt-2 text-sm font-medium ${isLast ? 'text-ink' : 'text-stone-700'}`}>
                      {stage.label}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        <section className="border-t border-stone-200 py-16">
          <h2 className="text-2xl font-semibold">Everything that used to be a follow-up email</h2>
          <p className="mt-2 max-w-2xl text-stone-600">
            Four things happen behind the scenes so your team doesn&apos;t have to do them by hand.
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <div
                  key={feature.title}
                  className="group rounded border border-stone-200 bg-white p-5 transition hover:-translate-y-0.5 hover:border-ocean/30 hover:shadow-md"
                >
                  <div className="grid h-10 w-10 place-items-center rounded bg-ocean/10 text-ocean transition group-hover:bg-ocean group-hover:text-white">
                    <Icon size={20} />
                  </div>
                  <h3 className="mt-4 font-semibold">{feature.title}</h3>
                  <p className="mt-2 text-sm text-stone-600">{feature.body}</p>
                </div>
              );
            })}
          </div>
        </section>

        <section className="border-t border-stone-200 py-16">
          <h2 className="text-2xl font-semibold">Live in four steps</h2>
          <p className="mt-2 max-w-2xl text-stone-600">
            No plugin to install and no addresses to type - connect your calendar once and the rest runs itself.
          </p>
          <div className="relative mt-10 grid gap-8 lg:grid-cols-4 lg:gap-6">
            {/* connecting line - desktop only, sits behind the number badges */}
            <div className="absolute left-0 right-0 top-6 hidden h-px bg-stone-200 lg:block" />
            {steps.map((step, i) => {
              const Icon = step.icon;
              return (
                <div key={step.title} className="relative">
                  <div className="flex items-center gap-3 lg:block">
                    <div className="relative z-10 grid h-12 w-12 shrink-0 place-items-center rounded-full border-2 border-ocean bg-[#f7f8f5] text-ocean">
                      <Icon size={20} />
                    </div>
                    <span className="text-xs font-semibold uppercase tracking-widest text-stone-400 lg:hidden">
                      Step {i + 1}
                    </span>
                  </div>
                  <span className="hidden text-xs font-semibold uppercase tracking-widest text-stone-400 lg:mt-4 lg:block">
                    Step {i + 1}
                  </span>
                  <h3 className="mt-1 font-semibold">{step.title}</h3>
                  <p className="mt-2 text-sm text-stone-600">{step.body}</p>
                </div>
              );
            })}
          </div>
          <p className="mt-8 flex items-start gap-2 text-xs text-stone-500">
            <Lock size={14} className="mt-0.5 shrink-0" />
            Sending mail itself (SMTP) is configured once for your organization by whoever set up your
            workspace - after that, every notification above goes out on its own.
          </p>
        </section>

        <section className="border-t border-stone-200 py-16">
          <div className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
            <div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-ocean/10 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-ocean">
                <Download size={12} />
                Desktop app
              </span>
              <h2 className="mt-4 text-2xl font-semibold">Capture audio straight from your PC</h2>
              <p className="mt-2 max-w-md text-stone-600">
                The MeetFlow Desktop app records your meeting&apos;s system audio and streams it to your
                workspace automatically - no browser extension, no manual uploads.
              </p>
              <a
                href={DESKTOP_APP_RELEASES_URL}
                target="_blank"
                rel="noreferrer"
                className="group mt-6 inline-flex h-12 items-center gap-2 rounded bg-ocean px-6 text-sm font-medium text-white shadow-sm transition hover:bg-[#0b5d56] hover:shadow-md"
              >
                <Download size={18} />
                Download for Windows
              </a>
              <p className="mt-3 text-xs text-stone-500">Free installer - takes under a minute to set up.</p>
            </div>

            <div className="rounded border border-stone-200 bg-white p-6 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-widest text-stone-400">How it works</div>
              <div className="mt-5 space-y-5">
                {desktopSteps.map((step, i) => {
                  const Icon = step.icon;
                  return (
                    <div key={step.title} className="flex gap-4">
                      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full border-2 border-ocean text-ocean">
                        <Icon size={16} />
                      </div>
                      <div>
                        <div className="text-xs font-semibold uppercase tracking-widest text-stone-400">
                          Step {i + 1}
                        </div>
                        <h3 className="font-semibold">{step.title}</h3>
                        <p className="mt-1 text-sm text-stone-600">{step.body}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </section>

        <section className="border-t border-stone-200 py-14">
          <div className="rounded border border-stone-200 bg-white p-6 sm:p-8">
            <div className="flex gap-0.5 text-gold">
              {[...Array(5)].map((_, i) => (
                <Star key={i} size={16} fill="currentColor" />
              ))}
            </div>
            <p className="mt-4 max-w-2xl text-lg font-medium text-stone-700">
              &ldquo;We stopped writing follow-up emails altogether. MeetFlow already has the tasks
              assigned before we&apos;re back at our desks.&rdquo;
            </p>
            <p className="mt-3 text-sm text-stone-500">Operations lead, mid-size services company</p>
          </div>
        </section>

        <section className="border-t border-stone-200 py-14">
          <div className="relative overflow-hidden rounded border border-stone-200 bg-ocean px-8 py-10 text-white sm:px-12">
            <div className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-white/10 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-20 left-10 h-64 w-64 rounded-full bg-coral/20 blur-3xl" />
            <div className="flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
              <div>
                <h2 className="text-2xl font-semibold">Set up your company workspace</h2>
                <p className="mt-2 max-w-md text-white/75">
                  Takes a couple of minutes. You&apos;ll be routing approvals from your first meeting today.
                </p>
              </div>
              <button
                className="inline-flex h-12 shrink-0 items-center gap-2 rounded bg-white px-6 text-sm font-medium text-ocean hover:bg-white/90"
                onClick={onSignup}
              >
                Create workspace
                <ArrowRight size={18} />
              </button>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-stone-200">
        <div className="mx-auto max-w-6xl px-6 py-10">
          <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-center">
            <div className="flex items-center gap-3">
              <div className="grid h-9 w-9 place-items-center rounded bg-ocean text-white">
                <Bot size={18} />
              </div>
              <div>
                <div className="text-sm font-semibold">MeetFlow AI</div>
                <div className="text-xs text-stone-500">Meetings in, workflows out.</div>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-stone-500">
              <button className="hover:text-ocean" onClick={onSignup}>
                Get started
              </button>
              <button className="hover:text-ocean" onClick={onLogin}>
                Sign in
              </button>
              <span className="flex items-center gap-1.5">
                <Lock size={13} />
                Isolated per-company data
              </span>
            </div>
          </div>
          <div className="mt-8 border-t border-stone-200 pt-6 text-xs text-stone-400">
            © {new Date().getFullYear()} MeetFlow AI. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
