# OminiVoice — Full Development Blueprint
**Repo:** `github.com/S-V-J/ominivoice` · **Owner:** S-V-J (stjl093@gmail.com) · **Env:** WSL2 Ubuntu, `/home/ML`
**Goal:** A multi-tenant SaaS where users register, configure inbound/outbound voice agents with editable prompts (+ "rewrite with AI" button), get an API key + webhook URL per agent, test the agent with a **simulated** browser call (no real PSTN dialing from this portal), and manage cold-calling lead queues + billing.

> This file is written as a sequence of **build prompts**. Each subphase is something you literally paste into Claude Code / Cursor / yourself, in order. Do not skip phases — each depends on the previous one's schema/contracts.

---

## 0. Research-backed tech decisions (read once, don't re-litigate)

| Layer | Choice | Why | License |
|---|---|---|---|
| Backend API | **FastAPI** (Python 3.11+) | async-native, plays well with the realtime voice stack, one language for API + voice engine | MIT |
| Realtime voice orchestration | **Pipecat** (Daily.co) | composable STT→LLM→TTS pipeline, you own every frame, best for a from-scratch product rather than a hosted platform | BSD-2 |
| Transport for demo/test calls | **FastRTC** (Hugging Face) | turns a plain Python function into a WebRTC/WebSocket audio stream, built-in pause/turn detection, perfect for an in-browser "simulate call" button with no telephony vendor | Apache-2.0 |
| VAD (is-user-speaking) | **Silero VAD** | ~1-2MB, ONNX, runs in <10ms/frame, industry default for barge-in | MIT |
| Turn/endpoint detection (is-user-*done*-speaking) | **Pipecat Smart Turn v2** (fallback: simple silence+semantic heuristic) | cuts false-interrupt rate by an order of magnitude vs VAD-only | Apache-2.0 |
| STT | **faster-whisper** (CTranslate2 build of Whisper) | MIT, streaming-friendly, GPU int8 ~4x faster than whisper.cpp, good multilingual WER | MIT |
| TTS | **Kokoro-82M** (primary) + **Piper** (low-resource fallback) | Kokoro: small, fast, fully commercial-safe, great quality/latency ratio. Piper: near-zero compute, good for CPU-only dev boxes. Avoid XTTS-v2/F5-TTS for commercial use (non-commercial licenses). | Apache-2.0 / MIT-ish (Piper now GPL-3.0 fork — fine self-hosted, mind copyleft if you ever ship it embedded in closed software) |
| LLM (agent brain) | **Exclusively NVIDIA `integrate.api.nvidia.com` with `stepfun-ai/step-3.7-flash`** — single provider, no Ollama fallback. API key via env `NVIDIA_API_KEY`. Request format: `POST https://integrate.api.nvidia.com/v1/chat/completions` with headers `Authorization: Bearer <key>`, `Accept: text/event-stream` for streaming, payload includes `model`, `messages`, `temperature=1`, `top_p=0.95`, `max_tokens=16384`, `seed=42`, `stream=true`. SSE parsing required for clean text deltas. | NVIDIA terms |
| DB | **PostgreSQL** | multi-tenant rows, JSONB for prompt configs, reliable under a cold-call queue workload | PostgreSQL license |
| Cache/session/queue | **Redis** | session tokens, call-queue (RQ or Celery broker), rate limiting on API keys | BSD |
| Auth | FastAPI + **fastapi-users** or hand-rolled JWT (access+refresh) + bcrypt | standard, avoids third-party paid auth SaaS | MIT |
| Frontend | **React + Vite + TypeScript + Tailwind** | fast dev loop, easy tab-based SPA | MIT |
| Billing | **Stripe** (test mode to start; only paid dependency, unavoidable for real payments) | industry standard, has a generous free/test tier | n/a |
| Background jobs (queue dialer, AI-rewrite calls) | **Celery + Redis** | mature, well documented | BSD |
| Containerization | **Docker Compose** (api, worker, postgres, redis, frontend, nginx) | one-command local + prod parity | Apache-2.0 |

**Design rule for the "simulated call" requirement:** the platform never opens a real PSTN/SIP trunk. The "Start Test Call" button opens a **WebRTC session in the user's own browser** (mic in, speaker out) via FastRTC, which is fed through the exact same Pipecat pipeline a real telephony bridge would use later. This satisfies "test how the voice agent behaves" without making Twilio/SIP a dependency or a cost center at MVP stage. A `telephony_adapter` interface is defined so a **real** SIP/Twilio bridge can be dropped in later without touching agent logic.

---

## PHASE 0 — Repo, environment, project skeleton

### 0.1 Init the GitHub repo (WSL terminal, `/home/ML`)
```bash
mkdir -p ~/projects/ominivoice && cd ~/projects/ominivoice
git init
git config user.name "S-V-J"
git config user.email "stjl093@gmail.com"
```
Build prompt: *"Create a monorepo skeleton for a project called OminiVoice with folders: `backend/` (FastAPI), `frontend/` (React+Vite+TS), `voice-engine/` (Pipecat pipeline + STT/TTS/VAD modules), `infra/` (docker-compose, nginx, alembic migrations), `docs/`. Add a root `.gitignore` for Python, Node, and WSL cruft (`__pycache__`, `.venv`, `node_modules`, `.env`, `*.db`)."*

### 0.2 README + LICENSE
Build prompt: *"Write a README.md for OminiVoice describing the product (multi-tenant voice-agent configuration platform with simulated call testing), the architecture diagram (text-based), and local dev setup steps. Add an MIT LICENSE file (or Apache-2.0, since several deps are Apache-2.0-licensed and you want compatibility)."*

### 0.3 First push
```bash
git add . && git commit -m "chore: project skeleton"
git branch -M main
git remote add origin https://github.com/S-V-J/ominivoice.git
git push -u origin main
```

### 0.4 Docker Compose baseline
Build prompt: *"Create `infra/docker-compose.yml` with services: `postgres:16`, `redis:7`, `api` (build from backend/, uvicorn --reload), `worker` (celery), `voice-engine` (separate container, GPU-optional), `frontend` (vite dev server), `nginx` (reverse proxy routing `/api` → api, `/ws` → voice-engine, `/` → frontend). Add `.env.example` with placeholders for `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `STRIPE_SECRET_KEY`, `NVIDIA_API_KEY`, `TTS_ENGINE`, `STT_ENGINE`."*

---

## PHASE 1 — Backend foundation: auth & multi-tenant core

### 1.1 Data model (Postgres via SQLAlchemy + Alembic)
Build prompt: *"In `backend/app/models.py`, define SQLAlchemy models: `User(id, email, hashed_password, plan, stripe_customer_id, created_at)`, `Agent(id, owner_id→User, name, direction ENUM[inbound,outbound], status, stt_engine, tts_engine, tts_voice, llm_provider, llm_model, system_prompt, greeting_prompt, fallback_prompt, interruption_sensitivity, max_call_duration_s, created_at, updated_at)`, `ApiKey(id, agent_id→Agent, key_hash, webhook_url, is_active, created_at, last_used_at)`, `CallLog(id, agent_id, direction, caller_ref, transcript JSONB, duration_s, status, started_at, ended_at)`, `ColdCallQueueEntry(id, agent_id, contact_name, phone_number, source, status ENUM[pending,queued,in_progress,completed,failed], payload JSONB, created_at)`, `Subscription(id, user_id, stripe_subscription_id, plan, status, current_period_end)`. Generate the first Alembic migration."*

### 1.2 Auth endpoints
Build prompt: *"Implement `POST /auth/register`, `POST /auth/login` (issues JWT access+refresh), `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` in `backend/app/routers/auth.py`. Passwords hashed with bcrypt via passlib. Email uniqueness enforced at DB level. Add rate limiting on login (5/min/IP) using slowapi+Redis."*

### 1.3 Multi-tenant guard
Build prompt: *"Add a FastAPI dependency `get_current_user` and a second dependency `get_owned_agent(agent_id)` that 404s (not 403, to avoid leaking existence) if the agent doesn't belong to the requesting user. Apply it to every agent-scoped route from here on."*

### 1.4 Tests
Build prompt: *"Write pytest tests for register/login/duplicate-email/invalid-password/tenant-isolation (user A cannot fetch user B's agent) using pytest-asyncio + httpx AsyncClient against a test Postgres schema."*

---

## PHASE 2 — Voice agent configuration system

This is the core product surface. Two agent types share one schema (`direction` field) but the UI shows different prompt slots.

### 2.1 Agent CRUD API
Build prompt: *"Implement `POST /agents`, `GET /agents`, `GET /agents/{id}`, `PATCH /agents/{id}`, `DELETE /agents/{id}` in `backend/app/routers/agents.py`. On create, default `status='draft'`. A `PATCH` to any prompt field bumps `updated_at` and appends a row to a new `AgentPromptVersion` table (id, agent_id, field_name, old_value, new_value, edited_at) so users can see prompt history."*

### 2.2 Prompt configuration schema (the "proper system")
Research-informed prompt slots per agent (this is what "more configuration steps" should look like — not just one textbox):

**Outbound (call-out) agent:**
- `system_prompt` — persona, tone, do's/don'ts
- `opening_line` — first thing said the instant the callee picks up
- `objective_prompt` — what the call is trying to achieve (book meeting, confirm order, survey, etc.)
- `objection_handling_prompt` — how to respond to pushback/"not interested"
- `voicemail_prompt` — what to say if it detects voicemail/no-answer
- `closing_prompt` — how to end the call / next steps
- `escalation_rule` — when to say "let me transfer you to a human" (even if simulated, define the trigger)

**Inbound (call-in) agent:**
- `system_prompt`
- `greeting_prompt` — first thing said when a call is answered
- `qualification_prompt` — questions to ask to route/understand caller intent
- `knowledge_prompt` — FAQ / product info the agent should ground answers in
- `fallback_prompt` — what to say when it doesn't know the answer
- `handoff_prompt` — how to hand off to a human/ticket

**Shared config fields (non-prompt):**
- `interruption_sensitivity` (low/medium/high — maps to VAD+turn-detection thresholds)
- `max_call_duration_s`, `silence_timeout_s`
- `stt_engine`, `tts_engine`, `tts_voice`, `language`
- `llm_provider` (`ollama_local` | `nvidia_integrate`), `llm_model`

Build prompt: *"Extend the `Agent` model and Pydantic schemas with all fields above as nullable TEXT columns (nullable so drafts can be incomplete). Add a `GET /agents/{id}/completeness` endpoint returning which required fields are still empty per direction, so the frontend can show a progress checklist."*

### 2.3 Prompt-writing UI (frontend)
Build prompt: *"Build a React component `PromptEditor` — a full-height textarea with: character count, a small 'Prompt tips' collapsible panel per field (e.g. for `objection_handling_prompt`: 'list 3-5 common objections and a one-line response to each'), autosave (debounced PATCH every 2s), and a version-history dropdown pulling from `AgentPromptVersion`. Render one `PromptEditor` per field, grouped in a left-nav wizard: Persona → Flow → Knowledge → Edge cases → Review, based on the field list from 2.2."*

### 2.4 "Rewrite with AI" button
Build prompt: *"Add `POST /agents/{id}/rewrite-prompt` — body: `{field_name, current_text, instruction?}`. Server-side, call the configured LLM provider (reuse the `llm_provider` abstraction from Phase 4) with a fixed meta-prompt: 'You are a prompt engineer. Rewrite the following voice-agent {field_name} prompt to be clearer, more concise, and more effective for a natural-sounding phone conversation. Preserve the original intent. Return only the rewritten prompt, no preamble.' Return the rewritten text as a suggestion (don't auto-save); frontend shows a diff view with Accept/Discard buttons before it PATCHes the field."*
Frontend: *"Add a small ✨ 'Rewrite with AI' button next to each `PromptEditor`, wired to the endpoint above, showing a loading spinner and the diff modal."*

---

## PHASE 3 — API key & webhook system

Interpreting "API key must be the webhost address of this voice agent": each agent gets **both** a secret API key (for auth) **and** a stable webhook URL (the address external systems/your own test page hit to interact with that specific agent).

### 3.1 Key + webhook generation
Build prompt: *"On agent creation (or via `POST /agents/{id}/api-key/regenerate`), generate a secret key `ov_live_<32 random url-safe chars>` (store only its SHA-256 hash, show plaintext once), and construct a deterministic webhook URL `https://<your-domain>/webhook/v1/agents/{agent_id}` returned alongside it. Persist both in the `ApiKey` table. Support key revocation (`is_active=false`) without deleting history."*

### 3.2 Webhook auth middleware
Build prompt: *"Add a FastAPI dependency that authenticates inbound webhook/API calls via header `Authorization: Bearer ov_live_...`, hashes it, looks up `ApiKey`, checks `is_active`, and attaches the resolved `agent_id` to the request state. Reject with 401 on mismatch, 429 via Redis-backed rate limit (e.g. 60 req/min per key)."*

### 3.3 Key management UI
Build prompt: *"In the agent Settings tab, add an 'API & Webhook' section showing the masked key (`ov_live_••••••ab12`), a Copy button, the webhook URL with Copy button, a Regenerate button (confirm dialog — invalidates the old key immediately), and simple usage stats (last used, calls today) pulled from `CallLog`."*

---

## PHASE 4 — Voice engine backend (Python, full-duplex, interruption-capable)

### 4.1 LLM provider abstraction
Build prompt: *"In `voice-engine/llm_providers.py`, define an abstract `LLMProvider.stream_reply(messages: list[dict]) -> AsyncIterator[str]`. Implement `OllamaProvider` (calls local `http://localhost:11434/api/chat`, streaming) and `NvidiaIntegrateProvider` using this exact call shape (streaming enabled), reading the key from env `NVIDIA_API_KEY`, never hardcoded:"*
```python
import os, requests

class NvidiaIntegrateProvider:
    def __init__(self, model="stepfun-ai/step-3.7-flash"):
        self.model = model
        self.key = os.environ["NVIDIA_API_KEY"]

    def stream_reply(self, messages):
        headers = {
            "Authorization": f"Bearer {self.key}",
            "Accept": "text/event-stream",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 1,
            "top_p": 0.95,
            "max_tokens": 16384,
            "seed": 42,
            "stream": True,
        }
        with requests.post(
            "https://integrate.api.nvidia.com/v1/chat/completions",
            headers=headers, json=payload, stream=True, timeout=60
        ) as r:
            for line in r.iter_lines():
                if line:
                    yield line.decode("utf-8")
```
*"Wrap the SSE parsing into clean text deltas. `messages[0]` is always the agent's compiled `system_prompt` (assembled from the Phase 2 prompt fields based on `direction`)."*

### 4.2 STT module
Build prompt: *"In `voice-engine/stt.py`, wrap `faster-whisper` (model size configurable, default `small` for dev / `medium` for prod, `compute_type='int8'` on CPU or `'float16'` on GPU). Expose `transcribe_stream(audio_chunk_generator) -> AsyncIterator[PartialTranscript]` producing interim + final results, so the pipeline can react to partial text for semantic endpointing."*

### 4.3 VAD + turn detection
Build prompt: *"In `voice-engine/turn_detection.py`, load Silero VAD (`torch.hub` or `onnxruntime`) to classify 20-30ms frames as speech/silence in real time. Layer a simple endpointing rule on top: trigger 'user finished' after `silence_ms` (mapped from the agent's `interruption_sensitivity`: high=350ms, medium=600ms, low=900ms) UNLESS the latest partial transcript looks syntactically incomplete (ends in a conjunction/preposition/comma) — in that case extend the wait by 500ms. Note this as a placeholder for a proper semantic turn model (e.g. Pipecat Smart Turn v2) to swap in later."*

### 4.4 TTS module
Build prompt: *"In `voice-engine/tts.py`, wrap Kokoro-82M as the default engine with `synthesize_stream(text_generator) -> AsyncIterator[AudioChunk]` so speech starts on the first sentence, not after the full LLM reply. Add a Piper backend behind the same interface, selectable per-agent via `tts_engine` config, for low-resource dev machines."*

### 4.5 The full-duplex pipeline (Pipecat)
Build prompt: *"In `voice-engine/pipeline.py`, wire a Pipecat pipeline: `AudioInput → VAD/TurnDetector → STT → LLMProvider (streamed) → TTS (streamed) → AudioOutput`, with a barge-in handler: the moment VAD detects user speech WHILE TTS is playing, immediately (a) stop TTS playback, (b) cancel/flush the in-flight LLM stream, (c) truncate the conversation transcript to what was actually spoken aloud (track via a running 'spoken so far' pointer, not the full generated text), (d) start a fresh STT segment for the interruption. Target end-to-end reaction time under 300ms. Log every turn (role, text, timestamp, interrupted:boolean) to `CallLog.transcript` as JSONB."*

### 4.6 Direction-aware prompt assembly
Build prompt: *"In `voice-engine/prompt_builder.py`, write `build_system_prompt(agent: Agent) -> str` that concatenates the agent's Phase-2 prompt fields into one well-structured system prompt, ordered logically (persona → objective/greeting → knowledge → objection/fallback → closing/handoff → escalation), inserting section headers so the LLM can distinguish them. This is what gets passed as `messages[0]` to the LLM provider."*

---

## PHASE 5 — Simulated call testing (no real telephony)

### 5.1 `telephony_adapter` interface (future-proofing, build now)
Build prompt: *"Define an abstract `CallSession` interface in `voice-engine/telephony_adapter.py` with `connect()`, `send_audio_chunk()`, `receive_audio_chunk()`, `hangup()`. Implement `BrowserSimulatedCallSession` (backed by FastRTC — mic/speaker over WebRTC in the user's browser) as the ONLY concrete implementation for now. Leave a commented stub `TwilioSipCallSession` showing where a real trunk would plug in later, explicitly NOT implemented/enabled — this platform makes no real calls."*

### 5.2 FastRTC test-call endpoint
Build prompt: *"In `voice-engine/demo_server.py`, use FastRTC's `Stream`/`ReplyOnPause` handler to expose a WebRTC endpoint `/demo/{agent_id}` that: authenticates the requester as the agent's owner, loads that agent's compiled system prompt + engine settings, and pipes the browser mic through the Phase 4 pipeline, playing the TTS response back to the browser speaker in real time, with barge-in enabled. Simulate BOTH directions from the same code path: for 'outbound' agents the agent speaks first (its `opening_line`) as soon as the session connects; for 'inbound' agents it waits for the user to speak first, then uses `greeting_prompt`."*

### 5.3 Demo page UI
Build prompt: *"Add a 'Test Agent' tab on the agent detail page with a big 'Start Test Call' button. On click, request mic permission, open the FastRTC WebRTC session to `/demo/{agent_id}`, show a live call UI: waveform/level meter, live transcript scrolling in real time (both sides), an 'agent is speaking / listening / thinking' status pill, an End Call button, and after hangup a summary card (duration, turn count, was-interrupted count) sourced from the `CallLog` row the backend just wrote. Clarify in the UI copy: 'This is a simulated test call in your browser — no real phone call is placed.'"*

---

## PHASE 6 — Frontend platform shell (tabs)

### 6.1 App shell & routing
Build prompt: *"Scaffold the React app with routes: `/login`, `/register`, `/dashboard` (agent list + 'New Agent'), `/agents/:id` (nested tabs: Configure, Prompts, API & Webhook, Test, Call Logs, Cold-Call Queue), `/settings` (account-level: profile, password, API preferences), `/about-dev` (static page: product info, changelog, links), `/account` (billing/plan — Phase 8). Use React Router + a shared `AppLayout` with top-level nav: **Dashboard | Settings | About/Dev | Account**."*

### 6.2 Agent dashboard
Build prompt: *"Build a dashboard listing all of the user's agents as cards: name, direction badge (inbound/outbound), status, last test call date, completeness %. 'New Agent' opens a modal asking name + direction, then routes into the Configure wizard from Phase 2.3."*

### 6.3 Settings tab
Build prompt: *"Build the Settings page: change email/password, default LLM provider preference, default TTS voice, notification preferences (email on failed queue calls), danger zone (delete account — cascades to agents/keys/logs after confirmation typing 'DELETE')."*

### 6.4 About/Dev tab
Build prompt: *"Build a static About/Dev page: what OminiVoice is, links to API docs (auto-generated from FastAPI's `/docs` OpenAPI schema, embedded via an iframe or Swagger UI React component), open-source components credited (Pipecat, FastRTC, faster-whisper, Kokoro, Silero — with license names), version/changelog, and a support/contact link."*

---

## PHASE 7 — Cold-call queue database (auto-fill from call requests)

### 7.1 Ingestion endpoint
Build prompt: *"Implement `POST /agents/{id}/cold-call-queue/import` accepting either (a) a CSV upload (`contact_name,phone_number,...extra columns→payload JSONB`) or (b) a JSON array via API — this is the 'call request' auto-fill path external systems (or your own frontend) POST to using the agent's API key. Each row becomes a `ColdCallQueueEntry(status='pending')`. Validate phone numbers with `phonenumbers` (Google's libphonenumber Python port, Apache-2.0) and dedupe on `(agent_id, phone_number)`."*

### 7.2 Queue worker (Celery)
Build prompt: *"Add a Celery task `process_cold_call_queue` that, on a schedule (Celery beat, every N minutes, configurable per agent), pulls `pending` entries up to the agent's `daily_call_cap`, flips them to `queued`, and — since no real dialing happens from this platform — writes a `CallLog` stub with `status='queued_for_external_dialer'` and emits a webhook event (`POST` to a user-configured callback URL) so the user's own telephony system (Twilio/SIP/etc., outside this platform) can pick it up and place the actual call. Document this hand-off contract clearly in `/about-dev`."*

### 7.3 Queue UI
Build prompt: *"Build a Cold-Call Queue tab per agent: table of entries (name, number, status, source, created_at) with CSV upload button, filters by status, a 'Copy import webhook + curl example' box (using the Phase 3 webhook URL + key), and a status distribution chart (pending/queued/completed/failed) using a lightweight chart lib (Recharts)."*

---

## PHASE 8 — Account / billing tab

### 8.1 Stripe integration
Build prompt: *"Wire Stripe Checkout for two plans (e.g. Free: 1 agent, 50 test-call minutes/mo; Pro: unlimited agents, queue automation, higher rate limits). Backend: `POST /billing/checkout-session`, `POST /billing/portal-session`, and a `/billing/webhook` endpoint verifying Stripe signatures and updating the local `Subscription` row on `checkout.session.completed` / `customer.subscription.updated` / `.deleted` events."*

### 8.2 Plan gating
Build prompt: *"Add a dependency `require_plan(min_plan)` that checks the caller's active `Subscription.plan` before allowing agent-creation past the free limit, queue-import above a row cap, etc. Return a clean 402-style error the frontend can render as an upgrade prompt."*

### 8.3 Account tab UI
Build prompt: *"Build the Account tab: current plan card, usage this period (minutes used, agents used, queue rows this month) with progress bars, 'Manage billing' button → Stripe customer portal, invoice history list."*

---

## PHASE 9 — Testing, hardening, deployment

### 9.1 Test coverage
Build prompt: *"Add integration tests: full agent lifecycle (create→configure→rewrite-prompt→api-key→simulated test call via a mocked FastRTC session→call log written), webhook auth rejection cases, queue import + dedupe, Stripe webhook idempotency. Target the critical paths, not 100% coverage vanity metrics."*

### 9.2 Observability
Build prompt: *"Add structured logging (structlog) across backend + voice-engine, a `/health` endpoint per service, and basic Prometheus metrics (request latency, active call sessions, STT/TTS latency histograms, interruption count) exposed at `/metrics` for later Grafana wiring."*

### 9.3 Deployment
Build prompt: *"Write `infra/docker-compose.prod.yml` (no `--reload`, gunicorn+uvicorn workers, nginx TLS via certbot, environment-injected secrets — never committed). Document a one-page deploy runbook in `docs/DEPLOY.md` for a single VPS (e.g. Hetzner/DigitalOcean) as the MVP target before considering k8s."*

### 9.4 Security pass
Build prompt: *"Checklist and fix: secrets never logged, API keys shown once and stored hashed, CORS locked to the frontend origin, JWT short-lived access + rotating refresh, Stripe webhook signature verification, rate limits on auth + webhook routes, input validation on CSV import (size cap, MIME check), HTTPS-only cookies if using cookie-based sessions."*

---

## Suggested build order (checklist)

- [ ] Phase 0 — repo, docker-compose skeleton
- [ ] Phase 1 — auth + multi-tenant models
- [ ] Phase 2 — agent CRUD + prompt fields + AI-rewrite
- [ ] Phase 3 — API key + webhook
- [ ] Phase 4 — voice engine (STT/VAD/LLM/TTS/full-duplex pipeline)
- [ ] Phase 5 — simulated test-call page (FastRTC)
- [ ] Phase 6 — frontend shell + all tabs
- [ ] Phase 7 — cold-call queue + import
- [ ] Phase 8 — billing
- [ ] Phase 9 — tests, observability, deploy, security

Build strictly in this order — Phase 5 needs Phase 4's pipeline contract, Phase 6 needs Phase 2/3/7 endpoints to render against, Phase 8 needs Phase 1's user model.