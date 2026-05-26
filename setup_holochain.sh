#!/bin/bash
set -e

echo "=== ValiChord Holochain Setup ==="

# Install Rust if not present
if ! command -v cargo &>/dev/null && [ ! -f "$HOME/.cargo/bin/cargo" ]; then
    echo "Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
fi

export PATH="$HOME/.cargo/bin:$PATH"

echo "Rust: $(cargo --version)"

# Add wasm32 target
echo "Adding wasm32 target..."
rustup target add wasm32-unknown-unknown

# Install holochain
echo "Installing holochain 0.6.1 (takes ~10 min)..."
cargo install holochain --version 0.6.1 --locked --force

# Install hc CLI
echo "Installing hc 0.6.1..."
cargo install holochain_cli --version 0.6.1 --locked --force

# Install bootstrap server
echo "Installing kitsune2-bootstrap-srv 0.4.1..."
cargo install kitsune2_bootstrap_srv --version 0.4.1 --locked --force

# Add PATH permanently
if ! grep -q '.cargo/bin' ~/.bashrc; then
    echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.bashrc
fi

echo ""
echo "=== Done! ==="
holochain --version
hc --version
