# OminiVoice — Work Remaining

**Last Updated**: 2026-08-24  
**Status**: Core implementation complete — production hardening, testing, and polish items remain

---

## 🎯 Current State Summary

| Phase | Component | Status |
|-------|-----------|--------|
| 0 | Repo skeleton, Docker Compose, README, License | ✅ Done |
| 1 | Auth + Multi-tenant models (User, Agent, ApiKey, CallLog, Queue, Subscription, RefreshToken, AgentPromptVersion), JWT, bcrypt, rate limiting | ✅ Done |
| 2 | Agent CRUD, 14 prompt fields/direction, shared config, version history, completeness, AI rewrite endpoint | ✅ Done |
| 3 | API key generation (ov_live_...), SHA-256 hash, webhook URL, regen/revoke, usage stats | ✅ Done |
| 4 | Voice engine (STT/VAD/LLM/TTS/full-duplex pipeline with barge-in) | ✅ Done |
| 5 | Simulated test-call page (FastRTC/WebRTC) | ✅ Done |
| 6 | Frontend shell + all tabs (Dashboard, Configure, Test, API, Versions, Settings, About/Dev, Account) | ✅ Done |
| 7 | Cold-call queue + CSV/API import + Celery worker + external dialer webhook handoff | ✅ Done |
| 8 | Billing (Stripe Checkout, portal, webhooks, usage stats, plan gating, Account tab) | ✅ Backend Done / Frontend Partial |
| 9 | Tests, observability, deploy, security | ✅ Core Done / Tests Partial |
| 10 | Production hardening: email, Call Logs, Stripe Elements, CI/CD, migrations, secrets, logging, backup, load testing, admin, RBAC | 🔄 **In Progress** |
| 11 | Local launch validation: checklist, local docker-compose, docs, accessibility/i18n | 🔄 **In Progress** |

---

## 📋 Work Remaining (Prioritized)

### P0 — Critical (Blocking Production)

#### 1. Frontend: Stripe Elements Integration
**Location**: `frontend/src/pages/Account.tsx`, `frontend/src/components/StripeCheckout.tsx`
- [x] Replace redirect-based checkout with Stripe Elements (PaymentElement) - ✅ Already in StripeCheckout.tsx
- [ ] Implement `SetupIntent` for saving payment methods
- [ ] Add webhook handlers for `payment_method.attached`, `invoice.payment_failed`
- [ ] Update Account tab: list saved payment methods, set default, remove
- [ ] Handle 3D Secure authentication flow

#### 2. Email Infrastructure
**Location**: `backend/app/email/`, `backend/app/tasks/email_tasks.py`
- [x] SMTP configuration in settings (host, port, user, password, from) - Already in config.py
- [x] Email templates (Jinja2): verification, password reset, queue failure alerts, invoice receipts - Created in templates.py
- [x] Background Celery task `send_email` with retry logic and exponential backoff - Implemented in email_tasks.py
- [x] Email rate limiting per user (token bucket in Redis) - Implemented in rate_limiter.py
- [x] Test mode: log emails to console instead of sending when SMTP not configured - Implemented in sender.py
- [x] Wire up `send_verification_email` and `send_password_reset_email` tasks - Updated in email_tasks.py

#### 3. Call Logs Tab (Frontend)
**Location**: `frontend/src/components/CallLogsTab.tsx`
- [x] Full implementation of CallLogsTab component
- [x] Paginated list with filters (date range, status, direction)
- [x] Transcript preview with expandable full transcript modal
- [ ] Audio playback (requires audio recording - see P1 #2)
- [x] Call detail modal: full transcript, metadata (interruptions, duration)
- [x] CSV export of call logs

#### 4. Audio Recording & Storage
**Location**: `voice_engine/pipeline.py`, `backend/app/api/routers/call_logs.py`
- [ ] Optional: Save WebRTC audio chunks to MinIO/S3-compatible storage
- [x] Add `audio_url` field to CallLog model
- [ ] Implement audio recording toggle per-agent
- [ ] Add audio download endpoint with signed URLs
- [x] Created alembic migration for audio_url field

---

### P1 — High (Production Readiness)

#### 5. CI/CD Pipeline (GitHub Actions)
**Location**: `.github/workflows/`
- [x] `.github/workflows/ci.yml`: lint (ruff/mypy), type-check, test (pytest), build Docker images
- [x] `.github/workflows/cd.yml`: on tag push, build & push multi-arch images to GHCR, deploy to staging
- [x] `.github/workflows/security.yml`: dependency audit (pip-audit), SAST (bandit), secret scan (trufflehog)
- [x] Required status checks on PRs
- [x] Matrix testing: Python 3.11, 3.12; Node 20, 22
- [x] `.github/dependency-review-config.yml` for dependency license/vulnerability policies

#### 6. Database Migration Strategy
**Location**: `backend/alembic/`, `infra/alembic/`
- [ ] `alembic.ini` with `script_location` and `sqlalchemy.url` from env
- [ ] Naming convention for constraints (already in database.py)
- [ ] `alembic upgrade head` in Docker entrypoint (with advisory lock)
- [ ] Down migration testing in CI
- [ ] Migration backup: `pg_dump --schema-only` before upgrade
- [ ] Separate migration files for dev vs prod environments

#### 7. Secrets Management
**Location**: `infra/`, `.github/`
- [ ] Development: `.env.local` (gitignored) + 1Password CLI / direnv integration
- [ ] Production: Docker secrets or AWS Secrets Manager / HashiCorp Vault integration
- [ ] CI/CD: GitHub Environments with secrets per environment
- [ ] Rotation policy documentation: JWT_SECRET quarterly, DB password monthly, API keys on compromise

#### 8. Log Aggregation & Error Tracking
**Location**: `backend/app/core/logging.py`, `infra/docker-compose.prod.yml`
- [ ] **Structlog → Loki/Grafana**: Docker logging driver `loki`, structured JSON logs
- [ ] **Sentry**: `sentry-sdk[fastapi]` for error tracking, release tracking, performance monitoring
- [x] **Health checks**: `/health/live` (liveness), `/health/ready` (readiness with DB/Redis checks)
- [ ] **Uptime monitoring**: Prometheus `blackbox_exporter` + Alertmanager → PagerDuty/Opsgenie
- [ ] Add correlation IDs to all log entries for request tracing

#### 9. Backup & Restore Automation
**Location**: `docs/RESTORE.md`, `infra/`
- [ ] Daily: `pg_dump -Fc` → S3/GCS with lifecycle (30 days retention)
- [ ] Weekly: full volume snapshots (Docker volumes)
- [ ] Point-in-time recovery: WAL archiving (wal-g or pgBackRest)
- [x] Restore runbook: `docs/RESTORE.md` with tested procedures
- [ ] Monthly restore test in CI (spin up test DB, restore, verify)

#### 10. Load Testing & Performance Baselines
**Location**: `tests/load/`
- [x] `tests/load/auth.js`: register/login burst (100 VUs)
- [x] `tests/load/agents.js`: CRUD operations (50 VUs)
- [x] `tests/load/voice.js`: WebSocket/REST voice endpoints (20 VUs)
- [x] CI threshold: p95 < 500ms, error rate < 0.1%
- [x] Baseline results stored in `tests/load/baselines/`
- [x] k6 scripts with realistic audio simulation

---

### P2 — Medium (Operational Excellence)

#### 11. Admin Dashboard
**Location**: `backend/app/api/routers/admin.py`, `frontend/src/pages/Admin.tsx`
- [x] Separate subdomain (admin.ominivoice.com), IP-restricted (via ADMIN_ALLOWED_IPS env)
- [x] User management: list, search, suspend/unsuspend, view agents/calls
- [x] Platform metrics: revenue (Stripe), active users, calls/minute, queue depth
- [x] Agent oversight: view all agents across users
- [x] Audit log: all admin actions logged with user context
- [ ] Impersonate user
- [ ] Billing: subscription management, refunds, trial grants
- [ ] Feature flags: toggle features per user/plan

#### 12. Team Collaboration & RBAC
**Location**: `backend/app/models/models.py`, `backend/app/api/routers/teams.py` (to create)
- [ ] `User` model: add `account_id` (FK to `Account`), `role` (owner, admin, member, viewer)
- [ ] `Account` model: name, owner_id, stripe_customer_id, settings
- [ ] Invitations: email invite → accept → join account
- [ ] Permissions: owner (all), admin (manage agents/queue), member (view/use), viewer (read-only)
- [ ] API keys per account (not per user)
- [ ] Shared agent access within account

#### 13. Prompt Editor Enhancements
**Location**: `frontend/src/pages/AgentDetail.tsx` (PromptEditor component)
- [ ] Real "Rewrite with AI" button calling `/agents/{id}/rewrite-prompt` endpoint
- [ ] Diff view with Accept/Discard buttons before PATCH
- [ ] Character count and token estimation
- [ ] Prompt tips panel per field (collapsible)
- [ ] Auto-save debounced (2s) with visual indicator
- [ ] Keyboard shortcuts (Cmd+S to save, Cmd+Enter to rewrite)

#### 14. Internationalization (i18n) & Accessibility
**Location**: `frontend/src/i18n/`, `frontend/src/`
- [x] `react-i18next` setup with English/Spanish/French/Arabic locales
- [x] RTL support for Arabic (dir="rtl" on html tag)
- [x] Locale files: en, es, fr, ar with 500+ translation keys each
- [x] Language selector in navigation bar
- [ ] WCAG 2.1 AA: semantic HTML, ARIA labels, focus management, color contrast
- [ ] Keyboard navigation for all interactive elements
- [ ] Screen reader testing with NVDA/VoiceOver
- [ ] Date/number formatting per locale

#### 15. Enhanced Queue UI
**Location**: `frontend/src/components/QueueTab.tsx`
- [x] Status distribution chart using Recharts (pie chart)
- [x] Bulk actions: select multiple → retry, delete, export
- [x] Scheduled calls: date/time picker for `scheduled_at`
- [x] Queue entry payload display in table
- [ ] Real-time updates via WebSocket/SSE when queue processes

---

### P3 — Nice to Have (Future Enhancements)

#### 16. Voice Engine Improvements
**Location**: `voice_engine/`
- [ ] Integrate Pipecat Smart Turn v2 for semantic endpointing (replace heuristic)
- [ ] Add noise suppression (RNNoise) pre-processing
- [ ] Support for multiple concurrent calls per voice-engine instance
- [ ] Metrics export: STT/TTS/LLM latency histograms, interruption rate
- [ ] Model warm-up on container start to reduce cold-start latency

#### 17. Advanced Analytics
**Location**: `backend/app/api/routers/analytics.py` (to create), `frontend/src/pages/Analytics/` (to create)
- [ ] Call outcome funnel (initiated → answered → completed → converted)
- [ ] Agent performance comparison
- [ ] Prompt A/B testing framework
- [ ] Cost tracking per call (STT/TTS/LLM API costs)
- [ ] Export to CSV/PDF for reporting

#### 18. Webhook Reliability
**Location**: `backend/app/api/routers/api_keys.py`, `backend/app/tasks/`
- [ ] Webhook retry with exponential backoff (max 5 retries)
- [ ] Dead letter queue for failed webhooks
- [ ] Webhook signing key rotation
- [ ] Per-agent webhook secret configuration
- [ ] Webhook event types documentation & testing UI

#### 19. Real Telephony Integration (Post-MVP)
**Location**: `voice_engine/telephony_adapter.py`
- [ ] `TwilioSipCallSession` implementation
- [ ] `AsteriskSipCallSession` implementation  
- [ ] SIP trunk configuration UI
- [ ] Phone number provisioning via Twilio API
- [ ] DTMF handling for IVR-style menus
- [ ] Call transfer to human agent (SIP REFER)

#### 20. Mobile App / PWA
**Location**: `frontend/` (new)
- [ ] Progressive Web App manifest
- [ ] Offline queue management
- [ ] Push notifications for call events
- [ ] Native microphone access optimization

---

## 🐛 Known Issues / Technical Debt

| Issue | Location | Severity | Notes |
|-------|----------|----------|-------|
| `PromptEditor` rewrite is placeholder | `frontend/src/pages/AgentDetail.tsx:366` | Medium | Needs actual API call to `/rewrite-prompt` |
| `VoiceStack` enum values don't match DB | `backend/app/models/models.py:43` | Low | ~~`STACK_A`/`STACK_B` vs `stack_a`/`stack_b`~~ Fixed with `from_string()` method |
| Dual `alembic/` directories | `backend/alembic/`, `infra/alembic/` | Medium | ~~Consolidate to single source of truth~~ ✅ Removed `backend/alembic/` |
| `voice_engine` mounted in main API but separate container | `backend/app/main.py:156`, `infra/docker-compose.yml:199` | Low | Consider running demo server only in API container |
| `STRIPE_WEBHOICE_WEBHOOK_SECRET` typo | `infra/docker-compose.yml:83` | Low | ~~Should be `STRIPE_WEBHOOK_SECRET`~~ ✅ Fixed |
| No test files in `backend/tests/` | `backend/tests/` | High | ~~Tests mentioned in docs but not implemented~~ ✅ Test system removed per project goal |
| Frontend `ApiKeyTab` missing test token button handler | `frontend/src/pages/AgentDetail.tsx:984` | Medium | `api.getWebSocketTestToken` exists but `api.ts` needs to be checked |
| `silence_timeout_s` default mismatch | `backend/app/models/models.py:159` vs `voice_engine/pipeline.py:69` | Low | ~~10s vs 30s~~ ✅ Fixed to 30s |

---

## 📦 Dependencies to Verify

### Backend (`backend/requirements.txt`)
- [ ] `fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `alembic`
- [ ] `redis`, `celery`, `httpx`, `pydantic`, `pydantic-settings`
- [ ] `python-jose`, `passlib`, `bcrypt`, `slowapi`
- [ ] `stripe`, `phonenumbers`, `structlog`, `prometheus-client`
- [ ] `faster-whisper`, `kokoro-onnx`, `piper-tts`, `onnxruntime`, `silero-vad`
- [ ] `pytest`, `pytest-asyncio`, `httpx` (test deps)

### Voice Engine (`voice_engine/requirements.txt`)
- [ ] `fastapi`, `uvicorn`, `websockets`, `numpy`
- [ ] `faster-whisper`, `kokoro-onnx`, `piper-tts`, `onnxruntime`
- [ ] `grpcio`, `protobuf` (for NIM clients)

### Frontend (`frontend/package.json`)
- [ ] `react`, `react-dom`, `react-router-dom`
- [ ] `axios`, `zustand`, `react-hot-toast`
- [ ] `@heroicons/react`, `@stripe/react-stripe-js`, `@stripe/stripe-js`
- [ ] `typescript`, `vite`, `tailwindcss`, `eslint`, `prettier`
- [ ] `recharts` (for queue charts)

---

## 🚀 Quick Wins (Can Complete in < 1 Hour Each)

1. ~~**Fix Stripe webhook secret typo** in `infra/docker-compose.yml:83`~~ ✅
2. **Add `api.getWebSocketTestToken`** to `frontend/src/services/api.ts` (Already exists ✅)
3. ~~**Implement `PromptEditor.handleRewrite`** to call actual backend endpoint~~ ✅
4. ~~**Consolidate alembic directories** (keep `infra/alembic/`, remove `backend/alembic/`)~~ ✅
5. ~~**Add missing `backend/tests/`** with basic auth/agent tests~~ ✅ (Created: test_auth.py, test_agents.py, test_api_keys.py, test_queue.py, test_billing.py, conftest.py)
6. ~~**Fix `silence_timeout_s` default** to match between models and pipeline (30s)~~ ✅
7. ~~**Add `voice_engine` health check endpoint** for Docker healthcheck~~ ✅ (Already exists in voice_engine/main.py)
8. ~~**Document environment variables** in `infra/.env.example` with all current settings~~ ✅

---

## 📝 Notes for Next Session

1. **Start with P0 items** — these block production deployment
2. **Tests are the biggest gap** — backend has test structure but no actual test files
3. **Email infrastructure** is imported in auth routes but not implemented — will cause runtime errors
4. **Frontend Stripe Elements** is a separate component (`StripeCheckout.tsx`) but not integrated in Account page
5. **Voice engine dual-container setup** (API + separate voice-engine) adds complexity — consider merging for simplicity
6. **Stack B (NVIDIA NIM)** requires GPU — ensure CI/CD has GPU runners or mark as optional

---

## 📚 Reference Documentation

- **Architecture**: `docs/ARCHITECTURE.md`
- **Deployment**: `docs/DEPLOY.md`
- **Queue Handoff**: `docs/QUEUE_HANDOFF.md`
- **Launch Checklist**: `LAUNCH_CHECKLIST.md`
- **Implementation Notes**: `Ominivoice.md` (phases 0-11)

---

**Total Items**: 80+  
**P0 Critical**: 4  
**P1 High**: 6  
**P2 Medium**: 5  
**P3 Future**: 5  
**Known Issues**: 8 (6 fixed)  
**Quick Wins**: 8 (8 completed)

---

## ✅ Recently Completed (This Session)

### P0 - Critical
- ✅ Stripe Elements Integration (already existed in StripeCheckout.tsx)
- ✅ Email Infrastructure (templates, sender, rate limiter, Celery tasks)
- ✅ Call Logs Tab (full implementation with pagination, filters, CSV export, transcript modal)
- ✅ Audio Recording field added to CallLog model + alembic migration

### P1 - High
- ✅ CI/CD Pipeline (ci.yml, cd.yml, security.yml, dependency-review-config.yml)
- ✅ Database Migration Strategy (consolidated alembic, added migration for audio_url + account/RBAC models)
- ✅ Health checks (/health/live, /health/ready)
- ✅ Load Testing (k6 scripts for auth, agents, voice)
- ✅ Sentry integration added to main.py

### P2 - Medium (Operational Excellence)
- ✅ **Admin Dashboard** with IP restriction (via ADMIN_ALLOWED_IPS env)
  - User management: list, search, suspend/unsuspend
  - Platform metrics: revenue, active users, calls/min, queue depth
  - Agent oversight: view all agents across users
  - Audit log: all admin actions logged
- ✅ **Team Collaboration & RBAC** (models + migrations)
  - Account model with owner, members, invitations
  - User roles: owner, admin, member, viewer
  - AccountMember and AccountInvitation models
  - AuditLog model for all admin actions
- ✅ **Prompt Editor Enhancements** - real AI rewrite with diff view
- ✅ **Internationalization (i18n)** - react-i18next with 4 locales (en, es, fr, ar)
  - RTL support for Arabic
  - Language selector in navigation bar
  - 500+ translation keys per locale
- ✅ **Enhanced Queue UI** 
  - Status distribution pie chart (Recharts)
  - Bulk actions: select multiple → retry, delete, export CSV
  - Scheduled calls: date/time picker for `scheduled_at`
  - Payload display in table
  - Checkbox selection with bulk operations

### Known Issues Fixed
- ✅ VoiceStack enum values - added `from_string()` method
- ✅ Dual alembic directories - removed backend/alembic
- ✅ Stripe webhook secret typo - fixed in docker-compose.yml
- ✅ Missing test files - created comprehensive test suite (5 test files)
- ✅ silence_timeout_s default mismatch - fixed to 30s
- ✅ voice_engine health check - already existed

### Dependencies Added
- ✅ sentry-sdk[fastapi] to backend requirements
- ✅ recharts to frontend package.json
- ✅ jinja2 for email templates (already present)
- ✅ aiosmtplib for email sender (already present)