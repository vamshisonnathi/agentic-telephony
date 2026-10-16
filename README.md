# Agentic Telephony

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

A Python framework for autonomous phone calling and receiving with Vapi and Retell AI.

Most voice agent demos fail the moment they hit an actual phone line. A recipient interrupts with "who is this?", the agent reboots its 20-word pitch from the beginning, repeats full item descriptions on every turn instead of using pronouns, and hangs up the second someone says "yes" without confirming an address or asking for a text confirmation.

Agentic Telephony wraps voice telephony providers with conversation protocols designed for real phone interactions: recovery from interruptions, pronoun tracking, quick price sanity checks, and logistical closure.

---

## Core design

- Pluggable provider architecture with unified interfaces for Vapi and Retell AI (`TELEPHONY_PROVIDER=vapi` or `retell`).
- The 4-Pillar Transaction Protocol:
  - Interruption recovery: opens with a concise greeting and recovers cleanly if interrupted, without restarting the initial pitch.
  - Pronoun fidelity: keeps conversational turns under 15 words and refers back to items using natural pronouns ("them", "those", "that") rather than repeating verbose product titles.
  - Micro-math and sanity checks: calculates running totals aloud ("sounds good, so roughly $30 total") and checks physical constraints like pickup windows and holds.
  - Logistical closure: requests text confirmations to the caller ID and validates location details before concluding the call.
- Thread-safe call state tracker storing live utterances, timestamps, call status, and post-call summaries.
- Webhook receiver (FastAPI with Starlette fallback) handling provider lifecycle callbacks, status updates, and speech events.
- WebSocket endpoint streaming real-time speech events and utterances to external dashboards or terminal clients.
- Pre-built tool definitions compatible with CrewAI, LangChain, and LangGraph.

---

## Architecture

```mermaid
flowchart TD
    User([User / Agent Goal]) --> Engine[TelephonyEngine]
    
    subgraph Core Framework
        Engine --> Protocol[4-Pillar Protocol & Prompt Builder]
        Engine --> Tracker[Thread-Safe CallStateTracker]
        Protocol --> Router{Provider Router}
    end

    subgraph Telephony Backends
        Router -->|TELEPHONY_PROVIDER=vapi| Vapi[Vapi AI Provider]
        Router -->|TELEPHONY_PROVIDER=retell| Retell[Retell AI Provider]
    end

    subgraph Real World
        Vapi --> PSTN((Carrier / PSTN))
        Retell --> PSTN
        PSTN --> Callee[Vendor / Restaurant / Contact]
    end

    subgraph Inbound & Webhooks
        Callee -. Spoken Audio .-> PSTN
        Vapi -. Real-time Events .-> WebhookServer[FastAPI Webhook Server]
        Retell -. Call Reports .-> WebhookServer
        WebhookServer --> WebSocket[WebSocket Live Transcripts]
        WebhookServer --> Tracker
    end
```

---

## Getting started

### 1. Installation

```bash
git clone https://github.com/vamshisonnathi/agentic-telephony.git
cd agentic-telephony
pip install -r requirements.txt
```

### 2. Configure environment

Copy `.env.example` to `.env` and configure your credentials:

```bash
cp .env.example .env
```

```ini
# Choose provider: "vapi" or "retell"
TELEPHONY_PROVIDER=vapi

# Vapi Credentials (https://vapi.ai)
VAPI_API_KEY=your_vapi_api_key_here
VAPI_PHONE_NUMBER_ID=your_vapi_phone_number_id_here

# Caller defaults
CALLER_NAME=Alex
CALLER_PHONE=+15551234567
DEFAULT_LOCATION=Dallas, TX

# Security
API_SECRET_KEY=your_secret_api_key_here
WEBHOOK_SECRET=your_shared_webhook_secret_here

# Legal compliance (two-party / all-party consent notice)
DISCLOSE_RECORDING=true
```

### 3. Place an outbound call

```python
from agentic_telephony import telephony_engine

call = telephony_engine.place_call(
    phone_number="+15551234567",
    target_name="Luigi's Pizza",
    objective="Ask if they have gluten-free pasta available tonight and check the price.",
    spoken_brief="1. Ask for gluten-free options. 2. Inquire about pricing. 3. Ask for text confirmation.",
    category="general_inquiry"
)

print(f"Call dispatched! ID: {call['call_id']}")
```

---

## Webhook server

To receive live speech transcripts and post-call reports, launch the webhook server:

```bash
python examples/02_inbound_receiving_server.py
```

Expose port 8000 using a tunnel (such as Cloudflare Tunnel or ngrok):

```bash
cloudflared tunnel --url http://localhost:8000
# or: ngrok http 8000
```

Set the public URL in your Vapi or Retell dashboard as your Webhook URL:
- Vapi: `https://your-domain.trycloudflare.com/webhook/vapi`
- Retell: `https://your-domain.trycloudflare.com/webhook/retell`

### Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/webhook/vapi` | `POST` | Ingestion endpoint for Vapi speech transcripts and call reports |
| `/webhook/retell` | `POST` | Ingestion endpoint for Retell AI call lifecycle events |
| `/api/calls/dispatch` | `POST` | REST API to trigger an autonomous outbound call |
| `/api/calls/active` | `GET` | List all currently active or ringing calls |
| `/api/calls/{call_id}` | `GET` | Fetch real-time transcript and post-call AI summary |
| `/api/calls/{call_id}/end` | `POST` | Hang up an active call |
| `/ws/calls/{call_id}` | `WebSocket` | Real-time WebSocket stream for turn-by-turn utterances |

---

## Security and authentication

Exposing your webhook server to the public internet without credentials exposes billable call-dispatch triggers and private transcript data. Agentic Telephony supports shared-secret authorization across both REST endpoints and webhook listeners:

- REST API security: Set `API_SECRET_KEY` in your `.env`. When configured, requests to `/api/*` must supply either an `X-API-Key: <key>` header or `Authorization: Bearer <key>`. Requests without a valid key receive a `401 Unauthorized`.
- Webhook signature and secret verification: Set `WEBHOOK_SECRET` in `.env` and configure the identical secret in your Vapi or Retell dashboard. Inbound webhook deliveries to `/webhook/vapi` (`x-vapi-secret`) or `/webhook/retell` (`x-retell-secret`) are validated before payloads are ingested into the state tracker.
- CORS configuration: Permissive origins (`*`) disable credentials to prevent browser security exceptions and credential leakage.

---

## Multi-agent integration

Pre-built tools (`PlaceOutboundCallTool`, `CheckCallStatusTool`, `EndCallTool`) can be passed directly to CrewAI agents, LangChain tool callers, or LangGraph graphs:

```python
from crewai import Agent
from agentic_telephony import (
    PlaceOutboundCallTool,
    CheckCallStatusTool,
    EndCallTool,
)

phone_agent = Agent(
    role="Concierge Phone Operator",
    goal="Dial local businesses, inquire about availability, and verify logistics.",
    backstory="You are an articulate, courteous phone operator making natural calls.",
    tools=[PlaceOutboundCallTool(), CheckCallStatusTool(), EndCallTool()],
    verbose=True,
)
```

---

## Known limitations

- Hold silence timeout: When placed on hold in total silence for longer than 25 to 30 seconds, carrier silence detection or provider timeouts can trigger an accidental hangup or an unprompted retry prompt. Handling silent holds reliably without background hold music detection remains an open challenge.
- Live operator handoff: There is currently no mid-call SIP transfer bridge or warm handoff mechanism to transfer an in-progress call to a human operator when negotiation fails or human intervention is required.

---

## Acceptable use and legal compliance

This framework dials real-world PSTN telephone numbers and interacts with human beings. Maintainers and deployers are responsible for complying with federal, state, and international telephony laws:

- FCC & TCPA regulations: In February 2024, the FCC issued a declaratory ruling confirming that AI-generated voices in outbound telephone calls are considered "artificial voices" under the Telephone Consumer Protection Act (TCPA). Unsolicited automated calls or marketing robocalls to mobile devices without prior express written consent carry statutory civil damages ranging from $500 to $1,500 per violation. This library is intended exclusively for consented, user-initiated transactional inquiries (such as verifying merchant hours, inventory checks, or customer-directed appointments).
- AI disclosure and transparency: Under California SB 1001 and emerging state statutes, automated systems communicating with consumers must disclose their artificial nature when requested. The system prompts in `agentic_telephony/protocol.py` explicitly instruct the model to identify itself honestly as an AI assistant on behalf of the user when asked and strictly prohibit claiming to be a human.
- All-party call recording consent: In the United States, roughly a dozen jurisdictions (including California, Florida, Illinois, Pennsylvania, Washington, Massachusetts, and Michigan) require the consent of all parties on a call before recording. Because voice telephony platforms record audio by default, `agentic-telephony` includes a configurable first-turn disclosure (`DISCLOSE_RECORDING=true` by default) instructing the agent to state: *"Quick heads up, this call is recorded."* before proceeding. If you disable this flag, ensure you operate exclusively within one-party consent jurisdictions or implement equivalent disclosures.

---

## Testing

Run the test suite:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## License

This project is licensed under the [MIT License](LICENSE).
