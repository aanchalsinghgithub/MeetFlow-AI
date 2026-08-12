/**
 * src/services/audioCapture.js
 *
 * Captures system audio using Electron's built-in WASAPI loopback
 * (setDisplayMediaRequestHandler set in main.js).
 *
 * Flow:
 *   getDisplayMedia({ video:true, audio:true })
 *   → Web Audio API ScriptProcessorNode collects PCM samples
 *   → every chunkSeconds seconds → encode WAV → POST to FastAPI
 *
 * No native modules required.
 */

const SAMPLE_RATE = 16000;

// ------------------------------------------------------------------
// WAV encoder (browser ArrayBuffer)
// ------------------------------------------------------------------
function encodeWav(float32, sampleRate = SAMPLE_RATE) {
  const numChannels  = 1;
  const bitsPerSample = 16;
  const byteRate     = sampleRate * numChannels * (bitsPerSample / 8);
  const blockAlign   = numChannels * (bitsPerSample / 8);
  const dataSize     = float32.length * 2;
  const buf          = new ArrayBuffer(44 + dataSize);
  const view         = new DataView(buf);
  const str          = (off, s) => [...s].forEach((c, i) => view.setUint8(off + i, c.charCodeAt(0)));

  str(0,  'RIFF'); view.setUint32(4,  36 + dataSize, true);
  str(8,  'WAVE'); str(12, 'fmt ');
  view.setUint32(16, 16,           true);
  view.setUint16(20, 1,            true);  // PCM
  view.setUint16(22, numChannels,  true);
  view.setUint32(24, sampleRate,   true);
  view.setUint32(28, byteRate,     true);
  view.setUint16(32, blockAlign,   true);
  view.setUint16(34, bitsPerSample,true);
  str(36, 'data'); view.setUint32(40, dataSize, true);

  let off = 44;
  for (let i = 0; i < float32.length; i++) {
    const s = Math.max(-1, Math.min(1, float32[i]));
    view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    off += 2;
  }
  return buf;
}

// ------------------------------------------------------------------
// AudioCapture class
// ------------------------------------------------------------------
export class AudioCapture {
  /**
   * @param {object}   opts
   * @param {number}   opts.meetingId
   * @param {string}   opts.backendUrl       e.g. "http://localhost:8000"
   * @param {number}   [opts.chunkSeconds=15]
   * @param {Function} [opts.onTranscript]   called with FastAPI response JSON
   * @param {Function} [opts.onError]        called with error string
   */
  constructor({ meetingId, backendUrl, chunkSeconds = 15, onTranscript, onError }) {
    this.meetingId    = meetingId;
    this.backendUrl   = backendUrl;
    this.chunkSeconds = chunkSeconds;
    this.onTranscript = onTranscript || (() => {});
    this.onError      = onError      || ((e) => console.error('[AudioCapture]', e));

    this._stream      = null;
    this._audioCtx    = null;
    this._processor   = null;
    this._source      = null;
    this._samples     = [];
    this._chunkIndex  = 0;
    this._running     = false;

    // BUGFIX: onaudioprocess used to call `this._sendChunk(...)` without
    // awaiting it, so a new chunk POST fired every `chunkSeconds` seconds
    // no matter whether the previous chunk's request had finished. Whisper
    // transcription (+ diarization) on the backend can take longer than
    // the 15s chunk interval, so this routinely piled up several
    // concurrent heavy transcription requests on the backend at once -
    // enough to OOM-crash a memory-constrained instance and take down
    // *every* in-flight request (including unrelated ones like
    // GET /upcoming) with 502/503s. Chunks are now queued and sent one at
    // a time, waiting for each request to settle before starting the next.
    this._sendQueue   = Promise.resolve();
  }

  // ------------------------------------------------------------------
  async start() {
    if (this._running) return;

    // Request display + loopback audio
    // Electron's setDisplayMediaRequestHandler intercepts this and returns
    // Windows WASAPI loopback audio — no user prompt needed.
    let stream;
    try {
      stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,   // required by spec; we discard the video track below
        audio: true,
      });
    } catch (err) {
      this.onError(`getDisplayMedia failed: ${err.message}`);
      return;
    }

    // Drop video tracks — we only want the audio loopback
    stream.getVideoTracks().forEach((t) => { t.stop(); stream.removeTrack(t); });

    if (stream.getAudioTracks().length === 0) {
      this.onError('No audio track in loopback stream. Is audio loopback enabled?');
      return;
    }

    this._stream   = stream;
    this._audioCtx = new AudioContext({ sampleRate: SAMPLE_RATE });
    this._source   = this._audioCtx.createMediaStreamSource(stream);

    const bufferSize      = 4096;
    const samplesPerChunk = SAMPLE_RATE * this.chunkSeconds;

    // ScriptProcessorNode is deprecated but works fine in Electron's Chromium
    this._processor = this._audioCtx.createScriptProcessor(bufferSize, 1, 1);

    this._processor.onaudioprocess = (e) => {
      if (!this._running) return;
      const data = e.inputBuffer.getChannelData(0);
      for (let i = 0; i < data.length; i++) this._samples.push(data[i]);

      while (this._samples.length >= samplesPerChunk) {
        const chunk = this._samples.splice(0, samplesPerChunk);
        const index = this._chunkIndex++;
        // Chain onto the queue instead of firing immediately - each chunk
        // now waits for the previous one's request (including retries) to
        // finish before it's sent, so the backend never sees overlapping
        // transcription jobs for the same meeting.
        this._sendQueue = this._sendQueue.then(() =>
          this._sendChunk(new Float32Array(chunk), index)
        );
      }
    };

    this._source.connect(this._processor);
    this._processor.connect(this._audioCtx.destination);
    this._running = true;
    console.log('[AudioCapture] Started — loopback stream active.');
  }

  // ------------------------------------------------------------------
  stop() {
    if (!this._running) return;
    this._running = false;

    // Flush remaining samples as a final (possibly short) chunk - still
    // goes through the queue so it doesn't overlap a chunk already in
    // flight.
    if (this._samples.length > 100) {
      const finalChunk = new Float32Array(this._samples);
      const index = this._chunkIndex++;
      this._sendQueue = this._sendQueue.then(() => this._sendChunk(finalChunk, index));
    }
    this._samples = [];

    try { this._processor?.disconnect(); } catch (_) {}
    try { this._source?.disconnect();    } catch (_) {}
    try { this._audioCtx?.close();       } catch (_) {}
    this._stream?.getTracks().forEach((t) => t.stop());

    this._processor = null;
    this._source    = null;
    this._audioCtx  = null;
    this._stream    = null;
    console.log('[AudioCapture] Stopped.');
  }

  get isRunning() { return this._running; }

  // ------------------------------------------------------------------
  // BUGFIX: a chunk that failed (e.g. a transient 502/503 while the
  // backend was mid-restart) used to just log an error and vanish - that
  // slice of audio was gone forever, with a gap in the transcript. 502,
  // 503, and network-level failures are usually transient (a redeploy, a
  // cold start, a momentary overload), so those are now retried a few
  // times with a short backoff before giving up. A 400 "meeting not
  // active" is NOT retried - that's a real rejection, not a hiccup.
  async _sendChunk(float32, chunkIndex, attempt = 1) {
    const MAX_ATTEMPTS = 4;
    const RETRY_DELAY_MS = 2000;

    const offsetSeconds = chunkIndex * this.chunkSeconds;
    const wav           = encodeWav(float32, SAMPLE_RATE);
    const blob          = new Blob([wav], { type: 'audio/wav' });
    const formData      = new FormData();
    formData.append('audio', blob, `chunk_${offsetSeconds}.wav`);

    const url = `${this.backendUrl}/api/meetings/${this.meetingId}/audio?chunk_offset=${offsetSeconds}`;

    // NOTE: must read the token the same way services/api.js does — this
    // fetch() bypasses that wrapper (it needs a raw FormData body, not
    // JSON), so the Authorization header has to be added explicitly here.
    // Do NOT set Content-Type manually: the browser needs to add the
    // multipart boundary itself when given a FormData body.
    const token = await window.electronAPI?.getAuthToken?.();
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    const retryable = async (reason) => {
      if (attempt >= MAX_ATTEMPTS) {
        this.onError(`Chunk ${chunkIndex} dropped after ${attempt} attempts: ${reason}`);
        return;
      }
      this.onError(`${reason} — retrying chunk ${chunkIndex} (attempt ${attempt + 1}/${MAX_ATTEMPTS})`);
      await new Promise((r) => setTimeout(r, RETRY_DELAY_MS * attempt));
      return this._sendChunk(float32, chunkIndex, attempt + 1);
    };

    try {
      const res = await fetch(url, { method: 'POST', headers, body: formData });
      if (!res.ok) {
        const text = await res.text();
        // If the backend ever rejects a chunk because the meeting isn't
        // active (e.g. already marked completed), stop capturing instead
        // of retrying forever — previously this just logged the error and
        // kept POSTing every chunkSeconds indefinitely.
        if (res.status === 400 && /not active/i.test(text)) {
          this.onError('Meeting has ended — stopping capture automatically.');
          this.stop();
          return;
        }
        // Bad Gateway / Service Unavailable almost always mean the
        // backend instance is restarting or briefly overloaded, not that
        // this chunk is invalid — worth a retry instead of dropping it.
        if (res.status === 502 || res.status === 503 || res.status === 504) {
          return retryable(`Backend ${res.status}`);
        }
        this.onError(`Backend ${res.status}: ${text}`);
        return;
      }
      const json = await res.json();
      this.onTranscript(json);
    } catch (err) {
      // Network-level failure (connection reset, DNS hiccup, etc.) — also
      // worth retrying rather than losing the chunk.
      return retryable(`Chunk POST failed: ${err.message}`);
    }
  }
}
