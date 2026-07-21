import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { useState } from 'react';
import { api, TranscriptResponse, UpcomingMeeting } from '../api';

const statusLabels: Record<string, string> = {
  scheduled: 'Scheduled',
  bot_joining: 'Bot is joining the meeting...',
  in_progress: 'Live - bot is in the meeting',
  completed: 'Meeting ended',
  failed: 'Bot failed to join'
};

export function LiveTranscript({
  meetingId,
  meetingTitle,
  meetings
}: {
  meetingId: number | null;
  meetingTitle: string | null;
  meetings: UpcomingMeeting[];
}) {
  const [search, setSearch] = useState('');

  const transcript = useQuery({
    queryKey: ['meeting-transcript', meetingId, search],
    queryFn: async () =>
      (
        await api.get<TranscriptResponse>(`/api/meetings/${meetingId}/transcript`, {
          params: search ? { q: search } : undefined
        })
      ).data,
    enabled: meetingId !== null,
    refetchInterval: meetingId !== null ? 5000 : false
  });

  if (meetingId === null) {
    return (
      <div className="rounded border border-stone-200 bg-white p-6 text-sm text-stone-500">
        Select a meeting from the Meetings dashboard to view its live transcript.
      </div>
    );
  }

  const status = transcript.data?.status;

  return (
    <div className="rounded border border-stone-200 bg-white">
      <div className="border-b border-stone-200 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">{meetingTitle ?? 'Live Transcript'}</h3>
            {status && <p className="text-sm text-stone-500">{statusLabels[status] ?? status}</p>}
          </div>
          <div className="relative">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400" />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search transcript..."
              className="h-9 w-56 rounded border border-stone-300 pl-9 pr-3 text-sm focus:border-ocean focus:outline-none"
            />
          </div>
        </div>
      </div>

      <div className="max-h-[28rem] overflow-y-auto p-4">
        {transcript.isLoading && <p className="text-sm text-stone-500">Loading transcript...</p>}
        {!transcript.isLoading && (transcript.data?.entries.length ?? 0) === 0 && (
          <p className="text-sm text-stone-500">
            {search ? 'No transcript entries match your search.' : 'No transcript yet. It will appear here once the bot joins and audio is captured.'}
          </p>
        )}
        {transcript.data?.entries.map((entry) => (
          <div key={entry.id} className="mb-3 rounded bg-stone-50 p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-ocean">
              <span>{entry.speaker}</span>
              {entry.timestamp && <span className="text-xs font-normal text-stone-400">[{entry.timestamp}]</span>}
            </div>
            <div className="text-sm">{entry.text}</div>
          </div>
        ))}
      </div>

      {meetings.length > 0 && (
        <div className="border-t border-stone-200 p-3 text-xs text-stone-400">Auto-refreshing every 5 seconds while a meeting is live.</div>
      )}
    </div>
  );
}
