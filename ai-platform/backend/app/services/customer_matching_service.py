"""
CustomerMatchingService — Automatic identity stitching.

When a new customer record is created (from any channel), this service
checks if they might already exist under a different record for the
same provider.

Match rules:
  STRONG (auto-merge):
    - Same email (exact, case-insensitive)
    - Same Instagram username → existing customer has that IG identity

  MEDIUM (propose merge, customer confirms):
    - Same phone number
    - Display name + email domain match

  WEAK (log only, no action):
    - Only first name matches

The provider NEVER does manual merging work. Our system handles it
automatically (strong) or asks the customer to confirm (medium).
"""
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.instagram_identity import InstagramIdentity
from app.models.merge_proposal import MergeProposal
from app.models.booking import Booking
from app.models.customer_preference import CustomerPreference

logger = logging.getLogger(__name__)


class CustomerMatchingService:

    @staticmethod
    def find_matches(
        db: Session,
        provider_id: str,
        new_customer: Customer,
    ) -> list[dict]:
        """
        Find potential matches for a newly created customer against
        existing customers for the same provider.

        Returns list of: {"customer": Customer, "match_type": str, "strength": str, "confidence": float, "details": str}
        """
        matches = []

        # Don't match against self or already-merged records
        existing = db.query(Customer).filter(
            Customer.provider_id == provider_id,
            Customer.customer_id != new_customer.customer_id,
            Customer.merge_status == "primary",  # only match against primary records
        ).all()

        for cust in existing:
            match = CustomerMatchingService._check_match(db, new_customer, cust)
            if match:
                matches.append(match)

        return matches

    @staticmethod
    def _check_match(db: Session, new: Customer, existing: Customer) -> dict | None:
        """Compare two customers and return match info if they might be the same person."""

        # ── STRONG: Same email (case-insensitive) ──
        if (
            new.customer_email
            and existing.customer_email
            and new.customer_email.strip().lower() == existing.customer_email.strip().lower()
        ):
            return {
                "customer": existing,
                "match_type": "email",
                "strength": "strong",
                "confidence": 0.95,
                "details": json.dumps({"matched_email": new.customer_email.lower()}),
            }

        # ── STRONG: Same Instagram username ──
        if new.instagram_username_snapshot and existing.instagram_username_snapshot:
            if new.instagram_username_snapshot.lower() == existing.instagram_username_snapshot.lower():
                return {
                    "customer": existing,
                    "match_type": "instagram",
                    "strength": "strong",
                    "confidence": 0.90,
                    "details": json.dumps({"matched_username": new.instagram_username_snapshot}),
                }

        # Also check: new customer's IG username matches an existing InstagramIdentity
        if new.instagram_username_snapshot:
            ig_match = db.query(InstagramIdentity).filter(
                InstagramIdentity.provider_id == new.provider_id,
                InstagramIdentity.instagram_username == new.instagram_username_snapshot,
                InstagramIdentity.customer_id != new.customer_id,
            ).first()
            if ig_match:
                ig_cust = db.query(Customer).filter(
                    Customer.customer_id == ig_match.customer_id,
                    Customer.merge_status == "primary",
                ).first()
                if ig_cust:
                    return {
                        "customer": ig_cust,
                        "match_type": "instagram",
                        "strength": "strong",
                        "confidence": 0.92,
                        "details": json.dumps({"matched_ig_identity": ig_match.instagram_username}),
                    }

        # ── MEDIUM: Same phone number ──
        if (
            new.phone
            and existing.phone
            and _normalize_phone(new.phone) == _normalize_phone(existing.phone)
        ):
            return {
                "customer": existing,
                "match_type": "phone",
                "strength": "medium",
                "confidence": 0.80,
                "details": json.dumps({"matched_phone": new.phone}),
            }

        # ── MEDIUM: Display name + email domain match ──
        if (
            new.display_name
            and existing.display_name
            and new.customer_email
            and existing.customer_email
        ):
            names_similar = _names_match(new.display_name, existing.display_name)
            domains_match = _email_domain(new.customer_email) == _email_domain(existing.customer_email)
            if names_similar and domains_match:
                return {
                    "customer": existing,
                    "match_type": "name_similarity",
                    "strength": "medium",
                    "confidence": 0.65,
                    "details": json.dumps({
                        "name_a": new.display_name,
                        "name_b": existing.display_name,
                        "domain": _email_domain(new.customer_email),
                    }),
                }

        return None

    @staticmethod
    def process_matches(
        db: Session,
        provider_id: str,
        new_customer: Customer,
        matches: list[dict],
    ) -> list[MergeProposal]:
        """
        Process match results:
          - Strong matches → auto-merge + create proposal record
          - Medium matches → create pending proposal (customer confirms)
          - Weak matches → log only
        """
        proposals = []

        for match in matches:
            existing_cust = match["customer"]
            strength = match["strength"]

            # Check if we already have a proposal for these two
            existing_proposal = db.query(MergeProposal).filter(
                MergeProposal.provider_id == provider_id,
                (
                    (MergeProposal.customer_a_id == new_customer.customer_id) & (MergeProposal.customer_b_id == existing_cust.customer_id)
                ) | (
                    (MergeProposal.customer_a_id == existing_cust.customer_id) & (MergeProposal.customer_b_id == new_customer.customer_id)
                ),
            ).first()

            if existing_proposal:
                continue  # already proposed

            if strength == "strong":
                # Auto-merge: new customer absorbs into existing
                proposal = MergeProposal(
                    provider_id=provider_id,
                    customer_a_id=existing_cust.customer_id,  # keep this one (older)
                    customer_b_id=new_customer.customer_id,    # merge this one into A
                    match_type=match["match_type"],
                    match_strength=strength,
                    confidence_score=match["confidence"],
                    match_details=match["details"],
                    status="auto_merged",
                    resolved_at=datetime.now(timezone.utc),
                )
                db.add(proposal)

                # Execute the merge
                CustomerMatchingService._execute_merge(db, existing_cust, new_customer)
                proposals.append(proposal)

                logger.info(
                    "Auto-merged customer %s into %s (match: %s, confidence: %.2f)",
                    new_customer.customer_id, existing_cust.customer_id,
                    match["match_type"], match["confidence"],
                )

            elif strength == "medium":
                # Create pending proposal — customer will confirm later
                proposal = MergeProposal(
                    provider_id=provider_id,
                    customer_a_id=existing_cust.customer_id,
                    customer_b_id=new_customer.customer_id,
                    match_type=match["match_type"],
                    match_strength=strength,
                    confidence_score=match["confidence"],
                    match_details=match["details"],
                    status="pending",
                )
                db.add(proposal)
                proposals.append(proposal)

                logger.info(
                    "Proposed merge for customer %s + %s (match: %s, confidence: %.2f)",
                    existing_cust.customer_id, new_customer.customer_id,
                    match["match_type"], match["confidence"],
                )

        if proposals:
            db.commit()

        return proposals

    @staticmethod
    def _execute_merge(db: Session, primary: Customer, secondary: Customer):
        """
        Merge secondary customer into primary:
          - Reassign all bookings to primary
          - Reassign all preferences to primary
          - Copy any missing identity fields from secondary to primary
          - Mark secondary as merged
        """
        # Reassign bookings
        db.query(Booking).filter(
            Booking.customer_id == secondary.customer_id,
        ).update({"customer_id": primary.customer_id})

        # Reassign preferences
        db.query(CustomerPreference).filter(
            CustomerPreference.customer_id == secondary.customer_id,
        ).update({"customer_id": primary.customer_id})

        # Reassign Instagram identities
        db.query(InstagramIdentity).filter(
            InstagramIdentity.customer_id == secondary.customer_id,
        ).update({"customer_id": primary.customer_id})

        # Fill in any missing fields on primary from secondary
        if not primary.customer_email and secondary.customer_email:
            primary.customer_email = secondary.customer_email
        if not primary.phone and secondary.phone:
            primary.phone = secondary.phone
        if not primary.display_name and secondary.display_name:
            primary.display_name = secondary.display_name
        if not primary.instagram_username_snapshot and secondary.instagram_username_snapshot:
            primary.instagram_username_snapshot = secondary.instagram_username_snapshot

        # Mark secondary as merged
        secondary.merge_status = "merged"
        secondary.merged_into_id = primary.customer_id

        db.flush()

    @staticmethod
    def approve_merge(db: Session, proposal_id: str) -> MergeProposal:
        """Customer approves a pending merge proposal."""
        proposal = db.query(MergeProposal).filter(
            MergeProposal.proposal_id == proposal_id,
            MergeProposal.status == "pending",
        ).first()
        if not proposal:
            raise ValueError("Merge proposal not found or already resolved")

        primary = db.query(Customer).filter(Customer.customer_id == proposal.customer_a_id).first()
        secondary = db.query(Customer).filter(Customer.customer_id == proposal.customer_b_id).first()

        if not primary or not secondary:
            raise ValueError("Customer records not found")

        CustomerMatchingService._execute_merge(db, primary, secondary)

        proposal.status = "customer_approved"
        proposal.resolved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(proposal)
        return proposal

    @staticmethod
    def deny_merge(db: Session, proposal_id: str) -> MergeProposal:
        """Customer denies a pending merge proposal."""
        proposal = db.query(MergeProposal).filter(
            MergeProposal.proposal_id == proposal_id,
            MergeProposal.status == "pending",
        ).first()
        if not proposal:
            raise ValueError("Merge proposal not found or already resolved")

        proposal.status = "customer_denied"
        proposal.resolved_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(proposal)
        return proposal

    @staticmethod
    def get_pending_proposals(db: Session, provider_id: str) -> list[MergeProposal]:
        """Get all pending merge proposals for a provider."""
        return db.query(MergeProposal).filter(
            MergeProposal.provider_id == provider_id,
            MergeProposal.status == "pending",
        ).order_by(MergeProposal.proposed_at.desc()).all()

    @staticmethod
    def get_customer_proposals(db: Session, customer_id: str) -> list[MergeProposal]:
        """Get all merge proposals involving a specific customer."""
        return db.query(MergeProposal).filter(
            (MergeProposal.customer_a_id == customer_id) | (MergeProposal.customer_b_id == customer_id),
        ).order_by(MergeProposal.proposed_at.desc()).all()


# ── Helper functions ──

def _normalize_phone(phone: str) -> str:
    """Strip non-digits for comparison."""
    return "".join(c for c in phone if c.isdigit())


def _email_domain(email: str) -> str:
    """Extract domain from email."""
    parts = email.strip().lower().split("@")
    return parts[1] if len(parts) == 2 else ""


def _names_match(name_a: str, name_b: str) -> bool:
    """
    Simple name similarity check.
    Returns True if first names match (case-insensitive).
    """
    a_parts = name_a.strip().lower().split()
    b_parts = name_b.strip().lower().split()
    if not a_parts or not b_parts:
        return False
    return a_parts[0] == b_parts[0]
