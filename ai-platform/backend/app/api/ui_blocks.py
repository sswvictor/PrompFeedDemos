"""
UIBlock contracts for Fixmeapp discovery and booking feeds.

The frontend renders from a closed set of typed blocks:
    prompt -> intent profile -> feed recipe -> typed blocks -> renderer
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class ServiceSummary(BaseModel):
    service_id: str
    name: str
    category: str | None
    duration_minutes: int
    price_ex_vat: float
    price_inc_vat: float
    home_service_available: bool


class TimeSlot(BaseModel):
    start: str
    end: str
    time_label: str
    available: bool = True


class CTAButton(BaseModel):
    label: str
    action: str
    provider_id: str | None = None
    booking_id: str | None = None
    style: Literal["primary", "secondary", "ghost"] = "primary"


class SearchSummaryData(BaseModel):
    query: str
    subtitle: str
    parsed_location: str | None
    parsed_service: str | None
    detected_signals: list[str]
    result_count: int


class ProviderCardData(BaseModel):
    provider_id: str
    slug: str | None = None
    name: str
    bio: str | None
    image_url: str | None
    city: str | None
    location_salon: str | None
    instagram_username: str | None
    services: list[ServiceSummary]
    matched_services: list[ServiceSummary]
    price_level: int
    price_level_label: str
    starting_from: float | None
    rating: float
    review_count: int
    revisit_rate: float
    total_completed_bookings: int
    next_available: str | None
    available_today: bool
    home_service: bool
    vibe_tags: list[str] = []
    vibe_summary: str | None = None


class ProviderResultsData(BaseModel):
    providers: list[ProviderCardData]
    total_found: int
    sort_strategy: str


class AvailabilityPickerData(BaseModel):
    provider_id: str
    provider_name: str
    service_options: list[ServiceSummary]
    slots_by_date: dict[str, list[TimeSlot]]
    available_dates: list[str]


class BookingDraftData(BaseModel):
    provider_id: str
    provider_name: str
    service_id: str
    service_name: str
    date: str
    time: str
    duration_minutes: int
    price_ex_vat: float
    price_inc_vat: float
    hold_expires_at: str | None
    customer_notes: str | None = None


class SafetyInfoData(BaseModel):
    title: str
    body: str
    gdpr_consent_required: bool = False
    consent_key: str | None = None


class InfoCardData(BaseModel):
    title: str
    body: str
    icon: str | None = None


class PreferenceSummary(BaseModel):
    category: str
    key: str
    value: str
    source: str
    confidence: float | None


class ProfileMemoryData(BaseModel):
    customer_id: str
    display_name: str | None
    visit_count: int
    last_visit: str | None
    preferences: list[PreferenceSummary]
    is_returning: bool


class CTAButtonRowData(BaseModel):
    buttons: list[CTAButton]


class HeroCardData(BaseModel):
    title: str
    subtitle: str
    goal: str
    tone: Literal["guided", "decisive", "explore", "returning"] = "guided"


class ConversationalFollowUpData(BaseModel):
    suggestions: list[str]


class IntentProfile(BaseModel):
    goal: Literal[
        "booking",
        "discovery",
        "inspiration",
        "rebook",
        "profile_lookup",
        "comparison",
    ]
    service_certainty: Literal["low", "medium", "high"] = "low"
    provider_certainty: Literal["low", "medium", "high"] = "low"
    time_certainty: Literal["low", "medium", "high"] = "low"
    location_certainty: Literal["low", "medium", "high"] = "low"
    budget_certainty: Literal["low", "medium", "high"] = "low"
    urgency: Literal["low", "medium", "high"] = "low"
    is_returning_customer: bool = False
    needs_clarification: list[str] = []
    explanation_style: Literal["guided", "concise", "premium"] = "guided"
    query_rewrite: str | None = None


class FeedRecipe(BaseModel):
    template: Literal[
        "guided_search",
        "guided_booking",
        "specific_booking",
        "inspiration_first",
        "returning_customer",
    ]
    ordered_blocks: list[str]
    primary_action: str


class UIBlock(BaseModel):
    type: Literal[
        "SearchSummaryCard",
        "ProviderCard",
        "ProviderResults",
        "AvailabilityPicker",
        "BookingDraftCard",
        "SafetyInfoCard",
        "InfoCard",
        "ProfileMemoryCard",
        "CTAButtonRow",
        "HeroCard",
        "ConversationalFollowUp",
    ]
    emphasis: list[str] = []
    data: (
        SearchSummaryData
        | ProviderCardData
        | ProviderResultsData
        | AvailabilityPickerData
        | BookingDraftData
        | SafetyInfoData
        | InfoCardData
        | ProfileMemoryData
        | CTAButtonRowData
        | HeroCardData
        | ConversationalFollowUpData
    )

    model_config = {"arbitrary_types_allowed": True}


class SearchFeedResponse(BaseModel):
    blocks: list[UIBlock]
    intent: dict


class PromptFeedResponse(BaseModel):
    blocks: list[UIBlock]
    intent: dict
    intent_profile: IntentProfile
    recipe: FeedRecipe


class ProviderFeedResponse(BaseModel):
    blocks: list[UIBlock]


class SearchFeedRequest(BaseModel):
    prompt: str
    customer_id: str | None = None
    customer_user_id: str | None = None


class PromptFeedRequest(BaseModel):
    prompt: str
    customer_id: str | None = None
    customer_user_id: str | None = None
    session_id: str | None = None
