class App {
  constructor() {
    this.ws         = null;
    this.audioCtx   = null;
    this.analyser   = null;
    this.stream     = null;
    this.recorder   = null;
    this.chunks     = [];
    this.rafId      = null;
    this.silenceRaf = null;

    this.canvas = document.getElementById('wave');
    this.ctx    = this.canvas.getContext('2d');

    document.getElementById('start-btn').addEventListener('click', () => this.init());
  }

  // ── Bootstrap ───────────────────────────────────────────────────────────────

  async init() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch {
      alert('Microphone access is required. Please allow it and try again.');
      return;
    }

    this.audioCtx = new AudioContext();
    await this.audioCtx.resume();

    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());

    this.showScreen('conversation');
    this.setStatus('connecting', 'Connecting');
    this.drawIdle();

    this.ws = new WebSocket(`ws://${location.host}/ws`);
    this.ws.binaryType = 'arraybuffer';
    this.ws.onopen    = () => this.ws.send(JSON.stringify({ type: 'start' }));
    this.ws.onmessage = (e) => this.onMessage(JSON.parse(e.data));
    this.ws.onerror   = () => this.setStatus('error', 'Connection error');
  }

  // ── Message handler ──────────────────────────────────────────────────────────

  async onMessage(msg) {
    switch (msg.type) {
      case 'question':
        await this.speak(msg.text, msg.audio);
        this.listen();
        break;
      case 'transcribed':
        this.flashHeard(msg.text);
        break;
      case 'no_speech':
        // Don't restart until the flash finishes so the user knows what happened
        setTimeout(() => this.listen(), 400);
        break;
      case 'end':
        // Replace the whole page with the self-contained transcript HTML
        document.open();
        document.write(msg.html);
        document.close();
        break;
    }
  }

  // ── Speaking ─────────────────────────────────────────────────────────────────

  async speak(text, audioB64) {
    this.stopDrawing();
    this.setStatus('speaking', 'Speaking');
    document.getElementById('question').textContent = text;

    const bytes = Uint8Array.from(atob(audioB64), c => c.charCodeAt(0));
    const audioBuf = await this.audioCtx.decodeAudioData(bytes.buffer.slice(0));

    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 256;

    const source = this.audioCtx.createBufferSource();
    source.buffer = audioBuf;
    source.connect(this.analyser);
    this.analyser.connect(this.audioCtx.destination);

    this.drawWave('#3d9bff');

    return new Promise(resolve => {
      source.onended = () => {
        this.stopDrawing();
        resolve();
      };
      source.start();
    });
  }

  // ── Recording & silence detection ────────────────────────────────────────────

  listen() {
    this.setStatus('listening', 'Listening');
    this.setSilenceBar(0);
    this.chunks = [];

    this.analyser = this.audioCtx.createAnalyser();
    this.analyser.fftSize = 256;
    const src = this.audioCtx.createMediaStreamSource(this.stream);
    src.connect(this.analyser);

    this.drawWave('#3dff8f');

    this.recorder = new MediaRecorder(this.stream);
    this.recorder.ondataavailable = (e) => { if (e.data.size > 0) this.chunks.push(e.data); };
    this.recorder.onstop = () => this.sendAudio();
    this.recorder.start();

    this.startSilenceDetection();
  }

  startSilenceDetection() {
    const THRESHOLD   = 12;    // average frequency magnitude (0–255) that counts as speech
    const SPEECH_MIN  = 500;   // ms of sound needed before silence countdown starts
    const SILENCE_MAX = 3000;  // ms of silence to trigger stop

    const data = new Uint8Array(this.analyser.frequencyBinCount);
    let speechStart   = null;
    let speechReady   = false;
    let silenceStart  = null;

    const check = () => {
      this.analyser.getByteFrequencyData(data);
      const avg = data.reduce((a, b) => a + b, 0) / data.length;

      if (avg > THRESHOLD) {
        if (!speechStart) speechStart = Date.now();
        if (!speechReady && Date.now() - speechStart >= SPEECH_MIN) speechReady = true;
        silenceStart = null;
        this.setSilenceBar(0);
      } else if (speechReady) {
        if (!silenceStart) silenceStart = Date.now();
        const elapsed = Date.now() - silenceStart;
        this.setSilenceBar(elapsed / SILENCE_MAX);
        if (elapsed >= SILENCE_MAX) {
          this.stopRecording();
          return;
        }
      }

      this.silenceRaf = requestAnimationFrame(check);
    };

    this.silenceRaf = requestAnimationFrame(check);
  }

  stopRecording() {
    cancelAnimationFrame(this.silenceRaf);
    this.stopDrawing();
    this.setStatus('processing', 'Processing');
    this.setSilenceBar(0);
    this.drawIdle();
    if (this.recorder?.state !== 'inactive') this.recorder.stop();
  }

  // ── Audio → WAV → WebSocket ──────────────────────────────────────────────────

  async sendAudio() {
    const blob = new Blob(this.chunks, { type: 'audio/webm' });
    try {
      const ab  = await blob.arrayBuffer();
      const buf = await this.audioCtx.decodeAudioData(ab);
      this.ws.send(this.encodeWAV(buf));
    } catch {
      // Send an empty WAV header so server knows we had a decode failure
      this.ws.send(new ArrayBuffer(44));
    }
  }

  encodeWAV(audioBuf) {
    const TARGET_RATE = 16000;
    const src   = audioBuf.getChannelData(0); // mono
    const ratio = audioBuf.sampleRate / TARGET_RATE;
    const len   = Math.floor(src.length / ratio);
    const pcm   = new Int16Array(len);

    for (let i = 0; i < len; i++) {
      const s = src[Math.min(Math.floor(i * ratio), src.length - 1)];
      pcm[i] = Math.max(-32768, Math.min(32767, s * 32768));
    }

    const buf = new ArrayBuffer(44 + pcm.length * 2);
    const v   = new DataView(buf);
    const str = (off, s) => [...s].forEach((c, i) => v.setUint8(off + i, c.charCodeAt(0)));

    str(0,  'RIFF'); v.setUint32(4,  36 + pcm.length * 2, true);
    str(8,  'WAVE'); str(12, 'fmt ');
    v.setUint32(16, 16,          true);  // chunk size
    v.setUint16(20, 1,           true);  // PCM
    v.setUint16(22, 1,           true);  // mono
    v.setUint32(24, TARGET_RATE, true);  // sample rate
    v.setUint32(28, TARGET_RATE * 2, true); // byte rate
    v.setUint16(32, 2,           true);  // block align
    v.setUint16(34, 16,          true);  // bits per sample
    str(36, 'data'); v.setUint32(40, pcm.length * 2, true);
    pcm.forEach((s, i) => v.setInt16(44 + i * 2, s, true));

    return buf;
  }

  // ── Waveform drawing ─────────────────────────────────────────────────────────

  drawWave(color) {
    const { canvas, ctx } = this;
    const data = new Uint8Array(this.analyser.frequencyBinCount);

    const frame = () => {
      this.rafId = requestAnimationFrame(frame);
      this.analyser.getByteFrequencyData(data);

      const W = canvas.width, H = canvas.height;
      ctx.clearRect(0, 0, W, H);

      const barW = W / data.length;
      const cy   = H / 2;

      ctx.shadowColor = color;
      ctx.shadowBlur  = 10;

      for (let i = 0; i < data.length; i++) {
        const bh = (data[i] / 255) * cy * 0.92;
        ctx.globalAlpha = 0.45 + (data[i] / 255) * 0.55;
        ctx.fillStyle   = color;
        ctx.fillRect(i * barW, cy - bh, Math.max(barW - 1, 1), bh < 1 ? 1 : bh * 2);
      }
    };

    frame();
  }

  drawIdle() {
    const { canvas, ctx } = this;
    let t = 0;

    const frame = () => {
      this.rafId = requestAnimationFrame(frame);
      const W = canvas.width, H = canvas.height;
      ctx.clearRect(0, 0, W, H);

      ctx.fillStyle   = '#1e1e3a';
      ctx.shadowBlur  = 0;
      ctx.globalAlpha = 1;

      const barW = 5, gap = 3;
      const count = Math.floor(W / (barW + gap));
      const cy = H / 2;

      for (let i = 0; i < count; i++) {
        const bh = Math.abs(Math.sin(i * 0.45 + t)) * 5 + 2;
        ctx.fillRect(i * (barW + gap), cy - bh, barW, bh * 2);
      }

      t += 0.025;
    };

    frame();
  }

  stopDrawing() {
    cancelAnimationFrame(this.rafId);
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
  }

  // ── UI helpers ───────────────────────────────────────────────────────────────

  resizeCanvas() {
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width  = rect.width;
    this.canvas.height = rect.height;
  }

  setStatus(state, label) {
    document.getElementById('status-dot').className  = `dot ${state}`;
    document.getElementById('status-text').textContent = label;
  }

  setSilenceBar(progress) {
    document.getElementById('silence-bar').style.width = `${Math.min(progress * 100, 100)}%`;
  }

  flashHeard(text) {
    const el = document.getElementById('heard');
    el.textContent = `"${text}"`;
    el.classList.add('visible');
    setTimeout(() => el.classList.remove('visible'), 2500);
  }

  showScreen(name) {
    document.querySelectorAll('.screen').forEach(el => {
      el.classList.toggle('active', el.id === name);
    });
  }
}

new App();
