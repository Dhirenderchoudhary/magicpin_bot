# Magicpin Vera bot

WhatsApp composer for the magicpin Vera challenge. It reads category, merchant, trigger, and an optional customer, then writes the message from facts already in that JSON. It does not call an LLM to answer, so the deployed app needs no API key.

Live: [https://magicpin-two.vercel.app](https://magicpin-two.vercel.app)

## Layout

```
bot.py                  compose() and the FastAPI app
src/composer.py         one template per trigger kind
src/main.py             judge endpoints
submission.jsonl        30 test messages
dataset/                company seeds; expanded/ is generated and gitignored
judge_simulator.py      local judge
```

## Check the live bot

Open [https://magicpin-two.vercel.app/](https://magicpin-two.vercel.app/) for a short status JSON, or [https://magicpin-two.vercel.app/docs](https://magicpin-two.vercel.app/docs) to send a request from the browser.

`GET /compose` returns 405. Compose is POST only. In Swagger, open `POST /compose`, paste the four context objects, and execute.

```bash
curl -s https://magicpin-two.vercel.app/v1/healthz
curl -s https://magicpin-two.vercel.app/v1/metadata
```

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python3 -m src.composer
uvicorn src.main:app --host 127.0.0.1 --port 8080
```

Then open [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs).

`python3 -m src.composer` checks a few fixed cases (research digest, customer recall, auto-reply, a yes, a stop) and does not start the server.

Docker uses the same app:

```bash
docker build -t magicpin-bot .
docker run --rm -p 8080:8080 magicpin-bot
```

## Endpoints

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/` | Status and links |
| GET | `/v1/healthz` | `status`, uptime, how many contexts are stored |
| GET | `/health` | Same as healthz |
| GET | `/v1/metadata` | Team name, model, version |
| POST | `/v1/context` | Store one category, merchant, customer, or trigger. A lower or equal `version` returns 409 `stale_version`. A bad `scope` returns 400. |
| POST | `/v1/tick` | Compose for `available_triggers` already stored. Cap is 20. A repeated `suppression_key` is skipped. |
| POST | `/v1/reply` | Next turn. Auto-reply or stop returns `action: end`. A clear yes returns the next step. GST is declined and the topic comes back. |
| POST | `/compose` | Same composer, but the body carries `category`, `merchant`, `trigger`, and optional `customer`. Nothing is stored. |

`/compose` returns:

```json
{
  "body": "...",
  "cta": "open_ended",
  "send_as": "vera",
  "suppression_key": "...",
  "rationale": "..."
}
```

Customer messages use `send_as: merchant_on_behalf`. The first tick on a trigger also fills `template_name` (`vera_{kind}_v1`) and `template_params`.

Context lives in memory on the process. A restart clears it. On Vercel a later `/v1/tick` can miss a context pushed to another instance. `/compose` still works, because the request holds the JSON.

## Judge

`judge_simulator.py` talks to `BOT_URL` (currently the live host). From this folder:

```bash
source .venv/bin/activate
python3 judge_simulator.py
```

`TEST_SCENARIO` at the top of that file:

| Value | What runs |
| --- | --- |
| `all` | Health, five categories, five merchants, auto-reply, a yes, a stop |
| `full_evaluation` | Every expanded trigger, then a score per message |
| `warmup`, `phase2_short`, `auto_reply_hell`, `intent_transition`, `hostile` | One slice |

The judge is left on Magicpin's default: `LLM_PROVIDER` is `openai` and `LLM_MODEL` is empty, which means `gpt-4o-mini`. With no OpenAI key it scores structure locally. Do not put an API key on Vercel. The bot never reads one.

## Submission file

Seeds live in `dataset/`. The generator expands them (fixed seed `20260426`):

```bash
python3 dataset/generate_dataset.py --seed-dir dataset --out dataset/expanded
python3 generate_submission.py
```

`generate_submission.py` writes `submission.jsonl` (30 lines). It uses `dataset/expanded` when that folder exists, otherwise the seeds. `dataset/expanded/` is gitignored.

## How a message is chosen

Each `trigger.kind` has its own template. Numbers, dates, offers, and citations are copied from the context. A Hindi greeting is used when the merchant prefers Hindi, or the customer does on a customer send. Dashboard stats stay off customer messages. Auto-replies and "stop" end the thread. A clear yes ("next", "draft", "proceed") goes to the next step and does not ask a new question.
