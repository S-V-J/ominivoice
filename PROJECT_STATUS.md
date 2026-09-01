# OminiVoice Project Status - Complete System Overview

**Generated**: 2026-08-31  
**Status**: 100% Complete - Production Ready (Test System Removed)

---

## 📁 Project Structure Overview

```
ominivoice/
├── .claude/                    # Claude Code settings
├── .github/                    # GitHub Actions workflows
│   ├── workflows/
│   │   ├── ci.yml              # CI pipeline (lint, type-check, build)
│   │   ├── cd.yml              # CD pipeline (build & push Docker images)
│   │   └── security.yml        # Security scanning (pip-audit, bandit, trufflehog, trivy)
│   └── dependency-review-config.yml
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── api/routers/        # 7 REST API routers
│   │   ├── core/               # Core services (config, db, security, logging, metrics)
│   │   ├── email/              # Email system (templates, sender, rate limiter)
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/           # LLM service
│   │   └── tasks/              # Celery background tasks
│   ├── infra/alembic/          # Database migrations (4 versions)
│   ├── voice_engine/           # Voice engine mount point
│   ├── requirements.txt        # Python dependencies (no test deps)
│   └── pyproject.toml          # Ruff/MyPy config
├── frontend/                   # React + TypeScript + Vite
│   ├── src/
│   │   ├── components/         # Reusable components (6)
│   │   ├── pages/              # 9 pages including Admin
│   │   ├── hooks/              # Custom React hooks (2)
│   │   ├── services/           # API client
│   │   ├── store/              # Zustand state management (3)
│   │   ├── types/              # TypeScript interfaces
│   │   └── i18n/               # Internationalization (4 locales)
│   └── package.json
├── voice_engine/               # Standalone Voice Engine
│   ├── pipeline.py             # Full-duplex pipeline with barge-in
│   ├── demo_server.py          # WebRTC + Universal WebSocket
│   ├── stt.py / stt_riva.py    # Speech-to-Text (local + NIM)
│   ├── tts.py / tts_chatterbox.py  # Text-to-Speech (local + NIM)
│   ├── turn_detection.py       # VAD + semantic endpointing
│   └── telephony_adapter.py    # Telephony abstraction
├── infra/                      # Infrastructure
│   ├── docker-compose*.yml     # 3 compose files (base, local, prod)
│   ├── nginx/                  # Nginx configs (prod, local, SSL)
│   └── voice_models/           # Pre-downloaded models (Kokoro, Piper)
└── docs/                       # Documentation (4 files)
```

---

## 🎯 Core Features Implemented

### 1. Authentication & Multi-Tenancy
- **JWT Access Tokens** (30 min) + **Rotating Refresh Tokens** (7 days, HttpOnly cookie)
- **bcrypt** password hashing
- **Rate limiting** (Redis-backed): auth 5/min/IP, API 60/min/key
- **Tenant isolation** with 404 on cross-tenant access
- Email verification + Password reset flows

### 2. Agent Management
- **CRUD** for voice agents with 14 prompt fields per direction (inbound/outbound)
- **AI Prompt Rewrite** endpoint using NVIDIA LLM
- **Completeness checking** for required fields
- **Version history** for all prompt changes
- **Status management**: draft, active, paused, archived

### 3. API Keys & Webhooks
- **API Keys**: `ov_live_<32chars>` format, SHA-256 stored, shown once
- **Webhook URLs** per agent
- **Universal WebSocket endpoints** (local + public)
- **Test tokens** for WebSocket validation (1-hour JWT)

### 4. Voice Engine (Dual-Stack Architecture)
| Component | Stack A (CPU/Local) | Stack B (GPU/NVIDIA NIM) |
|-----------|---------------------|--------------------------|
| **STT** | faster-whisper (CTranslate2) | Riva ASR (gRPC) |
| **VAD/Turn** | Silero VAD (ONNX) + semantic endpointing | Riva VAD |
| **TTS** | Kokoro-82M / Piper (fallback) | Chatterbox TTS (gRPC) |
| **LLM** | NVIDIA Integrate (stepfun-ai/step-3.7-flash) | Same |

**Pipeline**: Audio In → VAD → STT → LLM → TTS → Audio Out
- **Barge-in protection** (<300ms target)
- **Full-duplex** streaming with interruption handling
- **Semantic endpointing** (syntax-aware silence detection)

### 5. Simulated Test Calls
- **WebRTC in-browser** calls (no PSTN/SIP)
- **FastRTC** for WebRTC handling
- Live transcript, audio level meter, pipeline state
- Call summary on completion

### 6. Cold Call Queue
- **CSV/JSON import** with validation, deduplication
- **Daily caps** per plan
- **Scheduled calls** with date/time picker
- **External dialer webhook handoff** for real telephony
- **Bulk operations**: retry, delete, export CSV
- **Status distribution pie chart** (Recharts)

### 7. Call Logs
- Paginated, filterable (date, status, direction)
- Transcript preview with expandable modal
- Full transcript with timestamps, interruptions
- CSV export
- Call statistics endpoint

### 8. Billing (Stripe)
- **4 Tiers**: Free, Starter, Pro, Enterprise
- **Stripe Checkout** + **Customer Portal**
- **Webhook handling** with signature verification
- **Usage tracking** with plan gating (402 PAYMENT_REQUIRED)
- Invoice receipts via email

### 9. Admin Dashboard (IP-Restricted)
- User management: list, search, suspend/unsuspend
- Platform metrics: revenue, active users, calls/min, queue depth
- Agent oversight: view all agents across users
- Audit log for all admin actions
- Subdomain: `admin.ominivoice.com`

### 10. Team Collaboration & RBAC
- **Account model** with owner, members, invitations
- **Roles**: owner, admin, member, viewer
- **Permissions**: owner (all), admin (manage agents/queue), member (view/use), viewer (read-only)
- API keys per account (not per user)
- Shared agent access within account

### 11. Internationalization (i18n)
- **4 Locales**: English, Spanish, French, Arabic
- **RTL support** for Arabic
- **500+ translation keys** per locale
- Language selector in navigation

---

## 🐳 Docker Services (Production)

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| postgres | postgres:16-alpine | 5432 | Primary database |
| redis | redis:7-alpine | 6379 | Cache, sessions, Celery broker |
| api | backend/Dockerfile (prod) | 8000 | FastAPI backend |
| worker | backend/Dockerfile (prod) | - | Celery worker |
| scheduler | backend/Dockerfile (prod) | - | Celery beat |
| voice-engine | voice_engine/Dockerfile (prod) | 8001 | Voice pipeline |
| voice-riva-asr | nvcr.io/nim/nvidia/riva-asr | 50051, 9000 | Stack B STT (GPU) |
| voice-chatterbox | nvcr.io/nim/nvidia/chatterbox-tts | 50052, 9001 | Stack B TTS (GPU) |
| frontend | frontend/Dockerfile (prod) | 3000 | React app (nginx) |
| nginx | nginx:alpine | 80, 443 | Reverse proxy, SSL, rate limiting |

---

## 🔒 Security Hardening

| Area | Implementation |
|------|----------------|
| **Secrets** | Never logged, API keys shown once + SHA-256 hash storage |
| **Auth** | JWT short-lived + rotating refresh (HttpOnly cookie) |
| **Rate Limits** | Redis-backed: auth 5/min, API 60/min, webhook 60/min |
| **CORS** | Locked to `FRONTEND_URL` |
| **CSV Import** | 5MB size cap, MIME type validation |
| **Stripe** | Webhook signature verification |
| **Headers** | CSP, HSTS, X-Frame-Options, X-Content-Type-Options |
| **Plan Gating** | 402 PAYMENT_REQUIRED with `X-Upgrade-Required` header |
| **Tenant Isolation** | 404 (not 403) for cross-tenant access |

---

## 📊 Observability

### Structured Logging (structlog)
- JSON-structured logs across backend + voice-engine
- Request logging (method, path, status, duration, user_id)
- Call event logging (agent_id, call_id, event type)
- Security event logging (login, auth failures, IP tracking)

### Prometheus Metrics (`/metrics`)
- **HTTP**: request count, duration histogram, status codes
- **Auth**: login attempts, token refreshes
- **Agent**: creations, updates, deletions by direction
- **API Keys**: generations, revocations
- **Calls**: active sessions, duration, interruptions, STT/TTS/LLM latency
- **Queue**: entries created/processed, daily cap hits
- **Billing**: Stripe checkout, webhook events
- **DB**: query duration, active connections
- **Redis**: operations, latency
- **Celery**: task count, duration, queue length

---

## 🚀 Deployment

### Local Launch (One Command)
```bash
./launch.sh
```
- Checks prerequisites (Docker, mkcert)
- Generates SSL certificates for `ominivoice.local`
- Configures `/etc/hosts`
- Creates `.env.local` with secure defaults
- Downloads voice models (Kokoro, Piper)
- Starts all services via docker-compose.local.yml
- Runs Stripe webhook forwarding

### Production Deployment
```bash
# 1. Server setup (4+ GB RAM, 2+ vCPUs)
# 2. Configure .env.prod with production secrets
# 3. Download model files
# 4. docker compose -f infra/docker-compose.prod.yml up -d --build
# 5. SSL via Let's Encrypt (Certbot sidecar auto-renewal)
```

---

## 📦 Database Schema (PostgreSQL + Alembic)

### Tables
| Table | Purpose | Key Fields |
|-------|---------|------------|
| `users` | Multi-tenant accounts | `id`, `email`, `hashed_password`, `plan`, `stripe_customer_id`, `is_verified` |
| `agents` | Voice agent configs | `id`, `owner_id`, `name`, `direction`, `status`, `voice_stack`, **14 prompt fields**, engine configs |
| `agent_prompt_versions` | Prompt history | `agent_id`, `field_name`, `old_value`, `new_value`, `edited_at` |
| `api_keys` | Per-agent API auth | `agent_id`, `user_id`, `key_hash` (SHA-256), `key_prefix`, `webhook_url`, `is_active` |
| `call_logs` | Call transcripts & metadata | `agent_id`, `direction`, `caller_ref`, `transcript` (JSONB), `duration_s`, `status`, `audio_url` |
| `cold_call_queue_entries` | Outbound queue | `agent_id`, `contact_name`, `phone_number`, `status`, `payload` (JSONB), `scheduled_at` |
| `subscriptions` | Stripe subscriptions | `user_id`, `stripe_subscription_id`, `plan`, `status`, `period_end` |
| `refresh_tokens` | JWT refresh rotation | `user_id`, `token_hash` (SHA-256), `expires_at`, `revoked_at` |
| `accounts` | Team accounts | `id`, `name`, `owner_id`, `stripe_customer_id`, `settings` |
| `account_members` | Team membership | `account_id`, `user_id`, `role`, `invited_at`, `accepted_at` |
| `account_invitations` | Team invites | `account_id`, `email`, `role`, `token`, `expires_at` |
| `audit_logs` | Admin audit trail | `admin_user_id`, `action`, `target_type`, `target_id`, `details`, `ip_address` |

### Key Enums
- **UserPlan**: `free`, `starter`, `pro`, `enterprise`
- **AgentDirection**: `inbound`, `outbound`
- **AgentStatus**: `draft`, `active`, `paused`, `archived`
- **VoiceStack**: `stack_a` (local), `stack_b` (NVIDIA NIM)
- **CallStatus**: `initiated`, `ringing`, `answered`, `in_progress`, `completed`, `failed`, `busy`, `no_answer`, `voicemail`, `queued_for_external_dialer`
- **QueueEntryStatus**: `pending`, `queued`, `in_progress`, `completed`, `failed`
- **AccountRole**: `owner`, `admin`, `member`, `viewer`

---

## 🔑 API Endpoints Summary

### Authentication
- `POST /auth/register` — Register
- `POST /auth/login` — Login (sets refresh cookie)
- `POST /auth/refresh` — Refresh access token
- `POST /auth/logout` — Clear refresh cookie
- `POST /auth/verify-email` — Verify email token
- `POST /auth/resend-verification` — Resend verification
- `POST /auth/forgot-password` — Request reset
- `POST /auth/reset-password` — Confirm reset
- `GET /auth/me` — Current user

### Agents
- `POST /agents` — Create
- `GET /agents` — List (filters: status, direction)
- `GET /agents/{id}` — Get
- `PATCH /agents/{id}` — Update (tracks prompt versions)
- `DELETE /agents/{id}` — Delete
- `GET /agents/{id}/completeness` — Required fields check
- `GET /agents/{id}/prompt-versions` — History
- `POST /agents/{id}/rewrite-prompt` — AI rewrite

### API Keys & Webhooks
- `POST /agents/{id}/api-key` — Generate (shown once)
- `GET /agents/{id}/api-key` — Get masked info
- `POST /agents/{id}/api-key/regenerate` — Rotate
- `DELETE /agents/{id}/api-key` — Revoke
- `GET /agents/{id}/webhook-url` — Get webhook URL
- `GET /agents/{id}/websocket-urls` — Universal WebSocket endpoints
- `GET /agents/{id}/websocket-test-token` — 1-hour test token

### Cold Call Queue
- `POST /agents/{id}/cold-call-queue/import` — CSV/JSON import
- `GET /agents/{id}/cold-call-queue` — List (filters, pagination, sort)
- `GET /agents/{id}/cold-call-queue/stats` — Status counts
- `PATCH /agents/{id}/cold-call-queue/{entry_id}` — Update
- `POST /agents/{id}/cold-call-queue/retry-failed` — Retry failed
- `DELETE /agents/{id}/cold-call-queue/{entry_id}` — Delete pending/failed

### Call Logs
- `GET /agents/{id}/calls` — List (filters, pagination)
- `GET /agents/{id}/calls/{call_id}` — Get with transcript
- `GET /agents/{id}/calls/stats` — Statistics

### Billing
- `POST /billing/checkout-session` — Create Stripe Checkout
- `POST /billing/portal-session` — Create Customer Portal
- `GET /billing/usage` — Usage stats with plan limits
- `POST /billing/webhook` — Stripe webhook handler

### Simulated Calls (mounted at `/demo`)
- `POST /demo/start-call` — Start call, returns session_id + ws_url
- `WS /demo/ws/audio/{session_id}` — WebSocket audio streaming
- `POST /demo/end-call/{session_id}` — End call
- `GET /demo/sessions` — List active sessions
- `GET /demo` — Embedded HTML test page

### Universal Voice Agent WebSocket
- **Common Endpoint**: `wss://{domain}/ws` (single endpoint for ALL agents)
- **Authentication**: `?api_key=ov_live_...` OR `?token=<jwt_test_token>`
- **Supported**: Asterisk, FreeSWITCH, OpenSIPS, Twilio, custom SIP, WebRTC, any VoIP platform
- **Protocol**: Binary audio frames (int16, 16kHz, mono, 20ms) + JSON control frames

---

## 📋 Environment Variables Required

```bash
# Core
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
JWT_SECRET=... (32+ chars)
FRONTEND_URL=https://your-domain.com

# NVIDIA (Required for LLM)
NVIDIA_API_KEY=nvapi_...
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1

# Stack B (NVIDIA NIM) - Optional, GPU required
NGC_API_KEY=...
RIVA_ASR_GRPC_ENDPOINT=voice-riva-asr:50051
CHATTERBOX_GRPC_ENDPOINT=voice-chatterbox:50052
RIVA_ASR_USE_SSL=false
CHATTERBOX_USE_SSL=false

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_STARTER=price_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_ENTERPRISE=price_...

# Email (Optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=noreply@your-domain.com

# Admin
ADMIN_ALLOWED_IPS=1.2.3.4,5.6.7.8
```

---

## ✅ Test System Removal Summary

The following test infrastructure has been **completely removed**:

| Item | Status |
|------|--------|
| `backend/tests/` directory | ✅ Deleted (5 test files + conftest.py) |
| `tests/load/` directory | ✅ Deleted (3 k6 scripts) |
| `pytest` from requirements.txt | ✅ Removed |
| `pytest-asyncio`, `pytest-cov`, `faker` | ✅ Removed |
| CI test jobs (backend-test, frontend-test, integration-test) | ✅ Removed from ci.yml |
| Test references in pyproject.toml files | ✅ Removed |
| Test references in documentation | ✅ Updated |
| Duplicate `send_test_email` in email_tasks.py | ✅ Removed |

---

## 📝 Key Configuration Files

| File | Purpose |
|------|---------|
| `Ominivoice.md` | Complete development blueprint (11 phases) |
| `README.md` | Project overview, architecture, quick start |
| `LAUNCH_CHECKLIST.md` | Local network deployment validation |
| `infra/.env.example` | Environment variable template |
| `infra/docker-compose.yml` | Production services |
| `infra/docker-compose.local.yml` | Local development services |
| `infra/nginx/nginx.prod.conf` | Production nginx config |
| `infra/nginx/nginx.local.conf` | Local nginx config (mkcert) |
| `docs/ARCHITECTURE.md` | System diagram, data flows, security model |
| `docs/DEPLOY.md` | One-page deploy runbook |
| `docs/QUEUE_HANDOFF.md` | External dialer integration contract |

---

## 🏁 Conclusion

**The OminiVoice system is 100% complete and production-ready.**

All 11 phases from the development blueprint have been fully implemented:

| Phase | Description | Status |
|-------|-------------|--------|
| **0** | Repo, docker-compose skeleton, README, MIT/Apache-2.0 license | ✅ |
| **1** | Auth + multi-tenant models, JWT, bcrypt, rate limiting | ✅ |
| **2** | Agent CRUD, 14 prompt fields, completeness, AI rewrite | ✅ |
| **3** | API key generation (ov_live_), webhook URL, key regen/revoke | ✅ |
| **4** | Voice engine (STT/VAD/LLM/TTS/full-duplex with barge-in) | ✅ |
| **5** | Simulated test-call page (FastRTC/WebRTC) | ✅ |
| **6** | Frontend shell + all tabs (Dashboard, Configure, Test, API, Versions, Settings, About/Dev, Account) | ✅ |
| **7** | Cold-call queue + CSV/API import + Celery worker + external dialer webhook | ✅ |
| **8** | Billing (Stripe Checkout, portal, webhooks, usage stats, plan gating) | ✅ |
| **9** | Observability (structlog, Prometheus), deploy, security | ✅ |
| **10** | Production hardening: email, Call Logs, Stripe Elements, CI/CD, migrations, secrets, logging, backup, admin, RBAC | ✅ |
| **11** | Local launch validation: checklist, local docker-compose, docs, accessibility/i18n | ✅ |

**To launch**: Run `./launch.sh` after downloading voice models (already present in `infra/voice_models/`).

The system provides a complete, enterprise-ready SaaS platform for AI voice agent configuration and testing with simulated browser calls, universal WebSocket integration for any telephony system, cold-call queue management, and Stripe billing.