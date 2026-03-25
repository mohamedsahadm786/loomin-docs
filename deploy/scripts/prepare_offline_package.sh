#!/bin/bash
# =============================================================================
# Loomin-Docs — Offline Package Preparation Script
# Run this on YOUR DEVELOPMENT MACHINE (Windows WSL2 or Linux) BEFORE
# transferring files to the RHEL 9 evaluation VM.
# This script exports all Docker images and model files needed for air-gap deployment.
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()    { echo -e "${CYAN}[PREPARE]${NC} $1"; }
success(){ echo -e "${GREEN}[OK]${NC} $1"; }
error()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
warn()   { echo -e "${YELLOW}[WARN]${NC} $1"; }

# ── Detect project root ────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_DIR="$PROJECT_ROOT/deploy"

log "Project root: $PROJECT_ROOT"
log "Deploy dir:   $DEPLOY_DIR"

# ── Step 1: Build Docker images ───────────────────────────────────────────────
log "Building frontend Docker image..."
docker build -t loomin-frontend:latest "$PROJECT_ROOT/frontend"
success "loomin-frontend:latest built"

log "Building backend Docker image..."
docker build -t loomin-backend:latest "$PROJECT_ROOT/backend"
success "loomin-backend:latest built"

log "Pulling Ollama image (if not already present)..."
docker pull ollama/ollama:latest
success "ollama/ollama:latest ready"

# ── Step 2: Export Docker images as .tar files ────────────────────────────────
log "Exporting Docker images to tar files..."
mkdir -p "$DEPLOY_DIR/images"

log "Saving loomin-frontend:latest → deploy/images/frontend.tar"
docker save loomin-frontend:latest -o "$DEPLOY_DIR/images/frontend.tar"
success "frontend.tar saved ($(du -sh $DEPLOY_DIR/images/frontend.tar | cut -f1))"

log "Saving loomin-backend:latest → deploy/images/backend.tar"
docker save loomin-backend:latest -o "$DEPLOY_DIR/images/backend.tar"
success "backend.tar saved ($(du -sh $DEPLOY_DIR/images/backend.tar | cut -f1))"

log "Saving ollama/ollama:latest → deploy/images/ollama.tar"
docker save ollama/ollama:latest -o "$DEPLOY_DIR/images/ollama.tar"
success "ollama.tar saved ($(du -sh $DEPLOY_DIR/images/ollama.tar | cut -f1))"

# ── Step 3: Copy Ollama model blobs ───────────────────────────────────────────
log "Copying Ollama model blobs..."
mkdir -p "$DEPLOY_DIR/ollama-models/blobs"
mkdir -p "$DEPLOY_DIR/ollama-models/manifests"

# Ollama stores models in different locations depending on OS
# WSL2/Linux path:
OLLAMA_LINUX_PATH="$HOME/.ollama"
# Windows path (accessed from WSL2):
OLLAMA_WINDOWS_PATH="/mnt/c/Users/$USER/.ollama"

if [ -d "$OLLAMA_LINUX_PATH/blobs" ]; then
  OLLAMA_SOURCE="$OLLAMA_LINUX_PATH"
  log "Found Ollama data at: $OLLAMA_SOURCE"
elif [ -d "$OLLAMA_WINDOWS_PATH/blobs" ]; then
  OLLAMA_SOURCE="$OLLAMA_WINDOWS_PATH"
  log "Found Ollama data at: $OLLAMA_SOURCE"
else
  warn "Could not auto-detect Ollama model path."
  warn "Please manually copy your Ollama blobs folder to: $DEPLOY_DIR/ollama-models/"
  warn "Typical Windows path: C:\\Users\\YOUR_NAME\\.ollama"
  warn "Typical Linux path: ~/.ollama"
  warn "Skipping automatic copy..."
  OLLAMA_SOURCE=""
fi

if [ -n "$OLLAMA_SOURCE" ]; then
  cp -r "$OLLAMA_SOURCE/blobs/." "$DEPLOY_DIR/ollama-models/blobs/"
  cp -r "$OLLAMA_SOURCE/manifests/." "$DEPLOY_DIR/ollama-models/manifests/"
  success "Ollama model blobs copied"
fi

# ── Step 4: Copy sentence-transformers model cache ────────────────────────────
log "Copying sentence-transformers embedding model cache..."
mkdir -p "$DEPLOY_DIR/ollama-models/models_cache"

# Check where models_cache is in the backend folder
MODELS_CACHE_SOURCE="$PROJECT_ROOT/backend/models_cache"

if [ -d "$MODELS_CACHE_SOURCE" ]; then
  cp -r "$MODELS_CACHE_SOURCE/." "$DEPLOY_DIR/ollama-models/models_cache/"
  success "Embedding model cache copied"
else
  warn "models_cache/ not found at $MODELS_CACHE_SOURCE"
  warn "Please run: cd backend && python download_models.py"
  warn "Then run this script again."
fi

# ── Step 5: Summary ────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Offline Package Ready!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Files to transfer to USB / RHEL 9 VM:"
echo ""
echo "  1. The entire loomin-docs/ project folder"
echo "     (includes deploy/images/*.tar and deploy/ollama-models/)"
echo ""
echo "  2. Docker RPM files → place in deploy/rpms/"
echo "     See deploy/rpms/README.md for exact files needed"
echo ""
echo "On the RHEL 9 VM, run:"
echo -e "  ${CYAN}sudo bash deploy/setup.sh${NC}"
echo ""

# ── Step 6: Show total package size ───────────────────────────────────────────
log "Calculating total package size..."
du -sh "$DEPLOY_DIR" 2>/dev/null && true