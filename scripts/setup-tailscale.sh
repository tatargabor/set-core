#!/usr/bin/env bash
# Setup Tailscale for mobile wt-web dashboard access.
# Run as: sudo scripts/setup-tailscale.sh
# Or called from install.sh which handles sudo prompting.
#
# What it does:
#   1. Installs Tailscale (if missing)
#   2. Creates sudoers NOPASSWD rule for the calling user
#   3. Configures tailscale serve HTTP :80 → localhost:8765
#
# Works for any user — detects via SUDO_USER or whoami.

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[info]${NC} $*"; }
success() { echo -e "${GREEN}[ok]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC} $*"; }
error()   { echo -e "${RED}[error]${NC} $*"; }

# Determine the real user (not root when run via sudo)
if [[ -n "${SUDO_USER:-}" ]]; then
    TARGET_USER="$SUDO_USER"
elif [[ "$(id -u)" -eq 0 ]]; then
    error "Run with sudo (not as root directly) so we can detect your username"
    error "Usage: sudo $0"
    exit 1
else
    TARGET_USER="$(whoami)"
fi

info "Setting up Tailscale mobile access for user: $TARGET_USER"
echo ""

# --- 1. Install Tailscale ---
if ! command -v tailscale &>/dev/null; then
    info "Installing Tailscale..."
    curl -fsSL https://tailscale.com/install.sh | sh
    if ! command -v tailscale &>/dev/null; then
        error "Tailscale installation failed"
        exit 1
    fi
    success "Tailscale installed"
else
    success "Tailscale already installed"
fi

# --- 2. Check connection ---
if ! tailscale status &>/dev/null 2>&1; then
    warn "Tailscale is not connected"
    info "Run: sudo tailscale up"
    info "Then re-run this script"
    exit 1
fi

TS_HOSTNAME="$(tailscale status --json 2>/dev/null | jq -r '.Self.DNSName // empty' | sed 's/\.$//')"
info "Tailscale hostname: ${TS_HOSTNAME:-unknown}"

# --- 3. Sudoers NOPASSWD rule ---
SUDOERS_FILE="/etc/sudoers.d/tailscale-wt"

if [[ -f "$SUDOERS_FILE" ]] && grep -q "$TARGET_USER" "$SUDOERS_FILE" 2>/dev/null; then
    success "Sudoers rule already exists for $TARGET_USER"
else
    info "Creating sudoers rule: $TARGET_USER can run tailscale without password"
    echo "$TARGET_USER ALL=(ALL) NOPASSWD: /usr/bin/tailscale" > "$SUDOERS_FILE"
    chmod 440 "$SUDOERS_FILE"

    # Validate with visudo
    if visudo -cf "$SUDOERS_FILE" &>/dev/null; then
        success "Sudoers rule created: $SUDOERS_FILE"
    else
        error "Sudoers syntax check failed — removing broken file"
        rm -f "$SUDOERS_FILE"
        exit 1
    fi
fi

# --- 4. Configure tailscale serve ---
# HTTP (not HTTPS) because Tailscale auto-certs trigger Certificate Transparency
# errors on Android Chrome. WireGuard tunnel already encrypts all traffic.
info "Configuring tailscale serve: HTTP :80 → localhost:8765"
if tailscale serve --bg --http 80 http://localhost:7400 2>/dev/null; then
    success "Tailscale serve configured"
else
    warn "tailscale serve failed — is wt-web running on port 8765?"
    info "Start wt-web first, then run: sudo tailscale serve --bg --http 80 http://localhost:7400"
fi

echo ""
echo "================================"
success "Tailscale mobile access ready!"
echo "================================"
echo ""
if [[ -n "${TS_HOSTNAME:-}" ]]; then
    echo "  Dashboard URL: http://${TS_HOSTNAME}/"
    echo "  Open in Chrome on your phone (with Tailscale app connected)"
else
    echo "  Dashboard URL: http://<your-tailscale-hostname>/"
fi
echo ""
