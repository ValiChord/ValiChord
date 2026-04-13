#!/usr/bin/env bash
# oracle_setup.sh — Install the full ValiChord stack on a fresh Ubuntu 20.04 server.
# Run once after git clone. Takes ~20-40 min (Rust/Holochain compilation).
#
# Usage:
#   bash demo/oracle_setup.sh
#
# After this completes, start the stack with:
#   bash demo/start_oracle.sh
set -euo pipefail

echo "=== ValiChord Oracle Setup ==="
echo "This will install Node.js 20, Python 3 deps, Rust, and Holochain 0.6.0."
echo "Estimated time: 20-40 minutes."
echo ""

# ── System packages ───────────────────────────────────────────────────────────
echo "[1/6] Installing system packages…"
sudo apt-get update -q
sudo apt-get install -y -q \
    curl wget git build-essential pkg-config \
    libssl-dev libsodium-dev clang libclang-dev \
    cmake protobuf-compiler \
    python3 python3-pip

# ── Node.js 20 ────────────────────────────────────────────────────────────────
echo "[2/6] Installing Node.js 20…"
if ! node --version 2>/dev/null | grep -q "^v20"; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi
echo "  Node: $(node --version)  npm: $(npm --version)"

# ── Python deps ───────────────────────────────────────────────────────────────
echo "[3/6] Installing Python dependencies…"
pip3 install --quiet --upgrade pip
pip3 install --quiet \
    flask flask-cors gunicorn requests rarfile py7zr \
    python-docx pyreadstat pdfplumber xlrd anthropic

# ── Rust ──────────────────────────────────────────────────────────────────────
echo "[4/6] Installing Rust…"
if ! command -v cargo &>/dev/null; then
    curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable
fi
source "$HOME/.cargo/env"
echo "  Rust: $(rustc --version)"

# ── Holochain 0.6.0 ──────────────────────────────────────────────────────────
echo "[5/6] Installing Holochain 0.6.0 (this takes 15-30 min)…"
if ! holochain --version 2>/dev/null | grep -q "0.6.0"; then
    cargo install holochain --version 0.6.0 --locked
fi
echo "  Holochain: $(holochain --version)"

# ── Node deps for demo ────────────────────────────────────────────────────────
echo "[6/6] Installing Node dependencies for demo…"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR/demo"
npm install --omit=dev

# ── OS firewall (Oracle instances block ports by default) ─────────────────────
echo "[+] Opening OS firewall for ports 5000 and 8090…"
# Oracle Ubuntu images use iptables, not ufw.
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5000 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 8090 -j ACCEPT
# Persist across reboots (iptables-persistent may not be installed — that's ok)
sudo netfilter-persistent save 2>/dev/null || true

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Set your environment variables (see demo/start_oracle.sh)"
echo "  2. Run:  bash demo/start_oracle.sh"
