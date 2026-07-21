import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  Bot,
  CalendarDays,
  CheckCircle2,
  ClipboardList,
  Gauge,
  LayoutDashboard,
  MailCheck,
  Settings,
  ShieldCheck,
  Users
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { LucideIcon } from 'lucide-react';
import { api, AnalyticsSummary, Task, UpcomingMeeting } from './api';
import { useAppStore } from './store';
import { LiveTranscript } from './components/LiveTranscript';
import { MeetingsDashboard } from './components/MeetingsDashboard';

const pages = [
  { name: 'Dashboard', icon: LayoutDashboard },
  { name: 'Meetings', icon: CalendarDays },
  { name: 'Live Meeting', icon: Bot },
  { name: 'Tasks', icon: ClipboardList },
  { name: 'Approval Queue', icon: MailCheck },
  { name: 'Team Analytics', icon: Activity },
  { name: 'Settings', icon: Settings }
];

const sampleTranscript = {
  meeting_title: 'Client demo sync',
  transcript: [
    { speaker: 'Ajay', text: "I'll update the login page by Friday." },
    { speaker: 'Rahul', text: 'Priya should fix the API timeout issue.' },
    { speaker: 'Client', text: "We need dashboard filters fixed before next week's demo." }
  ]
};

export function App() {
  const { activePage, setActivePage } = useAppStore();
  const queryClient = useQueryClient();
  const [selectedMeeting, setSelectedMeeting] = useState<{ id: number; title: string } | null>(null);
  const [calendarBanner, setCalendarBanner] = useState<'connected' | 'error' | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const calendarStatus = params.get('calendar');
    if (calendarStatus === 'connected' || calendarStatus === 'error') {
      setCalendarBanner(calendarStatus);
      queryClient.invalidateQueries({ queryKey: ['calendar-status'] });
      queryClient.invalidateQueries({ queryKey: ['meetings-upcoming'] });
      params.delete('calendar');
      const newSearch = params.toString();
      window.history.replaceState({}, '', window.location.pathname + (newSearch ? `?${newSearch}` : ''));
    }
  }, [queryClient]);

  const analytics = useQuery({
    queryKey: ['analytics'],
    queryFn: async () => (await api.get<AnalyticsSummary>('/api/analytics/summary')).data,
    initialData: {
      meetings_processed: 12,
      tasks_generated: 38,
      tasks_approved: 24,
      pending_reviews: 7,
      average_confidence: 0.84,
      ai_accuracy: 0.91,
      tasks_by_domain: [
        { domain: 'Frontend', count: 12 },
        { domain: 'Backend', count: 9 },
        { domain: 'Product', count: 7 },
        { domain: 'DevOps', count: 4 }
      ]
    }
  });
  const tasks = useQuery({
    queryKey: ['tasks'],
    queryFn: async () => (await api.get<Task[]>('/api/tasks')).data,
    initialData: []
  });
  const upcomingMeetings = useQuery({
    queryKey: ['meetings-upcoming'],
    queryFn: async () => (await api.get<UpcomingMeeting[]>('/api/meetings/upcoming')).data,
    initialData: [],
    refetchInterval: 30000
  });
  const processTranscript = useMutation({
    mutationFn: async () => (await api.post<Task[]>('/api/meetings/process-transcript', sampleTranscript)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['analytics'] });
    }
  });

  const openTranscript = (meetingId: number, title: string) => {
    setSelectedMeeting({ id: meetingId, title });
    setActivePage('Live Meeting');
  };

  return (
    <div className="min-h-screen bg-[#f7f8f5] text-ink">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-stone-200 bg-white md:block">
        <div className="px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded bg-ocean text-white">
              <Bot size={22} />
            </div>
            <div>
              <h1 className="text-lg font-semibold leading-tight">MeetFlow AI</h1>
              <p className="text-xs text-stone-500">Meetings -&gt; Workflows</p>
            </div>
          </div>
        </div>
        <nav className="px-3">
          {pages.map((page) => {
            const Icon = page.icon;
            const active = activePage === page.name;
            return (
              <button
                key={page.name}
                className={`mb-1 flex h-10 w-full items-center gap-3 rounded px-3 text-left text-sm ${
                  active ? 'bg-ocean text-white' : 'text-stone-600 hover:bg-stone-100'
                }`}
                onClick={() => setActivePage(page.name)}
              >
                <Icon size={18} />
                <span>{page.name}</span>
              </button>
            );
          })}
        </nav>
      </aside>

      <main className="md:pl-64">
        <header className="sticky top-0 z-10 border-b border-stone-200 bg-white/95 px-5 py-4 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-xl font-semibold">{activePage}</h2>
              <p className="text-sm text-stone-500">Autonomous meeting intelligence and approval routing</p>
            </div>
            <button
              className="inline-flex h-10 items-center gap-2 rounded bg-coral px-4 text-sm font-medium text-white hover:bg-[#c94e34]"
              onClick={() => processTranscript.mutate()}
            >
              <Bot size={18} />
              Process demo transcript
            </button>
          </div>
        </header>

        <section className="p-5">
          {calendarBanner && (
            <div
              className={`mb-4 rounded border p-3 text-sm ${
                calendarBanner === 'connected'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-red-200 bg-red-50 text-red-700'
              }`}
            >
              {calendarBanner === 'connected'
                ? 'Google Calendar connected. Syncing upcoming meetings...'
                : 'Could not connect Google Calendar. Please try again.'}
            </div>
          )}
          {activePage === 'Dashboard' && <Dashboard summary={analytics.data} />}
          {activePage === 'Meetings' && <MeetingsDashboard onOpenTranscript={openTranscript} />}
          {activePage === 'Live Meeting' && (
            <LiveMeeting tasks={tasks.data} meetings={upcomingMeetings.data} selectedMeeting={selectedMeeting} onSelectMeeting={setSelectedMeeting} />
          )}
          {activePage === 'Tasks' && <Tasks tasks={tasks.data} />}
          {activePage === 'Approval Queue' && <ApprovalQueue />}
          {activePage === 'Team Analytics' && <TeamAnalytics summary={analytics.data} />}
          {activePage === 'Settings' && <SettingsView />}
        </section>
      </main>
    </div>
  );
}

function Dashboard({ summary }: { summary: AnalyticsSummary }) {
  const widgets: Array<[string, string | number, LucideIcon]> = [
    ['Meetings Processed', summary.meetings_processed, CalendarDays],
    ['Tasks Generated', summary.tasks_generated, ClipboardList],
    ['Tasks Approved', summary.tasks_approved, CheckCircle2],
    ['Pending Reviews', summary.pending_reviews, MailCheck],
    ['Average Confidence', `${Math.round(summary.average_confidence * 100)}%`, Gauge],
    ['AI Accuracy', `${Math.round(summary.ai_accuracy * 100)}%`, ShieldCheck]
  ];
  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {widgets.map(([label, value, Icon]) => (
          <div key={String(label)} className="rounded border border-stone-200 bg-white p-4">
            <div className="mb-3 flex items-center justify-between text-stone-500">
              <span className="text-sm">{String(label)}</span>
              <Icon size={18} />
            </div>
            <div className="text-3xl font-semibold">{String(value)}</div>
          </div>
        ))}
      </div>
      <Chart title="Tasks by Domain" data={summary.tasks_by_domain} />
    </div>
  );
}

function LiveMeeting({
  tasks,
  meetings,
  selectedMeeting,
  onSelectMeeting
}: {
  tasks: Task[];
  meetings: UpcomingMeeting[];
  selectedMeeting: { id: number; title: string } | null;
  onSelectMeeting: (meeting: { id: number; title: string } | null) => void;
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
      <div className="space-y-3">
        {meetings.length > 0 && (
          <div className="flex items-center gap-2 rounded border border-stone-200 bg-white p-3">
            <span className="text-sm text-stone-500">Meeting:</span>
            <select
              className="h-9 flex-1 rounded border border-stone-300 px-2 text-sm"
              value={selectedMeeting?.id ?? ''}
              onChange={(event) => {
                const id = Number(event.target.value);
                const meeting = meetings.find((m) => m.id === id);
                onSelectMeeting(meeting ? { id: meeting.id, title: meeting.title } : null);
              }}
            >
              <option value="">Select a meeting...</option>
              {meetings.map((meeting) => (
                <option key={meeting.id} value={meeting.id}>
                  {meeting.title}
                </option>
              ))}
            </select>
          </div>
        )}
        <LiveTranscript meetingId={selectedMeeting?.id ?? null} meetingTitle={selectedMeeting?.title ?? null} meetings={meetings} />
      </div>
      <Tasks tasks={tasks} compact />
    </div>
  );
}

function Tasks({ tasks, compact = false }: { tasks: Task[]; compact?: boolean }) {
  const fallback = tasks.length
    ? tasks
    : [
        { id: 1, title: 'Update login page', owner: 'Ajay', domain: 'Frontend', priority: 'medium', confidence: 0.91, status: 'auto_approve_candidate' },
        { id: 2, title: 'Fix API timeout issue', owner: 'Priya', domain: 'Backend', priority: 'medium', confidence: 0.83, status: 'review_required' }
      ] as Task[];
  return (
    <div className="rounded border border-stone-200 bg-white">
      <div className="border-b border-stone-200 p-4">
        <h3 className="font-semibold">{compact ? 'Extracted Tasks' : 'Tasks'}</h3>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead className="bg-stone-50 text-left text-stone-500">
            <tr>
              <th className="p-3">Task</th>
              <th className="p-3">Owner</th>
              <th className="p-3">Domain</th>
              <th className="p-3">Priority</th>
              <th className="p-3">Confidence</th>
              <th className="p-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {fallback.map((task) => (
              <tr key={task.id} className="border-t border-stone-100">
                <td className="p-3 font-medium">{task.title}</td>
                <td className="p-3">{task.owner ?? 'Unassigned'}</td>
                <td className="p-3">{task.domain ?? 'Unknown'}</td>
                <td className="p-3 capitalize">{task.priority}</td>
                <td className="p-3">{Math.round(task.confidence * 100)}%</td>
                <td className="p-3">{task.status.replace(/_/g, ' ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ApprovalQueue() {
  return (
    <div className="rounded border border-stone-200 bg-white p-4">
      <div className="mb-4 flex items-center gap-2 font-semibold">
        <MailCheck size={18} />
        Manager Review Required
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {['Approve', 'Edit', 'Reject'].map((action) => (
          <button key={action} className="h-10 rounded border border-stone-300 bg-white text-sm font-medium hover:bg-stone-50">
            {action}
          </button>
        ))}
      </div>
    </div>
  );
}

function TeamAnalytics({ summary }: { summary: AnalyticsSummary }) {
  return <Chart title="Team Workload and Domain Routing" data={summary.tasks_by_domain} />;
}

function Chart({ title, data }: { title: string; data: Array<{ domain: string; count: number }> }) {
  return (
    <div className="rounded border border-stone-200 bg-white p-4">
      <h3 className="mb-4 font-semibold">{title}</h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="domain" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" fill="#0f766e" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function SettingsView() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {['Mistral API', 'SMTP Email', 'Slack Webhook', 'Calendar OAuth'].map((item) => (
        <div key={item} className="rounded border border-stone-200 bg-white p-4">
          <div className="mb-2 flex items-center gap-2 font-semibold">
            <Users size={18} />
            {item}
          </div>
          <p className="text-sm text-stone-600">Configure through environment variables and organization secrets.</p>
        </div>
      ))}
    </div>
  );
}
