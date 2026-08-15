# OminiVoice

**A multi-tenant SaaS platform for configuring and testing AI voice agents with simulated browser calls.**

## Overview

OminiVoice enables users to:
- Register and manage voice agents with editable prompts
- Test agents instantly via **simulated browser calls** (WebRTC, no PSTN/SIP required)
- Get API keys and webhook URLs per agent for integration
- Manage cold-calling lead queues
- Handle billing via Stripe

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OminiVoice Architecture                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                  │
│  │  Frontend   │────▶│    API      │◀───▶│  Voice      │                  │
│  │  (React)    │     │  (FastAPI)  │     │  Engine     │                  │
│  └─────────────┘     └──────┬──────┘     └──────┬──────┘                  │
│                             │                    │                         │
│                    ┌────────┴────────┐          │                         │
│                    ▼                 ▼          ▼                         │
│             ┌────────────┐    ┌────────────┐  ┌─────────┐               │
│             │ PostgreSQL │    │   Redis    │  │ STT/TTS │               │
│             │  (Data)    │    │ (Cache/Q)  │  │ VAD/LLM │               │
│             └────────────┘    └────────────┘  └─────────┘               │
│                                                                             │
│  Simulated Call Flow:                                                       │
│  ┌─────────┐   WebRTC    ┌──────────┐   Pipecat    ┌─────────────┐        │
│  │ Browser │◀───────────▶│ FastRTC  │◀────────────▶│ STT→LLM→TTS │        │
│  │ (Mic/Spk)│             │ (Transport)              │ Pipeline    │        │
│  └─────────┘             └──────────┘              └─────────────┘        │
│                                                                             │
│  Real Telephony (future):                                                   │
│  ┌─────────┐   SIP/RTP  ┌────────────┐    Adapter    ┌─────────────┐       │
│  │  PSTN   │◀──────────▶│  Asterisk  │◀─────────────▶│ Same Pipeline│       │
│  │ / Twilio│            │  / Kamailio│               │ (no changes) │       │
│  └─────────┘            └────────────┘               └─────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology | License |
|-------|-----------|---------|
| Backend API | FastAPI (Python 3.11+) | MIT |
| Realtime Voice | Pipecat (Daily.co) | BSD-2 |
| Browser Transport | FastRTC (Hugging Face) | Apache-2.0 |
| VAD | Silero VAD | MIT |
| Turn Detection | Pipecat Smart Turn v2 | Apache-2.0 |
| STT | faster-whisper (CTranslate2) | MIT |
| TTS | Kokoro-82M (primary), Piper (fallback) | Apache-2.0 / MIT |
| LLM | Pluggable: Ollama (default), NVIDIA API | Mixed |
| Database | PostgreSQL 16 | PostgreSQL |
| Cache/Queue | Redis 7 | BSD |
| Auth | JWT (access + refresh) + bcrypt | MIT |
| Frontend | React + Vite + TypeScript + Tailwind | MIT |
| Billing | Stripe | Commercial |
| Background Jobs | Celery + Redis | BSD |
| Containerization | Docker Compose | Apache-2.0 |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 20+ (for frontend dev)
- Python 3.11+ (for backend dev)
- NVIDIA GPU (optional, for faster STT/TTS)

### Local Development

```bash
# 1. Clone and enter
cd ominivoice

# 2. Copy environment template
cp infra/.env.example .env
# Edit .env with your keys (at minimum: JWT_SECRET, STRIPE_SECRET_KEY)

# 3. Start all services
docker compose -f infra/docker-compose.yml up --build

# 4. Access the app
# Frontend: http://localhost:3000
# API docs: http://localhost:8000/docs
# Voice Engine WS: ws://localhost:8001/ws
```

### Manual Development (without Docker)

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev

# Voice Engine
cd voice-engine
pip install -r requirements.txt
python server.py
```

## Project Structure

```
ominivoice/
├── backend/              # FastAPI application
│   ├── app/
│   │   ├── api/          # API routes
│   │   ├── core/         # Config, security, database
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   └── tasks/        # Celery tasks
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/             # React + Vite + TypeScript
│   ├── src/
│   │   ├── components/   # Reusable UI components
│   │   ├── pages/        # Page components
│   │   ├── hooks/        # Custom React hooks
│   │   ├── services/     # API clients
│   │   ├── store/        # State management
│   │   └── types/        # TypeScript types
│   ├── package.json
│   └── Dockerfile
│
├── voice-engine/         # Pipecat pipeline + STT/TTS/VAD
│   ├── pipeline/         # Pipecat pipeline definitions
│   ├── stt/              # Speech-to-text modules
│   ├── tts/              # Text-to-speech modules
│   ├── vad/              # Voice activity detection
│   ├── llm/              # LLM provider abstraction
│   ├── transport/        # FastRTC transport
│   ├── server.py         # WebSocket server
│   ├── requirements.txt
│   └── Dockerfile
│
├── infra/                # Infrastructure as code
│   ├── docker-compose.yml
│   ├── nginx.conf
│   ├── .env.example
│   └── alembic/          # Database migrations
│
├── docs/                 # Documentation
│   ├── architecture.md
│   ├── api-reference.md
│   └── deployment.md
│
├── .gitignore
├── LICENSE
└── README.md
```

## Key Features

### 1. Agent Configuration
- Create voice agents with custom system prompts
- "Rewrite with AI" button to improve prompts via LLM
- Per-agent API keys and webhook URLs
- Model selection (Ollama local / NVIDIA API)

### 2. Simulated Call Testing
- In-browser WebRTC call (mic + speaker)
- No telephony provider needed
- Full STT→LLM→TTS pipeline execution
- Real-time transcript display

### 3. Cold-Calling Lead Queue
- Upload CSV/JSON lead lists
- Configure dialing schedules
- Track call outcomes
- Webhook notifications on call completion

### 4. Multi-Tenant Billing
- Stripe integration (test mode ready)
- Usage-based pricing (minutes, calls)
- Subscription tiers
- Invoice management

## Environment Variables

See `infra/.env.example` for all required variables:

```bash
# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/ominivoice

# Redis
REDIS_URL=redis://redis:6379/0

# Auth
JWT_SECRET=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# LLM Providers
NVIDIA_API_KEY=your-nvidia-api-key
OLLAMA_BASE_URL=http://ollama:11434

# Voice Engine
TTS_ENGINE=kokoro  # or piper
STT_ENGINE=faster-whisper
VAD_ENGINE=silero

# Frontend
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8001
```

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `docker compose -f infra/docker-compose.yml run --rm api pytest`
5. Submit a PR

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Pipecat](https://github.com/daily-co/pipecat) for the realtime voice pipeline framework
- [FastRTC](https://github.com/huggingface/fastrtc) for browser WebRTC transport
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) for streaming STT
- [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) for efficient TTS
- [Silero VAD](https://github.com/snakers4/silero-vad) for voice activity detection