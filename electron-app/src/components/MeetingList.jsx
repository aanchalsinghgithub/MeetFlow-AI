import { useEffect, useState } from 'react';
import { api } from '../services/api';

const STATUS_BADGE = {
  scheduled:   'gray',
  bot_joining: 'yellow',
  in_progress: 'green',
  completed:   'blue',
  failed:      'red',
};

function statusLabel(s) {
  return (s || 'scheduled').replace(/_/g, ' ');
}

export default function MeetingList({ onSelect, selectedId, capturing }) {
  const [tab,      setTab]      = useState('upcoming'); // 'upcoming' | 'recent'
  const [meetings, setMeetings] = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = tab === 'upcoming' ? await api.upcomingMeetings() : await api.recentMeetings();
      setMeetings(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [tab]);

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <div style={styles.tabs}>
          <button
            className={tab === 'upcoming' ? 'primary' : 'ghost'}
            onClick={() => setTab('upcoming')}
            style={styles.tabBtn}
          >
            Upcoming
          </button>
          <button
            className={tab === 'recent' ? 'primary' : 'ghost'}
            onClick={() => setTab('recent')}
            style={styles.tabBtn}
          >
            Recent
          </button>
        </div>
        <button className="ghost" onClick={load} disabled={loading} style={{ padding: '4px 10px' }}>
          {loading ? '⟳' : 'Refresh'}
        </button>
      </div>

      {error && <div style={styles.error}>⚠ {error}</div>}

      <div style={styles.list}>
        {meetings.length === 0 && !loading && (
          <div style={styles.empty}>
            {tab === 'upcoming' ? 'No upcoming meetings' : 'No recent meetings'}
          </div>
        )}
        {meetings.map((m) => {
          const isSelected = m.id === selectedId;
          const canSelect  = !capturing || isSelected;
          return (
            <div
              key={m.id}
              style={{
                ...styles.item,
                ...(isSelected ? styles.itemSelected : {}),
                opacity: canSelect ? 1 : 0.5,
                cursor: canSelect ? 'pointer' : 'not-allowed',
              }}
              onClick={() => canSelect && onSelect(m)}
            >
              <div style={styles.itemTitle}>{m.title}</div>
              <div style={styles.itemMeta}>
                {m.starts_at
                  ? new Date(m.starts_at).toLocaleString()
                  : 'Time not set'}
              </div>
              <span className={`badge ${STATUS_BADGE[m.status] || 'gray'}`}>
                {statusLabel(m.status)}
              </span>
              {m.status === 'failed' && m.error_message && (
                <div style={styles.itemError} title={m.error_message}>
                  {m.error_message}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const styles = {
  panel: {
    display:       'flex',
    flexDirection: 'column',
    height:        '100%',
    borderRight:   '1px solid var(--border)',
  },
  header: {
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    padding:        '14px 16px',
    borderBottom:   '1px solid var(--border)',
  },
  title:  { fontWeight: 600, fontSize: 13, color: 'var(--text)' },
  tabs:   { display: 'flex', gap: 6 },
  tabBtn: { padding: '4px 10px', fontSize: 12 },
  list:   { flex: 1, overflowY: 'auto', padding: '8px' },
  item:   {
    padding:      '10px 12px',
    borderRadius: 'var(--radius)',
    marginBottom: '4px',
    border:       '1px solid transparent',
    transition:   'background .12s',
  },
  itemSelected: {
    background:  'rgba(99,102,241,.15)',
    border:      '1px solid var(--accent)',
  },
  itemTitle:    { fontWeight: 600, marginBottom: 3 },
  itemMeta:     { color: 'var(--muted)', fontSize: 12, marginBottom: 5 },
  itemError:    {
    color: 'var(--danger)', fontSize: 11, marginTop: 5,
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
  empty:        { color: 'var(--muted)', textAlign: 'center', marginTop: 40 },
  error:        { color: 'var(--danger)', padding: '8px 16px', fontSize: 12 },
};
