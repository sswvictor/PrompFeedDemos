import os
import logging
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Text, Tuple

import openai
from dotenv import load_dotenv
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

load_dotenv()
logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent.parent
HISTORY_FILE = Path(os.getenv("GPT_HISTORY_FILE", str(BASE_DIR / "history" / "gpt_dialog_history.jsonl")))


def call_gpt(prompt: str, system_prompt: str = None, max_tokens: int = 500, temperature: float = 0.7) -> str:
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not found")
            return "Sorry, I'm having trouble connecting to the service."
        
        client = openai.OpenAI(api_key=api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"GPT API error: {str(e)}")
        return "Sorry, I encountered an error."


def append_gpt_history(
    *,
    tag: str,
    tracker: Tracker,
    user_message: str,
    gpt_response: str,
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tag": tag,
        "sender_id": tracker.sender_id,
        "turn": {
            "user": user_message,
            "assistant": gpt_response,
        },
    }
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        with HISTORY_FILE.open("a", encoding="utf-8") as file_handle:
            file_handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.error(f"Failed to append GPT history: {e}")


def read_gpt_history(tag: str = None, limit: int = 100) -> List[Dict[str, Any]]:
    if limit <= 0 or not HISTORY_FILE.exists():
        return []

    records: List[Dict[str, Any]] = []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as file_handle:
            for line in file_handle:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                if tag and record.get("tag") != tag:
                    continue
                records.append(record)
    except Exception as e:
        logger.error(f"Failed to read GPT history: {e}")
        return []

    return records[-limit:]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _extract_number_choice(text: str) -> Optional[int]:
    normalized = _normalize(text)
    if not normalized:
        return None

    direct = re.fullmatch(r"(\d+)", normalized)
    if direct:
        return int(direct.group(1))

    labeled = re.search(r"\b(?:number|no\.?)\s*(\d+)\b", normalized)
    if labeled:
        return int(labeled.group(1))

    ordinal_map = {
        "first": 1,
        "second": 2,
        "third": 3,
        "fourth": 4,
        "fifth": 5,
    }
    for word, value in ordinal_map.items():
        if re.search(rf"\b{word}\b", normalized):
            return value

    return None


def _extract_recommendation_candidates(recommendations: str) -> List[Tuple[int, str]]:
    candidates: List[Tuple[int, str]] = []
    for line in recommendations.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(\d+)\.\s*(.+)$", line)
        if not match:
            continue
        index = int(match.group(1))
        right = match.group(2).strip()
        name = right.split(" - ", 1)[0].strip()
        if name:
            candidates.append((index, name))
    return candidates


def _resolve_selection_from_list(user_message: str, recommendations: str) -> Optional[str]:
    candidates = _extract_recommendation_candidates(recommendations)
    if not candidates:
        return None

    number = _extract_number_choice(user_message)
    if number is not None:
        for idx, name in candidates:
            if idx == number:
                return name

    normalized = _normalize(user_message)
    for _, name in candidates:
        if _normalize(name) in normalized:
            return name

    return None


def _classify_user_input(text: str) -> str:
    normalized = _normalize(text)
    if not normalized:
        return "other"

    if _extract_number_choice(normalized) is not None:
        return "selection"

    date_keywords = [
        "today",
        "tomorrow",
        "tonight",
        "next week",
        "next month",
        "this weekend",
        "next monday",
        "next tuesday",
        "next wednesday",
        "next thursday",
        "next friday",
        "next saturday",
        "next sunday",
    ]
    if any(keyword in normalized for keyword in date_keywords):
        return "date"

    if re.search(r"\b\d{1,2}[/-]\d{1,2}([/-]\d{2,4})?\b", normalized) or re.search(
        r"\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b", normalized
    ):
        return "date"

    generic_selection_markers = ["that one", "this one", "the one"]
    if any(marker in normalized for marker in generic_selection_markers):
        return "selection"

    return "other"


class ActionGetRecommendations(Action):
    def name(self) -> Text:
        return "action_get_recommendations"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        service_type = tracker.get_slot("service_type")
        location = tracker.get_slot("location")
        user_message = tracker.latest_message.get("text", "")
        existing_recommendations = tracker.get_slot("recommendations")
        message_type = _classify_user_input(user_message)

        if not service_type:
            logger.warning("service_type is missing")
            return []

        if not location:
            logger.warning("location is missing")
            return []

        if existing_recommendations and message_type in {"selection", "date"}:
            logger.info(
                "Skip recommendation regeneration because current input appears to be selection/date while list already exists."
            )
            return []

        system_prompt = (
            "Task: generate local service recommendations for a booking assistant."
        )

        prompt = f"""
        Service type: {service_type}
        Location: {location}

        Output rules:
        - Return 3 to 5 options.
        - One line per option.
        - Format each line as: <index>. <business_name> - <short description> - <reason>.
        - Keep names specific and location-relevant.
        - Do not include preface text or role labels.
        """

        recommendations = call_gpt(prompt, system_prompt, max_tokens=600)
        append_gpt_history(
            tag="recommendations",
            tracker=tracker,
            user_message=user_message,
            gpt_response=recommendations,
        )

        return [
            SlotSet("recommendations", recommendations),
            SlotSet("service_type", service_type),
            SlotSet("location", location)
        ]


class ActionSelectRecommendation(Action):
    def name(self) -> Text:
        return "action_select_recommendation"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        user_message = tracker.latest_message.get("text", "")
        message_type = _classify_user_input(user_message)
        if message_type == "date":
            logger.warning(f"Selection step received date-like input, skipping extraction: {user_message}")
            return []

        recommendations = tracker.get_slot("recommendations")

        if not recommendations:
            logger.warning("No recommendations available")
            return []

        resolved_name = _resolve_selection_from_list(user_message, recommendations)
        if resolved_name:
            append_gpt_history(
                tag="selection_extraction",
                tracker=tracker,
                user_message=user_message,
                gpt_response=resolved_name,
            )
            logger.info(f"Resolved business_name without GPT: {resolved_name}")
            return [SlotSet("business_name", resolved_name)]

        system_prompt = (
            "Task: resolve the selected business from user input."
        )

        prompt = f"""
        Recommendation list:
        {recommendations}

        User input:
        "{user_message}"

        Resolution rules:
        - If user gives a number, map it to that index in the list.
        - If user gives a business name, return the matched name from the list.
        - If input is ambiguous, return "unknown".

        Output:
        - Return only the business name or "unknown".
        - No extra text.
        """

        business_name = call_gpt(prompt, system_prompt, max_tokens=100, temperature=0.3)
        append_gpt_history(
            tag="selection_extraction",
            tracker=tracker,
            user_message=user_message,
            gpt_response=business_name,
        )

        business_name = business_name.strip().replace('"', '').replace("'", "")

        if business_name.lower() in ["unknown", "sorry", "error", "not found"]:
            logger.warning(f"Could not extract business name from: {user_message}")
            return []

        logger.info(f"Extracted business_name: {business_name}")

        return [SlotSet("business_name", business_name)]


class ActionBookAppointment(Action):
    def name(self) -> Text:
        return "action_book_appointment"
    
    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        service_type = tracker.get_slot("service_type")
        location = tracker.get_slot("location")
        business_name = tracker.get_slot("business_name")
        date = tracker.get_slot("date")

        if not business_name:
            logger.warning("business_name is missing, cannot generate booking info")
            return []

        system_prompt = (
            "Task: provide practical booking guidance."
        )

        date_info = f" on {date}" if date else ""
        location_info = f" in {location}" if location else ""

        prompt = f"""
        Business: {business_name}
        Service type: {service_type}
        Location: {location or "not provided"}
        Date: {date or "not provided"}

        Output rules:
        - Include booking channels (website, phone, or equivalent).
        - Include contact details when known.
        - Provide 2 to 3 concise booking tips.
        - Keep the result short and actionable.
        - No preface text.
        """

        booking_info = call_gpt(prompt, system_prompt, max_tokens=300)
        append_gpt_history(
            tag="booking_info",
            tracker=tracker,
            user_message=tracker.latest_message.get("text", ""),
            gpt_response=booking_info,
        )

        return [SlotSet("booking_info", booking_info)]
