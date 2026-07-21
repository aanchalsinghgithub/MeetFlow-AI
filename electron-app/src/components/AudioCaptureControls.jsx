import { useEffect, useRef, useState } from 'react';
import { AudioCapture } from '../services/audioCapture';

export default function AudioCaptureControls({
  meeting,
  capturing,
  onStart,
  onStop,
  onTranscript,
  error,
}) {
  const [chunkSeconds, setChunkSeconds] = useState(15);
  const [loading,      setLoading]      = useState(false);
  const captureRef = useRef(null);

  // Clean up on unmount
  useEffect(() => () => captureRef.current?.stop(), []);

  const isElectron = typeof window !== 'undefined' && !!window.electronAPI?.isElectron;

  async function handleStart() {
    if (!meeting || loading) return;
    setLoading(true);

    try {
      // Get the backend URL from Electron or fall back
      const backendUrl = window.electronAPI
        ? await window.electronAPI.getBackendUrl()
        : 'http://localhost:8000';

      const capture = new AudioCapture({
        meetingId:    meeting.id,
        backendUrl,
        chunkSeconds,
        onTranscript: (data) => {
          onTranscript?.(data);
        },
        onError: (msg) => {
          console.error('[Capture error]', msg);
          window.electronAPI?.reportCaptureError?.(msg);
        },
      });

      await capture.start();

      if (!capture.isRunning) {
        // start() failed (error already reported via onError)
        setLoading(false);
        return;
      }

      captureRef.current = capture;
      onStart?.();
    } catch (err) {
      console.error('[handleStart]', err);
    } finally {
      setLoading(false);
    }
  }

  async function handleStop() {
    setLoading(true);
    try {
      captureRef.current?.stop();
      captureRef.current = null;
      onStop?.();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>🎙 WASAPI Loopback Capture</div>

      {!isElectron && (
        <div style={styles.warn}>
          ⚠ Running in browser — loopback capture requires the MeetFlow Desktop app.
        </div>
      )}

      <label style={styles.label}>Chunk size</label>
      <select
        value={chunkSeconds}
        onChange={(e) => setChunkSeconds(Number(e.target.value))}
        disabled={capturing}
        style={styles.select}
      >
        {[10, 15, 20, 30].map((s) => (
          <option key={s} value={s}>{s} seconds</option>
        ))}
      </select>

      <div style={styles.row}>
        {!capturing ? (
          <button
            className="primary"
            onClick={handleStart}
            disabled={!meeting || loading || !isElectron}
            style={{ flex: 1 }}
          >
            {loading ? 'Starting…' : '▶  Start Capture'}
          </button>
        ) : (
          <button
            className="danger"
            onClick={handleStop}
            disabled={loading}
            style={{ flex: 1 }}
          >
            {loading ? 'Stopping…' : '■  Stop Capture'}
          </button>
        )}
      </div>

      {error && <div style={styles.error}>⚠ {error}</div>}

      {capturing && (
        <div style={styles.live}>
          <span style={styles.dot} /> Capturing system audio…
        </div>
      )}
    </div>
  );
}

const styles = {
  card:      { background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px solid var(--border)', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 },
  cardTitle: { fontWeight: 700, fontSize: 13, marginBottom: 4 },
  label:     { fontSize: 11, color: 'var(--muted)', marginBottom: -6 },
  select:    { marginBottom: 0 },
  row:       { display: 'flex', gap: 8, marginTop: 4 },
  error:     { color: 'var(--danger)', fontSize: 12 },
  warn:      { color: 'var(--warn)', fontSize: 12 },
  live:      { display: 'flex', alignItems: 'center', gap: 6, color: 'var(--success)', fontSize: 12 },
  dot:       { width: 8, height: 8, borderRadius: '50%', background: 'var(--success)', display: 'inline-block' },
};
