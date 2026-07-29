import { useEffect, useState } from 'react';
import { api } from '../services/api';

export default function MeetingSummary({ meeting }) {
  const [detail,  setDetail]  = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  // Recipient list for the "Send summary" action below - seeded from the
  // meeting's participants (participant_emails), editable so extra people
  // who weren't original attendees can be added before sending.
  const [recipients, setRecipients] = useState([]);
  const [newEmail,   setNewEmail]   = useState('');
  const [sending,    setSending]    = useState(false);
  const [sendResult, setSendResult] = useState(null); // { results: [...] } | null
  const [sendError,  setSendError]  = useState(null);

  // NEW: edit mode for the summary itself - "what happened", key
  // discussion points, decisions, risks, blockers. `draft` holds the
  // editable working copy; `detail` (the saved version) is only replaced
  // once Save succeeds. Editing works whether or not the summary mail has
  // already been sent - sending and editing are independent actions.
  const [editing, setEditing] = useState(false);
  const [draft,   setDraft]   = useState(null);
  const [saving,  setSaving]  = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    if (!meeting) return;
    setDetail(null);
    setError(null);
    setLoading(true);
    setRecipients([]);
    setSendResult(null);
    setSendError(null);
    setEditing(false);
    setDraft(null);
    setSaveError(null);
    api
      .getMeeting(meeting.id)
      .then((d) => {
        setDetail(d);
        setRecipients(d.participant_emails || []);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [meeting?.id]);

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  function addRecipient() {
    const value = newEmail.trim();
    if (!value || !EMAIL_RE.test(value)) return;
    setRecipients((prev) => (prev.includes(value) ? prev : [...prev, value]));
    setNewEmail('');
    setSendResult(null);
  }

  function removeRecipient(email) {
    setRecipients((prev) => prev.filter((r) => r !== email));
    setSendResult(null);
  }

  async function sendSummary() {
    if (!meeting || recipients.length === 0) return;
    setSending(true);
    setSendError(null);
    setSendResult(null);
    try {
      const result = await api.sendMeetingSummary(meeting.id, recipients);
      setSendResult(result);
    } catch (e) {
      setSendError(e.message);
    } finally {
      setSending(false);
    }
  }

  // ---- edit mode -----------------------------------------------------

  function startEditing() {
    setDraft({
      summary: detail.summary || '',
      key_discussion_points: [...(detail.key_discussion_points || [])],
      decisions: [...(detail.decisions || [])],
      risks: (detail.risks || []).map((r) => ({
        risk: r.risk || '', impact: r.impact || '', mitigation: r.mitigation || '',
      })),
      blockers: (detail.blockers || []).map((b) => ({
        blocker: b.blocker || '', impact: b.impact || '', owner: b.owner || '', action: b.action || '',
      })),
    });
    setSaveError(null);
    setEditing(true);
  }

  function cancelEditing() {
    setEditing(false);
    setDraft(null);
    setSaveError(null);
  }

  function updateListItem(field, index, value) {
    setDraft((prev) => {
      const next = [...prev[field]];
      next[index] = value;
      return { ...prev, [field]: next };
    });
  }

  function removeListItem(field, index) {
    setDraft((prev) => ({ ...prev, [field]: prev[field].filter((_, i) => i !== index) }));
  }

  function addListItem(field) {
    setDraft((prev) => ({ ...prev, [field]: [...prev[field], ''] }));
  }

  function updateRisk(index, key, value) {
    setDraft((prev) => {
      const next = [...prev.risks];
      next[index] = { ...next[index], [key]: value };
      return { ...prev, risks: next };
    });
  }

  function removeRisk(index) {
    setDraft((prev) => ({ ...prev, risks: prev.risks.filter((_, i) => i !== index) }));
  }

  function addRisk() {
    setDraft((prev) => ({ ...prev, risks: [...prev.risks, { risk: '', impact: '', mitigation: '' }] }));
  }

  function updateBlocker(index, key, value) {
    setDraft((prev) => {
      const next = [...prev.blockers];
      next[index] = { ...next[index], [key]: value };
      return { ...prev, blockers: next };
    });
  }

  function removeBlocker(index) {
    setDraft((prev) => ({ ...prev, blockers: prev.blockers.filter((_, i) => i !== index) }));
  }

  function addBlocker() {
    setDraft((prev) => ({
      ...prev,
      blockers: [...prev.blockers, { blocker: '', impact: '', owner: '', action: '' }],
    }));
  }

  async function saveEditing() {
    if (!meeting || !draft) return;
    setSaving(true);
    setSaveError(null);
    try {
      const payload = {
        summary: draft.summary.trim(),
        key_discussion_points: draft.key_discussion_points.map((s) => s.trim()).filter(Boolean),
        decisions: draft.decisions.map((s) => s.trim()).filter(Boolean),
        risks: draft.risks
          .map((r) => ({ risk: r.risk.trim(), impact: r.impact.trim(), mitigation: r.mitigation.trim() }))
          .filter((r) => r.risk),
        blockers: draft.blockers
          .map((b) => ({
            blocker: b.blocker.trim(), impact: b.impact.trim(), owner: b.owner.trim(), action: b.action.trim(),
          }))
          .filter((b) => b.blocker),
      };
      const updated = await api.updateMeetingSummary(meeting.id, payload);
      setDetail(updated);
      setEditing(false);
      setDraft(null);
    } catch (e) {
      setSaveError(e.message);
    } finally {
      setSaving(false);
    }
  }

  // ---- render ----------------------------------------------------------

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

  if (!detail) {
    return <div style={styles.empty}>No summary available for this meeting.</div>;
  }

  return (
    <div style={styles.scroll}>
      <div style={styles.toolbar}>
        <div style={styles.blockLabelNoMargin}>Meeting Summary</div>
        {!editing ? (
          <button className="ghost" style={styles.smallBtn} onClick={startEditing}>
            ✎ Edit
          </button>
        ) : (
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="ghost" style={styles.smallBtn} onClick={cancelEditing} disabled={saving}>
              Cancel
            </button>
            <button className="primary" style={styles.smallBtn} onClick={saveEditing} disabled={saving}>
              {saving ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        )}
      </div>

      {saveError && (
        <div style={{ ...styles.subText, color: 'var(--danger)', marginBottom: 12 }}>⚠ {saveError}</div>
      )}

      <div style={styles.block}>
        <div style={styles.blockLabel}>What happened</div>
        {editing ? (
          <textarea
            value={draft.summary}
            onChange={(e) => setDraft((prev) => ({ ...prev, summary: e.target.value }))}
            style={styles.textarea}
            rows={4}
            placeholder="What happened in this meeting…"
          />
        ) : (
          <div style={styles.text}>
            {detail.summary || <span style={styles.subText}>No summary yet — click Edit to add one.</span>}
          </div>
        )}
      </div>

      {(editing || detail.key_discussion_points?.length > 0) && (
        <div style={styles.block}>
          <div style={styles.blockLabel}>Key discussion points</div>
          {editing ? (
            <>
              {draft.key_discussion_points.map((point, i) => (
                <div key={i} style={styles.editRow}>
                  <input
                    value={point}
                    onChange={(e) => updateListItem('key_discussion_points', i, e.target.value)}
                    style={styles.editListInput}
                    placeholder="Discussion point"
                  />
                  <button
                    type="button"
                    onClick={() => removeListItem('key_discussion_points', i)}
                    style={styles.chipRemove}
                    aria-label="Remove point"
                  >
                    ×
                  </button>
                </div>
              ))}
              <button className="ghost" style={styles.addItemBtn} onClick={() => addListItem('key_discussion_points')}>
                + Add point
              </button>
            </>
          ) : (
            <ul style={styles.list}>
              {detail.key_discussion_points.map((d, i) => (
                <li key={i} style={styles.listItem}>{d}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {(editing || detail.decisions?.length > 0) && (
        <div style={styles.block}>
          <div style={styles.blockLabel}>Decisions</div>
          {editing ? (
            <>
              {draft.decisions.map((point, i) => (
                <div key={i} style={styles.editRow}>
                  <input
                    value={point}
                    onChange={(e) => updateListItem('decisions', i, e.target.value)}
                    style={styles.editListInput}
                    placeholder="Decision"
                  />
                  <button
                    type="button"
                    onClick={() => removeListItem('decisions', i)}
                    style={styles.chipRemove}
                    aria-label="Remove decision"
                  >
                    ×
                  </button>
                </div>
              ))}
              <button className="ghost" style={styles.addItemBtn} onClick={() => addListItem('decisions')}>
                + Add decision
              </button>
            </>
          ) : (
            <ul style={styles.list}>
              {detail.decisions.map((d, i) => (
                <li key={i} style={styles.listItem}>{d}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/*
        BUGFIX (kept from earlier fix): the backend returns risks/blockers
        as structured objects - { blocker, impact, owner, action } and
        { risk, impact, mitigation } - not plain strings. Rendering `{d}`
        directly throws "Objects are not valid as a React child". The
        read-only branch below renders the known sub-fields explicitly;
        the edit branch gives each sub-field its own input.
      */}
      {(editing || detail.blockers?.length > 0) && (
        <div style={styles.block}>
          <div style={styles.blockLabel}>Blockers</div>
          {editing ? (
            <>
              {draft.blockers.map((b, i) => (
                <div key={i} style={styles.editCard}>
                  <div style={styles.editCardHeader}>
                    <span style={styles.editCardTitle}>Blocker {i + 1}</span>
                    <button
                      type="button"
                      onClick={() => removeBlocker(i)}
                      style={styles.chipRemove}
                      aria-label="Remove blocker"
                    >
                      ×
                    </button>
                  </div>
                  <input
                    value={b.blocker}
                    onChange={(e) => updateBlocker(i, 'blocker', e.target.value)}
                    style={styles.editFieldInput}
                    placeholder="Blocker"
                  />
                  <input
                    value={b.impact}
                    onChange={(e) => updateBlocker(i, 'impact', e.target.value)}
                    style={styles.editFieldInput}
                    placeholder="Impact (optional)"
                  />
                  <input
                    value={b.owner}
                    onChange={(e) => updateBlocker(i, 'owner', e.target.value)}
                    style={styles.editFieldInput}
                    placeholder="Owner (optional)"
                  />
                  <input
                    value={b.action}
                    onChange={(e) => updateBlocker(i, 'action', e.target.value)}
                    style={{ ...styles.editFieldInput, marginBottom: 0 }}
                    placeholder="Next step (optional)"
                  />
                </div>
              ))}
              <button className="ghost" style={styles.addItemBtn} onClick={addBlocker}>
                + Add blocker
              </button>
            </>
          ) : (
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
          )}
        </div>
      )}

      {(editing || detail.risks?.length > 0) && (
        <div style={styles.block}>
          <div style={styles.blockLabel}>Risks</div>
          {editing ? (
            <>
              {draft.risks.map((r, i) => (
                <div key={i} style={styles.editCard}>
                  <div style={styles.editCardHeader}>
                    <span style={styles.editCardTitle}>Risk {i + 1}</span>
                    <button
                      type="button"
                      onClick={() => removeRisk(i)}
                      style={styles.chipRemove}
                      aria-label="Remove risk"
                    >
                      ×
                    </button>
                  </div>
                  <input
                    value={r.risk}
                    onChange={(e) => updateRisk(i, 'risk', e.target.value)}
                    style={styles.editFieldInput}
                    placeholder="Risk"
                  />
                  <input
                    value={r.impact}
                    onChange={(e) => updateRisk(i, 'impact', e.target.value)}
                    style={styles.editFieldInput}
                    placeholder="Impact (optional)"
                  />
                  <input
                    value={r.mitigation}
                    onChange={(e) => updateRisk(i, 'mitigation', e.target.value)}
                    style={{ ...styles.editFieldInput, marginBottom: 0 }}
                    placeholder="Mitigation (optional)"
                  />
                </div>
              ))}
              <button className="ghost" style={styles.addItemBtn} onClick={addRisk}>
                + Add risk
              </button>
            </>
          ) : (
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
          )}
        </div>
      )}

      <div style={styles.block}>
        <div style={styles.blockLabel}>Tasks extracted</div>
        <div style={styles.text}>{detail.task_count} task(s) — see the Approvals tab to review them.</div>
      </div>

      <div style={styles.block}>
        <div style={styles.blockLabel}>Send summary to</div>

        <div style={styles.recipientList}>
          {recipients.length === 0 && (
            <div style={styles.subText}>
              No recipients yet — this meeting has no participant emails on file. Add one below.
            </div>
          )}
          {recipients.map((email) => (
            <span key={email} style={styles.chip}>
              {email}
              <button
                type="button"
                onClick={() => removeRecipient(email)}
                style={styles.chipRemove}
                aria-label={`Remove ${email}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>

        <div style={styles.addRow}>
          <input
            type="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addRecipient();
              }
            }}
            placeholder="Add another member's email"
            style={styles.addInput}
          />
          <button className="ghost" onClick={addRecipient} disabled={!newEmail.trim()}>
            Add
          </button>
        </div>

        <button
          className="primary"
          onClick={sendSummary}
          disabled={sending || recipients.length === 0 || editing}
          style={styles.sendButton}
        >
          {sending ? 'Sending…' : `✉ Send Summary Email${recipients.length ? ` (${recipients.length})` : ''}`}
        </button>

        {editing && <div style={{ ...styles.subText, marginTop: 6 }}>Save your changes before sending.</div>}

        {sendError && <div style={{ ...styles.subText, color: 'var(--danger)' }}>⚠ {sendError}</div>}

        {sendResult?.results && (
          <div style={styles.sendResults}>
            {sendResult.results.map((r) => (
              <div
                key={r.recipient}
                style={{ ...styles.subText, color: r.sent ? 'var(--success)' : 'var(--danger)' }}
              >
                {r.sent ? '✓' : '✗'} {r.recipient}
                {r.error ? ` — ${r.error}` : ''}
              </div>
            ))}
          </div>
        )}
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
  blockLabelNoMargin: {
    fontSize: 11, color: 'var(--muted)', textTransform: 'uppercase',
    letterSpacing: 0.5, fontWeight: 600,
  },
  text:    { color: 'var(--text)', lineHeight: 1.7, whiteSpace: 'pre-wrap' },
  list:    { paddingLeft: 18, color: 'var(--text)', lineHeight: 1.9 },
  listItem:{ marginBottom: 6 },
  subText: { fontSize: 11, color: 'var(--muted)', lineHeight: 1.6 },
  empty:   { color: 'var(--muted)', textAlign: 'center', marginTop: 60, padding: '0 20px', fontSize: 13 },
  error:   { color: 'var(--danger)', textAlign: 'center', marginTop: 60, fontSize: 13 },
  recipientList: {
    display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10,
  },
  chip: {
    display: 'inline-flex', alignItems: 'center', gap: 6,
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 999, padding: '3px 6px 3px 10px', fontSize: 12,
    color: 'var(--text)',
  },
  chipRemove: {
    background: 'none', border: 'none', cursor: 'pointer',
    color: 'var(--muted)', fontSize: 14, lineHeight: 1, padding: '0 2px',
  },
  addRow: { display: 'flex', gap: 6, marginBottom: 10 },
  addInput: { flex: 1 },
  sendButton: { width: '100%' },
  sendResults: { marginTop: 10, display: 'flex', flexDirection: 'column', gap: 3 },

  // edit mode
  toolbar: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 16, paddingBottom: 12, borderBottom: '1px solid var(--border)',
  },
  smallBtn: { padding: '4px 10px', fontSize: 11 },
  textarea: {
    width: '100%', minHeight: 90, background: 'var(--surface)',
    border: '1px solid var(--border)', borderRadius: 6,
    color: 'var(--text)', padding: '6px 10px', fontFamily: 'inherit',
    fontSize: 13, lineHeight: 1.6, resize: 'vertical', outline: 'none',
    boxSizing: 'border-box',
  },
  editRow: { display: 'flex', gap: 6, marginBottom: 6, alignItems: 'center' },
  editListInput: { flex: 1 },
  editFieldInput: { marginBottom: 6, boxSizing: 'border-box' },
  addItemBtn: { fontSize: 11, padding: '4px 10px', marginTop: 2 },
  editCard: {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius)', padding: 10, marginBottom: 8,
  },
  editCardHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6,
  },
  editCardTitle: { fontSize: 11, color: 'var(--muted)', fontWeight: 600 },
};
