# MagicPin AI Challenge — Vera bot

Deterministic WhatsApp composer for magicpin merchants. It reads the four contexts (category, merchant, trigger, optional customer) and writes a message from facts already in those objects. No API key.

## Run locally

```bash
cd magicpin_bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# sanity check (no server)
python3 -m src.composer

# 30-line submission file
python3 dataset/generate_dataset.py --seed-dir dataset --out dataset/expanded
python3 generate_submission.py

# judge-compatible API on port 8080
uvicorn src.main:app --host 127.0.0.1 --port 8080
```

Endpoints: `GET /v1/healthz`, `GET /v1/metadata`, `POST /v1/context`, `POST /v1/tick`, `POST /v1/reply`, `POST /compose`.

In a second terminal, from this same folder:

```bash
source .venv/bin/activate
python3 judge_simulator.py
```

That checks health, context, auto-reply, a yes, and a stop. For every expanded trigger, set `TEST_SCENARIO = "full_evaluation"` at the top of `judge_simulator.py` and run it again. With no API key the judge scores locally. Paste `LLM_API_KEY` in that file to score with a model.

## Deploy on Vercel

The GitHub repo is [Dhirenderchoudhary/Magicpin](https://github.com/Dhirenderchoudhary/Magicpin). Vercel reads `src/main.py`.

1. Open [vercel.com/new](https://vercel.com/new) and import `Dhirenderchoudhary/Magicpin`.
2. Leave the framework preset as FastAPI. No environment variables.
3. Deploy. Open `https://YOUR-APP.vercel.app/` and `https://YOUR-APP.vercel.app/v1/healthz`.
4. In `judge_simulator.py`, set `BOT_URL` to that host (no path).

The bot does not need an API key. Callers send the context JSON and get the message back.

## Approach

Each `trigger.kind` has its own template. Numbers, dates, offers, and citations are copied from the context. Hindi greeting is used when the merchant (or the customer, on customer-facing sends) prefers Hindi. Auto-replies and "stop" end the thread. "Let's do it" moves straight to the draft.
