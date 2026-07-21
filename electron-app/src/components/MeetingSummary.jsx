import { useEffect, useState } from 'react';
import { api } from '../services/api';

export default function MeetingSummary({ meeting }) {
  const [detail,  setDetail]  = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    if (!meeting) return;
    setDetail(null);
    setError(null);
    setLoading(true);
    api
      .getMeeting(meeting.id)
      .then(setDetail)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [meeting?.id]);

  if (!meeting) {
    return <div style={styles.empty}>Select a meeting to view its summary.</div>;
  }

  if (loading) {
    return <div style={styles.empty}>Loading summary…</div>;
  }

  if (error) {
    return <div style={styles.error}>⚠ {error}</div>;
  }

  const stillRunning = ['scheduled', 'bot_joining', 'in_progress'].includes(meeting.status);

  if (!detail?.summary && stillRunning) {
    return (
      <div style={styles.empty}>
        Summary is generated when the meeting is finalized — click{' '}
        <b>Stop Capture</b> once it ends.
      </div>
    );
  }

  if (!detail?.summary) {
    return <div style={styles.empty}>No summary available for this meeting.</div>;
  }

  return (
    <div style={styles.scroll}>
      <div style={styles.block}>
        <div style={styles.blockLabel}>What happened</div>
        <div style={styles.text}>{detail.summary}</div>
      </div>

      {detail.key_discussion_points?.length > 0 && (
        <div style={styles.block}>
          <div style={styles.blockLabel}>Key discussion points</div>
          <ul style={styles.list}>
            {detail.key_discussion_points.map((d, i) => (
              <li key={i} style={styles.listItem}>{d}</li>
            ))}
          </ul>
        </div>
      )}

      {detail.decisions?.length > 0 && (
        <div style={styles.block}>
          <div style={styles.blockLabel}>Decisions</div>
          <ul style={styles.list}>
            {detail.decisions.map((d, i) => (
              <li key={i} style={styles.listItem}>{d}</li>
            ))}
          </ul>
        </div>
      )}

      {/*
        BUGFIX: the backend now returns risks/blockers as structured objects
        - { blocker, impact, owner, action } and { risk, impact, mitigation }
        - instead of plain strings (app/schemas/meeting.py::RiskItem /
        BlockerItem). Rendering `{d}` directly, like this used to, throws
        "Objects are not valid as a React child" as soon as a meeting has
        structured data. Render the known sub-fields explicitly instead;
        `blocker`/`risk` falls back to an empty string so old plain-string
        rows (which the backend normalizes into {"blocker": "<string>"} /
        {"risk": "<string>"}) still display exactly as before.
      */}
      {detail.blockers?.length > 0 && (
        <div style={styles.block}>
          <div style={styles.blockLabel}>Blockers</div>
          <ul style={styles.list}>
            {detail.blockers.map((b, i) => (
              <li key={i} style={{ ...styles.listItem, color: 'var(--danger)' }}>
                <div>{b.blocker}</div>
                {(b.impact || b.owner || b.action) && (
                  <div style={styles.subText}>
                    {b.impact && <span>Impact: {b.impact}</span>}
                    {b.owner && <span> · Owner: {b.owner}</span>}
                    {b.action && <span> · Next step: {b.action}</span>}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {detail.risks?.length > 0 && (
        <div style={styles.block}>
          <div style={styles.blockLabel}>Risks</div>
          <ul style={styles.list}>
            {detail.risks.map((r, i) => (
              <li key={i} style={{ ...styles.listItem, color: 'var(--warn)' }}>
                <div>{r.risk}</div>
                {(r.impact || r.mitigation) && (
                  <div style={styles.subText}>
                    {r.impact && <span>Impact: {r.impact}</span>}
                    {r.mitigation && <span> · Mitigation: {r.mitigation}</span>}
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div style={styles.block}>
        <div style={styles.blockLabel}>Tasks extracted</div>
        <div style={styles.text}>{detail.task_count} task(s) — see the Approvals tab to review them.</div>
      </div>
    </div>
  );
}

const styles = {
  scroll:  { flex: 1, overflowY: 'auto', padding: '16px' },
  block:   { marginBottom: 20 },
  blockLabel: {
    fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase',
    letterSpacing: 0.5, marginBottom: 8, fontWeight: 600,
  },
  text:    { color: 'var(--text)', lineHeight: 1.7, whiteSpace: 'pre-wrap' },
  list:    { paddingLeft: 18, color: 'var(--text)', lineHeight: 1.9 },
  listItem:{ marginBottom: 6 },
  subText: { fontSize: 11, color: 'var(--muted)', lineHeight: 1.6 },
  empty:   { color: 'var(--muted)', textAlign: 'center', marginTop: 60, padding: '0 20px', fontSize: 13 },
  error:   { color: 'var(--danger)', textAlign: 'center', marginTop: 60, fontSize: 13 },
};
