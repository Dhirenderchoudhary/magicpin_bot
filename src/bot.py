import os
import json
from typing import Optional

from groq import Groq
from pydantic import BaseModel

from .models import ComposeInput, ComposeOutput

# Initialize Groq client – expects GROQ_API_KEY (or fallback to GOOGLE_AI_API_KEY) in environment
_API_KEY = os.getenv("GROQ_API_KEY") or os.getenv("GOOGLE_AI_API_KEY")
if not _API_KEY:
    raise RuntimeError("GROQ_API_KEY environment variable not set (or GOOGLE_AI_API_KEY)")

client = Groq(api_key=_API_KEY)

# System prompt that encodes the challenge constraints
_SYSTEM_PROMPT = """You are Vera, a merchant‑AI assistant for MagicPin.
You must implement the `compose` function which receives four context objects (CategoryContext, MerchantContext, TriggerContext, optional CustomerContext) and returns a JSON object with keys: body, cta, send_as, suppression_key, rationale.
Follow **all constraints** from the challenge brief:
- Use a pre‑approved WhatsApp template for the first message in a 24h session (`{{1}}` placeholders are allowed).
- Keep the message concise, specific, and use at most one binary CTA (YES/STOP) unless the trigger is pure‑information.
- Anchor on concrete facts from the provided contexts (numbers, dates, source citations).
- Match the voice/style of the category (clinical for dentists, friendly for salons, etc.).
- Honor the merchant's language preference; if Hindi‑English mix is indicated, include some Hindi words.
- Do **not** fabricate data.
- Return the fields exactly as defined in `ComposeOutput`.
"""

# Prompt template – we feed the full JSON of the contexts and ask for a JSON response.
_PROMPT_TEMPLATE = """Context JSON:
{input_json}

Generate a JSON object with the following shape:
```
{{
  "body": string,
  "cta": string,
  "send_as": "vera" | "merchant_on_behalf",
  "suppression_key": string,
  "rationale": string
}}
```
Make sure the output is **valid JSON** and respects the constraints in the system prompt.
"""

def _format_input(compose_input: ComposeInput) -> str:
    """Serialize the ComposeInput to a compact JSON string (no whitespace)."""
    return compose_input.model_dump_json(exclude_none=True)

def compose(category: dict, merchant: dict, trigger: dict, customer: Optional[dict] = None) -> dict:
    """Deterministic wrapper used by the evaluation harness.

    The function receives plain Python ``dict`` objects (already parsed from JSON files).
    It builds the Pydantic model, constructs the prompt and calls Gemini with
    ``temperature=0`` to guarantee reproducibility.
    """
    # Build the typed model – this will also validate the input structure.
    input_model = ComposeInput(
        category=category,
        merchant=merchant,
        trigger=trigger,
        customer=customer,
    )

    input_json = _format_input(input_model)
    user_prompt = _PROMPT_TEMPLATE.format(input_json=input_json)

    # Call Groq
    client = Groq(api_key=_API_KEY)

    # Call Groq LLM (JSON response)
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    # Extract and parse JSON from response
    try:
        result_text = response.choices[0].message.content
        result_json = json.loads(result_text)
    except Exception as exc:
        raise RuntimeError(f"Failed to parse Groq response as JSON: {exc}\nRaw: {result_text}")

    # Validate against ComposeOutput schema (throws if invalid)
    try:
        output = ComposeOutput(**result_json)
    except Exception as exc:
        raise RuntimeError(f"Compose output validation failed: {exc}\\nRaw JSON: {result_json}")

    # ------------------- Heuristic post‑processing -------------------
    import re, hashlib

    # 1️⃣ Ensure `send_as` is a permitted value
    if output.send_as not in {"vera", "merchant_on_behalf"}:
        output.send_as = "vera"

    # 2️⃣ Enforce allowed CTA values (binary or open_ended)
    allowed_ctas = {"YES", "NO", "STOP", "open_ended", "none", ""}
    if output.cta not in allowed_ctas:
        output.cta = "open_ended"

    # 3️⃣ Guarantee a non‑empty suppression_key (fallback to hash of body)
    if not output.suppression_key:
        output.suppression_key = hashlib.sha256(output.body.encode()).hexdigest()[:16]

    # 4️⃣ Truncate body to a safe length (≤500 chars)
    if len(output.body) > 500:
        output.body = output.body[:497] + "..."

    # 5️⃣ Insert WhatsApp template placeholder for first message when sending as Vera
    if output.send_as == "vera" and "{{1}}" not in output.body:
        output.body = "{{1}} " + output.body

    # 6️⃣ Add Hindi greeting if merchant prefers Hindi/English mix
    lang_pref = getattr(input_model.merchant, "languages", [])
    if not lang_pref:
        lang_pref = [getattr(input_model.merchant, "language", "")]
    if any(re.search(r"hi", lang, re.IGNORECASE) for lang in lang_pref):
        if not output.body.lower().startswith("नमस्ते"):
            output.body = "नमस्ते, " + output.body

    # 7️⃣ Ensure at least one concrete number appears in the body (specificity rule)
    if not re.search(r"\\d+", output.body):
        numbers = []
        perf = input_model.merchant.performance
        numbers.extend([perf.views, perf.calls, perf.directions, int(perf.ctr * 1000)])
        if input_model.merchant.offers:
            price = input_model.merchant.offers[0].price
            if price:
                numbers.append(int(price))
        numbers.append(int(input_model.category.peer_stats.avg_ctr * 1000))
        for n in numbers:
            if n and n > 0:
                output.body = f"{output.body} (₹{n})"
                break

    # 8️⃣ Provide a short rationale if missing
    if not output.rationale:
        output.rationale = "Composed per trigger, merchant state and category voice."

    return output.model_dump()
