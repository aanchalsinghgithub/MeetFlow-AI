import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { CalendarDays, Link2, RefreshCw } from 'lucide-react';
import { api, CalendarAuthURL, CalendarConnection, UpcomingMeeting } from '../api';

function formatStartTime(starts_at: string | null): string {
  if (!starts_at) return 'No start time';
  const date = new Date(starts_at);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  const time = date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  if (isToday) return `Today ${time}`;
  return `${date.toLocaleDateString([], { month: 'short', day: 'numeric' })} ${time}`;
}

function formatDuration(starts_at: string | null, ends_at: string | null): string {
  if (!starts_at || !ends_at) return '-';
  const minutes = Math.round((new Date(ends_at).getTime() - new Date(starts_at).getTime()) / 60000);
  if (minutes <= 0) return '-';
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours}h ${rest}m` : `${hours}h`;
}

const statusLabels: Record<string, string> = {
  scheduled: 'Scheduled',
  in_progress: 'In progress',
  completed: 'Completed',
  failed: 'Failed'
};

const statusStyles: Record<string, string> = {
  scheduled: 'bg-stone-100 text-stone-600',
  in_progress: 'bg-emerald-100 text-emerald-700',
  completed: 'bg-stone-100 text-stone-500',
  failed: 'bg-red-100 text-red-700'
};

export function MeetingsDashboard({ onOpenTranscript }: { onOpenTranscript: (meetingId: number, title: string) => void }) {
  const queryClient = useQueryClient();

  const connections = useQuery({
    queryKey: ['calendar-status'],
    queryFn: async () => (await api.get<CalendarConnection[]>('/api/calendar/status')).data,
    initialData: []
  });

  const meetings = useQuery({
    queryKey: ['meetings-upcoming'],
    queryFn: async () => (await api.get<UpcomingMeeting[]>('/api/meetings/upcoming')).data,
    initialData: [],
    refetchInterval: 30000
  });

  const connectCalendar = useMutation({
    mutationFn: async () => (await api.get<CalendarAuthURL>('/api/calendar/connect')).data,
    onSuccess: (data) => {
      window.location.href = data.authorization_url;
    }
  });

  const isConnected = connections.data.length > 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-stone-200 bg-white p-4">
        <div className="flex items-center gap-2">
          <CalendarDays size={18} className="text-ocean" />
          <div>
            <div className="font-semibold">Google Calendar</div>
            <p className="text-sm text-stone-500">
              {isConnected
                ? `Connected as ${connections.data.map((c) => c.user_email).join(', ')}`
                : 'Connect your Google account to pull upcoming Google Meet meetings.'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            className="inline-flex h-10 items-center gap-2 rounded border border-stone-300 px-3 text-sm font-medium hover:bg-stone-50"
            onClick={() => queryClient.invalidateQueries({ queryKey: ['meetings-upcoming'] })}
          >
            <RefreshCw size={16} className={meetings.isFetching ? 'animate-spin' : ''} />
            Refresh
          </button>
          <button
            className="inline-flex h-10 items-center gap-2 rounded bg-ocean px-4 text-sm font-medium text-white hover:bg-[#0b5d56]"
            onClick={() => connectCalendar.mutate()}
          >
            <Link2 size={16} />
            {isConnected ? 'Reconnect Google Calendar' : 'Connect Google Calendar'}
          </button>
        </div>
      </div>

      <div className="rounded border border-stone-200 bg-white">
        <div className="border-b border-stone-200 p-4">
          <h3 className="font-semibold">Upcoming Meetings</h3>
          <p className="text-sm text-stone-500">Google Meet meetings from your connected calendar.</p>
        </div>
        {meetings.data.length === 0 ? (
          <div className="p-6 text-sm text-stone-500">
            No upcoming Google Meet meetings found yet. Connect Google Calendar above, or check back closer to your next meeting.
          </div>
        ) : (
          <div className="divide-y divide-stone-100">
            {meetings.data.map((meeting) => (
              <div key={meeting.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <button className="text-left font-medium hover:text-ocean" onClick={() => onOpenTranscript(meeting.id, meeting.title)}>
                    {meeting.title}
                  </button>
                  <div className="text-sm text-stone-500">
                    {formatStartTime(meeting.starts_at)} &middot; {formatDuration(meeting.starts_at, meeting.ends_at)}
                    {meeting.participants.length > 0 && <> &middot; {meeting.participants.length} participants</>}
                  </div>
                  {meeting.join_url && (
                    <a href={meeting.join_url} target="_blank" rel="noreferrer" className="text-sm text-ocean hover:underline">
                      {meeting.join_url}
                    </a>
                  )}
                </div>
                <div className="flex items-center gap-4">
                  <span className={`rounded px-2 py-1 text-xs font-medium ${statusStyles[meeting.status] ?? 'bg-stone-100 text-stone-600'}`}>
                    {statusLabels[meeting.status] ?? meeting.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
