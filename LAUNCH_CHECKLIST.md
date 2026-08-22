# OminiVoice Local Network Launch Checklist

**Purpose**: Verify the complete system works on local network before any production deployment.

---

## 📋 Pre-Flight Checks

### 1. Prerequisites Installed
- [ ] Docker 24+ and Docker Compose 2.20+
- [ ] `mkcert` installed (`brew install mkcert` / `sudo apt install mkcert`)
- [ ] Git with repo cloned
- [ ] Stripe CLI installed (for webhook testing)

### 2. Generate Local SSL Certificates
```bash
# Install mkcert CA
mkcert -install

# Generate certificates for local domains
mkcert -key-file infra/nginx/ssl/ominivoice.local-key.pem \
       -cert-file infra/nginx/ssl/ominivoice.local.pem \
       ominivoice.local "*.ominivoice.local" localhost 127.0.0.1 ::1

# Verify certificates
ls -la infra/nginx/ssl/
# Should show: ominivoice.local.pem, ominivoice.local-key.pem
```

### 3. Configure Environment Files
```bash
# Copy and edit environment files
cp infra/.env.example infra/.env.local

# Edit infra/.env.local with these REQUIRED values:
```
**Required variables in `.env.local`:**
```bash
# Core (generate with: openssl rand -hex 32)
JWT_SECRET=your-64-char-hex-secret-here
POSTGRES_PASSWORD=your-secure-db-password
REDIS_PASSWORD=your-secure-redis-password

# Frontend/Backend URLs (local HTTPS)
FRONTEND_URL=https://ominivoice.local
# DOMAIN=ominivoice.local

# NVIDIA (REQUIRED for LLM)
NVIDIA_API_KEY=nvapi-your-actual-key-here

# Stripe (test mode)
STRIPE_SECRET_KEY=sk_test_your-stripe-secret
STRIPE_PUBLISHABLE_KEY=pk_test_your-stripe-publishable
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret
STRIPE_PRICE_ID_STARTER=price_your-starter-price-id
STRIPE_PRICE_ID_PRO=price_your-pro-price-id
STRIPE_PRICE_ID_ENTERPRISE=price_your-enterprise-price-id

# Email (optional - will log to console if not configured)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=noreply@ominivoice.local

# Optional: Stack B (NVIDIA NIM - requires GPU)
# NGC_API_KEY=your-ngc-key
# RIVA_ASR_GRPC_ENDPOINT=voice-riva-asr:50051
# CHATTERBOX_GRPC_ENDPOINT=voice-chatterbox:50051
```

### 4. Download Voice Models (Stack A - Local)
```bash
# Create model directories
mkdir -p infra/voice_models/kokoro infra/voice_models/whisper infra/voice_models/piper

# Download Kokoro TTS model (required for Stack A)
wget -O infra/voice_models/kokoro/kokoro-v1.0.onnx \
  https://github.com/hexgrad/kokoro/releases/download/v1.0/kokoro-v1.0.onnx

# Download Piper voice (optional fallback)
mkdir -p infra/voice_models/piper
wget -O infra/voice_models/piper/en_US-lessac-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/en_US-lessac-medium/en_US-lessac-medium.onnx
wget -O infra/voice_models/piper/en_US-lessac-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/en_US-lessac-medium/en_US-lessac-medium.onnx.json

# Verify
ls -la infra/voice_models/
```

### 5. Configure Local DNS
```bash
# Add to /etc/hosts (Linux/Mac) or C:\Windows\System32\drivers\etc\hosts (Windows)
# Requires admin/sudo
echo "127.0.0.1 ominivoice.local" | sudo tee -a /etc/hosts

# Verify
ping ominivoice.local
# Should resolve to 127.0.0.1
```

---

## 🚀 Launch Sequence

### 1. Start Services
```bash
cd /home/ML/ominivoice/infra

# Build and start all services
docker compose -f docker-compose.local.yml up -d --build

# Watch logs (in separate terminal)
docker compose -f docker-compose.local.yml logs -f
```

### 2. Verify Service Health
```bash
# Check all containers running
docker compose -f docker-compose.local.yml ps
# All should show "Up" status

# Health checks
curl -k https://ominivoice.local/health
curl -k https://ominivoice.local/metrics | head -20

# API docs (development only)
curl -k https://ominivoice.local/docs
```

### 3. Start Stripe Webhook Forwarding
```bash
# In separate terminal
stripe listen --forward-to https://ominivoice.local/billing/webhook
# Copy the webhook signing secret (whsec_...) and add to .env.local if not set
```

---

## ✅ Functional Validation Tests

### Test 1: User Registration & Auth
```bash
# Register
curl -k -X POST https://ominivoice.local/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'

# Login
curl -k -X POST https://ominivoice.local/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"test@example.com","password":"testpass123"}'
# Save access_token and refresh_token
```

### Test 2: Create Agent
```bash
# Use access_token from login
TOKEN="your-access-token-here"

curl -k -X POST https://ominivoice.local/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Sales Agent",
    "direction": "outbound",
    "system_prompt": "You are a friendly sales agent.",
    "opening_line": "Hi, this is a test call.",
    "objective_prompt": "Schedule a demo."
  }'
# Save agent_id
```

### Test 3: Configure Agent Prompts
```bash
# Update all required prompts
curl -k -X PATCH https://ominivoice.local/agents/$AGENT_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "system_prompt": "You are Sarah, a friendly sales representative for Acme Corp.",
    "opening_line": "Hi, this is Sarah from Acme Corp. I'm calling because we have a special offer.",
    "objective_prompt": "Schedule a 15-minute demo call.",
    "objection_handling_prompt": "If not interested: 'I understand. Many customers felt the same before seeing the demo.'",
    "voicemail_prompt": "Hi, this is Sarah from Acme Corp. Please call back at 555-0123.",
    "closing_prompt": "Great! I'll send a calendar invite. What's your best email?",
    "escalation_rule": "If asked for manager, say 'I'll have my manager reach out within 24 hours.'"
  }'
```

### Test 4: Generate API Key & Webhook
```bash
curl -k -X POST https://ominivoice.local/agents/$AGENT_ID/api-key \
  -H "Authorization: Bearer $TOKEN"
# Save the key (shown once!) and webhook_url
```

### Test 5: Import Cold Call Queue
```bash
# Create test CSV
cat > test_contacts.csv << 'EOF'
contact_name,phone_number,email,company
John Doe,+15551234567,john@example.com,Acme Corp
Jane Smith,+15559876543,jane@example.com,Globex Inc
EOF

curl -k -X POST https://ominivoice.local/agents/$AGENT_ID/cold-call-queue/import \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test_contacts.csv" \
  -F "source=csv_upload"
```

### Test 6: Start Simulated Test Call
```bash
# Open browser to https://ominivoice.local
# Navigate to agent detail → "Test Agent" tab
# Click "Start Test Call"
# Allow microphone permission
# Speak and verify:
#   - Agent responds with opening_line (outbound) or waits for greeting (inbound)
#   - Live transcript appears
#   - Audio level meter moves
#   - Pipeline state changes: listening → processing → speaking
#   - Barge-in works: interrupt agent mid-sentence
#   - End call → summary card shows duration, turns, interruptions
```

### Test 7: Verify API Key & Agent Configuration (curl)
```bash
# Get WebSocket URLs (includes common endpoint + test token)
curl -k -X GET "https://ominivoice.local/api/agents/$AGENT_ID/websocket-urls" \
  -H "Authorization: Bearer $TOKEN"

# Get one-time test token (valid 1 hour)
curl -k -X GET "https://ominivoice.local/api/agents/$AGENT_ID/websocket-test-token" \
  -H "Authorization: Bearer $TOKEN"
# Save test_token from response

# Verify agent configuration is complete
curl -k -X GET "https://ominivoice.local/agents/$AGENT_ID/completeness" \
  -H "Authorization: Bearer $TOKEN"
# Should return: {"is_complete": true, "completion_percentage": 100, ...}

# Verify API key exists and get usage stats
curl -k -X GET "https://ominivoice.local/api/agents/$AGENT_ID/api-key" \
  -H "Authorization: Bearer $TOKEN"
# Returns: key_prefix, webhook_url, usage_today, etc.

# Complete curl-only verification script
cat > verify_agent.sh << 'EOF'
#!/bin/bash
# Usage: ./verify_agent.sh <TOKEN> <AGENT_ID>

TOKEN=$1
AGENT_ID=$2

if [ -z "$TOKEN" ] || [ -z "$AGENT_ID" ]; then
    echo "Usage: $0 <ACCESS_TOKEN> <AGENT_ID>"
    exit 1
done

echo "=== Verifying Agent $AGENT_ID ==="
echo ""

echo "1. Checking agent completeness..."
curl -k -s -X GET "https://ominivoice.local/agents/$AGENT_ID/completeness" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "2. Getting API key info..."
curl -k -s -X GET "https://ominivoice.local/api/agents/$AGENT_ID/api-key" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "3. Getting WebSocket URLs..."
curl -k -s -X GET "https://ominivoice.local/api/agents/$AGENT_ID/websocket-urls" \
  -H "Authorization: Bearer $TOKEN" | jq '.'

echo ""
echo "4. Getting test token..."
TEST_TOKEN=$(curl -k -s -X GET "https://ominivoice.local/api/agents/$AGENT_ID/websocket-test-token" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.test_token')
echo "Test token: $TEST_TOKEN"

echo ""
echo "5. Testing test token endpoint (via curl - will fail for WS but shows connection)..."
echo "WebSocket URI: wss://ominivoice.local/ws?token=$TEST_TOKEN"
echo "(Use Python script for actual WebSocket test)"

echo ""
echo "=== Verification Complete ==="
echo "If all curl commands returned 200, agent is ready for WebSocket testing."
EOF
chmod +x verify_agent.sh

# Run: ./verify_agent.sh "YOUR_TOKEN" "YOUR_AGENT_ID"
```

### Test 8: Universal Voice Agent WebSocket Test Scripts
```bash
# Test 1: Using test token (agent_id embedded in token, no config needed for agent resolution)
# Requires: pip install websockets
cat > test_ws_universal_token.py << 'EOF'
import asyncio
import websockets
import json
import sys

async def test():
    if len(sys.argv) < 2:
        print("Usage: python test_ws_universal_token.py <TEST_TOKEN>")
        return
    
    token = sys.argv[1]
    uri = f"wss://ominivoice.local/ws?token={token}"
    
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri, ping_interval=20) as ws:
        print("✓ Connected successfully")
        
        # 1. Wait for READY message
        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(msg)
        print(f"← {data['type']}: session_id={data['data'].get('session_id')}")
        
        if data["type"] != "ready":
            print(f"✗ Expected 'ready', got {data['type']}")
            return
        
        # 2. Send FULL config (test token has agent_id, but config still required for voice setup)
        config = {
            "type": "config",
            "data": {
                "direction": "outbound",
                "system_prompt": "You are a test agent. Keep responses very brief - one sentence max.",
                "voice_stack": "stack_a",
                "opening_line": "Hello! This is a test call.",
                "objective_prompt": "Verify the WebSocket connection works.",
                "interruption_sensitivity": "medium",
                "max_call_duration_s": 60,
                "silence_timeout_s": 5,
                "language": "en-US",
                "stt_engine": "faster-whisper",
                "tts_engine": "kokoro",
                "tts_voice": "af_heart",
                "llm_provider": "nvidia_integrate",
                "llm_model": "stepfun-ai/step-3.7-flash"
            }
        }
        await ws.send(json.dumps(config))
        print("→ Sent config")
        
        # 3. Wait for STARTED
        msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
        data = json.loads(msg)
        print(f"← {data['type']}: {data['data'].get('session_id')}")
        
        if data["type"] != "started":
            print(f"✗ Expected 'started', got {data['type']}")
            if data["type"] == "error":
                print(f"  Error: {data['data'].get('message')}")
            return
        
        print(f"✓ Call started with capabilities: {data['data'].get('capabilities')}")
        
        # 4. Listen for messages
        for i in range(10):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                if isinstance(msg, bytes):
                    print(f"← [Audio chunk: {len(msg)} bytes]")
                else:
                    data = json.loads(msg)
                    if data["type"] == "transcript":
                        print(f"  📝 {data['data']['role']}: {data['data']['text'][:60]}...")
                    elif data["type"] == "state":
                        print(f"  🔄 State: {data['data']}")
                    elif data["type"] == "ended":
                        print(f"✓ Call ended: {data['data']['duration_seconds']:.1f}s")
                        break
                    elif data["type"] == "error":
                        print(f"✗ Error: {data['data'].get('message')}")
                        break
            except asyncio.TimeoutError:
                continue
        
        # 5. End call
        await ws.send(json.dumps({"type": "end"}))
        print("✓ Test completed - sent end")

asyncio.run(test())
EOF

# Run: python test_ws_universal_token.py "YOUR_TEST_TOKEN_HERE"
```

```bash
# Test 2: Using API key (full config required including agent_id for tracking)
cat > test_ws_universal_apikey.py << 'EOF'
import asyncio
import websockets
import json
import sys

async def test():
    if len(sys.argv) < 3:
        print("Usage: python test_ws_universal_apikey.py <API_KEY> <AGENT_ID>")
        return
    
    api_key = sys.argv[1]
    agent_id = sys.argv[2]
    uri = f"wss://ominivoice.local/ws?api_key={api_key}"
    
    print(f"Connecting to {uri} for agent {agent_id}...")
    async with websockets.connect(uri, ping_interval=20) as ws:
        print("✓ Connected successfully")
        
        # 1. Wait for READY
        msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
        data = json.loads(msg)
        print(f"← {data['type']}: session_id={data['data'].get('session_id')}")
        
        if data["type"] != "ready":
            print(f"✗ Expected 'ready', got {data['type']}")
            return
        
        # 2. Send FULL config (REQUIRED - no portal setup)
        config = {
            "type": "config",
            "data": {
                "agent_id": agent_id,
                "direction": "outbound",
                "system_prompt": "You are a test agent. Keep responses very brief - one sentence max.",
                "voice_stack": "stack_a",
                "opening_line": "Hello! This is a test call from external system.",
                "objective_prompt": "Verify the WebSocket connection works.",
                "interruption_sensitivity": "medium",
                "max_call_duration_s": 60,
                "silence_timeout_s": 5,
                "language": "en-US",
                "stt_engine": "faster-whisper",
                "tts_engine": "kokoro",
                "tts_voice": "af_heart",
                "llm_provider": "nvidia_integrate",
                "llm_model": "stepfun-ai/step-3.7-flash"
            }
        }
        await ws.send(json.dumps(config))
        print("→ Sent config")
        
        # 3. Wait for STARTED
        msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
        data = json.loads(msg)
        print(f"← {data['type']}: {data['data'].get('session_id')}")
        
        if data["type"] != "started":
            print(f"✗ Expected 'started', got {data['type']}")
            if data["type"] == "error":
                print(f"  Error: {data['data'].get('message')}")
            return
        
        print(f"✓ Call started with capabilities: {data['data'].get('capabilities')}")
        
        # 4. Listen for messages
        for i in range(10):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5.0)
                if isinstance(msg, bytes):
                    print(f"← [Audio chunk: {len(msg)} bytes]")
                else:
                    data = json.loads(msg)
                    if data["type"] == "transcript":
                        print(f"  📝 {data['data']['role']}: {data['data']['text'][:60]}...")
                    elif data["type"] == "state":
                        print(f"  🔄 State: {data['data']}")
                    elif data["type"] == "ended":
                        print(f"✓ Call ended: {data['data']['duration_seconds']:.1f}s")
                        break
                    elif data["type"] == "error":
                        print(f"✗ Error: {data['data'].get('message')}")
                        break
            except asyncio.TimeoutError:
                continue
        
        # 5. End call
        await ws.send(json.dumps({"type": "end"}))
        print("✓ Test completed - sent end")

asyncio.run(test())
EOF

# Run: python test_ws_universal_apikey.py "ov_live_YOUR_32_CHAR_KEY" "AGENT_ID_HERE"
```

```bash
# Test 3: Complete curl + WebSocket verification script
cat > test_universal_agent.sh << 'EOF'
#!/bin/bash
# Complete verification: curl checks + WebSocket test
# Usage: ./test_universal_agent.sh <ACCESS_TOKEN> <AGENT_ID> <API_KEY>

set -e

TOKEN=$1
AGENT_ID=$2
API_KEY=$3

if [ -z "$TOKEN" ] || [ -z "$AGENT_ID" ] || [ -z "$API_KEY" ]; then
    echo "Usage: $0 <ACCESS_TOKEN> <AGENT_ID> <API_KEY>"
    exit 1
fi

echo "============================================"
echo "  Universal Voice Agent Verification"
echo "============================================"

# Get test token
TEST_TOKEN=$(curl -k -s -X GET "https://ominivoice.local/api/agents/$AGENT_ID/websocket-test-token" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.test_token')

echo "Test Token: $TEST_TOKEN"
echo "WebSocket URI (token): wss://ominivoice.local/ws?token=$TEST_TOKEN"
echo "WebSocket URI (apikey): wss://ominivoice.local/ws?api_key=$API_KEY"
echo ""

# Run Python test with test token
if command -v python3 &> /dev/null; then
    echo "Running WebSocket test with test token..."
    python3 test_ws_universal_token.py "$TEST_TOKEN"
else
    echo "Python3 not found - install to run WebSocket test"
fi

echo ""
echo "============================================"
echo "  Manual Test Commands"
echo "============================================"
echo "# With test token (agent_id in token):"
echo "python3 test_ws_universal_token.py \"$TEST_TOKEN\""
echo ""
echo "# With API key (full config required):"
echo "python3 test_ws_universal_apikey.py \"$API_KEY\" \"$AGENT_ID\""
echo ""
echo "# Direct WebSocket URLs:"
echo "wss://ominivoice.local/ws?token=$TEST_TOKEN"
echo "wss://ominivoice.local/ws?api_key=$API_KEY"
EOF
chmod +x test_universal_agent.sh

# Run: ./test_universal_agent.sh "YOUR_TOKEN" "YOUR_AGENT_ID" "ov_live_YOUR_KEY"
```

### Test 9: Complete Agent Verification Script (All curl)
```bash
# Complete verification script - run after creating agent and getting token
cat > verify_agent_complete.sh << 'EOF'
#!/bin/bash
# Usage: ./verify_agent_complete.sh <ACCESS_TOKEN> <AGENT_ID> [API_KEY]
# API_KEY is optional - if provided, also tests WebSocket with API key auth

set -e

TOKEN=$1
AGENT_ID=$2
API_KEY=$3

if [ -z "$TOKEN" ] || [ -z "$AGENT_ID" ]; then
    echo "Usage: $0 <ACCESS_TOKEN> <AGENT_ID> [API_KEY]"
    exit 1
fi

echo "============================================"
echo "  OminiVoice Agent Verification"
echo "============================================"
echo "Agent ID: $AGENT_ID"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

check() {
    local name=$1
    local cmd=$2
    echo -n "[$name] "
    if eval "$cmd" > /tmp/check_result.json 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        cat /tmp/check_result.json | jq '.' 2>/dev/null || cat /tmp/check_result.json
    else
        echo -e "${RED}✗ FAIL${NC}"
        cat /tmp/check_result.json
    fi
    echo ""
}

echo "--- 1. Agent Configuration ---"
check "Completeness" \
  "curl -k -s -X GET \"https://ominivoice.local/agents/$AGENT_ID/completeness\" -H \"Authorization: Bearer $TOKEN\" | jq -e '.is_complete == true'"

check "Agent Details" \
  "curl -k -s -X GET \"https://ominivoice.local/agents/$AGENT_ID\" -H \"Authorization: Bearer $TOKEN\" | jq -e '.id == \"$AGENT_ID\"'"

echo "--- 2. API Key & WebSocket ---"
check "API Key Info" \
  "curl -k -s -X GET \"https://ominivoice.local/api/agents/$AGENT_ID/api-key\" -H \"Authorization: Bearer $TOKEN\" | jq -e '.is_active == true'"

check "WebSocket URLs" \
  "curl -k -s -X GET \"https://ominivoice.local/api/agents/$AGENT_ID/websocket-urls\" -H \"Authorization: Bearer $TOKEN\" | jq -e '.common_websocket_endpoint != null'"

check "Test Token" \
  "curl -k -s -X GET \"https://ominivoice.local/api/agents/$AGENT_ID/websocket-test-token\" -H \"Authorization: Bearer $TOKEN\" | jq -e '.test_token != null'"

# Extract test token for WebSocket test
TEST_TOKEN=$(curl -k -s -X GET "https://ominivoice.local/api/agents/$AGENT_ID/websocket-test-token" -H "Authorization: Bearer $TOKEN" | jq -r '.test_token')
echo "Test Token: $TEST_TOKEN"
echo "WebSocket URI (test token): wss://ominivoice.local/ws?token=$TEST_TOKEN"
echo ""

if [ -n "$API_KEY" ]; then
    echo "--- 3. API Key WebSocket Test ---"
    echo "WebSocket URI (API key): wss://ominivoice.local/ws?api_key=$API_KEY"
    echo "Required config message:"
    cat << CONFIGEOF
{
  "type": "config",
  "data": {
    "agent_id": "$AGENT_ID",
    "direction": "outbound",
    "system_prompt": "Test agent",
    "voice_stack": "stack_a",
    "opening_line": "Test call",
    "objective_prompt": "Verify",
    "interruption_sensitivity": "medium",
    "max_call_duration_s": 60,
    "silence_timeout_s": 5,
    "language": "en-US",
    "stt_engine": "faster-whisper",
    "tts_engine": "kokoro",
    "tts_voice": "af_heart",
    "llm_provider": "nvidia_integrate",
    "llm_model": "stepfun-ai/step-3.7-flash"
  }
}
CONFIGEOF
fi

echo "--- 4. Call Logs & Queue ---"
check "Call Logs" \
  "curl -k -s -X GET \"https://ominivoice.local/agents/$AGENT_ID/calls\" -H \"Authorization: Bearer $TOKEN\" | jq -e 'type == \"array\"'"

check "Call Stats" \
  "curl -k -s -X GET \"https://ominivoice.local/agents/$AGENT_ID/calls/stats\" -H \"Authorization: Bearer $TOKEN\" | jq -e '.total_calls != null'"

check "Queue Stats" \
  "curl -k -s -X GET \"https://ominivoice.local/agents/$AGENT_ID/cold-call-queue/stats\" -H \"Authorization: Bearer $TOKEN\" | jq -e '.total != null'"

echo "============================================"
echo "  Verification Complete"
echo "============================================"
echo ""
echo "If all checks passed (✓ PASS), the agent is ready for:"
echo "  - Simulated browser calls (Test Agent tab)"
echo "  - External WebSocket dialer integration"
echo "  - Cold call queue processing"
echo ""
echo "WebSocket endpoints:"
echo "  Test Token: wss://ominivoice.local/ws?token=$TEST_TOKEN"
if [ -n "$API_KEY" ]; then
    echo "  API Key:    wss://ominivoice.local/ws?api_key=$API_KEY"
fi
EOF
chmod +x verify_agent_complete.sh

# Run: ./verify_agent_complete.sh "YOUR_TOKEN" "YOUR_AGENT_ID" "YOUR_API_KEY"
```

### Test 10: Billing Flow
```bash
# Upgrade plan
curl -k -X POST https://ominivoice.local/billing/checkout-session \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan": "starter",
    "success_url": "https://ominivoice.local/account?success=true",
    "cancel_url": "https://ominivoice.local/account?canceled=true"
  }'
# Follow returned URL, complete Stripe test payment (card: 4242 4242 4242 4242)

# Check usage stats
curl -k -X GET https://ominivoice.local/billing/usage \
  -H "Authorization: Bearer $TOKEN"
```

### Test 11: Email Verification Flow
```bash
# Register new user
curl -k -X POST https://ominivoice.local/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@example.com","password":"newpass123"}'

# Check console logs for verification email (logs to stdout in dev)
# Click link in email (or extract token from logs)
curl -k -X POST https://ominivoice.local/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"token":"verification-token-from-email"}'

# Verify user is now verified
curl -k -X GET https://ominivoice.local/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

---

## 🔍 Troubleshooting Common Issues

| Issue | Solution |
|-------|----------|
| `curl: (60) SSL certificate problem` | Use `-k` flag or install mkcert CA: `mkcert -install` |
| `Connection refused` | Check `docker compose -f docker-compose.local.yml ps` - all services must be "Up" |
| `WebSocket connection failed` | Verify nginx config has `proxy_set_header Upgrade $http_upgrade` |
| `No audio in test call` | Check browser microphone permissions; verify HTTPS (required for mic) |
| `Stripe webhook not received` | Ensure `stripe listen` is running and `.env.local` has correct `STRIPE_WEBHOOK_SECRET` |
| `Email not sending` | Check SMTP settings in `.env.local`; logs show emails in dev mode |
| `Queue not processing` | Check worker logs: `docker compose -f docker-compose.local.yml logs worker` |

---

## ✅ Launch Sign-Off

- [ ] All services healthy (`docker compose ps`)
- [ ] HTTPS works with valid cert (no browser warnings)
- [ ] User registration → verification → login works
- [ ] Agent creation with all 14 prompts works
- [ ] API key generation + webhook URL works
- [ ] CSV import with dedupe works
- [ ] Simulated call: audio in/out, transcript, barge-in, summary
- [ ] Call logs recorded with transcript
- [ ] Cold call queue: import → process → stats
- [ ] Stripe checkout → payment → plan upgrade → usage stats
- [ ] Email verification → password reset flows
- [ ] Prometheus metrics at `/metrics`
- [ ] Structured JSON logs in container output
- [ ] WebSocket endpoints: `/api/agents/{id}/websocket-urls` returns local + internet URLs (common endpoint)
- [ ] WebSocket test token: `/api/agents/{id}/websocket-test-token` returns valid JWT
- [ ] External WebSocket connection: `wss://ominivoice.local/ws?token=...` works (common endpoint)
- [ ] WebSocket protocol: config → transcript/state/end messages flow correctly

---

## 📝 Post-Launch Notes

Record any issues found during validation:
- Issue 1:
- Issue 2:
- Issue 3:

**Validated by**: ________________ **Date**: ________________