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
