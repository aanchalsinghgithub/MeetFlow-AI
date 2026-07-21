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
        this._sendChunk(new Float32Array(chunk), this._chunkIndex++);
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

    // Flush remaining samples as a final (possibly short) chunk
    if (this._samples.length > 100) {
      this._sendChunk(new Float32Array(this._samples), this._chunkIndex++);
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
  async _sendChunk(float32, chunkIndex) {
    const offsetSeconds = chunkIndex * this.chunkSeconds;
    const wav           = encodeWav(float32, SAMPLE_RATE);
    const blob          = new Blob([wav], { type: 'audio/wav' });
    const formData      = new FormData();
    formData.append('audio', blob, `chunk_${offsetSeconds}.wav`);

    const url = `${this.backendUrl}/api/meetings/${this.meetingId}/audio?chunk_offset=${offsetSeconds}`;

    try {
      const res = await fetch(url, { method: 'POST', body: formData });
      if (!res.ok) {
        const text = await res.text();
        // BUGFIX: the backend returns 400 "Meeting is not active" once the
        // bot detects the meeting has ended and flips status to
        // "completed". Previously we just reported the error and kept
        // capturing/POSTing every chunkSeconds forever (visible in the
        // logs as a 400 every ~15s until someone manually hit Stop).
        // Auto-stop as soon as the backend tells us the meeting is over.
        if (res.status === 400 && /not active/i.test(text)) {
          this.onError('Meeting has ended — stopping capture automatically.');
          this.stop();
          return;
        }
        this.onError(`Backend ${res.status}: ${text}`);
        return;
      }
      const json = await res.json();
      this.onTranscript(json);
    } catch (err) {
      this.onError(`Chunk POST failed: ${err.message}`);
    }
  }
}
