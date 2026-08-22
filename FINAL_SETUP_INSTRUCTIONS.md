# OminiVoice Final Setup Instructions

Your .env file is already configured with valid API keys!
You just need to download the voice model files.

## 📥 Step 1: Download Voice Models (Run these commands)

### Kokoro TTS Model (~70MB - REQUIRED)
```bash
wget -O /home/ML/ominivoice/infra/voice_models/kokoro/kokoro-v1.0.onnx \
  https://github.com/hexgrad/kokoro/releases/download/v1.0/kokoro-v1.0.onnx
```

### Piper Voice Model (~45MB) + Config (OPTIONAL - Fallback)
```bash
wget -O /home/ML/ominivoice/infra/voice_models/piper/en_US-lessac-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/en_US-lessac-medium/en_US-lessac-medium.onnx

wget -O /home/ML/ominivoice/infra/voice_models/piper/en_US-lessac-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/en_US-lessac-medium/en_US-lessac-medium.onnx.json
```

## 🔍 Step 2: Verify Downloads
```bash
# Check file sizes (should NOT be 0 bytes)
ls -lh /home/ML/ominivoice/infra/voice_models/kokoro/
ls -lh /home/ML/ominivoice/infra/voice_models/piper/

# Expected:
# kokoro-v1.0.onnx: ~70MB
# en_US-lessac-medium.onnx: ~45MB  
# en_US-lessac-medium.onnx.json: ~1KB
```

## 🚀 Step 3: Launch the System
```bash
# From project root directory:
./launch.sh

# OR manually:
cd /home/ML/ominivoice/infra
docker compose -f docker-compose.local.yml up -d --build

# In a separate terminal (for Stripe webhook testing):
stripe listen --forward-to https://ominivoice.local/billing/webhook
```

## ✅ Step 4: Verify Health & Access
```bash
# Health check (should return healthy)
curl -k https://ominivoice.local/health

# Metrics endpoint
curl -k https://ominivoice.local/metrics

# Access the application:
# Frontend: https://ominivoice.local
# API Docs: https://ominivoice.local/docs
```

## 🎯 What You'll Be Able To Do

Once running, you can:
1. **Register** a user account at https://ominivoice.local/register
2. **Create** voice agents with detailed prompts (14 fields per direction)
3. **Test agents** via simulated WebRTC calls (no phone numbers needed!)
4. **Import** cold call queues via CSV
5. **Get API keys** and webhook URLs for integration
6. **Use universal WebSocket** endpoint for ANY telephony system (Asterisk, Twilio, SIP, WebRTC)
7. **Manage billing** via Stripe (Free/Starter/Pro/Enterprise tiers)
8. **View full call logs** with transcripts and statistics
9. **Monitor system health** via logs and Prometheus metrics

## 🔑 Your .env Already Contains:
- ✅ NVIDIA_API_KEY: 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
- ✅ NGC_API_KEY: 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
- ✅ JWT_SECRET: 358ad583cba6a6d701ea3198a992447d691941be251cccc27bdd6317df34ba6f
- ✅ All other required variables (with placeholders for Stripe that you can use test keys for)

## 📝 Note on Stripe Keys
For local testing, you can use:
- STRIPE_SECRET_KEY=sk_test_... (get from Stripe Dashboard → Developers → API keys)
- STRIPE_PUBLISHABLE_KEY=pk_test_...
- STRIPE_WEBHOOK_SECRET=whsec_... (from: stripe listen --forward-to https://ominivoice.local/billing/webhook)
- STRIPE_PRICE_ID_*: Create test products in Stripe Dashboard → Products

The system is 100% implemented and ready - just needs the two voice model downloads to complete the setup!