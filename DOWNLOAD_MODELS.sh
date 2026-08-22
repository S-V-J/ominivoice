#!/bin/bash
# Script to download required voice models for OminiVoice
# Run this script to download the missing model files

set -e

echo "=== Downloading Voice Models for OminiVoice ==="
echo ""

# Create directories if they don't exist
mkdir -p /home/ML/ominivoice/infra/voice_models/kokoro
mkdir -p /home/ML/ominivoice/infra/voice_models/piper

# Download Kokoro TTS model (~70MB) - PRIMARY TTS ENGINE
echo "Downloading Kokoro TTS model (~70MB)..."
wget --show-progress --progress=bar:force:noscroll \
  -O /home/ML/ominivoice/infra/voice_models/kokoro/kokoro-v1.0.onnx \
  https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/kokoro-v1.0.onnx

# Download Piper voice model (~45MB) + config (OPTIONAL FALLBACK)
echo ""
echo "Downloading Piper voice model (~45MB)..."
wget --show-progress --progress=bar:force:noscroll \
  -O /home/ML/ominivoice/infra/voice_models/piper/en_US-lessac-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/en_US-lessac-medium/en_US-lessac-medium.onnx

echo ""
echo "Downloading Piper voice model config..."
wget --show-progress --progress=bar:force:noscroll \
  -O /home/ML/ominivoice/infra/voice_models/piper/en_US-lessac-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en_US/en_US-lessac-medium/en_US-lessac-medium.onnx.json

echo ""
echo "=== Download Complete ==="
echo "File sizes:"
echo "Kokoro model: $(du -h /home/ML/ominivoice/infra/voice_models/kokoro/kokoro-v1.0.onnx | cut -f1)"
echo "Piper model: $(du -h /home/ML/ominivoice/infra/voice_models/piper/en_US-lessac-medium.onnx | cut -f1)"
echo "Piper config: $(du -h /home/ML/ominivoice/infra/voice_models/piper/en_US-lessac-medium.onnx.json | cut -f1)"
echo ""
echo "You can now run: ./launch.sh"
