#!/bin/bash
set -e

echo "=== ValiChord Codespace Setup ==="

# Install Claude Code
echo "Installing Claude Code..."
npm install -g @anthropic-ai/claude-code
echo "Claude Code: $(claude --version)"

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

# Install holochain-dev Claude Code skill
echo "Installing holochain-dev skill..."
mkdir -p ~/.claude/skills
cp -r "$(dirname "$0")/skills/holochain-dev" ~/.claude/skills/
echo "Skill installed."

echo ""
echo "=== Holochain tools installed. Building ValiChord DNAs (~5-10 min)... ==="

cd "$(dirname "$0")/valichord"
cargo build --target wasm32-unknown-unknown --release

hc dna pack dnas/attestation           -o workdir/attestation.dna
hc dna pack dnas/researcher_repository -o workdir/researcher_repository.dna
hc dna pack dnas/validator_workspace   -o workdir/validator_workspace.dna
hc dna pack dnas/governance            -o workdir/governance.dna
hc app pack .                          -o workdir/valichord.happ

echo ""
echo "=== All done! ==="
holochain --version
hc --version
echo ""
echo "One more step: open Claude Code and type this in the chat:"
echo "  /plugin install superpowers"
echo "That reinstalls the superpowers skills (TDD, debugging, planning etc)."
