import html
import json
import re
from datetime import datetime

from config.settings import Settings
from src.session.transcript import Transcript
from src.vocabulary.lookup import VocabularyLookup
from src.vocabulary.conjugator import SpanishConjugator


class TranscriptViewer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lookup = VocabularyLookup(settings)
        self.conjugator = SpanishConjugator()

    def to_html(self, transcript: Transcript) -> str:
        unique_words = transcript.unique_spanish_words()
        vocab = self.lookup.lookup_batch(list(unique_words))

        for word, data in vocab.items():
            if self.conjugator.looks_like_infinitive(word):
                conj = self.conjugator.conjugate(word)
                if conj:
                    data["conjugation"] = conj

        return self._render(transcript, vocab)

    def generate(self, transcript: Transcript) -> str:
        self.settings.TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
        html = self.to_html(transcript)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = self.settings.TRANSCRIPT_DIR / f"transcript_{timestamp}.html"
        out.write_text(html, encoding="utf-8")
        return str(out)

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------

    def _annotate(self, text: str, speaker: str) -> str:
        """Wrap each word token in a real <button> so it is keyboard-reachable."""
        parts = re.split(r"(\s+)", text)
        result = []
        for part in parts:
            if part.strip():
                clean = re.sub(r"[^a-záéíóúüñ]", "", part.lower())
                punct_before = re.match(r"^([¿¡])", part)
                punct_after = re.search(r"([.,!?;:]+)$", part)
                prefix = punct_before.group(1) if punct_before else ""
                suffix = punct_after.group(1) if punct_after else ""
                inner = part[len(prefix):len(part) - len(suffix)]

                if clean:
                    span = (
                        f'{prefix}<button type="button" class="word {speaker}-word" '
                        f'data-word="{clean}">{html.escape(inner)}</button>{suffix}'
                    )
                    result.append(span)
                else:
                    result.append(html.escape(part))
            else:
                result.append(part)
        return "".join(result)

    def _turns_html(self, transcript: Transcript) -> str:
        html = ""
        for turn in transcript.turns:
            bot = self._annotate(turn.question, "bot")
            user = self._annotate(turn.response, "user")
            html += f"""
      <div class="turn">
        <div class="bubble bot-bubble">
          <span class="label">Tutor</span>
          <p lang="es">{bot}</p>
        </div>
        <div class="bubble user-bubble">
          <span class="label">You</span>
          <p lang="es">{user}</p>
        </div>
      </div>"""
        return html

    def _render(self, transcript: Transcript, vocab: dict) -> str:
        turns_html = self._turns_html(transcript)
        # Escape "<" so a translation containing "</script>" can't break out of the tag.
        vocab_json = json.dumps(vocab, ensure_ascii=False).replace("<", "\\u003c")
        mins, secs = divmod(transcript.duration_seconds(), 60)
        date_str = transcript.started_at.strftime("%B %d, %Y %H:%M") if transcript.started_at else ""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Spanish Practice Transcript</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #1a1a2e;
    color: #e0e0e0;
    display: flex;
    min-height: 100vh;
  }}

  .sr-only {{
    position: absolute; width: 1px; height: 1px;
    padding: 0; margin: -1px; overflow: hidden;
    clip-path: inset(50%); white-space: nowrap; border: 0;
  }}

  /* ── Layout ── */
  #main {{ flex: 1; max-width: 760px; margin: 0 auto; padding: 2rem 1.5rem 6rem; }}
  /* visibility, not just transform, so the closed panel leaves the
     accessibility tree and the tab order instead of lurking off-screen. */
  #panel {{
    position: fixed; right: 0; top: 0; bottom: 0;
    width: 340px; background: #16213e; border-left: 1px solid #0f3460;
    padding: 1.5rem; overflow-y: auto;
    transform: translateX(100%); visibility: hidden;
    transition: transform 0.25s ease, visibility 0s linear 0.25s;
  }}
  #panel.open {{
    transform: translateX(0); visibility: visible;
    transition: transform 0.25s ease, visibility 0s;
  }}
  #panel:focus {{ outline: none; }}
  #main.panel-open {{ margin-right: 340px; }}

  /* One consistent, high-contrast focus ring. */
  :focus-visible {{ outline: 3px solid #7fb4ff; outline-offset: 2px; border-radius: 3px; }}

  /* ── Header ── */
  header {{ margin-bottom: 2rem; }}
  header h1 {{ font-size: 1.5rem; color: #e94560; margin-bottom: 0.25rem; }}
  .meta {{ color: #a8a8c0; font-size: 0.85rem; }}
  .hint {{ font-size: 0.85rem; color: #a8a8c0; margin-top: 0.5rem; font-style: italic; }}

  /* ── Turns & Bubbles ── */
  .turn {{ margin-bottom: 1.5rem; }}
  .bubble {{ padding: 0.75rem 1rem; border-radius: 12px; margin-bottom: 0.5rem; max-width: 92%; line-height: 1.6; }}
  .bot-bubble {{ background: #0f3460; border-bottom-left-radius: 2px; }}
  .user-bubble {{ background: #2d2d44; margin-left: auto; border-bottom-right-radius: 2px; }}
  .label {{ display: block; font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 0.35rem; }}
  .bot-bubble .label {{ color: #9ad4ff; }}
  .user-bubble .label {{ color: #b5e0b7; }}

  /* ── Clickable words ──
     Real <button> elements, reset to read as inline text. */
  .word {{
    cursor: pointer; border-radius: 3px;
    transition: background 0.15s;
    padding: 0 1px;
    background: none; border: none;
    font: inherit; color: inherit;
    line-height: inherit;
  }}
  .word:hover {{ background: rgba(233, 69, 96, 0.35); }}
  .word.active {{ background: rgba(233, 69, 96, 0.55); }}

  /* ── Side panel ── */
  #panel h2 {{ font-size: 1.4rem; color: #e94560; margin-bottom: 0.25rem; }}
  #panel .translation {{ font-size: 1rem; color: #a5d6a7; margin-bottom: 1rem; }}
  #panel .close-btn {{
    position: absolute; top: 1rem; right: 1rem;
    background: none; border: none; color: #888;
    font-size: 1.3rem; cursor: pointer;
  }}
  #panel .close-btn:hover {{ color: #e94560; }}
  .section-title {{ font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #a8a8c0; margin: 1.2rem 0 0.5rem; }}
  table.conj {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
  table.conj th {{ text-align: left; color: #6ec6ff; font-weight: 600; padding: 0.25rem 0.5rem; border-bottom: 1px solid #0f3460; }}
  table.conj td {{ padding: 0.25rem 0.5rem; color: #ccc; }}
  table.conj tr:nth-child(even) td {{ background: rgba(255,255,255,0.03); }}
  .no-data {{ color: #a8a8c0; font-style: italic; font-size: 0.85rem; }}

  @media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
      animation-duration: 0.001ms !important;
      transition-duration: 0.001ms !important;
    }}
    #panel {{ transition: none; }}
  }}
</style>
</head>
<body>
<div id="main">
  <header>
    <h1>Spanish Practice Transcript</h1>
    <div class="meta">{date_str} &nbsp;·&nbsp; {len(transcript.turns)} turns &nbsp;·&nbsp; {mins}m {secs}s</div>
    <div class="hint">Select any word (click, or Tab then Enter) to see its translation and conjugation. Escape closes the panel.</div>
  </header>
  {turns_html}
</div>

<aside id="panel" role="region" aria-label="Word details" tabindex="-1">
  <button class="close-btn" type="button" aria-label="Close word details">✕</button>
  <div id="panel-body"></div>
</aside>

<script>
const vocab = {vocab_json};

// Remembered so Escape can hand focus back to the word you came from.
let lastTrigger = null;

function showWord(word, trigger) {{
  const data = vocab[word] || {{}};
  lastTrigger = trigger || null;

  // highlight every instance of the selected word
  document.querySelectorAll('.word.active').forEach(el => el.classList.remove('active'));
  document.querySelectorAll(`[data-word="${{word}}"]`).forEach(el => el.classList.add('active'));

  const translation = data.translation
    ? `<div class="translation" lang="en">${{data.translation}}</div>`
    : `<div class="translation"><span class="no-data">no translation found</span></div>`;
  let html = `<h2 lang="es">${{word}}</h2>${{translation}}`;

  if (data.conjugation && Object.keys(data.conjugation).length > 0) {{
    html += `<div class="section-title">Conjugation</div>`;
    for (const [tense, forms] of Object.entries(data.conjugation)) {{
      html += `<div class="section-title" style="margin-top:0.8rem;color:#e0e0e0">${{tense}}</div>`;
      html += `<table class="conj"><caption class="sr-only">${{tense}} of ${{word}}</caption><tbody>`;
      for (const [pronoun, form] of Object.entries(forms)) {{
        html += `<tr><th scope="row" style="color:#6ec6ff;width:45%;font-weight:400" lang="es">${{pronoun}}</th><td lang="es">${{form}}</td></tr>`;
      }}
      html += `</tbody></table>`;
    }}
  }}

  document.getElementById('panel-body').innerHTML = html;
  document.getElementById('panel').classList.add('open');
  document.getElementById('main').classList.add('panel-open');
  // Move focus in, so the panel is read out and its close button is reachable.
  document.getElementById('panel').focus();
}}

function closePanel() {{
  document.getElementById('panel').classList.remove('open');
  document.getElementById('main').classList.remove('panel-open');
  document.querySelectorAll('.word.active').forEach(el => el.classList.remove('active'));
  if (lastTrigger) {{ lastTrigger.focus(); lastTrigger = null; }}
}}

// Delegated, so no inline handlers and every word works via mouse or keyboard.
document.addEventListener('click', e => {{
  const word = e.target.closest('.word');
  if (word) {{ showWord(word.dataset.word, word); return; }}
  if (e.target.closest('.close-btn')) closePanel();
}});

document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closePanel(); }});
</script>
</body>
</html>"""
