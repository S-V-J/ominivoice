# OminiVoice Deployment Runbook

**Target**: Single VPS (Hetzner CX41 / DigitalOcean 4GB RAM / AWS t3.medium equivalent)
**Architecture**: Docker Compose with Nginx + Certbot for SSL

---

## 📋 Prerequisites

- VPS with **4+ GB RAM**, **2+ vCPUs**, **50+ GB SSD**
- Domain name pointed to VPS IP (A record)
- Docker 24+ and Docker Compose 2.20+ installed
- SSH access with sudo privileges

---

## 🔐 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose plugin
sudo apt install docker-compose-plugin

# Verify
docker compose version
```

---

## 🔧 2. Repository & Configuration

```bash
# Clone repo
git clone https://github.com/S-V-J/ominivoice.git
cd ominivoice

# Create production environment file
cp infra/.env.example infra/.env.prod
# EDIT infra/.env.prod with your values (see below)
```

### Required `.env.prod` Variables

```bash
# Core
POSTGRES_DB=ominivoice
POSTGRES_USER=ominivoice
POSTGRES_PASSWORD=<generate-strong-password>
REDIS_PASSWORD=<generate-strong-password>
JWT_SECRET=<generate-64-char-hex>
FRONTEND_URL=https://your-domain.com
DOMAIN=your-domain.com

# NVIDIA (Required for LLM)
NVIDIA_API_KEY=nvapi-your-key-here

# Stripe (Production keys)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_STARTER=price_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_ENTERPRISE=price_...

# Email (Optional - for notifications, password reset, invoices)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
SMTP_FROM=noreply@your-domain.com
EMAIL_RATE_LIMIT_PER_HOUR=50

# Optional: Stack B (NVIDIA NIM - requires GPU)
NGC_API_KEY=...
RIVA_ASR_GRPC_ENDPOINT=voice-riva-asr:50051
CHATTERBOX_GRPC_ENDPOINT=voice-chatterbox:50051
```

### Generate Secrets

```bash
# JWT Secret (64 hex chars)
openssl rand -hex 32

# Postgres/Redis passwords
openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
```

---

## 📦 3. Model Files (Stack A - Local Voice Engine)

**Required for Kokoro TTS and faster-whisper STT:**

```bash
# Create models directory
mkdir -p infra/voice_models/{kokoro,whisper,piper}

# Download Kokoro model
wget -O infra/voice_models/kokoro/kokoro-v1.0.onnx \
  https://github.com/hexgrad/kokoro/releases/download/v1.0/kokoro-v1.0.onnx

# Download Piper voice (optional fallback)
mkdir -p infra/voice_models/piper
wget -O infra/voice_models/piper/en_US-lessac-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/en_US-lessac-medium/en_US-lessac-medium.onnx
wget -O infra/voice_models/piper/en_US-lessac-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/en_US-lessac-medium/en_US-lessac-medium.onnx.json
```

> **Note**: faster-whisper downloads models automatically on first run (cached in `/models`).

---

## 🚀 4. Deploy

```bash
# Navigate to infra directory
cd infra

# Pull/build images
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml build

# Start services
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# Follow logs
docker compose -f docker-compose.prod.yml logs -f
```

---

## 🔒 5. SSL Certificate (Let's Encrypt)

The Nginx config automatically handles ACME challenges. Certbot runs as a sidecar container and renews automatically.

**First-time certificate request** (after DNS propagates):

```bash
# Certbot will auto-request on first nginx startup
# Monitor logs:
docker compose -f docker-compose.prod.yml logs -f certbot

# Force renewal if needed:
docker compose -f docker-compose.prod.yml exec certbot certbot renew --force-renewal
```

**Verify SSL**:
```bash
curl -I https://your-domain.com/health
# Should return 200 with SSL cert info
```

---

## ✅ 6. Verify Deployment

```bash
# Health checks
curl https://your-domain.com/health
curl https://your-domain.com/metrics

# API docs (dev only - disabled in prod)
# https://your-domain.com/docs

# Frontend
open https://your-domain.com

# Test user registration
curl -X POST https://your-domain.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'

# Verify Agent WebSocket endpoints (for external dialer integrations)
# After creating an agent and API key:
curl https://your-domain.com/api/agents/{AGENT_ID}/websocket-urls \
  -H "Authorization: Bearer $TOKEN"

curl https://your-domain.com/api/agents/{AGENT_ID}/websocket-test-token \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📊 7. Monitoring & Maintenance

### View Logs

```bash
# All services
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f worker
docker compose -f docker-compose.prod.yml logs -f nginx
```

### Metrics (Prometheus)

```bash
# Scrape metrics
curl https://your-domain.com/metrics

# Key metrics to alert on:
# - http_request_duration_seconds (p95 > 1s)
# - call_sessions_active (unexpected spikes)
# - db_connections_active (near pool limit)
# - celery_queue_length (growing backlog)
```

### Backup Database

```bash
# Daily backup (add to crontab)
docker exec ominivoice-postgres pg_dump -U ominivoice ominivoice | gzip > /backups/ominivoice_$(date +%F).sql.gz

# Keep last 30 days
find /backups -name "*.sql.gz" -mtime +30 -delete
```

### Restore Database

```bash
gunzip -c /backups/ominivoice_2026-08-17.sql.gz | docker exec -i ominivoice-postgres psql -U ominivoice -d ominivoice
```

### Update Application

```bash
cd /path/to/ominivoice
git pull origin main
docker compose -f infra/docker-compose.prod.yml build
docker compose -f infra/docker-compose.prod.yml up -d --remove-orphans
```

### Scale Workers

```bash
# Increase Celery workers
docker compose -f docker-compose.prod.yml up -d --scale worker=6
```

---

## 🛠 Troubleshooting

| Issue | Solution |
|-------|----------|
| SSL not working | Check DNS propagation, certbot logs, nginx config |
| API returns 502 | Check `docker logs ominivoice-api`, verify DB/Redis connectivity |
| WebSocket fails | Verify nginx proxy_read_timeout, websocket upgrade headers |
| Celery tasks stuck | Check worker logs, Redis connectivity, task timeouts |
| Out of memory | Reduce worker concurrency, check for memory leaks |

---

## 🔐 Security Checklist

- [ ] All `.env` secrets generated with strong randomness
- [ ] PostgreSQL and Redis passwords set (not defaults)
- [ ] JWT_SECRET is 64+ hex chars
- [ ] Nginx rate limits configured
- [ ] SSL/TLS working (A+ on SSL Labs)
- [ ] Security headers present (CSP, HSTS, etc.)
- [ ] Stripe webhook secret configured
- [ ] NVIDIA_API_KEY restricted to necessary permissions
- [ ] Database not exposed to internet (internal network only)
- [ ] Redis requires password
- [ ] Non-root users in containers

---

## 📞 Support

- **Logs**: `docker compose -f docker-compose.prod.yml logs -f`
- **Metrics**: `curl https://your-domain.com/metrics`
- **Health**: `curl https://your-domain.com/health`
- **Repo**: https://github.com/S-V-J/ominivoice