"""Deterministic Vera composer.

Uses only facts present in the four context dicts. No network, no API key.
"""

from __future__ import annotations

import re
from typing import Any, Optional


def compose(
    category: dict,
    merchant: dict,
    trigger: dict,
    customer: Optional[dict] = None,
) -> dict:
    category = category or {}
    merchant = merchant or {}
    trigger = trigger or {}
    payload = trigger.get("payload") or {}
    kind = trigger.get("kind") or "update"
    customer_scope = trigger.get("scope") == "customer" or bool(trigger.get("customer_id"))
    send_as = "merchant_on_behalf" if customer_scope else "vera"
    who = greet(category, merchant)
    hi = wants_hindi(merchant, customer, customer_scope)
    opener = f"Namaste {who}" if hi else who

    handler = _HANDLERS.get(kind, _generic)
    body, cta, why = handler(opener, category, merchant, trigger, payload, customer)
    body = scrub(body, category)
    # Merchant-facing only. Customer texts must not carry dashboard stats.
    if send_as == "vera" and not re.search(r"\d", body):
        perf = merchant.get("performance") or {}
        if perf.get("views") is not None:
            window = perf.get("window_days") or 30
            body = f"{body} Last {window}d views: {perf['views']}."

    return {
        "body": body.strip(),
        "cta": cta,
        "send_as": send_as,
        "suppression_key": trigger.get("suppression_key") or trigger.get("id") or kind,
        "rationale": why,
    }


def respond(message: str, state: Optional[dict] = None) -> dict:
    """Multi-turn reply. Detects auto-replies, opt-outs, and explicit yes."""
    state = state or {}
    text = (message or "").strip()
    low = text.lower()
    topic = state.get("topic") or "the open item"

    if _is_auto(low):
        return {
            "action": "end",
            "rationale": "Canned WhatsApp auto-reply. Ending so we do not burn extra turns.",
        }
    if _is_stop(low):
        return {
            "action": "end",
            "rationale": "Merchant asked to stop. Closing this conversation.",
        }
    if _is_off_topic(low):
        return {
            "action": "send",
            "body": (
                f"That one sits outside what I can do from here — your CA handles GST. "
                f"Back to {topic}: the draft is ready. Reply YES and I proceed."
            ),
            "cta": "YES",
            "rationale": "Off-topic ask declined, then returned to the open trigger.",
        }
    if _is_commit(low):
        return {
            "action": "send",
            "body": (
                f"Next step on {topic}: draft is ready. "
                f"I will proceed and send it for a confirm. Reply YES."
            ),
            "cta": "YES",
            "rationale": "Explicit commit. Switched from pitch to the next concrete action.",
        }
    return {
        "action": "send",
        "body": (
            f"Got it. Next on {topic}: I will draft it from the numbers already on your account "
            f"and send it for a confirm. Reply YES."
        ),
        "cta": "YES",
        "rationale": "Merchant replied in their own words. Advancing to a single confirm.",
    }


def _is_auto(low: str) -> bool:
    needles = (
        "thank you for contacting",
        "thanks for contacting",
        "our team will respond",
        "we will get back",
        "we'll get back",
        "automated assistant",
        "automated message",
        "this is an automated",
        "auto-reply",
        "auto reply",
        "aapki jaankari",
        "bahut-bahut shukriya",
        "bahut bahut shukriya",
    )
    return any(n in low for n in needles)


def _is_stop(low: str) -> bool:
    needles = (
        "stop messaging",
        "stop message",
        "not interested",
        "don't message",
        "do not message",
        "dont message",
        "unsubscribe",
        "leave me alone",
        "useless spam",
        "this is spam",
    )
    return any(n in low for n in needles)


def _is_commit(low: str) -> bool:
    needles = (
        "lets do it",
        "let's do it",
        "let us do it",
        "go ahead",
        "whats next",
        "what's next",
        "yes please",
        "yes, please",
        "do it",
        "proceed",
        "i want to join",
        "judrna",
        "judna hai",
        "ok yes",
        "okay yes",
        "haan",
        "ha kar do",
    )
    return any(n in low for n in needles)


def _is_off_topic(low: str) -> bool:
    return any(n in low for n in ("gst", "income tax", "itr filing", "file my tax"))


def greet(category: dict, merchant: dict) -> str:
    ident = merchant.get("identity") or {}
    first = (ident.get("owner_first_name") or "").strip()
    slug = category.get("slug") or merchant.get("category_slug") or ""
    if slug == "dentists":
        if not first:
            return ident.get("name") or "Doctor"
        if first.lower().startswith("dr"):
            return first
        return f"Dr. {first.split()[0]}"
    if first:
        return first.split()[0]
    return ident.get("name") or "there"


def wants_hindi(merchant: dict, customer: Optional[dict], customer_scope: bool) -> bool:
    if customer_scope and customer:
        pref = ((customer.get("identity") or {}).get("language_pref") or "").lower()
        return "hi" in pref
    langs = (merchant.get("identity") or {}).get("languages") or []
    return any(str(lang).lower().startswith("hi") for lang in langs)


def scrub(body: str, category: dict) -> str:
    taboos = ((category.get("voice") or {}).get("vocab_taboo")) or []
    out = body
    for raw in taboos:
        phrase = str(raw).split("(")[0].strip()
        if len(phrase) < 4:
            continue
        out = re.sub(re.escape(phrase), "", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).replace(" ,", ",")


def _perf(merchant: dict) -> str:
    p = merchant.get("performance") or {}
    bits = []
    if p.get("views") is not None:
        bits.append(f"{p['views']} views")
    if p.get("calls") is not None:
        bits.append(f"{p['calls']} calls")
    if p.get("directions") is not None:
        bits.append(f"{p['directions']} direction requests")
    if p.get("ctr") is not None:
        bits.append(f"CTR {float(p['ctr']) * 100:.1f}%")
    if not bits:
        return ""
    window = p.get("window_days") or 30
    return f"Last {window}d: " + ", ".join(bits) + "."


def _peer_ctr(category: dict) -> Optional[str]:
    val = (category.get("peer_stats") or {}).get("avg_ctr")
    if val is None:
        return None
    return f"{float(val) * 100:.1f}%"


def _move(value: Any) -> str:
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    pct = abs(n) * 100 if abs(n) <= 1.5 else abs(n)
    word = "up" if n > 0 else "down" if n < 0 else "flat"
    return f"{pct:.0f}% {word}"


def _place(merchant: dict) -> str:
    ident = merchant.get("identity") or {}
    loc = ident.get("locality")
    city = ident.get("city")
    if loc and city:
        return f"{loc}, {city}"
    return loc or city or "your area"


def _biz(merchant: dict) -> str:
    return (merchant.get("identity") or {}).get("name") or "your business"


def _active_offer(merchant: dict) -> Optional[str]:
    for offer in merchant.get("offers") or []:
        if offer.get("status") == "active" and offer.get("title"):
            return offer["title"]
    return None


def _catalog_offer(category: dict) -> Optional[str]:
    catalog = category.get("offer_catalog") or []
    for offer in catalog:
        if offer.get("type") == "service_at_price" and offer.get("title"):
            return offer["title"]
    for offer in catalog:
        if offer.get("title"):
            return offer["title"]
    return None


def _offer(merchant: dict, category: dict) -> Optional[str]:
    return _active_offer(merchant) or _catalog_offer(category)


def _digest(category: dict, item_id: Optional[str]) -> Optional[dict]:
    items = category.get("digest") or []
    if item_id:
        for item in items:
            if item.get("id") == item_id:
                return item
    return items[0] if items else None


def _customer_name(customer: Optional[dict], trigger: dict) -> str:
    if customer:
        name = (customer.get("identity") or {}).get("name")
        if name:
            return name.split("(")[0].strip()
    cid = trigger.get("customer_id") or ""
    parts = cid.split("_")
    if len(parts) >= 3 and parts[2] not in {"for", "jr"}:
        return parts[2].capitalize()
    return "there"


def _slot(payload: dict) -> Optional[str]:
    slots = payload.get("available_slots") or payload.get("next_session_options") or []
    if slots and isinstance(slots[0], dict):
        return slots[0].get("label")
    return None


def _join(bits) -> str:
    clean = []
    for bit in bits:
        text = str(bit).strip().rstrip(".")
        if not text:
            continue
        clean.append(text[0].upper() + text[1:])
    return ". ".join(clean) + "."


def _finish(opener: str, facts: str, ask: str) -> str:
    text = f"{opener} — {facts}".strip()
    if ask:
        text = f"{text} {ask}"
    return text


def _research(opener, category, merchant, trigger, payload, customer):
    item = _digest(category, payload.get("top_item_id") or payload.get("digest_item_id")) or {}
    title = item.get("title") or "this week's category note"
    source = item.get("source") or "this week's digest"
    extra = []
    if item.get("trial_n"):
        extra.append(f"n={item['trial_n']}")
    if item.get("patient_segment"):
        extra.append(str(item["patient_segment"]).replace("_", " "))
    agg = merchant.get("customer_aggregate") or {}
    if agg.get("high_risk_adult_count"):
        extra.append(f"you have {agg['high_risk_adult_count']} high-risk adults on file")
    tail = f" ({', '.join(extra)})" if extra else ""
    facts = f"{source}: {title}{tail}."
    return _finish(opener, facts, "Want the short abstract, or should I draft a patient note you can forward?"), "open_ended", (
        f"Research digest {item.get('id') or payload.get('top_item_id')} matched to this merchant."
    )


def _regulation(opener, category, merchant, trigger, payload, customer):
    item = _digest(category, payload.get("top_item_id")) or {}
    title = item.get("title") or "a compliance update"
    source = item.get("source") or "the regulator circular"
    deadline = payload.get("deadline_iso") or ""
    when = f" Deadline {deadline}." if deadline else ""
    actionable = item.get("actionable")
    facts = f"{source}: {title}.{when}"
    if actionable:
        facts += f" {actionable}."
    return _finish(opener, facts, "Want a one-page checklist for the clinic?"), "open_ended", (
        "Compliance trigger with a cited source and deadline from context."
    )


def _perf_dip(opener, category, merchant, trigger, payload, customer):
    metric = payload.get("metric") or "calls"
    move = _move(payload.get("delta_pct")) if payload.get("delta_pct") is not None else "down"
    window = payload.get("window") or "7d"
    base = payload.get("vs_baseline")
    base_bit = f" Baseline was {base}." if base is not None else ""
    peer = _peer_ctr(category)
    peer_bit = f" Peer CTR is {peer}." if peer else ""
    facts = f"{metric} are {move} over {window}.{base_bit} {_perf(merchant)}{peer_bit}"
    offer = _offer(merchant, category)
    ask = f"I can draft a Google post around {offer}." if offer else "I can draft one Google post from the live numbers."
    return _finish(opener, facts, ask), "open_ended", "Performance dip anchored on the trigger metric and this merchant's snapshot."


def _perf_spike(opener, category, merchant, trigger, payload, customer):
    metric = payload.get("metric") or "calls"
    move = _move(payload.get("delta_pct")) if payload.get("delta_pct") is not None else "up"
    window = payload.get("window") or "7d"
    driver = payload.get("likely_driver")
    driver_bit = f" Likely driver: {str(driver).replace('_', ' ')}." if driver else ""
    facts = f"{metric} are {move} over {window}.{driver_bit} {_perf(merchant)}"
    return _finish(opener, facts, "Want me to turn that into one Google post while it is still fresh?"), "open_ended", (
        "Spike message uses the trigger metric and the likely driver from context."
    )


def _renewal(opener, category, merchant, trigger, payload, customer):
    sub = merchant.get("subscription") or {}
    days = payload.get("days_remaining", sub.get("days_remaining"))
    plan = payload.get("plan") or sub.get("plan") or "Pro"
    amount = payload.get("renewal_amount")
    price = f" (₹{amount})" if amount else ""
    when = f"in {days} days" if days is not None else "soon"
    facts = f"{plan} renewal is {when}{price}. {_perf(merchant)}"
    return _finish(opener, facts, "Reply YES to renew, or STOP."), "YES", "Renewal window from the trigger, with this merchant's recent numbers."


def _festival(opener, category, merchant, trigger, payload, customer):
    name = payload.get("festival") or "the festival"
    when = payload.get("date") or ""
    days = payload.get("days_until")
    when_bit = f" on {when}" if when else ""
    days_bit = f" ({days} days out)" if days is not None else ""
    offer = _offer(merchant, category)
    offer_bit = f" Live offer to anchor it: {offer}." if offer else ""
    facts = f"{name}{when_bit}{days_bit}.{offer_bit} {_place(merchant)}."
    return _finish(opener, facts, "Reply YES and I draft one Google post."), "YES", "Festival date from the trigger, offer taken from this merchant or the category catalog."


def _curious(opener, category, merchant, trigger, payload, customer):
    facts = f"quick question from {_place(merchant)}. Which service got the most walk-ins this week?"
    return (
        f"{opener} — {facts} I will turn your answer into one Google post. {_perf(merchant)}",
        "open_ended",
        "Curiosity ask. The merchant's own answer becomes the next post.",
    )


def _winback(opener, category, merchant, trigger, payload, customer):
    days = payload.get("days_since_expiry")
    dip = payload.get("perf_dip_pct")
    lapsed = payload.get("lapsed_customers_added_since_expiry")
    bits = [f"{_biz(merchant)} has been paused {days} days" if days is not None else f"{_biz(merchant)} is paused"]
    if dip is not None:
        bits.append(f"calls { _move(dip) }")
    if lapsed is not None:
        bits.append(f"{lapsed} more customers lapsed since expiry")
    facts = ". ".join(bits) + f". {_perf(merchant)}"
    return _finish(opener, facts, "Reply YES and I restart profile upkeep."), "YES", "Winback uses expiry age and the dip from this trigger only."


def _ipl(opener, category, merchant, trigger, payload, customer):
    match = payload.get("match") or "tonight's match"
    venue = payload.get("venue") or _place(merchant)
    offer = _offer(merchant, category)
    offer_bit = f" Catalog fit: {offer}." if offer else ""
    facts = f"{match} at {venue}.{offer_bit}"
    return _finish(opener, facts, "Reply YES and I post a match-night note."), "YES", "Match, venue, and a catalog offer already in context."


def _review_theme(opener, category, merchant, trigger, payload, customer):
    theme = str(payload.get("theme") or "a review theme").replace("_", " ")
    n = payload.get("occurrences_30d")
    quote = payload.get("common_quote")
    count = f"{n} reviews in 30d mention {theme}" if n is not None else f"Reviews mention {theme}"
    quote_bit = f' Quote: "{quote}".' if quote else ""
    facts = f"{count}.{quote_bit}"
    return _finish(opener, facts, "Want a short reply you can paste on those reviews?"), "open_ended", "Review theme, count, and quote come from the trigger."


def _milestone(opener, category, merchant, trigger, payload, customer):
    metric = str(payload.get("metric") or "reviews").replace("_", " ")
    now = payload.get("value_now")
    goal = payload.get("milestone_value")
    if now is not None and goal is not None:
        facts = f"{metric} are at {now}, milestone is {goal}. {_perf(merchant)}"
    else:
        facts = f"a {metric} milestone is close. {_perf(merchant)}"
    return _finish(opener, facts, "Want a thank-you post ready for the day you cross it?"), "open_ended", "Milestone uses the current value and the target from the trigger."


def _planning(opener, category, merchant, trigger, payload, customer):
    topic = str(payload.get("intent_topic") or "the package").replace("_", " ")
    said = payload.get("merchant_last_message")
    said_bit = f' You said: "{said}".' if said else ""
    live = _active_offer(merchant)
    catalog = None if live else _catalog_offer(category)
    if live:
        offer_bit = f" Your live offer: {live}."
    elif catalog:
        offer_bit = f" Starting point from the category catalog: {catalog}."
    else:
        offer_bit = ""
    facts = f"next step on {topic} is a one-page draft.{said_bit}{offer_bit}"
    return _finish(opener, facts, "Reply YES and I send the draft."), "YES", "Merchant already committed. Message starts the action instead of re-qualifying."


def _seasonal_dip(opener, category, merchant, trigger, payload, customer):
    metric = payload.get("metric") or "views"
    move = _move(payload.get("delta_pct")) if payload.get("delta_pct") is not None else "down"
    note = str(payload.get("season_note") or "this season").replace("_", " ")
    facts = f"{metric} are {move} over {payload.get('window') or '7d'}. This matches {note}, not a one-off drop. {_perf(merchant)}"
    return _finish(opener, facts, "Want a short note on what usually recovers first?"), "open_ended", "Seasonal dip is framed as expected, using the season note in the trigger."


def _customer_hello(merchant, customer, trigger):
    name = _customer_name(customer, trigger)
    hello = f"Namaste {name}" if wants_hindi(merchant, customer, True) else f"Hi {name}"
    return hello


def _lapsed_customer(opener, category, merchant, trigger, payload, customer):
    hello = _customer_hello(merchant, customer, trigger)
    rel = (customer or {}).get("relationship") or {}
    bits = [f"{_biz(merchant)} here"]
    days = payload.get("days_since_last_visit")
    if days is not None:
        bits.append(f"it has been {days} days since your last visit")
    elif rel.get("last_visit"):
        bits.append(f"last visit was {rel['last_visit']}")
    if payload.get("previous_focus"):
        bits.append(f"last focus was {str(payload['previous_focus']).replace('_', ' ')}")
    if payload.get("previous_membership_months"):
        bits.append(f"that plan ran {payload['previous_membership_months']} months")
    if rel.get("visits_total"):
        bits.append(f"{rel['visits_total']} visits on file")
    body = f"{hello} — {_join(bits)} Reply YES if you want one slot held."
    return body, "YES", "Customer winback uses only visit facts present on the customer or trigger."


def _recall(opener, category, merchant, trigger, payload, customer):
    hello = _customer_hello(merchant, customer, trigger)
    service = payload.get("service_due")
    due = f"Your {str(service).replace('_', ' ')} is due." if service else "A recall visit is due."
    slot = _slot(payload)
    slot_bit = f" Open slot: {slot}." if slot else ""
    last = payload.get("last_service_date") or (customer or {}).get("relationship", {}).get("last_visit")
    last_bit = f" Last visit {last}." if last else ""
    body = f"{hello} — {_biz(merchant)} here. {due}{last_bit}{slot_bit} Reply YES to hold it, or STOP."
    return body, "YES", "Recall uses the due service, last date, and the first offered slot."


def _wedding(opener, category, merchant, trigger, payload, customer):
    hello = _customer_hello(merchant, customer, trigger)
    bits = [f"{_biz(merchant)} here"]
    wedding = payload.get("wedding_date")
    days = payload.get("days_to_wedding")
    if wedding and days is not None:
        bits.append(f"wedding date {wedding} ({days} days)")
    elif wedding:
        bits.append(f"wedding date {wedding}")
    if payload.get("trial_completed"):
        bits.append(f"trial was {payload['trial_completed']}")
    if payload.get("next_step_window_open"):
        bits.append(f"next window: {str(payload['next_step_window_open']).replace('_', ' ')}")
    body = f"{hello} — {_join(bits)} Reply YES and we hold a slot."
    return body, "YES", "Bridal follow-up uses the wedding date and the next step already in the trigger."


def _trial(opener, category, merchant, trigger, payload, customer):
    hello = _customer_hello(merchant, customer, trigger)
    bits = [f"{_biz(merchant)} here"]
    if payload.get("trial_date"):
        bits.append(f"trial on {payload['trial_date']} is done")
    else:
        bits.append("your trial session is done")
    slot = _slot(payload)
    if slot:
        bits.append(f"next option {slot}")
    body = f"{hello} — {_join(bits)} Reply YES to lock it."
    return body, "YES", "Trial follow-up names the trial date and the next session from the trigger."


def _refill(opener, category, merchant, trigger, payload, customer):
    hello = _customer_hello(merchant, customer, trigger)
    meds = payload.get("molecule_list") or []
    line = f"Refill due for {', '.join(meds)}." if meds else "Your refill is due."
    out = payload.get("stock_runs_out_iso") or ""
    when = f" Stock runs out {out[:10]}." if out else ""
    body = f"{hello} — {_biz(merchant)} here. {line}{when} Reply YES and we pack it for delivery."
    return body, "YES", "Refill lists only the molecules and run-out date from the trigger."


def _supply(opener, category, merchant, trigger, payload, customer):
    batches = payload.get("affected_batches") or []
    bits = [f"supply alert on {payload['molecule']}" if payload.get("molecule") else "a supply alert just landed"]
    if batches:
        bits.append("affected batches: " + ", ".join(batches))
    if payload.get("manufacturer"):
        bits.append(f"manufacturer: {payload['manufacturer']}")
    facts = ". ".join(bits) + "."
    return _finish(opener, facts, "Reply YES and I draft the counter note for your team."), "YES", "Supply alert quotes molecule, batches, and manufacturer from the trigger."


def _seasonal_category(opener, category, merchant, trigger, payload, customer):
    season = str(payload.get("season") or "this season").replace("_", " ")
    trends = payload.get("trends") or []
    trend_bit = "; ".join(str(t).replace("_", " ") for t in trends[:4])
    place = _place(merchant)
    if trend_bit:
        facts = f"{season} shelf shift at {place}: {trend_bit}."
    else:
        facts = f"{season} shelf shift at {place}. {_perf(merchant)}"
    return _finish(opener, facts, "Want a 4-line shelf note you can hand the counter?"), "open_ended", "Seasonal trends copied from the trigger, not invented."


def _unverified(opener, category, merchant, trigger, payload, customer):
    path = str(payload.get("verification_path") or "postcard or phone").replace("_", " ")
    lift = payload.get("estimated_uplift_pct")
    lift_bit = f" Similar shops see about {_move(lift)} after verification." if lift is not None else ""
    facts = f"{_biz(merchant)} in {_place(merchant)} is still unverified on Google. Path: {path}.{lift_bit} {_perf(merchant)}"
    return _finish(opener, facts, "Reply YES and I start the verification steps."), "YES", "Unverified GBP with the uplift figure from the trigger."


def _cde(opener, category, merchant, trigger, payload, customer):
    item = _digest(category, payload.get("digest_item_id")) or {}
    title = item.get("title") or "a CDE session"
    when = item.get("date") or ""
    credits = payload.get("credits") or item.get("credits")
    fee = str(payload.get("fee") or "").replace("_", " ")
    bits = [title]
    if when:
        bits.append(str(when))
    if credits:
        bits.append(f"{credits} credits")
    if fee:
        bits.append(fee)
    facts = " — ".join(bits) + "."
    return _finish(opener, facts, "Want the joining details?"), "open_ended", "CDE item pulled from the category digest cited by the trigger."


def _competitor(opener, category, merchant, trigger, payload, customer):
    name = payload.get("competitor_name") or "a new listing"
    km = payload.get("distance_km")
    opened = payload.get("opened_date")
    where = f"{km} km away" if km is not None else "nearby"
    when = f" on {opened}" if opened else ""
    facts = f"{name} opened {where}{when}."
    if payload.get("their_offer"):
        facts += f" Their offer: {payload['their_offer']}."
    ours = _active_offer(merchant)
    if ours:
        facts += f" Yours still live: {ours}."
    facts += f" {_perf(merchant)}"
    return _finish(opener, facts, "Want a post that leads with your price, not a discount slogan?"), "open_ended", "Competitor name, distance, and offer are from the trigger."


def _dormant(opener, category, merchant, trigger, payload, customer):
    days = payload.get("days_since_last_merchant_message")
    gap = f"it has been {days} days since we last heard from you" if days is not None else "it has been a while since we last heard from you"
    topic = payload.get("last_topic")
    topic_bit = f" Last topic was {str(topic).replace('_', ' ')}." if topic else ""
    facts = f"{gap}.{topic_bit} {_perf(merchant)}"
    return _finish(opener, facts, "What should we pick up first?"), "open_ended", "Dormancy nudge uses the gap and the last topic, then asks the merchant."


def _appointment(opener, category, merchant, trigger, payload, customer):
    name = _customer_name(customer, trigger)
    hello = f"Namaste {name}" if wants_hindi(merchant, customer, True) else f"Hi {name}"
    slot = _slot(payload)
    when = slot or "tomorrow"
    body = f"{hello} — {_biz(merchant)} here. You have an appointment {when}. Reply YES to confirm, or STOP."
    return body, "YES", "Appointment reminder. A clock time is included only when the trigger has a slot."


def _generic(opener, category, merchant, trigger, payload, customer):
    kind = str(trigger.get("kind") or "update").replace("_", " ")
    if trigger.get("scope") == "customer" or trigger.get("customer_id"):
        name = _customer_name(customer, trigger)
        hello = f"Namaste {name}" if wants_hindi(merchant, customer, True) else f"Hi {name}"
        slot = _slot(payload)
        slot_bit = f" Slot: {slot}." if slot else ""
        body = f"{hello} — {_biz(merchant)} here. This is about your {kind}.{slot_bit} Reply YES if you want us to hold it."
        return body, "YES", "Customer-facing fallback. Dashboard numbers stay off this message."
    offer = _offer(merchant, category)
    offer_bit = f" Relevant offer: {offer}." if offer else ""
    facts = f"new {kind} for {_biz(merchant)} in {_place(merchant)}.{offer_bit} {_perf(merchant)}"
    return _finish(opener, facts, "Want me to draft it?"), "open_ended", "Fallback uses merchant identity and performance only."


_HANDLERS = {
    "research_digest": _research,
    "regulation_change": _regulation,
    "perf_dip": _perf_dip,
    "perf_spike": _perf_spike,
    "renewal_due": _renewal,
    "festival_upcoming": _festival,
    "curious_ask_due": _curious,
    "winback_eligible": _winback,
    "ipl_match_today": _ipl,
    "review_theme_emerged": _review_theme,
    "milestone_reached": _milestone,
    "active_planning_intent": _planning,
    "seasonal_perf_dip": _seasonal_dip,
    "customer_lapsed_hard": _lapsed_customer,
    "customer_lapsed_soft": _lapsed_customer,
    "recall_due": _recall,
    "wedding_package_followup": _wedding,
    "trial_followup": _trial,
    "chronic_refill_due": _refill,
    "supply_alert": _supply,
    "category_seasonal": _seasonal_category,
    "gbp_unverified": _unverified,
    "cde_opportunity": _cde,
    "competitor_opened": _competitor,
    "dormant_with_vera": _dormant,
    "appointment_tomorrow": _appointment,
}


def _self_check() -> None:
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "dataset"
    dentists = json.loads((root / "categories" / "dentists.json").read_text())
    merchants = json.loads((root / "merchants_seed.json").read_text())["merchants"]
    triggers = json.loads((root / "triggers_seed.json").read_text())["triggers"]
    meera = next(m for m in merchants if m["merchant_id"].startswith("m_001"))
    research = next(t for t in triggers if t["kind"] == "research_digest")
    out = compose(dentists, meera, research)
    assert "JIDA" in out["body"], out["body"]
    assert out["send_as"] == "vera"
    assert "guaranteed" not in out["body"].lower()
    assert re.search(r"\d", out["body"])

    recall = next(t for t in triggers if t["kind"] == "recall_due")
    customers = json.loads((root / "customers_seed.json").read_text())["customers"]
    priya = next(c for c in customers if c["customer_id"] == recall["customer_id"])
    recalled = compose(dentists, meera, recall, priya)
    assert recalled["send_as"] == "merchant_on_behalf"
    assert "Priya" in recalled["body"]
    assert "YES" in recalled["body"]

    auto = respond("Thank you for contacting us! Our team will respond shortly.")
    assert auto["action"] == "end"
    intent = respond("Ok lets do it. Whats next?")
    blob = intent["body"].lower()
    assert intent["action"] == "send"
    assert any(w in blob for w in ("next", "draft", "proceed"))
    assert not any(w in blob for w in ("would you", "do you", "how about", "what if"))
    hostile = respond("Stop messaging me. This is useless spam.")
    assert hostile["action"] == "end"
    print("composer self-check ok")


if __name__ == "__main__":
    _self_check()
