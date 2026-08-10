import axios from 'axios';
import { getAuthToken } from './auth';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
});

api.interceptors.request.use((config) => {
  const token = getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export type Task = {
  id: number;
  title: string;
  owner?: string | null;
  mentioned_by?: string | null;
  requested_by?: string | null;
  priority: string;
  deadline?: string | null;
  domain?: string | null;
  confidence: number;
  status: string;
};

export type AnalyticsSummary = {
  meetings_processed: number;
  tasks_generated: number;
  tasks_approved: number;
  pending_reviews: number;
  average_confidence: number;
  tasks_by_domain: Array<{ domain: string; count: number }>;
  ai_accuracy: number;
};

export type UpcomingMeeting = {
  id: number;
  title: string;
  provider: string;
  join_url: string | null;
  starts_at: string | null;
  ends_at: string | null;
  status: string;
  auto_join: boolean;
  participants: string[];
};

export type MeetingStatus = {
  id: number;
  status: string;
  auto_join: boolean;
  title: string;
};

export type TranscriptEntry = {
  id: number;
  speaker: string;
  text: string;
  timestamp: string | null;
};

export type TranscriptResponse = {
  meeting_id: number;
  status: string;
  entries: TranscriptEntry[];
};

export type CalendarAuthURL = {
  authorization_url: string;
};

export type CalendarConnection = {
  id: number;
  user_email: string;
  connected: boolean;
};

export type BotSessionStatus = {
  configured: boolean;
  email: string | null;
};

// The bot needs to join Meet as a real logged-in Google account instead of
// an anonymous guest (Google blocks anonymous/automated guest joins). This
// takes the cookies.txt a person exports from their own browser (via the
// "Get cookies.txt LOCALLY" extension, after signing in normally) and
// stores it against their organization — see BotAccountSettings.tsx.
export async function uploadBotSessionCookiesFile(email: string, file: File): Promise<BotSessionStatus> {
  const form = new FormData();
  form.append('email', email);
  form.append('file', file);
  return (await api.post<BotSessionStatus>('/api/organizations/google-bot-session/upload-cookies-file', form)).data;
}

export async function clearBotSession(): Promise<BotSessionStatus> {
  return (await api.delete<BotSessionStatus>('/api/organizations/google-bot-session')).data;
}
