# Service Booking Bot

This bot is built with Rasa Flows and custom actions. It is designed for a simple service-booking experience: users ask for a service in a location, the assistant returns recommendations, and then provides booking guidance for a selected option.

## What is in this folder

The core runtime logic is in `actions/actions.py`, including GPT calls and local turn-history persistence. Flow behavior is defined in `data/flows.yml` and `data/patterns.yml`. Conversation state and response templates live in `domain.yml`, while runtime wiring is split between `config.yml`, `endpoints.yml`, and `credentials.yml`.

## Requirements

You need Python 3.10+ and `pip`. The project expects an OpenAI key through `OPENAI_API_KEY`.

## Setup

Run all commands from `my-rasa-assistant/bot`.

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `.env` from the template and set your key:

```bash
Copy-Item .env.example .env
```

```env
OPENAI_API_KEY=your_key_here
```

## Typical workflow

If you only need model prep and visual inspection, this is enough:

```bash
rasa train
rasa inspect
```

If you want to run real conversations, start both services. The action server is required because the flows call custom actions.

```bash
rasa run actions
```

```bash
rasa run --enable-api --cors "*"
```

For CLI testing:

```bash
rasa shell
```

## GPT turn history

GPT outputs are written to a local JSONL file for each turn.  
Default path: `history/gpt_dialog_history.jsonl` (relative to `my-rasa-assistant/bot`).  
You can override it with `GPT_HISTORY_FILE`.

Each line contains timestamp, tag, sender id, user text, and assistant text. Current tags are:

- `recommendations`
- `selection_extraction`
- `booking_info`

History can be read via `read_gpt_history(tag: str = None, limit: int = 100)` in `actions/actions.py`.

## Troubleshooting

If you see `OPENAI_API_KEY not found`, verify `.env` is present and correctly formatted.  
If `train` and `inspect` work but runtime fails, the action server is usually not running.  
If ports are already in use, start Rasa services on different ports or stop conflicting processes.

## Licensing

This project currently depends on `rasa-pro` (see `requirements.txt`), which is licensed separately by Rasa.  
Before syncing to a company repository or deploying in shared environments, confirm your organization has a valid Rasa Pro license/subscription and follows your internal compliance process.
