# ── Stage 1: Build holochain binary ──────────────────────────────────────────
FROM rust:1.88 AS builder

RUN apt-get update && apt-get install -y \
    libssl-dev pkg-config \
    clang libclang-dev \
    cmake \
    protobuf-compiler \
    libsodium-dev \
    && rm -rf /var/lib/apt/lists/*

# holochain 0.6.0 — lair_server_in_proc mode (no separate lair-keystore needed)
RUN cargo install holochain --version 0.6.0 --locked

# ── Stage 2: Runtime (Node.js + holochain binary) ────────────────────────────
FROM node:20-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/cargo/bin/holochain /usr/local/bin/holochain

WORKDIR /app

# Copy the pre-built happ and demo files
COPY valichord/workdir/valichord.happ ./valichord/workdir/valichord.happ
COPY demo/ ./demo/

# Install demo JS dependencies (provides @holochain/client for setup.mjs)
RUN cd demo && npm install --omit=dev

EXPOSE 10000

CMD ["bash", "demo/render-start.sh"]
