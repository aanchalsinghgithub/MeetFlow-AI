import { useCallback, useEffect, useState } from "react";
import MeetingList from "./components/MeetingList";
import AudioCaptureControls from "./components/AudioCaptureControls";
import TranscriptView from "./components/TranscriptView";
import ApprovalQueue from "./components/ApprovalQueue";
import { api } from "./services/api";

// ------------------------------------------------------------------
// Settings bar
// ------------------------------------------------------------------
function SettingsBar({ onSave }) {
  const [url, setUrl] = useState("http://localhost:8000");
  const [ok, setOk] = useState(null);

  async function save() {
    if (window.electronAPI) await window.electronAPI.setBackendUrl(url);
    try {
      await api.health();
      setOk(true);
    } catch {
      setOk(false);
    }
    onSave?.(url);
  }

  return (
    <div style={sb.bar}>
      <span style={sb.label}>Backend</span>
      <input
        style={sb.input}
        value={url}
        onChange={(e) => {
          setUrl(e.target.value);
          setOk(null);
        }}
        placeholder="http://localhost:8000"
      />
      <button className="ghost" onClick={save} style={{ padding: "4px 12px" }}>
        Connect
      </button>
      {ok === true && (
        <span style={{ color: "var(--success)", fontSize: 12 }}>
          ✓ Connected
        </span>
      )}
      {ok === false && (
        <span style={{ color: "var(--danger)", fontSize: 12 }}>
          ✗ Unreachable
        </span>
      )}
    </div>
  );
}

const sb = {
  bar: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 16px",
    background: "var(--surface)",
    borderBottom: "1px solid var(--border)",
  },
  label: { fontSize: 11, color: "var(--muted)", whiteSpace: "nowrap" },
  input: { width: 280 },
};

// ------------------------------------------------------------------
// App root
// ------------------------------------------------------------------
export default function App() {
  const [view, setView] = useState("meetings"); // "meetings" | "approvals"
  const [selectedMeeting, setSelectedMeeting] = useState(null);
  const [capturing, setCapturing] = useState(false);
  const [captureError, setCaptureError] = useState(null);
  const [liveEntries, setLiveEntries] = useState([]);

  // Join bot when capture starts (so backend marks meeting in_progress)
  const handleStart = useCallback(async () => {
    setCaptureError(null);
    setLiveEntries([]);
    try {
      if (selectedMeeting?.status === "scheduled") {
        await api.joinBot(selectedMeeting.id);
      }
    } catch (e) {
      console.warn("joinBot (non-fatal):", e.message);
    }
    setCapturing(true);
  }, [selectedMeeting]);

  const handleStop = useCallback(async () => {
    setCapturing(false);
    try {
      if (selectedMeeting?.id) await api.finalizeMeeting(selectedMeeting.id);
    } catch (e) {
      console.warn("finalizeMeeting failed:", e.message);
    }
  }, [selectedMeeting]);

  // Called by AudioCaptureControls each time a chunk is transcribed
  const handleTranscript = useCallback((data) => {
    if (data?.transcript?.length) {
      setLiveEntries((prev) => [...prev, ...data.transcript]);
    }
    // Also relay through IPC for any other windows (optional)
    window.electronAPI?.reportTranscriptChunk?.(data);
  }, []);

  const handleSelect = useCallback(
    (meeting) => {
      if (capturing) return;
      setSelectedMeeting(meeting);
      setLiveEntries([]);
      setCaptureError(null);
    },
    [capturing],
  );

  return (
    <div style={styles.app}>
      <div style={styles.topBar}>
        <span style={styles.logo}>⚡ MeetFlow Desktop</span>
        <div style={styles.nav}>
          <button
            className={view === "meetings" ? "primary" : "ghost"}
            onClick={() => setView("meetings")}
            style={styles.navBtn}
          >
            Meetings
          </button>
          <button
            className={view === "approvals" ? "primary" : "ghost"}
            onClick={() => setView("approvals")}
            style={styles.navBtn}
          >
            Approvals
          </button>
        </div>
        <SettingsBar />
      </div>

      {view === "approvals" ? (
        <div style={styles.main}>
          <ApprovalQueue />
        </div>
      ) : (
      <div style={styles.main}>
        <div style={styles.sidebar}>
          <MeetingList
            onSelect={handleSelect}
            selectedId={selectedMeeting?.id}
            capturing={capturing}
          />
        </div>

        <div style={styles.center}>
          <TranscriptView meeting={selectedMeeting} liveEntries={liveEntries} />
        </div>

        <div style={styles.right}>
          {selectedMeeting && (
            <div style={styles.meetingInfo}>
              <div style={styles.meetingTitle}>{selectedMeeting.title}</div>
              <div style={styles.meetingMeta}>
                ID: {selectedMeeting.id} ·{" "}
                {selectedMeeting.starts_at
                  ? new Date(selectedMeeting.starts_at).toLocaleTimeString()
                  : "No time"}
              </div>
            </div>
          )}

          <AudioCaptureControls
            meeting={selectedMeeting}
            capturing={capturing}
            onStart={handleStart}
            onStop={handleStop}
            onTranscript={handleTranscript}
            error={captureError}
          />

          <div style={styles.howTo}>
            <div style={styles.howToTitle}>How it works</div>
            <ol style={styles.howToList}>
              <li>Select an upcoming meeting.</li>
              <li>
                Click <b>Start Capture</b> — WASAPI loopback records system
                audio.
              </li>
              <li>Chunks are sent to your FastAPI backend every 15 s.</li>
              <li>Whisper transcribes and stores each chunk live.</li>
              <li>
                Click <b>Stop Capture</b> when the meeting ends — this also
                generates the meeting Summary and sends tasks for approval.
              </li>
            </ol>
          </div>
        </div>
      </div>
      )}
    </div>
  );
}

const styles = {
  app: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    background: "var(--bg)",
  },
  topBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 16px",
    height: 48,
    background: "var(--surface)",
    borderBottom: "1px solid var(--border)",
    flexShrink: 0,
  },
  logo: { fontWeight: 700, fontSize: 15, letterSpacing: 0.3 },
  nav: { display: "flex", gap: 6 },
  navBtn: { padding: "5px 12px", fontSize: 12 },
  main: { display: "flex", flex: 1, overflow: "hidden" },
  sidebar: { width: 280, flexShrink: 0, overflow: "hidden" },
  center: {
    flex: 1,
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
  },
  right: {
    width: 300,
    flexShrink: 0,
    padding: 16,
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: 16,
    borderLeft: "1px solid var(--border)",
  },
  meetingInfo: {
    background: "var(--surface)",
    borderRadius: "var(--radius)",
    border: "1px solid var(--border)",
    padding: "12px 14px",
  },
  meetingTitle: { fontWeight: 700, marginBottom: 4 },
  meetingMeta: { fontSize: 11, color: "var(--muted)" },
  howTo: {
    background: "var(--surface)",
    borderRadius: "var(--radius)",
    border: "1px solid var(--border)",
    padding: 14,
  },
  howToTitle: {
    fontWeight: 600,
    marginBottom: 10,
    fontSize: 12,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: 0.5,
  },
  howToList: {
    paddingLeft: 18,
    color: "var(--muted)",
    fontSize: 12,
    lineHeight: 2,
  },
};
