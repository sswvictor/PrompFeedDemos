import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite:///./chat_runtime_test.db")

import app.models  # noqa: F401
from app.db.session import Base, SessionLocal, engine
from app.models.conversation import Conversation
from app.models.conversation_state import ConversationState
from app.models.customer import Customer
from app.models.provider import Provider
from app.models.service import Service
from app.orchestrators.base import process_message
from app.orchestrators.platform_tools import execute_platform_tool
from app.services.chat_runtime import ChatRuntimeService
from app.services.conversation_service import ConversationService
from app.services.conversation_state_service import ConversationStateService


class ChatRuntimeTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def _create_provider(self, name="Test Provider"):
        provider = Provider(name=name)
        self.db.add(provider)
        self.db.commit()
        self.db.refresh(provider)
        return provider

    def _create_customer(self, provider_id, email=None, name=None):
        customer = Customer(
            provider_id=provider_id,
            customer_number=1,
            customer_email=email,
            display_name=name,
            source_channel="web",
        )
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def _create_service(self, provider_id, name="Haircut"):
        service = Service(
            provider_id=provider_id,
            name=name,
            duration_minutes=60,
            price_ex_vat=400.0,
            vat_percent=25.0,
        )
        self.db.add(service)
        self.db.commit()
        self.db.refresh(service)
        return service

    async def test_provider_runtime_routes_to_provider_orchestrator(self):
        provider = self._create_provider()
        customer = self._create_customer(provider.provider_id)

        with patch("app.services.chat_runtime.process_message", new=AsyncMock(return_value="provider reply")) as provider_mock, patch(
            "app.services.chat_runtime.platform_process_message", new=AsyncMock(return_value="platform reply")
        ) as platform_mock:
            result = await ChatRuntimeService.handle_message(
                db=self.db,
                mode="provider",
                channel="web",
                thread_id="web-thread-1",
                text="hello",
                provider_id=provider.provider_id,
                customer_id=customer.customer_id,
            )

        self.assertEqual(result.reply, "provider reply")
        provider_mock.assert_awaited_once()
        platform_mock.assert_not_called()
        state = self.db.query(ConversationState).filter_by(conversation_id=result.conversation_id).one()
        self.assertEqual(state.mode, "provider")
        self.assertEqual(state.selected_provider_id, provider.provider_id)

    async def test_platform_runtime_routes_to_platform_orchestrator(self):
        with patch("app.services.chat_runtime.process_message", new=AsyncMock(return_value="provider reply")) as provider_mock, patch(
            "app.services.chat_runtime.platform_process_message", new=AsyncMock(return_value="platform reply")
        ) as platform_mock:
            result = await ChatRuntimeService.handle_message(
                db=self.db,
                mode="platform",
                channel="web",
                thread_id="platform-thread-1",
                text="find me balayage in stockholm",
            )

        self.assertEqual(result.reply, "platform reply")
        platform_mock.assert_awaited_once()
        provider_mock.assert_not_called()
        state = self.db.query(ConversationState).filter_by(conversation_id=result.conversation_id).one()
        self.assertEqual(state.mode, "platform")
        conv = self.db.query(Conversation).filter_by(conversation_id=result.conversation_id).one()
        self.assertEqual(conv.conversation_type, "discovery")

    async def test_runtime_stops_after_handoff_requested(self):
        provider = self._create_provider()
        customer = self._create_customer(provider.provider_id)
        conversation = ConversationService.get_or_create_conversation(
            db=self.db,
            provider_id=provider.provider_id,
            channel="web",
            external_thread_id="handoff-thread",
            customer_id=customer.customer_id,
        )
        ConversationStateService.get_or_create_state(
            self.db,
            conversation.conversation_id,
            mode="provider",
            provider_id=provider.provider_id,
        )
        ConversationStateService.mark_handoff_requested(self.db, conversation.conversation_id)

        with patch("app.services.chat_runtime.process_message", new=AsyncMock(return_value="should not run")) as provider_mock:
            result = await ChatRuntimeService.handle_message(
                db=self.db,
                mode="provider",
                channel="web",
                thread_id="handoff-thread",
                text="hello again",
                provider_id=provider.provider_id,
                customer_id=customer.customer_id,
            )

        provider_mock.assert_not_called()
        self.assertIn("already", result.reply.lower())

    async def test_provider_handoff_is_persisted(self):
        provider = self._create_provider()
        customer = self._create_customer(provider.provider_id)
        conversation = ConversationService.get_or_create_conversation(
            db=self.db,
            provider_id=provider.provider_id,
            channel="web",
            external_thread_id="provider-human-thread",
            customer_id=customer.customer_id,
        )

        reply = await process_message(
            db=self.db,
            provider_id=provider.provider_id,
            customer_id=customer.customer_id,
            conversation_id=conversation.conversation_id,
            text="I want to talk to a human",
        )

        state = ConversationStateService.get_state(self.db, conversation.conversation_id)
        self.assertEqual(state.handoff_status, "requested")
        self.assertIn("human", reply.lower())

    async def test_provider_confirmation_uses_structured_state(self):
        provider = self._create_provider()
        customer = self._create_customer(provider.provider_id, email="test@example.com")
        conversation = ConversationService.get_or_create_conversation(
            db=self.db,
            provider_id=provider.provider_id,
            channel="web",
            external_thread_id="provider-confirm-thread",
            customer_id=customer.customer_id,
        )
        ConversationStateService.get_or_create_state(
            self.db,
            conversation.conversation_id,
            mode="provider",
            provider_id=provider.provider_id,
        )
        ConversationStateService.update_selection(
            self.db,
            conversation.conversation_id,
            provider_id=provider.provider_id,
            service_name="Haircut",
            date="2026-03-20",
            time="14:00",
            booking_status="pending",
        )

        with patch("app.orchestrators.base.execute_tool", new=AsyncMock(return_value="booked")) as execute_mock:
            reply = await process_message(
                db=self.db,
                provider_id=provider.provider_id,
                customer_id=customer.customer_id,
                conversation_id=conversation.conversation_id,
                text="yes please",
            )

        self.assertEqual(reply, "booked")
        execute_mock.assert_awaited_once()
        args = execute_mock.await_args.args
        self.assertEqual(args[0], "book_appointment")
        self.assertEqual(args[1]["service_name"], "Haircut")
        self.assertEqual(args[1]["date"], "2026-03-20")
        self.assertEqual(args[1]["time"], "14:00")

    async def test_provider_contact_capture_is_persisted_once(self):
        provider = self._create_provider()
        customer = self._create_customer(provider.provider_id)
        conversation = ConversationService.get_or_create_conversation(
            db=self.db,
            provider_id=provider.provider_id,
            channel="web",
            external_thread_id="provider-contact-thread",
            customer_id=customer.customer_id,
        )
        ConversationStateService.get_or_create_state(
            self.db,
            conversation.conversation_id,
            mode="provider",
            provider_id=provider.provider_id,
        )
        ConversationStateService.mark_contact_requested(self.db, conversation.conversation_id)

        reply = await process_message(
            db=self.db,
            provider_id=provider.provider_id,
            customer_id=customer.customer_id,
            conversation_id=conversation.conversation_id,
            text="My name is Jane Doe jane@example.com",
        )

        self.assertIn("jane@example.com", reply)
        refreshed_customer = self.db.query(Customer).filter_by(customer_id=customer.customer_id).one()
        self.assertEqual(refreshed_customer.customer_email, "jane@example.com")
        state = ConversationStateService.get_state(self.db, conversation.conversation_id)
        self.assertEqual(state.contact_email, "jane@example.com")
        self.assertIsNotNone(state.contact_received_at)

    async def test_platform_provider_selection_is_persisted(self):
        provider = self._create_provider()
        conversation = ConversationService.get_or_create_discovery_conversation(
            db=self.db,
            user_id="platform-user-1",
            channel="web",
            external_thread_id="platform-selection-thread",
        )
        ConversationStateService.get_or_create_state(self.db, conversation.conversation_id, mode="platform")

        await execute_platform_tool(
            "get_provider_details",
            {"provider_id": provider.provider_id},
            db=self.db,
            conversation_id=conversation.conversation_id,
        )

        state = ConversationStateService.get_state(self.db, conversation.conversation_id)
        self.assertEqual(state.selected_provider_id, provider.provider_id)

    async def test_platform_booking_requires_selected_provider(self):
        provider = self._create_provider()
        service = self._create_service(provider.provider_id)
        conversation = ConversationService.get_or_create_discovery_conversation(
            db=self.db,
            user_id="platform-user-2",
            channel="web",
            external_thread_id="platform-booking-thread-1",
        )
        ConversationStateService.get_or_create_state(self.db, conversation.conversation_id, mode="platform")

        reply = await execute_platform_tool(
            "book_with_provider",
            {
                "provider_id": provider.provider_id,
                "service_id": service.service_id,
                "date": "2026-03-21",
                "time": "10:00",
                "customer_name": "Jane",
                "customer_email": "jane@example.com",
            },
            db=self.db,
            conversation_id=conversation.conversation_id,
        )

        self.assertIn("confirm which provider", reply.lower())

    async def test_platform_booking_confirms_selected_provider(self):
        provider = self._create_provider()
        service = self._create_service(provider.provider_id)
        customer = self._create_customer(provider.provider_id, email="jane@example.com", name="Jane")
        conversation = ConversationService.get_or_create_discovery_conversation(
            db=self.db,
            user_id="platform-user-3",
            channel="web",
            external_thread_id="platform-booking-thread-2",
        )
        ConversationStateService.get_or_create_state(self.db, conversation.conversation_id, mode="platform")
        ConversationStateService.update_selection(
            self.db,
            conversation.conversation_id,
            provider_id=provider.provider_id,
            booking_status="none",
        )

        with patch("app.orchestrators.platform_tools.AvailabilityService.check_slot_available", return_value=True), patch(
            "app.orchestrators.platform_tools.BookingService.create_booking",
            return_value=SimpleNamespace(booking_id="booking-1", booking_number="BK-1"),
        ), patch(
            "app.orchestrators.platform_tools.CustomerService.find_by_email_and_provider",
            return_value=customer,
        ):
            reply = await execute_platform_tool(
                "book_with_provider",
                {
                    "provider_id": provider.provider_id,
                    "service_id": service.service_id,
                    "date": "2026-03-21",
                    "time": "10:00",
                    "customer_name": "Jane",
                    "customer_email": "jane@example.com",
                },
                db=self.db,
                conversation_id=conversation.conversation_id,
            )

        self.assertIn("booked", reply.lower())
        state = ConversationStateService.get_state(self.db, conversation.conversation_id)
        self.assertEqual(state.booking_status, "confirmed")
        self.assertEqual(state.selected_provider_id, provider.provider_id)
        self.assertEqual(state.contact_email, "jane@example.com")


if __name__ == "__main__":
    unittest.main()
