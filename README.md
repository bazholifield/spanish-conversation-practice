# Spanish Conversation Practice

I built this while living in Spain to help me practice speaking. It holds a simple conversation with you where it asks a question, listens to your answer, and asks a follow-up question, without using an LLM. When you're done, it saves a transcript you can click through word by word to see what you actually said.

## How it works

The dialogue manager reads scenario trees from `data/scenarios/`, matches keywords in your reply against the triggers in each tree, and picks a follow-up from whatever fires. If nothing matches it reaches for a generic probe instead, and after three of those in a row it ends the session.

Underneath, spaCy (`es_core_news_sm`) lemmatizes and tags every utterance, so "comí" and "comer" both hit the same trigger. Speech goes out to Google's recognizer, and Edge TTS reads the prompts back. The transcript viewer builds a standalone HTML file, translating each unique word once and conjugating anything that looks like an infinitive.

## Running it

```bash
pip install -r requirements.txt
python -m spacy download es_core_news_sm
```

Two ways in:

```bash
python main.py     # terminal
python server.py   # browser, voice only, localhost:8000
```

The terminal version asks which scenario you want, or `0` to just talk. It defaults to typing; set `INPUT_MODE = "speech"` in `config/settings.py` to use the mic instead. Say or type `salir` to stop. Transcripts land in `transcripts/`.

Speech and translation both need a network connection. Typing works offline, apart from the vocabulary lookups the transcript does at the end.

## Scenarios

Six of them: a bar, a restaurant, shopping, asking directions, meeting someone, and the doctor. They're plain JSON, so a new one can be added by dropping a file into `data/scenarios/` with the same format. Both front ends find it on their own and sort by the `order` field.

## What it doesn't do

It only speaks Spanish, and the spaCy model and every scenario tree are Spanish-specific, so another language means another pipeline and a full retranslation.

It has no memory between sessions, and it won't correct you, just keep the conversation going.
