# MagicPin AI Challenge – Vera Bot

## Overview
This repository implements a deterministic AI‑assistant that composes WhatsApp messages for MagicPin merchants (the **Vera** product) as described in the challenge brief.

- **Core logic** – `src/bot.py` provides a `compose` function that follows the specification in sections 5‑6 of the brief.
- **API** – `src/main.py` runs a FastAPI service exposing a single endpoint `POST /compose` that accepts the four JSON contexts (`category`, `merchant`, `trigger`, `customer?`) and returns the composed message.
- **Submission** – `generate_submission.py` loads the provided dataset, runs the bot on 30 representative test pairs and writes `submission.jsonl`.
- **Optional multi‑turn** – `src/conversation_handlers.py` contains a stub for a multi‑turn responder (extra‑credit feature).
- **Container** – `Dockerfile` builds a lightweight `python:3.11‑slim` image.
- **Deployment** – The container can be deployed to **Google Cloud Run** with a single click; Cloud Run is fully managed, gives you a public HTTPS URL and requires no additional infra.

## How to run locally
```bash
# Clone (already in your workspace) and navigate to the project root
cd "/Users/sudharhodes3/Downloads/magicpin-ai-challenge 2"

# Create a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Export your Gemini API key (you need a Gemini/Google AI account)
export GOOGLE_AI_API_KEY="YOUR_API_KEY"

# Run the API (development server)
uvicorn src.main:app --reload --port 8000
```
The service will be reachable at `http://127.0.0.1:8000/compose`.

## Deploy to Google Cloud Run
1. Install the Google Cloud SDK and initialise it (`gcloud init`).
2. Build and push the container:
   ```bash
   gcloud builds submit --tag gcr.io/$(gcloud config get-value project)/magicpin-vera-bot
   ```
3. Deploy:
   ```bash
   gcloud run deploy magicpin-vera-bot \
     --image gcr.io/$(gcloud config get-value project)/magicpin-vera-bot \
     --platform managed \
     --allow-unauthenticated \
     --region us-central1
   ```
   The command will output a public URL (e.g., `https://magicpin-vera-bot-xxxxx.run.app`).

## Project structure
```
magicpin-ai-challenge 2/
│   README.md               # you are reading it
│   requirements.txt        # python deps
│   Dockerfile              # container definition
│   generate_submission.py  # creates submission.jsonl
│
├── src/
│   ├── __init__.py
│   ├── bot.py              # core compose() implementation
│   ├── main.py             # FastAPI server
│   ├── conversation_handlers.py  # optional multi‑turn support
│   └── models.py           # Pydantic schemas for the contexts
│
└── dataset/                # provided dataset (unchanged)
```

## License
CC0 – public domain (the challenge data is synthetic).

---
*Feel free to open an issue or pull‑request if you spot bugs or want to extend functionality.*
