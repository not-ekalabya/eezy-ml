FROM node:24-bookworm-slim AS client-builder

WORKDIR /build/client
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_URL=/api

COPY client/package*.json ./
RUN npm ci

COPY client/ ./
RUN npm run build
RUN npm prune --omit=dev

FROM node:24-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PATH="/opt/venv/bin:${PATH}"
ENV NEXT_TELEMETRY_DISABLED=1
ENV NEXT_PUBLIC_API_URL=/api
ENV HOSTNAME=0.0.0.0
ENV PORT=8000
ENV BACKEND_HOST=127.0.0.1
ENV BACKEND_PORT=3000

COPY requirements.txt ./requirements.txt
COPY backend/requirements.txt ./backend/requirements.txt
RUN python3 -m venv /opt/venv \
    && pip install --no-cache-dir -r requirements.txt -r backend/requirements.txt

COPY backend/src ./backend/src
COPY client/package*.json ./client/
COPY --from=client-builder /build/client/.next ./client/.next
COPY --from=client-builder /build/client/node_modules ./client/node_modules
COPY --from=client-builder /build/client/public ./client/public
COPY --from=client-builder /build/client/next.config.ts ./client/next.config.ts
COPY docker-entrypoint.sh ./docker-entrypoint.sh

EXPOSE 8000

CMD ["sh", "/app/docker-entrypoint.sh"]
