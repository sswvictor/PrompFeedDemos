from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.booking import Booking
from app.models.customer import Customer
from app.models.invoice import Invoice


class InvoiceService:

    @staticmethod
    def _get_next_invoice_number(db: Session, provider_id: str) -> int:
        max_num = db.query(func.max(Invoice.invoice_number)).filter(
            Invoice.provider_id == provider_id
        ).scalar()
        return (max_num or 0) + 1

    @staticmethod
    def create_invoice_from_booking(db: Session, booking_id: str) -> Invoice:
        booking = db.query(Booking).filter(Booking.booking_id == booking_id).first()
        if not booking:
            raise ValueError(f"Booking {booking_id} not found")

        # Check if invoice already exists for this booking
        existing = db.query(Invoice).filter(Invoice.booking_id == booking_id).first()
        if existing:
            raise ValueError(f"Invoice already exists for booking {booking_id}")

        customer = db.query(Customer).filter(Customer.customer_id == booking.customer_id).first()
        invoice_number = InvoiceService._get_next_invoice_number(db, booking.provider_id)

        invoice = Invoice(
            provider_id=booking.provider_id,
            booking_id=booking.booking_id,
            customer_id=booking.customer_id,
            customer_email=customer.customer_email if customer else None,
            invoice_number=invoice_number,
            total_ex_vat=booking.total_amount_ex_vat,
            total_vat=booking.total_vat_amount,
            total_inc_vat=booking.total_amount_inc_vat,
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def get_invoice(db: Session, invoice_id: str) -> Invoice | None:
        return db.query(Invoice).filter(Invoice.invoice_id == invoice_id).first()

    @staticmethod
    def list_invoices_by_provider(db: Session, provider_id: str) -> list[Invoice]:
        return db.query(Invoice).filter(Invoice.provider_id == provider_id).order_by(Invoice.issued_date.desc()).all()

    @staticmethod
    def update_status(db: Session, invoice_id: str, new_status: str) -> Invoice:
        invoice = InvoiceService.get_invoice(db, invoice_id)
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        valid = {"draft", "sent", "paid"}
        if new_status not in valid:
            raise ValueError(f"Invalid status: {new_status}")
        invoice.status = new_status
        db.commit()
        db.refresh(invoice)
        return invoice
