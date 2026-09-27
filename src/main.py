"""HTTP surface the magicpin judge calls, plus POST /compose for local checks."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from .composer import compose, respond

app = FastAPI(title="MagicPin Vera Bot", version="1.0.0")
START = time.time()

# (scope, context_id) -> {version, payload}
_contexts: dict[tuple[str, str], dict] = {}
_sent: set[str] = set()
_conversations: dict[str, dict] = {}
_ended: set[str] = set()

_SCOPES = {"category", "merchant", "customer", "trigger"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _counts() -> dict[str, int]:
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    for scope, _cid in _contexts:
        if scope in counts:
            counts[scope] += 1
    return counts


def _get(scope: str, context_id: Optional[str]) -> Optional[dict]:
    if not context_id:
        return None
    row = _contexts.get((scope, context_id))
    return row["payload"] if row else None


class ContextIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scope: str
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: Optional[str] = None


class TickIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    now: Optional[str] = None
    available_triggers: list[str] = []


class ReplyIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str = "merchant"
    message: str = ""
    received_at: Optional[str] = None
    turn_number: int = 1


class ComposeIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    category: dict[str, Any]
    merchant: dict[str, Any]
    trigger: dict[str, Any]
    customer: Optional[dict[str, Any]] = None


@app.get("/v1/healthz")
def healthz():
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START),
        "contexts_loaded": _counts(),
    }


@app.get("/health")
def health():
    return healthz()


@app.get("/v1/metadata")
def metadata():
    return {
        "team_name": "magicpin_bot",
        "team_members": ["kaiser"],
        "model": "deterministic-composer",
        "approach": "trigger dispatch over category, merchant, trigger, and customer; no invented facts",
        "contact_email": "local@localhost",
        "version": "1.0.0",
        "submitted_at": "2026-09-27T00:00:00Z",
    }


@app.post("/v1/context")
def push_context(body: ContextIn):
    if body.scope not in _SCOPES:
        return JSONResponse(
            status_code=400,
            content={"accepted": False, "reason": "invalid_scope", "details": body.scope},
        )
    key = (body.scope, body.context_id)
    current = _contexts.get(key)
    if current and current["version"] >= body.version:
        return JSONResponse(
            status_code=409,
            content={
                "accepted": False,
                "reason": "stale_version",
                "current_version": current["version"],
            },
        )
    _contexts[key] = {"version": body.version, "payload": body.payload}
    return {
        "accepted": True,
        "ack_id": f"ack_{body.context_id}_v{body.version}",
        "stored_at": _now(),
    }


def _action(trigger_id: str, trigger: dict, message: dict, merchant_id: str) -> dict:
    conv = f"conv_{merchant_id}_{trigger_id}"
    customer_id = trigger.get("customer_id")
    _conversations[conv] = {
        "merchant_id": merchant_id,
        "customer_id": customer_id,
        "trigger_id": trigger_id,
        "topic": (trigger.get("kind") or "update").replace("_", " "),
        "last_body": message["body"],
    }
    kind = trigger.get("kind") or "update"
    return {
        "conversation_id": conv,
        "merchant_id": merchant_id,
        "customer_id": customer_id,
        "send_as": message["send_as"],
        "trigger_id": trigger_id,
        "template_name": f"vera_{kind}_v1",
        "template_params": [message["body"][:180], message["cta"], message["suppression_key"]],
        "body": message["body"],
        "cta": message["cta"],
        "suppression_key": message["suppression_key"],
        "rationale": message["rationale"],
    }


@app.post("/v1/tick")
def tick(body: TickIn):
    actions = []
    for trigger_id in body.available_triggers:
        if len(actions) >= 20:
            break
        trigger = _get("trigger", trigger_id)
        if not trigger:
            continue
        suppression = trigger.get("suppression_key") or trigger_id
        if suppression in _sent:
            continue
        merchant_id = trigger.get("merchant_id")
        merchant = _get("merchant", merchant_id)
        if not merchant:
            continue
        category = _get("category", merchant.get("category_slug"))
        if not category:
            continue
        customer = _get("customer", trigger.get("customer_id"))
        message = compose(category, merchant, trigger, customer)
        actions.append(_action(trigger_id, trigger, message, merchant_id))
        _sent.add(suppression)
    return {"actions": actions}


@app.post("/v1/reply")
def reply(body: ReplyIn):
    if body.conversation_id in _ended:
        return {
            "action": "end",
            "rationale": "This conversation is already closed.",
        }
    state = _conversations.setdefault(
        body.conversation_id,
        {"merchant_id": body.merchant_id, "topic": "the open item", "turns": []},
    )
    state.setdefault("turns", []).append({"from": body.from_role, "message": body.message})
    result = respond(body.message, state)
    if result.get("action") == "end":
        _ended.add(body.conversation_id)
    elif result.get("body"):
        state["last_body"] = result["body"]
    return result


@app.post("/compose")
def compose_endpoint(body: ComposeIn):
    return compose(body.category, body.merchant, body.trigger, body.customer)
