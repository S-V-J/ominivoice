# Cold Call Queue - External Dialer Handoff Contract

## Overview

This document defines the contract between OminiVoice's cold call queue system and external telephony systems (Twilio, SIP providers, etc.) for placing actual outbound calls.

The OminiVoice platform **does not place real PSTN calls**. Instead, it manages lead queues and hands off ready-to-dial entries to external systems via webhook notifications.

**NEW**: OminiVoice now supports **real-time WebSocket audio streaming** for external dialers. External systems can connect directly to an agent's voice pipeline via WebSocket, sending audio frames and receiving TTS audio in real-time. This enables full-duplex conversation with barge-in support.

---

## Connection Methods

### Method 1: Webhook Handoff (Traditional)
External dialer places PSTN call, sends call events via webhooks. OminiVoice does not handle audio.

### Method 2: WebSocket Audio Streaming (New - Recommended)
External dialer connects via WebSocket to OminiVoice's voice engine, streams audio in real-time. OminiVoice handles the full voice pipeline (VAD → STT → LLM → TTS).

**WebSocket Endpoint**: `wss://{domain}/ws?api_key=ov_live_...` (universal endpoint for all telephony systems)

---

## Handoff Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  OminiVoice     │     │  Webhook         │     │  External       │
│  Queue Worker   │────▶│  Notification    │────▶│  Dialer         │
│  (Celery Beat)  │     │  (HTTP POST)     │     │  (Twilio/SIP)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                       │                       │
         │                       │                       ▼
         │                       │              ┌─────────────────┐
         │                       │              │  PSTN Network   │
         │                       │              │  (Real Call)    │
         │                       │              └────────┬────────┘
         │                       │                       │
         │                       │                       ▼
         │              ┌──────────────────┐     ┌─────────────────┐
         │              │  Webhook         │     │  Call Logs &    │
         │              │  (Call Events)   │────▶│  Transcripts    │
         │              └──────────────────┘     └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────────────┐
│  OminiVoice Database (CallLog, QueueEntry)     │
└─────────────────────────────────────────────────┘
```

---

## Queue Entry Lifecycle

```
PENDING → QUEUED → IN_PROGRESS → COMPLETED/FAILED
                    │
                    ▼
         ┌───────────────────────┐
         │ External Dialer picks │
         │ up QUEUED entries     │
         └───────────────────────┘
```

| Status | Description | Next State |
|--------|-------------|------------|
| `PENDING` | Imported, waiting for queue worker | `QUEUED` |
| `QUEUED` | Picked by worker, handed to external dialer | `IN_PROGRESS` (via webhook) |
| `IN_PROGRESS` | External dialer placed call, call connected | `COMPLETED` / `FAILED` |
| `COMPLETED` | Call finished successfully | (terminal) |
| `FAILED` | Dialer error, no answer, busy, etc. | `PENDING` (retry) |

---

## Webhook Notifications

### 1. Entry Queued for Dialing

**Event**: `queue.entry.queued`

**Trigger**: Queue worker marks entry as `QUEUED` and creates `CallLog` stub.

**POST** `{webhook_url}/v1/queue/entry/queued`

```json
{
  "event": "queue.entry.queued",
  "timestamp": "2026-08-17T10:30:00Z",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "queue_entry": {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "contact_name": "John Doe",
    "phone_number": "+15551234567",
    "source": "csv_upload",
    "payload": {
      "email": "john@example.com",
      "company": "Acme Corp"
    }
  },
  "call_log": {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "status": "queued_for_external_dialer"
  },
  "agent_config": {
    "direction": "outbound",
    "opening_line": "Hi, this is Sarah from Acme Corp...",
    "voice_stack": "stack_a",
    "tts_engine": "kokoro",
    "tts_voice": "af_heart"
  }
}
```

**Expected Response**: `200 OK` within 5 seconds

```json
{
  "accepted": true,
  "dialer_call_id": "CA1234567890abcdef",
  "estimated_dial_time": "2026-08-17T10:30:05Z"
}
```

### 2. Call Started (Dialing)

**Event**: `call.started`

**Trigger**: External dialer initiated the call.

**POST** `{webhook_url}/v1/call/started`

```json
{
  "event": "call.started",
  "timestamp": "2026-08-17T10:30:05Z",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "call_log_id": "770e8400-e29b-41d4-a716-446655440002",
  "dialer_call_id": "CA1234567890abcdef",
  "direction": "outbound",
  "caller_ref": "+15551234567"
}
```

### 3. Call Answered

**Event**: `call.answered`

**Trigger**: Call was answered (human or voicemail detected).

**POST** `{webhook_url}/v1/call/answered`

```json
{
  "event": "call.answered",
  "timestamp": "2026-08-17T10:30:12Z",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "call_log_id": "770e8400-e29b-41d4-a716-446655440002",
  "dialer_call_id": "CA1234567890abcdef",
  "answered_by": "human",
  "duration_to_answer_seconds": 7
}
```

### 4. Call Progress Events

**Event**: `call.progress`

**Trigger**: Periodic updates during call (optional, for real-time dashboard).

**POST** `{webhook_url}/v1/call/progress`

```json
{
  "event": "call.progress",
  "timestamp": "2026-08-17T10:31:00Z",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "call_log_id": "770e8400-e29b-41d4-a716-446655440002",
  "dialer_call_id": "CA1234567890abcdef",
  "status": "in_progress",
  "duration_seconds": 48
}
```

### 5. Call Completed

**Event**: `call.completed`

**Trigger**: Call ended normally.

**POST** `{webhook_url}/v1/call/completed`

```json
{
  "event": "call.completed",
  "timestamp": "2026-08-17T10:35:22Z",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "call_log_id": "770e8400-e29b-41d4-a716-446655440002",
  "dialer_call_id": "CA1234567890abcdef",
  "status": "completed",
  "duration_seconds": 310,
  "ended_reason": "completed",
  "recording_url": "https://dialer.example.com/recordings/CA1234567890abcdef.mp3",
  "transcript": [
    {"role": "assistant", "text": "Hi, this is Sarah from Acme Corp...", "timestamp": "2026-08-17T10:30:12Z"},
    {"role": "user", "text": "Hello, what is this about?", "timestamp": "2026-08-17T10:30:15Z"},
    {"role": "assistant", "text": "I'm calling because we have a special offer...", "timestamp": "2026-08-17T10:30:18Z"}
  ]
}
```

### 6. Call Failed

**Event**: `call.failed`

**Trigger**: Call failed to connect or ended abnormally.

**POST** `{webhook_url}/v1/call/failed`

```json
{
  "event": "call.failed",
  "timestamp": "2026-08-17T10:30:45Z",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "call_log_id": "770e8400-e29b-41d4-a716-446655440002",
  "dialer_call_id": "CA1234567890abcdef",
  "status": "failed",
  "failure_reason": "no_answer",
  "failure_details": "Rang for 30 seconds, no answer",
  "retry_eligible": true
}
```

---

## Failure Reasons

| Reason | Description | Retry Eligible |
|--------|-------------|----------------|
| `no_answer` | Rang but no answer | Yes |
| `busy` | Line busy | Yes |
| `voicemail` | Reached voicemail | Yes (if configured) |
| `invalid_number` | Invalid phone format | No |
| `blocked` | Number blocked | No |
| `carrier_error` | Carrier/network error | Yes |
| `dialer_error` | Dialer internal error | Yes |
| `timeout` | Dial timeout | Yes |

---

## Authentication

All webhooks from external dialer to OminiVoice must include:

```
Authorization: Bearer ov_live_<32-char-api-key>
Content-Type: application/json
```

The API key is the agent's API key (same as used for other API calls).

---

## Retry Logic

### Queue Entry Retry
- Failed entries with `retry_eligible: true` are reset to `PENDING`
- `attempts` counter incremented
- Max retries: configurable per agent (default 3)
- Retry triggered by: `POST /agents/{id}/cold-call-queue/retry-failed`

### Webhook Delivery Retry
- External dialer should retry failed webhook deliveries
- Exponential backoff: 1s, 2s, 4s, 8s, 16s (max 5 attempts)
- Dead letter queue for permanently failed deliveries

---

## Security

### Webhook Signature Verification (Recommended)
```
X-Webhook-Signature: sha256=<hmac-sha256(payload, webhook_secret)>
```

### Rate Limiting
- OminiVoice accepts webhooks at up to 60/min per API key
- Excess requests return `429 Too Many Requests`

### IP Allowlist (Optional)
Configure allowed dialer IPs in firewall/security group.

---

## Testing the Integration

### 1. Mock Dialer for Development
```bash
# Use a simple HTTP server to receive webhooks
python -m http.server 8080
# Check received payloads in terminal
```

### 2. Stripe CLI for Webhook Testing
```bash
stripe listen --forward-to https://ominivoice.local/webhook/v1/queue/entry/queued
```

### 3. Test with curl
```bash
# Simulate entry queued
curl -X POST https://ominivoice.local/webhook/v1/queue/entry/queued \
  -H "Authorization: Bearer ov_live_abcdefghijklmnopqrstuvwxyz123456" \
  -H "Content-Type: application/json" \
  -d '{
    "event": "queue.entry.queued",
    "timestamp": "2026-08-17T10:30:00Z",
    "agent_id": "550e8400-e29b-41d4-a716-446655440000",
    "queue_entry": {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "contact_name": "Test User",
      "phone_number": "+15551234567",
      "source": "csv_upload",
      "payload": {}
    },
    "call_log": {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "status": "queued_for_external_dialer"
    }
  }'
```

---

## Implementation Checklist for External Dialer

- [ ] Receive `queue.entry.queued` webhook
- [ ] Parse agent config (opening_line, voice_stack, etc.)
- [ ] Place outbound call via Twilio/SIP
- [ ] Send `call.started` webhook
- [ ] On answer: send `call.answered` with `answered_by`
- [ ] During call: optional `call.progress` updates
- [ ] On end: send `call.completed` or `call.failed` with transcript/recording
- [ ] Handle retries with exponential backoff
- [ ] Verify webhook signatures
- [ ] Respect rate limits (60/min)

---

## Method 2: Universal Voice Agent WebSocket (New)

### Authentication

Connect to universal endpoint: `wss://{domain}/ws?api_key=ov_live_<32-char-key>`

Or with test token: `wss://{domain}/ws?token=<jwt-test-token>`

Get URLs/tokens via:
- `GET /api/agents/{id}/websocket-urls` - Returns local & internet WebSocket URLs
- `GET /api/agents/{id}/websocket-test-token` - Returns 1-hour test token

**Supported Systems**: Asterisk, FreeSWITCH, OpenSIPS, Twilio, custom SIP, WebRTC, any VoIP platform

### Protocol

**Audio Format:**
- Binary frames: int16, 16kHz, mono, 20ms frames (320 samples = 640 bytes)

**Message Flow:**
1. CONNECT → Server sends `ready` with session info
2. CLIENT → `config` with FULL agent configuration (REQUIRED)
3. SERVER → `started` with capabilities
4. EXCHANGE: Binary audio + JSON control messages
5. END → `end` → Server sends `ended`

**Control Messages (JSON text frames):**

| Type | Direction | Description |
|------|-----------|-------------|
| `ready` | Server→Client | Connection ready with session_id, protocol version |
| `config` | Client→Server | FULL agent configuration (REQUIRED - no portal setup) |
| `started` | Server→Client | Call started with capabilities |
| `transcript` | Server→Client | Real-time transcript updates |
| `state` | Server→Client | Pipeline state: `listening`, `processing`, `speaking`, `ended`, `error` |
| `dtmf_received` | Server→Client | DTMF digit received from SIP |
| `ended` | Server→Client | Call ended with full transcript & duration |
| `error` | Server→Client | Error with code and message |
| `ping`/`pong` | Both | Keep-alive |
| `end` | Client→Server | Request call termination |

### Config Message (Client→Server - First Message After Connect)

```json
{
  "type": "config",
  "data": {
    "direction": "outbound",
    "system_prompt": "You are Sarah, a friendly sales representative...",
    "voice_stack": "stack_a",
    "opening_line": "Hi, this is Sarah from Acme Corp...",
    "objective_prompt": "Schedule a 15-minute demo.",
    "objection_handling_prompt": "If not interested: 'I understand...'",
    "voicemail_prompt": "Hi, this is Sarah... Please call back.",
    "closing_prompt": "Great! I'll send a calendar invite.",
    "escalation_rule": "If asked for manager: 'I'll have my manager reach out.'",
    "interruption_sensitivity": "medium",
    "max_call_duration_s": 300,
    "silence_timeout_s": 10,
    "language": "en-US",
    "stt_engine": "faster-whisper",
    "tts_engine": "kokoro",
    "tts_voice": "af_heart",
    "llm_provider": "nvidia_integrate",
    "llm_model": "stepfun-ai/step-3.7-flash"
  }
}
```

For Stack B (NVIDIA NIM):
```json
{
  "type": "config",
  "data": {
    "direction": "outbound",
    "system_prompt": "...",
    "voice_stack": "stack_b",
    "chatterbox_voice": "Chatterbox-Multilingual.en-US.Female",
    "chatterbox_emotion_exaggeration": 0.5,
    "riva_asr_language": "en-US",
    "riva_vad_threshold": 0.5,
    "llm_provider": "nvidia_integrate",
    "llm_model": "stepfun-ai/step-3.7-flash"
  }
}
```

### Transcript Message (Server→Client)

```json
{
  "type": "transcript",
  "data": {
    "turn_id": 1,
    "role": "assistant",
    "text": "Hi, this is Sarah from Acme Corp...",
    "timestamp": "2026-08-17T10:30:12.123Z",
    "duration_ms": 2500,
    "interrupted": false
  }
}
```

### State Message (Server→Client)

```json
{
  "type": "state",
  "data": "listening"
}
```

### End Message (Server→Client)

```json
{
  "type": "end",
  "data": {
    "session_id": "uuid",
    "transcript": [...],
    "duration": 45.2
  }
}
```

### Example: Python WebSocket Dialer Integration

```python
# websocket_dialer.py
import asyncio
import websockets
import json
import numpy as np
import soundfile as sf

class WebSocketDialer:
    def __init__(self, agent_id, api_key, domain="ominivoice.local"):
        self.agent_id = agent_id
        # Common endpoint - agent_id sent in config message
        self.uri = f"wss://{domain}/ws?api_key={api_key}"
        self.ws = None
        self.audio_out_queue = asyncio.Queue()

    async def connect(self, config):
        self.ws = await websockets.connect(self.uri)
        
        # Send config first
        await self.ws.send(json.dumps({"type": "config", "data": config}))
        
        # Wait for started confirmation
        response = await self.ws.recv()
        msg = json.loads(response)
        if msg["type"] == "started":
            print(f"Call started: {msg['data']['session_id']}")
        elif msg["type"] == "error":
            raise Exception(msg["data"]["message"])

    async def send_audio(self, audio_int16: np.ndarray):
        """Send int16 audio frames (16kHz, mono, 20ms chunks)."""
        if self.ws and self.ws.open:
            await self.ws.send(audio_int16.tobytes())

    async def receive_messages(self):
        """Handle incoming messages from OminiVoice."""
        async for message in self.ws:
            if isinstance(message, bytes):
                # Audio from TTS - play or save
                audio_int16 = np.frombuffer(message, dtype=np.int16)
                await self.audio_out_queue.put(audio_int16)
            else:
                # Control message
                msg = json.loads(message)
                await self.handle_control_message(msg)

    async def handle_control_message(self, msg):
        if msg["type"] == "transcript":
            turn = msg["data"]
            print(f"[{turn['role'].upper()}] {turn['text']}")
        elif msg["type"] == "state":
            print(f"Pipeline state: {msg['data']}")
        elif msg["type"] == "end":
            print(f"Call ended. Duration: {msg['data']['duration']:.1f}s")
            return False  # Stop loop
        elif msg["type"] == "error":
            print(f"Error: {msg['data']['message']}")
            return False
        return True

    async def run_call(self, config, audio_input_generator):
        """Main call loop."""
        await self.connect(config)
        
        # Start receiver task
        receiver_task = asyncio.create_task(self.receive_messages())
        
        # Send audio frames
        async for audio_chunk in audio_input_generator:
            if not self.ws or not self.ws.open:
                break
            await self.send_audio(audio_chunk)
        
        # End call
        if self.ws and self.ws.open:
            await self.ws.send(json.dumps({"type": "end"}))
        
        await receiver_task
        await self.ws.close()


# Usage example
async def main():
    dialer = WebSocketDialer(
        agent_id="550e8400-e29b-41d4-a716-446655440000",
        api_key="ov_live_abcdefghijklmnopqrstuvwxyz123456"
    )
    
    config = {
        "direction": "outbound",
        "system_prompt": "You are Sarah, a friendly sales representative...",
        "voice_stack": "stack_a",
        "opening_line": "Hi, this is Sarah from Acme Corp...",
        "objective_prompt": "Schedule a 15-minute demo.",
        # ... other fields
    }
    
    # Example: stream audio from a file or SIP/RTP
    async def audio_from_file():
        data, sr = sf.read("input.wav", dtype='int16')
        # Resample to 16kHz if needed
        # Chunk into 20ms frames (320 samples)
        for i in range(0, len(data), 320):
            chunk = data[i:i+320]
            if len(chunk) < 320:
                chunk = np.pad(chunk, (0, 320 - len(chunk)))
            yield chunk
            await asyncio.sleep(0.02)  # 20ms real-time pacing
    
    await dialer.run_call(config, audio_from_file())

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Example: Twilio Integration (Webhook Method)

```python
# twilio_dialer.py
from twilio.rest import Client
import requests

class TwilioDialer:
    def __init__(self, account_sid, auth_token, ominivoice_webhook_base, api_key):
        self.client = Client(account_sid, auth_token)
        self.webhook_base = ominivoice_webhook_base
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def dial(self, queue_entry, agent_config):
        # 1. Notify OminiVoice: call started
        self._send_webhook("call.started", {
            "agent_id": queue_entry["agent_id"],
            "call_log_id": queue_entry["call_log_id"],
            "dialer_call_id": None,  # Will be filled after create
            "direction": "outbound",
            "caller_ref": queue_entry["phone_number"]
        })

        # 2. Place call via Twilio
        call = self.client.calls.create(
            to=queue_entry["phone_number"],
            from_=agent_config.get("twilio_from_number", "+15550000000"),
            url=f"{self.webhook_base}/twilio/voice",
            status_callback=f"{self.webhook_base}/twilio/status",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            record=True,
            recording_channels="dual"
        )

        # 3. Update with dialer_call_id
        self._send_webhook("call.started", {
            "agent_id": queue_entry["agent_id"],
            "call_log_id": queue_entry["call_log_id"],
            "dialer_call_id": call.sid,
            "direction": "outbound",
            "caller_ref": queue_entry["phone_number"]
        })

    def _send_webhook(self, event, payload):
        payload["event"] = event
        payload["timestamp"] = datetime.utcnow().isoformat() + "Z"
        requests.post(
            f"{self.webhook_base}/{event.replace('.', '/')}",
            json=payload,
            headers=self.headers,
            timeout=5
        )
```

---

## Support

For integration questions or issues:
- GitHub: https://github.com/S-V-J/ominivoice/issues
- Email: stjl093@gmail.com
- Documentation: https://github.com/S-V-J/ominivoice/docs