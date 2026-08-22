# Frontend - Multi-stage Dockerfile for production-grade React + Vite + TypeScript + Tailwind
# Build stage
FROM node:20-alpine AS builder

# Install build dependencies
RUN apk add --no-cache python3 make g++

WORKDIR /app

# Copy package files first for better cache
COPY frontend/package*.json ./
RUN npm install --prefer-offline --no-audit --no-fund

# Copy source and build
COPY frontend/ ./
RUN npm run build

# Production stage - Nginx serving static files
FROM nginx:alpine AS production

# Install runtime deps (for healthcheck, etc.)
RUN apk add --no-cache curl

# Copy custom nginx config
COPY infra/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]