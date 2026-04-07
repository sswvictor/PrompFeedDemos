"""
CustomerPreferenceService — Manages AI-learned and manual customer insights.

This service handles:
  - Adding preferences (from AI conversations or manual provider input)
  - Auto-approval for low-sensitivity categories
  - Customer approval/denial flow
  - Retrieving provider-visible preferences (only approved ones)
  - Archiving outdated preferences

Ethical rules:
  1. The AI NEVER stores deeply personal information (emotional state, relationships)
  2. Health/allergy info goes to "pending" — customer must approve
  3. Service preferences auto-approve — low sensitivity
  4. Customer can deny ANY preference at any time → hidden from provider
  5. All preference changes are timestamped for audit trail
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.customer_preference import (
    CustomerPreference,
    AUTO_APPROVE_CATEGORIES,
    PENDING_CATEGORIES,
)

logger = logging.getLogger(__name__)


class CustomerPreferenceService:

    @staticmethod
    def add_preference(
        db: Session,
        customer_id: str,
        provider_id: str,
        category: str,
        key: str,
        value: str,
        source: str = "ai_learned",
        source_conversation_id: str | None = None,
        confidence: float | None = None,
    ) -> CustomerPreference:
        """
        Add a new preference for a customer.

        Auto-approval logic:
          - service_preference, scheduling_pattern, communication → auto-approved
          - allergy_sensitivity, personal, health_signal → pending (customer must approve)
        """
        # Check for existing preference with same key for this customer+provider
        existing = db.query(CustomerPreference).filter(
            CustomerPreference.customer_id == customer_id,
            CustomerPreference.provider_id == provider_id,
            CustomerPreference.key == key,
            CustomerPreference.status.in_(["approved", "pending"]),
        ).first()

        if existing:
            # Update existing preference value (don't create duplicates)
            existing.value = value
            existing.source = source
            existing.source_conversation_id = source_conversation_id
            existing.confidence = confidence
            existing.learned_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            logger.info("Updated preference '%s' for customer %s", key, customer_id)
            return existing

        # Determine initial status based on category
        if category in AUTO_APPROVE_CATEGORIES:
            initial_status = "approved"
        elif category in PENDING_CATEGORIES:
            initial_status = "pending"
        else:
            initial_status = "pending"  # default to pending for unknown categories

        pref = CustomerPreference(
            customer_id=customer_id,
            provider_id=provider_id,
            category=category,
            key=key,
            value=value,
            source=source,
            source_conversation_id=source_conversation_id,
            status=initial_status,
            confidence=confidence,
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)

        logger.info(
            "Added preference '%s' for customer %s (category: %s, status: %s)",
            key, customer_id, category, initial_status,
        )
        return pref

    @staticmethod
    def get_provider_visible_preferences(
        db: Session,
        customer_id: str,
        provider_id: str,
    ) -> list[CustomerPreference]:
        """
        Get preferences the provider can see (approved only).
        This is what shows on the customer profile card.
        """
        return db.query(CustomerPreference).filter(
            CustomerPreference.customer_id == customer_id,
            CustomerPreference.provider_id == provider_id,
            CustomerPreference.status == "approved",
        ).order_by(CustomerPreference.category, CustomerPreference.learned_at.desc()).all()

    @staticmethod
    def get_all_preferences(
        db: Session,
        customer_id: str,
        provider_id: str,
    ) -> dict[str, list[CustomerPreference]]:
        """
        Get ALL preferences grouped by status — for the customer's "My Data" view.
        Returns: {"approved": [...], "pending": [...], "denied": [...]}
        """
        prefs = db.query(CustomerPreference).filter(
            CustomerPreference.customer_id == customer_id,
            CustomerPreference.provider_id == provider_id,
            CustomerPreference.status != "archived",
        ).order_by(CustomerPreference.learned_at.desc()).all()

        grouped = {"approved": [], "pending": [], "denied": []}
        for p in prefs:
            if p.status in grouped:
                grouped[p.status].append(p)
        return grouped

    @staticmethod
    def approve_preference(db: Session, preference_id: str) -> CustomerPreference:
        """Customer approves a pending preference."""
        pref = db.query(CustomerPreference).filter(
            CustomerPreference.preference_id == preference_id,
        ).first()
        if not pref:
            raise ValueError("Preference not found")
        if pref.status == "denied":
            raise ValueError("Cannot approve a denied preference — customer must re-add it")

        pref.status = "approved"
        pref.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(pref)
        return pref

    @staticmethod
    def deny_preference(db: Session, preference_id: str) -> CustomerPreference:
        """Customer denies a preference — hidden from provider forever (until re-added)."""
        pref = db.query(CustomerPreference).filter(
            CustomerPreference.preference_id == preference_id,
        ).first()
        if not pref:
            raise ValueError("Preference not found")

        pref.status = "denied"
        pref.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(pref)
        return pref

    @staticmethod
    def archive_preference(db: Session, preference_id: str) -> CustomerPreference:
        """Archive an outdated preference."""
        pref = db.query(CustomerPreference).filter(
            CustomerPreference.preference_id == preference_id,
        ).first()
        if not pref:
            raise ValueError("Preference not found")

        pref.status = "archived"
        pref.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(pref)
        return pref

    @staticmethod
    def add_manual_preference(
        db: Session,
        customer_id: str,
        provider_id: str,
        category: str,
        key: str,
        value: str,
    ) -> CustomerPreference:
        """
        Provider manually adds a preference (always approved immediately).
        Used when a provider notices something during an appointment.
        """
        return CustomerPreferenceService.add_preference(
            db=db,
            customer_id=customer_id,
            provider_id=provider_id,
            category=category,
            key=key,
            value=value,
            source="manual",
            confidence=1.0,
        )

    @staticmethod
    def get_preferences_summary(
        db: Session,
        customer_id: str,
        provider_id: str,
    ) -> dict:
        """
        Returns a compact summary for the customer profile card.
        Groups approved preferences by category with counts.
        """
        prefs = CustomerPreferenceService.get_provider_visible_preferences(
            db, customer_id, provider_id,
        )

        summary = {
            "total_approved": len(prefs),
            "pending_count": db.query(CustomerPreference).filter(
                CustomerPreference.customer_id == customer_id,
                CustomerPreference.provider_id == provider_id,
                CustomerPreference.status == "pending",
            ).count(),
            "by_category": {},
            "items": [],
        }

        for p in prefs:
            if p.category not in summary["by_category"]:
                summary["by_category"][p.category] = []
            summary["by_category"][p.category].append({
                "preference_id": p.preference_id,
                "key": p.key,
                "value": p.value,
                "source": p.source,
                "confidence": p.confidence,
                "learned_at": p.learned_at.isoformat() if p.learned_at else None,
            })
            summary["items"].append({
                "preference_id": p.preference_id,
                "category": p.category,
                "key": p.key,
                "value": p.value,
            })

        return summary
