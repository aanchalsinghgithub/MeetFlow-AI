import { useEffect, useRef, useState } from 'react';
import { api } from '../services/api';

const SPEAKER_COLORS = [
  '#818cf8', '#34d399', '#f472b6',
  '#fbbf24', '#60a5fa', '#a78bfa',
];

const colorFor = (() => {
  const map = {};
  let   idx = 0;
  return (speaker) => {
    if (!map[speaker]) map[speaker] = SPEAKER_COLORS[idx++ % SPEAKER_COLORS.length];
    return map[speaker];
  };
})();

export default function TranscriptView({ meeting, liveEntries }) {
  const [entries,  setEntries]  = useState([]);
  const [search,   setSearch]   = useState('');
  const [polling,  setPolling]  = useState(false);
  const bottomRef = useRef(null);

  // Poll transcript from backend every 5 s when meeting is in_progress
  useEffect(() => {
    if (!meeting) return;
    setEntries([]);

    async function poll() {
      try {
        const data = await api.getTranscript(meeting.id, search);
        setEntries(data.entries || []);
      } catch (_) {}
    }

    poll();
    const isActive = meeting.status === 'in_progress';
    setPolling(isActive);

    if (!isActive) return;
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, [meeting?.id, meeting?.status, search]);

  // Merge live entries pushed via IPC
  useEffect(() => {
    if (!liveEntries?.length) return;
    setEntries((prev) => {
      const ids = new Set(prev.map((e) => `${e.timestamp}-${e.text}`));
      const news = liveEntries.filter(
        (e) => !ids.has(`${e.timestamp}-${e.text}`),
      );
      return news.length ? [...prev, ...news] : prev;
    });
  }, [liveEntries]);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [entries.length]);

  if (!meeting) {
    return (
      <div style={styles.empty}>
        Select a meeting to view its transcript.
      </div>
    );
  }

  const filtered = search
    ? entries.filter(
        (e) =>
          e.text.toLowerCase().includes(search.toLowerCase()) ||
          e.speaker.toLowerCase().includes(search.toLowerCase()),
      )
    : entries;

  return (
    <div style={styles.container}>
      {/* Search bar */}
      <div style={styles.toolbar}>
        <input
          placeholder="Search transcript…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={styles.search}
        />
        {polling && <span style={styles.pill}>● Live</span>}
      </div>

      {/* Transcript entries */}
      <div style={styles.scroll}>
        {filtered.length === 0 && (
          <div style={styles.empty}>
            {entries.length === 0
              ? 'No transcript yet. Start capture to begin.'
              : 'No matches.'}
          </div>
        )}
        {filtered.map((e, i) => (
          <div key={i} style={styles.entry}>
            <div style={styles.entryMeta}>
              <span style={{ ...styles.speaker, color: colorFor(e.speaker) }}>
                {e.speaker}
              </span>
              <span style={styles.ts}>{e.timestamp}</span>
            </div>
            <div style={styles.text}>{e.text}</div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

const styles = {
  container: {
    display:       'flex',
    flexDirection: 'column',
    height:        '100%',
  },
  toolbar: {
    display:      'flex',
    alignItems:   'center',
    gap:          10,
    padding:      '10px 16px',
    borderBottom: '1px solid var(--border)',
  },
  search: { flex: 1 },
  pill: {
    fontSize:  11,
    color:     'var(--success)',
    whiteSpace:'nowrap',
    fontWeight: 600,
  },
  scroll: {
    flex:      1,
    overflowY: 'auto',
    padding:   '12px 16px',
  },
  entry: {
    marginBottom:  12,
    borderLeft:    '3px solid var(--border)',
    paddingLeft:   12,
  },
  entryMeta: {
    display:     'flex',
    gap:         10,
    marginBottom: 2,
    alignItems:  'baseline',
  },
  speaker: { fontWeight: 700, fontSize: 12 },
  ts:      { color: 'var(--muted)', fontSize: 11 },
  text:    { color: 'var(--text)', lineHeight: 1.6 },
  empty: {
    color:     'var(--muted)',
    textAlign: 'center',
    marginTop: 60,
    fontSize:  13,
  },
};
