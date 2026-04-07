import json
from datetime import datetime
from pydantic import BaseModel, field_validator


# --- Line Items ---
class LineItemIn(BaseModel):
    service_type: str
    quantity: int = 1
    unit_price_ex_vat: float
    vat_percent: float | None = None  # Falls back to provider default


class LineItemOut(BaseModel):
    booking_item_id: str
    service_type: str
    quantity: int
    unit_price_ex_vat: float
    vat_percent: float
    total_line_ex_vat: float
    total_line_vat: float
    total_line_inc_vat: float


# --- Booking ---
class BookingCreateIn(BaseModel):
    provider_id: str
    customer_id: str | None = None  # None for walk-ins
    scheduled_start: datetime
    scheduled_end: datetime
    line_items: list[LineItemIn]
    customer_notes: str | None = None
    provider_notes: str | None = None
    is_walkin: bool = False
    walkin_customer_name: str | None = None
    walkin_customer_email: str | None = None
    session_preferences: list[str] = []  # e.g. ["quiet_session", "bringing_dog"]
    referral_source: str | None = None   # "provider_link", "instagram", "qr_code", "customer_favorite"
    status: str | None = None            # optional override, e.g. "confirmed"


class BookingUpdateIn(BaseModel):
    status: str | None = None
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    customer_notes: str | None = None
    provider_notes: str | None = None


class BookingOut(BaseModel):
    booking_id: str
    provider_id: str
    customer_id: str
    booking_number: int
    status: str
    scheduled_start: datetime
    scheduled_end: datetime
    actual_start_time: datetime | None
    actual_end_time: datetime | None
    total_amount_ex_vat: float
    total_vat_amount: float
    total_amount_inc_vat: float
    currency: str = "SEK"  # inherited from provider
    customer_notes: str | None = None
    provider_notes: str | None = None
    is_walkin: bool | None = False
    created_at: datetime
    line_items: list[LineItemOut] = []
    session_preferences: list[str] = []
    referral_source: str | None = None

    @field_validator("session_preferences", mode="before")
    @classmethod
    def _parse_prefs(cls, v):
        """Accept JSON string (from DB) or list (from code)."""
        if v is None:
            return []
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v

    model_config = {"from_attributes": True}


# --- Invoice ---
class InvoiceOut(BaseModel):
    invoice_id: str
    provider_id: str
    booking_id: str
    customer_id: str
    customer_email: str | None
    invoice_number: int
    issued_date: datetime
    total_ex_vat: float
    total_vat: float
    total_inc_vat: float
    currency: str = "SEK"  # inherited from provider
    status: str

    model_config = {"from_attributes": True}


# --- Customer ---
class CustomerCreateIn(BaseModel):
    provider_id: str
    customer_email: str | None = None
    user_id: str | None = None
    instagram_username_snapshot: str | None = None
    display_name: str | None = None
    phone: str | None = None
    source_channel: str | None = None


class CustomerOut(BaseModel):
    customer_id: str
    provider_id: str
    user_id: str | None
    customer_email: str | None
    instagram_username_snapshot: str | None
    display_name: str | None = None
    phone: str | None = None
    source_channel: str | None = None
    merge_status: str = "primary"
    customer_number: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Customer Preferences ---
class PreferenceCreateIn(BaseModel):
    customer_id: str
    provider_id: str
    category: str
    key: str
    value: str
    source: str = "manual"  # manual, ai_learned


class PreferenceOut(BaseModel):
    preference_id: str
    customer_id: str
    provider_id: str
    category: str
    key: str
    value: str
    source: str
    status: str
    confidence: float | None = None
    learned_at: datetime
    reviewed_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Merge Proposals ---
class MergeProposalOut(BaseModel):
    proposal_id: str
    provider_id: str
    customer_a_id: str
    customer_b_id: str
    match_type: str
    match_strength: str
    confidence_score: float
    match_details: str | None = None
    status: str
    proposed_at: datetime
    resolved_at: datetime | None = None

    model_config = {"from_attributes": True}


# --- Instagram ---
class InstagramResolveIn(BaseModel):
    provider_id: str
    instagram_user_id: str
    instagram_username: str | None = None


class InstagramIdentityOut(BaseModel):
    id: str
    provider_id: str
    instagram_user_id: str
    instagram_username: str | None
    customer_id: str
    user_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Service Catalog ---
class ServiceCreateIn(BaseModel):
    provider_id: str
    name: str
    category: str | None = None
    description: str | None = None
    duration_minutes: int
    price_ex_vat: float
    vat_percent: float | None = None
    home_service_available: bool = False


class ServiceOut(BaseModel):
    service_id: str
    provider_id: str
    name: str
    category: str | None
    description: str | None
    duration_minutes: int
    price_ex_vat: float
    vat_percent: float | None
    is_active: bool
    home_service_available: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Provider Search ---
class ProviderOut(BaseModel):
    provider_id: str
    user_id: str | None
    name: str
    org_number: str | None
    vat_percent: float
    currency: str = "SEK"
    location_salon: str | None
    home_service: bool
    bio: str | None = None
    image_url: str | None = None
    lat: float | None = None
    lng: float | None = None
    city: str | None = None
    price_level: int = 2
    rating: float = 0.0
    review_count: int = 0
    revisit_rate: float = 0.0
    total_completed_bookings: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Availability ---
class WorkingHoursIn(BaseModel):
    provider_id: str
    day_of_week: int  # 0=Mon, 6=Sun
    start_minutes: int  # e.g. 540 = 09:00
    end_minutes: int  # e.g. 1020 = 17:00


class WorkingHoursOut(BaseModel):
    availability_id: str
    provider_id: str
    day_of_week: int
    start_minutes: int
    end_minutes: int

    model_config = {"from_attributes": True}


class OverrideIn(BaseModel):
    provider_id: str
    date: datetime
    is_closed: bool = False
    start_minutes: int | None = None
    end_minutes: int | None = None
    reason: str | None = None


class OverrideOut(BaseModel):
    override_id: str
    provider_id: str
    date: datetime
    is_closed: bool
    start_minutes: int | None
    end_minutes: int | None
    reason: str | None

    model_config = {"from_attributes": True}


class SlotOut(BaseModel):
    start: str
    end: str


# --- Conversation ---
class ConversationCreateIn(BaseModel):
    provider_id: str
    channel: str  # instagram_dm, whatsapp, web
    external_thread_id: str
    customer_id: str | None = None


class ConversationOut(BaseModel):
    conversation_id: str
    provider_id: str
    customer_id: str | None
    channel: str
    external_thread_id: str
    status: str
    last_message_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageIn(BaseModel):
    conversation_id: str
    direction: str  # in/out
    text: str | None = None
    raw_payload_json: str | None = None
    idempotency_key: str | None = None


class MessageOut(BaseModel):
    message_id: str
    conversation_id: str
    direction: str
    text: str | None
    idempotency_key: str | None
    timestamp: datetime

    model_config = {"from_attributes": True}


# --- Webhook ---
class WebhookEventOut(BaseModel):
    event_id: str
    provider_id: str
    platform: str
    platform_event_id: str
    status: str
    received_at: datetime
    processed_at: datetime | None
    error_detail: str | None

    model_config = {"from_attributes": True}


# --- Slot Hold ---
class SlotHoldIn(BaseModel):
    provider_id: str
    start: datetime
    end: datetime
    conversation_id: str | None = None
    hold_minutes: int = 10


class SlotHoldOut(BaseModel):
    hold_id: str
    provider_id: str
    conversation_id: str | None
    start: datetime
    end: datetime
    expires_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}

