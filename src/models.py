from __future__ import annotations

from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

class OfferTemplate(BaseModel):
    title: str
    description: Optional[str] = None

class VoiceProfile(BaseModel):
    tone: str
    allowed_vocabulary: List[str] = []
    taboo_words: List[str] = []

class PeerStats(BaseModel):
    avg_rating: float
    avg_reviews: int
    avg_ctr: float

class DigestItem(BaseModel):
    title: str
    source: str
    summary: Optional[str] = None

class ContentItem(BaseModel):
    title: str
    url: Optional[str] = None
    snippet: Optional[str] = None

class SeasonalBeat(BaseModel):
    month: str
    note: str

class TrendSignal(BaseModel):
    description: str

class CategoryContext(BaseModel):
    slug: str
    offer_catalog: List[OfferTemplate]
    voice: VoiceProfile
    peer_stats: PeerStats
    digest: List[DigestItem]
    patient_content_library: List[ContentItem]
    seasonal_beats: List[SeasonalBeat]
    trend_signals: List[TrendSignal]

class Identity(BaseModel):
    name: str
    place_id: Optional[str] = None
    locality: Optional[str] = None
    city: str
    verified: bool = False
    languages: List[str] = []

class Subscription(BaseModel):
    status: Literal["active", "inactive", "trial"]
    days_remaining: int
    plan: str

class PerformanceSnapshot(BaseModel):
    views: int
    calls: int
    directions: int
    ctr: float
    period: Literal["30d", "7d"]
    delta: Optional[Dict[str, Any]] = None

class MerchantOffer(BaseModel):
    title: str
    price: Optional[float] = None
    active: bool = True
    expires_at: Optional[str] = None

class ConversationTurn(BaseModel):
    role: Literal["merchant", "vera", "customer"]
    message: str
    timestamp: Optional[str] = None

class ConversationHistory(BaseModel):
    turns: List[ConversationTurn]

class CustomerAggregate(BaseModel):
    active_count: int
    lapsed_count: int
    retention_percent: float

class DerivedSignal(BaseModel):
    name: str
    details: Optional[Dict[str, Any]] = None

class MerchantContext(BaseModel):
    merchant_id: str
    identity: Identity
    subscription: Subscription
    performance: PerformanceSnapshot
    offers: List[MerchantOffer]
    conversation_history: ConversationHistory
    customer_aggregate: CustomerAggregate
    signals: List[DerivedSignal]

class TriggerContext(BaseModel):
    id: str
    scope: Literal["merchant", "customer"]
    kind: str
    source: Literal["external", "internal"]
    payload: Dict[str, Any]
    urgency: int = Field(..., ge=1, le=5)
    suppression_key: str
    expires_at: str

class CustomerIdentity(BaseModel):
    name: str
    phone: str
    language_pref: str

class Relationship(BaseModel):
    first_visit: str
    last_visit: str
    visits_total: int
    services: List[str]

class Preferences(BaseModel):
    preferred_time: Optional[str] = None
    channel: Optional[str] = None
    opt_in_scope: List[str] = []

class Consent(BaseModel):
    opted_in_at: str
    source: str
    scopes: List[str]

class CustomerContext(BaseModel):
    customer_id: str
    merchant_id: str
    identity: CustomerIdentity
    relationship: Relationship
    state: Literal["new", "active", "lapsed_soft", "lapsed_hard", "churned"]
    preferences: Preferences
    consent: Consent

class ComposeInput(BaseModel):
    category: CategoryContext
    merchant: MerchantContext
    trigger: TriggerContext
    customer: Optional[CustomerContext] = None

class ComposeOutput(BaseModel):
    body: str
    cta: str
    send_as: Literal["vera", "merchant_on_behalf"]
    suppression_key: str
    rationale: str
