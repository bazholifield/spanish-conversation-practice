# Spanish Conversation Practice Tool

While living in Spain, I built this to reduce the anxiety of speaking Spanish in real life. It simulates short conversations by asking questions, listening to your answers, and following up without using an LLM. At the end of each session it saves an interactive transcript where you can click any word to see its definition and conjugation table.

## How it works

1. **Dialogue manager** — a rule-based engine loads scenario question trees from JSON (`data/scenarios/`). It selects follow-up questions based on pattern matching against your response, keeping the conversation on-topic without needing a language model.
2. **NLP pipeline** — [spaCy](https://spacy.io/) (`es_core_news_sm`) handles morphological analysis: lemmatization, POS tagging, and dependency parsing on every Spanish utterance.
3. **Voice input** — `src/speech/stt.py` wraps the Google Speech Recognition API to transcribe microphone input. Text mode is also available for offline use.
4. **TTS output** — `src/speech/tts.py` uses Edge TTS to speak the tool's prompts aloud.
5. **Interactive transcript** — `ui/transcript_viewer.py` generates a self-contained HTML file. The frontend (`static/`) adds a click-to-lookup UI: clicking a word fires a vocabulary lookup and displays the definition and conjugation inline.

## Tech stack

Python · spaCy · Google Speech API · Edge TTS · HTML/CSS/JS frontend

## Setup

```bash
pip install -r requirements.txt
python -m spacy download es_core_news_sm
```

## Usage

```bash
python main.py
```

By default the tool runs in text mode (type your answers). To use your microphone, set `INPUT_MODE = "speech"` in `config/settings.py`. An internet connection is required for speech recognition and TTS.

Type or say `salir` to end the session. The transcript is saved to `transcripts/` — open it in a browser to review vocabulary.

## Scenarios

Pre-built conversation trees are in `data/scenarios/`: bar, restaurant, shopping, directions, meeting people, and medical. New scenarios can be added by dropping a JSON file into that directory following the same schema.

## Limitations

- **Rule-based by design** — the dialogue manager was built deliberately rather than delegating conversation logic to an API, which meant writing the NLP pipeline from scratch. The tradeoff is that responses outside the expected pattern can break the conversational flow.
- **Internet required for speech** — Google Speech Recognition and Edge TTS both need a network connection. Text mode works offline.
- **Spanish only** — the spaCy model and scenario trees are Spanish-specific; adapting to another language requires a new spaCy pipeline and translated scenario files.
- **No memory across sessions** — each session starts fresh; the tool doesn't track vocabulary you've struggled with over time.
