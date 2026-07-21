import { useEffect, useState } from 'react';
import { api } from '../services/api';

const CONFIDENCE_COLOR = (c) => (c >= 0.9 ? 'green' : c >= 0.7 ? 'yellow' : 'red');

const PRIORITIES = ['low', 'medium', 'high', 'urgent'];

// Groups flat approval rows by the meeting they came from, preserving the
// backend's ordering (newest approval first) for which group appears first.
function groupByMeeting(rows) {
  const groups = [];
  const byKey = new Map();
  for (const row of rows) {
    const key = row.meeting_id ?? 'none';
    let group = byKey.get(key);
    if (!group) {
      group = {
        meetingId: row.meeting_id ?? null,
        meetingTitle: row.meeting_title || 'No meeting',
        items: [],
      };
      byKey.set(key, group);
      groups.push(group);
    }
    group.items.push(row);
  }
  return groups;
}

export default function ApprovalQueue() {
  const [rows,    setRows]    = useState([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [busyId,  setBusyId]  = useState(null);   // approval currently being approved/rejected
  const [editing, setEditing] = useState(null);   // { taskId, form } while an edit form is open

  async function load() {
    setLoading(true);
    setError(null);
    try {
      setRows(await api.listApprovals());
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
  }, []);

  async function decide(taskId, decision, recipientEmail) {
    setBusyId(taskId);
    try {
      await api.decideApproval(taskId, {
        decision,
        // Keep sending to whatever email is already shown for this task
        // ("Goes to: ...") unless the user edited it - see EditForm below
        // for the editable path.
        ...(recipientEmail ? { recipient_email: recipientEmail } : {}),
      });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  }

  async function openEdit(row) {
    setError(null);
    try {
      const task = await api.getTask(row.task_id);
      setEditing({
        taskId: row.task_id,
        approvalId: row.approval_id,
        form: {
          title:       task.title || '',
          owner:       task.owner || '',
          domain:      task.domain || '',
          priority:    task.priority || 'medium',
          deadline:    task.deadline || '',
          description: task.description || task.title || '',
          dependencies: task.dependencies || [],
          confidence:  task.confidence ?? 0,
          // NEW: editable "send approval email to" field, prefilled from
          // what the queue is currently showing for this task.
          recipientEmail: row.manager_email || '',
        },
      });
    } catch (e) {
      setError(e.message);
    }
  }

  async function saveEdit() {
    if (!editing) return;
    setBusyId(editing.taskId);
    try {
      // recipientEmail routes the assignment email (ApprovalUpdate.recipient_email);
      // it isn't a task field, so it's kept out of edited_task.
      const { recipientEmail, ...taskFields } = editing.form;
      await api.decideApproval(editing.taskId, {
        decision: 'edited',
        edited_task: taskFields,
        recipient_email: recipientEmail,
      });
      setEditing(null);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusyId(null);
    }
  }

  const pending = rows.filter((r) => (r.decision || 'pending') === 'pending');
  const decided = rows.filter((r) => (r.decision || 'pending') !== 'pending');
  const pendingGroups = groupByMeeting(pending);

  return (
    <div style={styles.container}>
      <div style={styles.toolbar}>
        <span style={styles.title}>Approval Queue</span>
        <button className="ghost" onClick={load} disabled={loading} style={{ padding: '4px 10px' }}>
          {loading ? '⟳' : 'Refresh'}
        </button>
      </div>

      {error && <div style={styles.error}>⚠ {error}</div>}

      <div style={styles.scroll}>
        {pending.length === 0 && !loading && (
          <div style={styles.empty}>No tasks waiting for approval.</div>
        )}

        {pendingGroups.map((group) => (
          <div key={group.meetingId ?? 'none'} style={styles.meetingGroup}>
            <div style={styles.meetingHeader}>
              <span>📁 {group.meetingTitle}</span>
              <span style={styles.meetingCount}>{group.items.length} task(s)</span>
            </div>

            {group.items.map((row) => (
              <div key={row.approval_id} style={styles.card}>
                {editing?.taskId === row.task_id ? (
                  <EditForm
                    form={editing.form}
                    busy={busyId === row.task_id}
                    onChange={(form) => setEditing({ ...editing, form })}
                    onCancel={() => setEditing(null)}
                    onSave={saveEdit}
                  />
                ) : (
                  <>
                    <div style={styles.cardTop}>
                      <div style={styles.taskTitle}>{row.task}</div>
                      <span className={`badge ${CONFIDENCE_COLOR(row.confidence)}`}>
                        {Math.round((row.confidence || 0) * 100)}% confidence
                      </span>
                    </div>

                    <div style={styles.meta}>
                      <span>
                        Owner:{' '}
                        <b style={!row.owner ? styles.missing : undefined}>
                          {row.owner || 'unassigned'}
                        </b>
                      </span>
                      <span>
                        Domain: <b>{row.domain || 'Unclassified'}</b>
                      </span>
                      <span>
                        Goes to: <b>{row.manager_email}</b>
                      </span>
                    </div>

                    <div style={styles.actions}>
                      <button
                        className="primary"
                        disabled={busyId === row.task_id}
                        onClick={() => decide(row.task_id, 'approved', row.manager_email)}
                      >
                        Approve
                      </button>
                      <button
                        className="ghost"
                        disabled={busyId === row.task_id}
                        onClick={() => openEdit(row)}
                      >
                        Edit
                      </button>
                      <button
                        className="danger"
                        disabled={busyId === row.task_id}
                        onClick={() => decide(row.task_id, 'rejected')}
                      >
                        Reject
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        ))}

        {decided.length > 0 && (
          <>
            <div style={styles.sectionLabel}>Already decided</div>
            {decided.map((row) => (
              <div key={row.approval_id} style={{ ...styles.card, opacity: 0.6 }}>
                <div style={styles.cardTop}>
                  <div style={styles.taskTitle}>{row.task}</div>
                  <span
                    className={`badge ${
                      row.decision === 'rejected' ? 'red' : 'blue'
                    }`}
                  >
                    {row.decision}
                  </span>
                </div>
                <div style={styles.meta}>
                  <span>Meeting: <b>{row.meeting_title || 'No meeting'}</b></span>
                  <span>Owner: <b>{row.owner || 'unassigned'}</b></span>
                  <span>Domain: <b>{row.domain || 'Unclassified'}</b></span>
                </div>
                {(row.decision === 'approved' || row.decision === 'edited') && (
                  <div style={styles.actions}>
                    <button
                      className="ghost"
                      disabled={busyId === row.task_id}
                      onClick={() => decide(row.task_id, row.decision, row.manager_email)}
                      title="Re-runs the same decision, which re-sends the task-assignment email - useful after fixing SMTP/env settings"
                    >
                      {busyId === row.task_id ? 'Sending…' : '✉ Resend email'}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

function EditForm({ form, busy, onChange, onCancel, onSave }) {
  const set = (key) => (e) => onChange({ ...form, [key]: e.target.value });

  return (
    <div style={styles.editForm}>
      <label style={styles.label}>Task</label>
      <input value={form.title} onChange={set('title')} />

      <label style={styles.label}>Owner</label>
      <input value={form.owner} onChange={set('owner')} placeholder="e.g. Aanchal" />

      <label style={styles.label}>Domain (routes the approval email)</label>
      <input value={form.domain} onChange={set('domain')} placeholder="frontend / backend / aws / ..." />

      <label style={styles.label}>Priority</label>
      <select value={form.priority} onChange={set('priority')}>
        {PRIORITIES.map((p) => (
          <option key={p} value={p}>{p}</option>
        ))}
      </select>

      <label style={styles.label}>Deadline</label>
      <input value={form.deadline} onChange={set('deadline')} placeholder="e.g. Friday" />

      <label style={styles.label}>Send approval email to</label>
      <input
        type="email"
        value={form.recipientEmail}
        onChange={set('recipientEmail')}
        placeholder="e.g. aanchal2025.singh@gmail.com"
      />

      <div style={styles.actions}>
        <button className="primary" disabled={busy} onClick={onSave}>
          Save &amp; Approve
        </button>
        <button className="ghost" disabled={busy} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

const styles = {
  container: { display: 'flex', flexDirection: 'column', height: '100%' },
  toolbar: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '14px 16px', borderBottom: '1px solid var(--border)',
  },
  title: { fontWeight: 600, fontSize: 13, color: 'var(--text)' },
  scroll: { flex: 1, overflowY: 'auto', padding: 16 },
  error: { color: 'var(--danger)', padding: '8px 16px', fontSize: 12 },
  empty: { color: 'var(--muted)', textAlign: 'center', marginTop: 40 },
  meetingGroup: { marginBottom: 20 },
  meetingHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    fontSize: 12, fontWeight: 600, color: 'var(--text)',
    padding: '6px 2px', marginBottom: 8, borderBottom: '1px solid var(--border)',
  },
  meetingCount: { fontWeight: 400, color: 'var(--muted)', fontSize: 11 },
  sectionLabel: {
    color: 'var(--muted)', fontSize: 11, textTransform: 'uppercase',
    letterSpacing: 0.5, margin: '18px 0 10px',
  },
  card: {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius)', padding: 14, marginBottom: 10,
  },
  cardTop: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    gap: 10, marginBottom: 8,
  },
  taskTitle: { fontWeight: 600 },
  meta: {
    display: 'flex', flexWrap: 'wrap', gap: 14,
    fontSize: 12, color: 'var(--muted)', marginBottom: 12,
  },
  missing: { color: 'var(--warn)' },
  actions: { display: 'flex', gap: 8 },
  editForm: { display: 'flex', flexDirection: 'column', gap: 6 },
  label: { fontSize: 11, color: 'var(--muted)', marginTop: 4 },
};
