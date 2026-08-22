#!/usr/bin/env bash
# OminiVoice Local Launch Script
# Usage: ./launch.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $*"; }
ok() { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err() { echo -e "${RED}[✗]${NC} $*"; }

# Project root
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

log "Starting OminiVoice local launch..."

# 1. Check prerequisites
log "Checking prerequisites..."

for cmd in docker docker-compose mkcert; do
    if ! command -v "$cmd" &>/dev/null; then
        err "Missing required command: $cmd"
        exit 1
    fi
done
ok "All prerequisites found"

# 2. Generate SSL certificates
log "Generating SSL certificates with mkcert..."
if [[ ! -f "infra/nginx/ssl/ominivoice.local.pem" ]] || [[ ! -f "infra/nginx/ssl/ominivoice.local-key.pem" ]]; then
    mkcert -install
    mkcert -key-file infra/nginx/ssl/ominivoice.local-key.pem \
           -cert-file infra/nginx/ssl/ominivoice.local.pem \
           ominivoice.local "*.ominivoice.local" localhost 127.0.0.1 ::1
    ok "SSL certificates generated"
else
    ok "SSL certificates already exist"
fi

# 3. Configure /etc/hosts
log "Configuring /etc/hosts..."
if ! grep -q "ominivoice.local" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1 ominivoice.local" | sudo tee -a /etc/hosts >/dev/null
    ok "Added ominivoice.local to /etc/hosts"
else
    ok "/etc/hosts already configured"
fi

# 4. Check environment file
log "Checking environment configuration..."
if [[ ! -f "infra/.env.local" ]]; then
    warn "Creating infra/.env.local from example..."
    cp infra/.env.example infra/.env.local

    # Generate secure defaults
    JWT_SECRET=$(openssl rand -hex 32)
    POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
    REDIS_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)

    sed -i "s|JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" infra/.env.local
    sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|" infra/.env.local
    sed -i "s|REDIS_PASSWORD=.*|REDIS_PASSWORD=$REDIS_PASSWORD|" infra/.env.local
    sed -i "s|FRONTEND_URL=.*|FRONTEND_URL=https://ominivoice.local|" infra/.env.local

    warn "Please edit infra/.env.local and add your:"
    warn "  - NVIDIA_API_KEY (required for LLM)"
    warn "  - STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET"
    warn "  - STRIPE_PRICE_ID_STARTER, STRIPE_PRICE_ID_PRO, STRIPE_PRICE_ID_ENTERPRISE"
    warn "  - SMTP settings (optional)"
    echo ""
    read -p "Press Enter after editing infra/.env.local to continue..."
fi
ok "Environment file ready"

# 5. Download voice models
log "Checking voice models..."
mkdir -p infra/voice_models/kokoro infra/voice_models/piper
if [[ ! -f "infra/voice_models/kokoro/kokoro-v1.0.onnx" ]]; then
    log "Downloading Kokoro TTS model (~70MB)..."
    wget -q --show-progress -O infra/voice_models/kokoro/kokoro-v1.0.onnx \
        https://github.com/hexgrad/kokoro/releases/download/v1.0/kokoro-v1.0.onnx
    ok "Kokoro model downloaded"
else
    ok "Kokoro model already present"
fi

if [[ ! -f "infra/voice_models/piper/en_US-lessac-medium.onnx" ]]; then
    log "Downloading Piper voice model (~45MB)..."
    wget -q --show-progress -O infra/voice_models/piper/en_US-lessac-medium.onnx \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/en_US-lessac-medium/en_US-lessac-medium.onnx
    wget -q -O infra/voice_models/piper/en_US-lessac-medium.onnx.json \
        https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/en_US-lessac-medium/en_US-lessac-medium.onnx.json
    ok "Piper voice downloaded"
else
    ok "Piper voice already present"
fi

# 6. Launch services
log "Starting Docker services..."
cd infra
docker compose -f docker-compose.local.yml up -d --build

# 7. Wait for services to be healthy
log "Waiting for services to be healthy..."
sleep 5

for i in {1..30}; do
    if curl -k -s https://ominivoice.local/health >/dev/null 2>&1; then
        ok "API is healthy"
        break
    fi
    if [[ $i -eq 30 ]]; then
        warn "API health check timeout. Check logs: docker compose -f docker-compose.local.yml logs api"
        break
    fi
    sleep 2
done

# 8. Start Stripe webhook forwarding (background)
if command -v stripe &>/dev/null; then
    log "Starting Stripe webhook forwarding..."
    stripe listen --forward-to https://ominivoice.local/billing/webhook > /tmp/stripe-webhook.log 2>&1 &
    STRIPE_PID=$!
    echo $STRIPE_PID > /tmp/stripe-webhook.pid
    sleep 2
    ok "Stripe webhook forwarding started (PID: $STRIPE_PID)"
    log "Webhook secret (add to .env.local): $(grep 'whsec_' /tmp/stripe-webhook.log 2>/dev/null | head -1 || echo 'Check /tmp/stripe-webhook.log')"
else
    warn "Stripe CLI not found. Install with: https://stripe.com/docs/stripe-cli"
    warn "Then run: stripe listen --forward-to https://ominivoice.local/billing/webhook"
fi

# 9. Final status
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║          OminiVoice is now running locally! 🎉          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}Access points:${NC}"
echo -e "  Frontend:      https://ominivoice.local"
echo -e "  API Health:    https://ominivoice.local/health"
echo -e "  API Docs:      https://ominivoice.local/docs"
echo -e "  Metrics:       https://ominivoice.local/metrics"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo -e "  View logs:     docker compose -f infra/docker-compose.local.yml logs -f"
echo -e "  Stop all:      docker compose -f infra/docker-compose.local.yml down"
echo -e "  Restart:       docker compose -f infra/docker-compose.local.yml restart"
echo -e "  Stripe logs:   tail -f /tmp/stripe-webhook.log"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Open https://ominivoice.local in browser"
echo -e "  2. Register an account"
echo -e "  3. Create an agent (Configure tab)"
echo -e "  4. Add prompts, generate API key"
echo -e "  5. Import cold call queue (CSV)"
echo -e "  6. Start a test call (Test Agent tab)"
echo ""
echo -e "${GREEN}Happy testing! 🚀${NC}"