const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

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

    document.getElementById('start-btn').addEventListener('click', () => this.init(null));
    document.getElementById('end-btn').addEventListener('click', () => this.endSession());

    this.loadScenarios();
  }

  // ── Setup ────────────────────────────────────────────────────────────────────

  async loadScenarios() {
    const scenarios = await fetch('/api/scenarios').then(r => r.json()).catch(() => []);
    const grid = document.getElementById('scenario-grid');
    scenarios.forEach(s => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'scenario-card';
      btn.dataset.id = s.id;

      // The emoji is decoration; the name alone is the accessible label.
      const icon = document.createElement('span');
      icon.className = 'scenario-icon';
      icon.setAttribute('aria-hidden', 'true');
      icon.textContent = s.icon;

      const name = document.createElement('span');
      name.className = 'scenario-name';
      name.textContent = s.name;

      btn.append(icon, name);
      btn.addEventListener('click', () => this.init(s.id));
      grid.appendChild(btn);
    });
  }

  showError(message) {
    const box = document.getElementById('mic-error');
    box.textContent = message;
    box.hidden = false;
  }

  clearError() {
    const box = document.getElementById('mic-error');
    box.hidden = true;
    box.textContent = '';
  }

  async init(scenarioId) {
    this.clearError();
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    } catch {
      // Announced via role="alert", and focus stays on the button they pressed.
      this.showError('Necesito acceso al micrófono. Permítelo en tu navegador e inténtalo de nuevo.');
      return;
    }

    this.audioCtx = new AudioContext();
    await this.audioCtx.resume();
    this.resizeCanvas();
    window.addEventListener('resize', () => this.resizeCanvas());

    document.getElementById('scenario-label').textContent = scenarioId
      ? document.querySelector(`[data-id="${scenarioId}"] .scenario-name`)?.textContent || ''
      : '';

    this.showScreen('conversation');
    this.setStatus('connecting', 'Connecting');
    this.drawIdle();

    this.ws = new WebSocket(`ws://${location.host}/ws`);
    this.ws.binaryType = 'arraybuffer';
    this.ws.onopen    = () => this.ws.send(JSON.stringify({ type: 'start', scenario: scenarioId }));
    this.ws.onmessage = (e) => this.onMessage(JSON.parse(e.data));
    this.ws.onerror   = () => this.setStatus('error', 'Connection error');
  }

  // ── Message handler ──────────────────────────────────────────────────────────

  async onMessage(msg) {
    switch (msg.type) {
      case 'question':
        // Show it as well as speak it: needed if you can't hear the audio,
        // and the only way to tell the app is still following you.
        this.setQuestion(msg.text);
        this.setHeard('');
        await this.speak(msg.audio);
        this.listen();
        break;
      case 'transcribed':
        this.setHeard(`“${msg.text}”`);
        break;
      case 'no_speech':
        this.setHeard('No te he oído bien. Inténtalo otra vez.');
        setTimeout(() => this.listen(), 400);
        break;
      case 'end':
        document.open();
        document.write(msg.html);
        document.close();
        break;
    }
  }

  // ── End button ───────────────────────────────────────────────────────────────

  endSession() {
    cancelAnimationFrame(this.silenceRaf);
    this.stopDrawing();
    if (this.recorder?.state !== 'inactive') {
      this.recorder.onstop = null; // prevent sendAudio from firing
      this.recorder.stop();
    }
    this.setStatus('processing', 'Ending');
    this.drawIdle();
    this.ws?.send(JSON.stringify({ type: 'end_session' }));
  }

  // ── Speaking ─────────────────────────────────────────────────────────────────

  async speak(audioB64) {
    this.stopDrawing();
    this.setStatus('speaking', 'Speaking');

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
      source.onended = () => { this.stopDrawing(); resolve(); };
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
    const SPEECH_MIN    = 500;
    const SILENCE_MAX   = 2000;
    const CALIBRATE_MS  = 350;   // listen to the room before judging
    const MARGIN        = 10;    // how far above the room floor counts as speech
    const MIN_THRESHOLD = 8;     // floor, for very quiet rooms

    const data = new Uint8Array(this.analyser.frequencyBinCount);

    // Speech lives roughly between 85 Hz and 3.4 kHz. Averaging the whole
    // spectrum buries it under ~110 near-empty high-frequency bins, so only
    // measure the bins that can actually contain a voice.
    const hzPerBin = (this.audioCtx.sampleRate / 2) / data.length;
    const lo = Math.max(1, Math.floor(85 / hzPerBin));
    const hi = Math.min(data.length - 1, Math.ceil(3400 / hzPerBin));

    const speechLevel = () => {
      this.analyser.getByteFrequencyData(data);
      let sum = 0;
      for (let i = lo; i <= hi; i++) sum += data[i];
      return sum / (hi - lo + 1);
    };

    const startedAt = Date.now();
    let floorSum = 0, floorCount = 0, threshold = null;
    let speechStart  = null;
    let speechReady  = false;
    let silenceStart = null;

    const check = () => {
      const avg = speechLevel();

      // Measure this room and this mic before deciding what counts as speech,
      // instead of trusting one hardcoded number for every setup.
      if (threshold === null) {
        floorSum += avg;
        floorCount++;
        if (Date.now() - startedAt >= CALIBRATE_MS) {
          threshold = Math.max(floorSum / floorCount + MARGIN, MIN_THRESHOLD);
        }
        this.silenceRaf = requestAnimationFrame(check);
        return;
      }

      if (avg > threshold) {
        if (!speechStart) speechStart = Date.now();
        if (!speechReady && Date.now() - speechStart >= SPEECH_MIN) speechReady = true;
        silenceStart = null;
        this.setSilenceBar(0);
      } else if (speechReady) {
        if (!silenceStart) silenceStart = Date.now();
        const elapsed = Date.now() - silenceStart;
        this.setSilenceBar(elapsed / SILENCE_MAX);
        if (elapsed >= SILENCE_MAX) { this.stopRecording(); return; }
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
      this.ws.send(new ArrayBuffer(44));
    }
  }

  encodeWAV(audioBuf) {
    const TARGET_RATE = 16000;
    const src   = audioBuf.getChannelData(0);
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
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, TARGET_RATE, true); v.setUint32(28, TARGET_RATE * 2, true);
    v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    str(36, 'data'); v.setUint32(40, pcm.length * 2, true);
    pcm.forEach((s, i) => v.setInt16(44 + i * 2, s, true));

    return buf;
  }

  // ── Waveform ─────────────────────────────────────────────────────────────────

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
      // The idle shimmer is pure decoration, so it stops entirely when the
      // viewer has asked for reduced motion. The live waveform stays, since
      // that one is feedback about whether the mic is hearing you.
      if (!REDUCED_MOTION) this.rafId = requestAnimationFrame(frame);
      const W = canvas.width, H = canvas.height;
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle  = '#1e1e3a';
      ctx.shadowBlur = 0;
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
    document.getElementById('status-dot').className   = `dot ${state}`;
    document.getElementById('status-text').textContent = label;
  }

  setQuestion(text) {
    document.getElementById('question-text').textContent = text || '';
  }

  setHeard(text) {
    document.getElementById('heard-text').textContent = text || '';
  }

  setSilenceBar(progress) {
    const pct = Math.min(Math.round(progress * 100), 100);
    document.getElementById('silence-bar').style.width = `${pct}%`;
    document.getElementById('silence-track').setAttribute('aria-valuenow', pct);
  }

  showScreen(name) {
    document.querySelectorAll('.screen').forEach(el => {
      el.classList.toggle('active', el.id === name);
    });
    // Move focus into the screen we just revealed, so keyboard and screen
    // reader users follow the transition instead of being stranded behind it.
    document.getElementById(name)?.focus();
  }
}

new App();
