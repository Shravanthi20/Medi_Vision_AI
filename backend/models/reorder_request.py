"""Domain — Reorder: reorder_requests.

Tracks outbound WhatsApp reorder requests sent to suppliers via n8n/Twilio,
including the full supplier conversation lifecycle.
"""

from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import JSONB
from ..extensions import db


REORDER_STATUSES = (
    "PENDING",
    "PROCESSING",
    "SENT",
    "PARTIALLY_CONFIRMED",
    "CONFIRMED",
    "FAILED",
    "REJECTED",
)


class ReorderRequest(db.Model):
    __tablename__ = "reorder_requests"

    reorder_id = db.Column(db.Integer, primary_key=True)

    # --- Who & what ---
    supplier_id = db.Column(
        db.Integer, db.ForeignKey("suppliers.supplier_id"), nullable=False
    )
    location_id = db.Column(
        db.Integer, db.ForeignKey("locations.location_id"), nullable=False
    )

    # Items requested — list of {item_id, item_name, quantity, unit}
    items = db.Column(JSONB, nullable=False)

    # --- Lifecycle ---
    status = db.Column(db.String(30), nullable=False, default="PENDING")

    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    sent_at = db.Column(db.DateTime, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # --- n8n / Twilio conversation ---
    n8n_conversation_id = db.Column(db.String(100), nullable=True)
    """Conversation tracking ID assigned by n8n (or the backend itself)."""

    supplier_response = db.Column(db.Text, nullable=True)
    """Raw text reply received from the supplier over WhatsApp."""

    confirmed_items = db.Column(JSONB, nullable=True)
    """
    Resolved item quantities after the supplier's menu reply, e.g.:
    [{"item_id": "ITM001", "requested_qty": 30, "confirmed_qty": 25}, ...]
    Set for CONFIRMED and PARTIALLY_CONFIRMED statuses.
    """

    # Optional Twilio message SID for audit trail
    provider_message_id = db.Column(db.String(100), nullable=True)

    # Free-text notes (e.g. failure reason, parse errors)
    notes = db.Column(db.Text, nullable=True)

    # --- Relationships ---
    supplier = db.relationship(
        "Supplier",
        foreign_keys=[supplier_id],
        lazy="select",
        overlaps="reorder_requests",
    )
    location = db.relationship(
        "Location",
        foreign_keys=[location_id],
        lazy="select",
        overlaps="reorder_requests",
    )

    __table_args__ = (
        db.CheckConstraint(
            f"status IN {tuple(REORDER_STATUSES)}",
            name="reorder_status_valid",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "reorder_id": self.reorder_id,
            "supplier_id": self.supplier_id,
            "location_id": self.location_id,
            "items": self.items,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "n8n_conversation_id": self.n8n_conversation_id,
            "supplier_response": self.supplier_response,
            "confirmed_items": self.confirmed_items,
            "provider_message_id": self.provider_message_id,
            "notes": self.notes,
        }
