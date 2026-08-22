# OminiVoice System Architecture

## Overview

OminiVoice is a multi-tenant SaaS platform for configuring and testing AI voice agents. Users can create inbound/outbound voice agents with detailed prompt configurations, get API keys and webhook URLs, test agents via simulated WebRTC calls, and manage cold-calling lead queues with billing.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL CLIENTS                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │   Browser   │  │  External   │  │   Stripe    │  │   Email (SMTP)  │   │
│  │  (WebRTC)   │  │   Systems   │  │  (Webhooks) │  │                 │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘   │
└─────────┼────────────────┼────────────────┼──────────────────┼────────────┘
          │                │                │                  │
          ▼                ▼                ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              NGINX (Reverse Proxy)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │  Rate Limit │  │   SSL/TLS   │  │   Routing   │  │  Static Assets  │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘   │
└─────────┼────────────────┼────────────────┼──────────────────┼────────────┘
          │                │                │                  │
          ▼                ▼                ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI BACKEND (Port 8000)                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        API ROUTERS                                   │   │
│  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐  │   │
│  │  │ /auth  │ │/agents │ │ /api   │ │/billing│ │ /queue │ │/calls  │  │   │
│  │  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        CORE SERVICES                                 │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐  │   │
│  │  │ Auth (JWT)   │ │ Rate Limiter │ │ Email Sender │ │ Metrics    │  │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    VOICE ENGINE SUB-APP (/demo)                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │              FULL-DUPLEX VOICE PIPELINE                     │    │   │
│  │  │  Audio In → VAD → STT → LLM → TTS → Audio Out              │    │   │
│  │  │       ↑              │              │                       │    │   │
│  │  │       └──── Barge-in ────────────────┘                       │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │                │                │                  │
          ▼                ▼                ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATA LAYER                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  PostgreSQL  │  │    Redis     │  │   MinIO/S3   │  │  Stripe      │   │
│  │  (Primary)   │  │ (Cache/Queue)│  │ (Audio Files)│  │  (Billing)   │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
          │                │                │                  │
          ▼                ▼                ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          BACKGROUND WORKERS                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Celery Beat  │  │ Queue Worker │  │ Billing Work │  │ Email Worker │   │
│  │ (Scheduler)  │  │ (Dialer)     │  │ (Stripe)     │  │ (SMTP)       │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. FastAPI Backend (`backend/app/`)

| Module | Responsibility |
|--------|----------------|
| `app/main.py` | App entry point, middleware, router mounting |
| `app/api/routers/` | REST endpoints (auth, agents, api_keys, billing, queue, call_logs) |
| `app/core/` | Config, database, security, logging, metrics, celery |
| `app/models/` | SQLAlchemy ORM models |
| `app/schemas/` | Pydantic request/response validation |
| `app/services/` | Business logic (LLM providers) |
| `app/tasks/` | Celery background tasks |
| `app/email/` | Email templates and sender |
| `app/api/deps.py` | FastAPI dependencies (auth, tenant isolation) |

### 2. Voice Engine (`voice_engine/`)

| Module | Responsibility |
|--------|----------------|
| `pipeline.py` | Full-duplex pipeline with barge-in |
| `stt.py` / `stt_riva.py` | STT interfaces (faster-whisper, Riva ASR) |
| `tts.py` / `tts_chatterbox.py` | TTS interfaces (Kokoro, Piper, Chatterbox) |
| `turn_detection.py` / `turn_detection_riva.py` | VAD + semantic endpointing |
| `telephony_adapter.py` | Abstract interface + browser WebRTC session |
| `demo_server.py` | FastAPI + WebSocket for simulated calls |
| `prompt_builder.py` | Direction-aware system prompt assembly |

### 3. Frontend (`frontend/src/`)

| Module | Responsibility |
|--------|----------------|
| `pages/` | Dashboard, AgentDetail, Settings, AboutDev, Account |
| `components/` | Layout, QueueTab, CallLogsTab, ProtectedRoute, StripeCheckout |
| `hooks/` | useAuth, useDemoCall (WebRTC audio handling) |
| `services/api.ts` | Axios client with JWT refresh interceptor |
| `store/` | Zustand stores (auth, agent, demoCall) |

### 4. Background Workers (`app/tasks/`)

| Task Module | Responsibilities |
|-------------|------------------|
| `queue_tasks.py` | Cold call queue processing, retry failed |
| `billing_tasks.py` | Stripe subscription sync |
| `email_tasks.py` | Verification, password reset, queue failures, invoices |
| `auth_tasks.py` | Cleanup expired refresh tokens |

---

## Data Models (PostgreSQL)

### Core Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `users` | Multi-tenant accounts | `id`, `email`, `hashed_password`, `plan`, `stripe_customer_id`, `is_verified` |
| `agents` | Voice agent configs | `id`, `owner_id`, `name`, `direction`, `status`, `voice_stack`, 14 prompt fields, engine configs |
| `agent_prompt_versions` | Prompt history | `agent_id`, `field_name`, `old_value`, `new_value`, `edited_at` |
| `api_keys` | Per-agent API auth | `agent_id`, `user_id`, `key_hash`, `key_prefix`, `webhook_url`, `is_active` |
| `call_logs` | Call transcripts & metadata | `agent_id`, `direction`, `caller_ref`, `transcript` (JSONB), `duration_s`, `status` |
| `cold_call_queue_entries` | Outbound queue | `agent_id`, `contact_name`, `phone_number`, `status`, `payload`, `call_log_id` |
| `subscriptions` | Stripe subscriptions | `user_id`, `stripe_subscription_id`, `plan`, `status`, `period_end` |
| `refresh_tokens` | JWT refresh token rotation | `user_id`, `token_hash`, `expires_at`, `revoked_at` |

### Enums

- `UserPlan`: free, starter, pro, enterprise
- `AgentDirection`: inbound, outbound
- `AgentStatus`: draft, active, paused, archived
- `VoiceStack`: stack_a (local), stack_b (NVIDIA NIM)
- `CallStatus`: initiated, ringing, answered, in_progress, completed, failed, busy, no_answer, voicemail, queued_for_external_dialer
- `QueueEntryStatus`: pending, queued, in_progress, completed, failed

---

## Voice Engine Pipeline

### Stack A (Local - CPU)

```
Audio Input (16kHz, 20ms frames)
    │
    ▼
VAD: Silero VAD (ONNX) → Speech probability per frame
    │
    ▼
Turn Detector: Silence timeout + semantic endpointing
    │  (high=350ms, medium=600ms, low=900ms + 500ms if incomplete)
    ▼
STT: faster-whisper (CTranslate2) → streaming interim + final transcripts
    │  (model: tiny/base/small/medium/large-v3, compute_type: int8/float16)
    ▼
LLM: NVIDIA Integrate API (stepfun-ai/step-3.7-flash) → streaming SSE tokens
    │  (temperature=1, top_p=0.95, max_tokens=16384, seed=42)
    ▼
TTS: Kokoro-82M (primary) / Piper (fallback) → streaming audio chunks
    │  (sample_rate: 24kHz, voices: af_heart, am_puck, bf_emma, etc.)
    ▼
Audio Output (WebRTC → browser speaker)
```

### Stack B (NVIDIA NIM - GPU Required)

```
Same pipeline, different engines:
- STT: Riva ASR (gRPC) → streaming
- VAD: Riva VAD (via ASR) → embedded in ASR stream
- TTS: Chatterbox TTS (gRPC) → streaming
- Requires: NGC_API_KEY, GPU, NIM containers
```

### Barge-In Flow

```
1. VAD detects user speech DURING TTS playback
2. Immediately: stop TTS audio output
3. Cancel in-flight LLM stream
4. Truncate conversation history to `spoken_so_far` (what was actually played)
5. Reset turn detector for fresh utterance
6. Start new STT segment for interruption
Target: <300ms end-to-end reaction time
```

---

## Authentication & Authorization

### JWT Tokens

- **Access Token**: 30 min, HS256, `sub`=user_id, `type`="access"
- **Refresh Token**: 7 days, HS256, `sub`=user_id, `type`="refresh", stored in HttpOnly cookie + DB
- **Email Tokens**: 24 hours, separate secret (`JWT_SECRET + "_email"`), `type`="email"

### Tenant Isolation

- All agent-scoped routes use `get_owned_agent` dependency
- Returns 404 (not 403) if agent doesn't belong to user
- Prevents existence leakage

### API Key Auth

- Format: `ov_live_<32 url-safe chars>`
- Stored: SHA-256 hash only
- Rate limit: 60 req/min per key via Redis
- Webhook URL: deterministic `https://domain/webhook/v1/agents/{agent_id}`

### Rate Limiting

| Endpoint | Limit | Storage |
|----------|-------|---------|
| Auth (login/register) | 5/min/IP | Redis |
| API (general) | 60/min/key | Redis |
| Webhook | 60/min/key | Redis |
| CSV Import | 5MB, MIME check | - |
| Email | 50/hour/user | In-memory token bucket |

---

## Billing (Stripe)

### Plans

| Plan | Agents | Minutes/Month | Queue Rows | Features |
|------|--------|---------------|------------|----------|
| Free | 3 | 100 | 0 | Basic prompts, simulated calls |
| Starter | 10 | 1,000 | 1,000 | AI rewrite, webhooks, history |
| Pro | Unlimited | 10,000 | Unlimited | Queue automation, priority support |
| Enterprise | Unlimited | Unlimited | Unlimited | SLA, custom integrations, SSO |

### Stripe Events Handled

- `checkout.session.completed` → create subscription
- `customer.subscription.created/updated/deleted` → sync local DB
- `invoice.payment_failed` → notify user
- `payment_method.attached` → save payment method

### Plan Gating

- `require_plan(min_plan)` dependency → 402 PAYMENT_REQUIRED with `X-Upgrade-Required` header
- Enforced on: agent creation, queue import, API rate limits

---

## Cold Call Queue

### Flow

```
1. Import CSV/JSON → validate phones (phonenumbers lib) → dedupe on (agent_id, phone)
2. Celery Beat (every 5 min) → process_cold_call_queue
3. For each agent: pull pending up to daily_call_cap
4. Mark QUEUED, create CallLog with status=QUEUED_FOR_EXTERNAL_DIALER
5. External dialer (Twilio/SIP) picks up via webhook
6. On call completion: webhook → update CallLog, queue entry status
```

### Webhook Handoff Contract

```json
POST /webhook/v1/agents/{agent_id}
{
  "event": "queue.entry.queued",
  "agent_id": "uuid",
  "queue_entry_id": "uuid",
  "contact_name": "John Doe",
  "phone_number": "+15551234567",
  "call_log_id": "uuid",
  "timestamp": "2026-08-17T10:30:00Z"
}
```

---

## API Endpoints Summary

### Authentication

- `POST /auth/register` - Register
- `POST /auth/login` - Login (sets refresh cookie)
- `POST /auth/refresh` - Refresh access token
- `POST /auth/logout` - Clear refresh cookie
- `POST /auth/verify-email` - Verify email token
- `POST /auth/resend-verification` - Resend verification
- `POST /auth/forgot-password` - Request reset
- `POST /auth/reset-password` - Confirm reset
- `GET /auth/me` - Current user

### Agents

- `POST /agents` - Create
- `GET /agents` - List (filters: status, direction)
- `GET /agents/{id}` - Get
- `PATCH /agents/{id}` - Update (tracks prompt versions)
- `DELETE /agents/{id}` - Delete
- `GET /agents/{id}/completeness` - Required fields check
- `GET /agents/{id}/prompt-versions` - History
- `POST /agents/{id}/rewrite-prompt` - AI rewrite

### API Keys

- `POST /agents/{id}/api-key` - Generate (shown once)
- `GET /agents/{id}/api-key` - Get masked info
- `POST /agents/{id}/api-key/regenerate` - Rotate
- `DELETE /agents/{id}/api-key` - Revoke
- `GET /agents/{id}/webhook-url` - Get webhook URL
- `GET /agents/{id}/websocket-urls` - Get local & internet WebSocket URLs
- `GET /agents/{id}/websocket-test-token` - Get one-time test token

### Cold Call Queue

- `POST /agents/{id}/cold-call-queue/import` - CSV/JSON import
- `GET /agents/{id}/cold-call-queue` - List (filters, pagination, sort)
- `GET /agents/{id}/cold-call-queue/stats` - Status counts
- `PATCH /agents/{id}/cold-call-queue/{entry_id}` - Update
- `POST /agents/{id}/cold-call-queue/retry-failed` - Retry failed
- `DELETE /agents/{id}/cold-call-queue/{entry_id}` - Delete pending/failed

### Call Logs

- `GET /agents/{id}/calls` - List (filters, pagination)
- `GET /agents/{id}/calls/{call_id}` - Get with transcript
- `GET /agents/{id}/calls/stats` - Statistics

### Billing

- `POST /billing/checkout-session` - Create Stripe Checkout
- `POST /billing/payment-intent` - Create PaymentIntent for Stripe Elements
- `GET /billing/prices` - Get Stripe price IDs for each plan
- `POST /billing/portal-session` - Create Customer Portal
- `GET /billing/usage` - Usage stats with plan limits
- `POST /billing/webhook` - Stripe webhook handler

### Simulated Calls (mounted at `/demo`)

- `POST /demo/start-call` - Start call, returns session_id + ws_url
- `WS /demo/ws/audio/{session_id}` - WebSocket audio streaming
- `POST /demo/end-call/{session_id}` - End call
- `GET /demo/sessions` - List active sessions
- `GET /demo` - Embedded HTML test page

### Universal Voice Agent WebSocket (External Telephony Integration)

- `GET /api/agents/{id}/websocket-urls` - Get local & internet WebSocket URLs
- `GET /api/agents/{id}/websocket-test-token` - Get one-time test token
- `WS /ws?api_key=...` - **Universal** endpoint for all telephony systems
- `WS /ws?token=...` - **Universal** endpoint with test token

**Supported Systems**: Asterisk, FreeSWITCH, OpenSIPS, Twilio, custom SIP, WebRTC, any VoIP platform

Protocol for `/ws`:
- Audio: Binary frames, int16, 16kHz, mono, 20ms (320 samples = 640 bytes)
- Control: JSON text frames

Message Flow:
1. CONNECT → `{"type": "ready", "data": {"session_id": "...", "protocol_version": "1.0", ...}}`
2. CLIENT → `{"type": "config", "data": {FULL_AGENT_CONFIG}}` (REQUIRED - no portal setup)
3. SERVER → `{"type": "started", "data": {"session_id": "...", "capabilities": [...]}`
4. EXCHANGE: Binary audio + JSON (`transcript`, `state`, `dtmf_received`, `error`)
5. END → `{"type": "end"}` → `{"type": "ended", "data": {...}}`

**Config Fields (all passed at connection - NO PORTAL CONFIG NEEDED):**
- Required: `direction` (outbound|inbound), `system_prompt`
- Optional: `agent_id`, `voice_stack`, `opening_line`, `greeting_prompt`, `objective_prompt`, `qualification_prompt`, `knowledge_prompt`, `objection_handling_prompt`, `fallback_prompt`, `voicemail_prompt`, `closing_prompt`, `escalation_rule`, `handoff_prompt`, `interruption_sensitivity`, `max_call_duration_s`, `silence_timeout_s`, `language`, `stt_engine`, `tts_engine`, `tts_voice`, `llm_provider`, `llm_model`, Stack B fields, `metadata`

### Health & Metrics

- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

---

## Deployment

### Local Development

```bash
# Generate certs
mkcert -install
mkcert -key-file infra/nginx/ssl/ominivoice.local-key.pem \
       -cert-file infra/nginx/ssl/ominivoice.local.pem \
       ominivoice.local

# Add to /etc/hosts
echo "127.0.0.1 ominivoice.local" | sudo tee -a /etc/hosts

# Launch
docker compose -f infra/docker-compose.local.yml up -d --build
stripe listen --forward-to https://ominivoice.local/billing/webhook
```

### Production

```bash
# Configure .env.prod
cp infra/.env.example infra/.env.prod
# Edit with production secrets

# Deploy
docker compose -f infra/docker-compose.prod.yml up -d --build

# SSL via Let's Encrypt (Certbot sidecar)
# DNS must point to server IP
```

---

## Security Model

### Threats Mitigated

| Threat | Mitigation |
|--------|------------|
| SQL Injection | SQLAlchemy ORM, parameterized queries |
| XSS | CSP headers, React auto-escaping |
| CSRF | SameSite=lax cookies, no cookie-based auth for APIs |
| Token Theft | Short-lived access (30min), HttpOnly refresh cookies |
| API Key Leakage | SHA-256 hash storage, shown once |
| Rate Limit Abuse | Redis-backed per-IP/key limits |
| Data Leakage | Tenant isolation (404 not 403), CORS locked to frontend origin |
| Stripe Fraud | Webhook signature verification |

### Compliance Considerations

- GDPR: Data deletion on account removal, email verification
- PCI DSS: Stripe handles card data, no card data stored
- SOC 2: Structured logging, audit trail via prompt versions

---

## Scaling Considerations

### Horizontal Scaling

- **API**: Stateless, scale behind load balancer
- **Workers**: Add Celery workers for queue/billing/email
- **Voice Engine**: Separate containers, GPU for Stack B

### Database

- Connection pooling (asyncpg)
- Read replicas for analytics
- Partition call_logs by date if >100M rows

### Redis

- Separate DBs: 0=cache, 1=celery broker, 2=celery results
- Cluster mode for >100k keys

### Voice Engine

- WebSocket connection pooling
- GPU sharing for Stack B (NVIDIA MIG)
- Model caching in shared volume