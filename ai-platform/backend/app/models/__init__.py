# Import all models so SQLAlchemy resolves string-based relationships
from app.models.user import User  # noqa: F401
from app.models.provider import Provider  # noqa: F401
from app.models.customer import Customer  # noqa: F401
from app.models.instagram_identity import InstagramIdentity  # noqa: F401
from app.models.booking import Booking, BookingLineItem  # noqa: F401
from app.models.invoice import Invoice  # noqa: F401
from app.models.service import Service  # noqa: F401
from app.models.availability import Availability, AvailabilityOverride  # noqa: F401
from app.models.conversation import Conversation, Message  # noqa: F401
from app.models.conversation_state import ConversationState  # noqa: F401
from app.models.webhook_event import WebhookEvent  # noqa: F401
from app.models.calendar_event import CalendarEvent  # noqa: F401
from app.models.timeslot_hold import TimeSlotHold  # noqa: F401
from app.models.provider_instagram_page import ProviderInstagramPage  # noqa: F401
from app.models.customer_preference import CustomerPreference  # noqa: F401
from app.models.merge_proposal import MergeProposal  # noqa: F401
from app.models.worker import Worker  # noqa: F401
from app.models.provider_amenity import ProviderAmenity  # noqa: F401
from app.models.service_constraint import ServiceConstraint  # noqa: F401
from app.models.consent_record import ConsentRecord  # noqa: F401
from app.models.data_retention_log import DataRetentionLog  # noqa: F401
from app.models.plan import Plan  # noqa: F401
from app.models.subscription import Subscription  # noqa: F401
from app.models.provider_bot_settings import ProviderBotSettings  # noqa: F401
from app.models.provider_time_block import ProviderTimeBlock  # noqa: F401
from app.models.waitlist import WaitlistEntry, WaitlistOffer  # noqa: F401
from app.models.salon_link_request import SalonLinkRequest  # noqa: F401
from app.models.chat_magic_link import ChatMagicLink  # noqa: F401
from app.models.provider_follow import ProviderFollow  # noqa: F401
from app.models.referral_payout import ReferralPayout  # noqa: F401

from app.models.provider_intelligence import ProviderIntelligence  # noqa: F401

from app.models.search_event import SearchEvent  # noqa: F401
from app.models.discovery_event import DiscoveryEvent  # noqa: F401
from app.models.business_verification import BusinessVerification  # noqa: F401

from app.models.provider_calendar_connection import ProviderCalendarConnection  # noqa: F401
from app.models.external_calendar_event import ExternalCalendarEvent  # noqa: F401
from app.models.sync_job import SyncJob  # noqa: F401

from app.models.customer_reliability_report import CustomerReliabilityReport  # noqa: F401
from app.models.gdpr_request import GDPRRequest  # noqa: F401

from app.models.loyalty_event import LoyaltyEvent  # noqa: F401
from app.models.admin_audit_log import AdminAuditLog  # noqa: F401


from app.models.provider_incident_report import ProviderIncidentReport  # noqa: F401
