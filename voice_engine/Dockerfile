# syntax=docker/dockerfile:1.7
# Multi-stage build for voice-engine (Pipecat pipeline + STT/TTS/VAD)
# Supports both CPU-only and GPU (CUDA) builds

################################################################################
# BASE IMAGE - Common dependencies
################################################################################
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies for audio processing and ONNX runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libasound2 \
    libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

################################################################################
# BUILDER - Install Python dependencies
################################################################################
FROM base AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt ./requirements.txt

# Install Python dependencies - use official PyPI with extended timeout for slow networks
# Install heavy ML packages first with extended timeout
# torch/torchaudio must come from official PyTorch index (aliyun mirror lacks these versions)
RUN pip install --no-cache-dir --default-timeout=7200 torch==2.4.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --default-timeout=7200 ctranslate2==4.4.0 && \
    pip install --no-cache-dir --default-timeout=7200 -r requirements.txt

################################################################################
# GPU VARIANT - CUDA-enabled build (optional)
################################################################################
FROM nvidia/cuda:12.4-runtime-ubuntu22.04 AS gpu-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    ffmpeg \
    libsndfile1 \
    libasound2 \
    libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

RUN python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

FROM gpu-base AS gpu-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
COPY requirements-gpu.txt ./requirements-gpu.txt

# Install with CUDA support for faster-whisper, ONNX GPU, etc.
RUN pip install --no-cache-dir --default-timeout=7200 torch==2.4.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121 && \
    pip install --no-cache-dir --default-timeout=7200 ctranslate2==4.4.0 && \
    pip install --no-cache-dir --default-timeout=7200 -r requirements.txt -r requirements-gpu.txt

################################################################################
# PRODUCTION - CPU-only runtime
################################################################################
FROM base AS production

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . ./voice_engine/

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import voice_engine; print('OK')" || exit 1

CMD ["python", "-m", "voice_engine.main"]

################################################################################
# PRODUCTION-GPU - CUDA runtime (build with: docker build --target production-gpu -t voice-engine:gpu .)
################################################################################
FROM gpu-base AS production-gpu

COPY --from=gpu-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . ./voice-engine/

RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import voice_engine; print('OK')" || exit 1

CMD ["python", "-m", "voice_engine.main"]