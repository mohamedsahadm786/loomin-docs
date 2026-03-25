#!/bin/bash
# =============================================================================
# Loomin-Docs — RHEL 9 Air-Gap Bootstrap Script
# Run this as root on a clean RHEL 9 machine with no internet connection.
# Usage: sudo bash setup.sh
# =============================================================================

set -e  # Exit immediately if any command fails

# ── Colors for output ─────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

log()    { echo -e "${CYAN}[LOOMIN]${NC} $1"; }
success(){ echo -e "${GREEN}[OK]${NC} $1"; }
warn()   { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Step 0: Check running as root ─────────────────────────────────────────────
log "Checking permissions..."
if [ "$EUID" -ne 0 ]; then
  error "Please run as root: sudo bash setup.sh"
fi
success "Running as root"

# ── Step 1: Detect script location ────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
log "Script directory: $SCRIPT_DIR"

# ── Step 2: Install Docker from offline RPMs ──────────────────────────────────
log "Installing Docker from offline RPMs..."

RPM_DIR="$SCRIPT_DIR/rpms"

if [ ! -d "$RPM_DIR" ] || [ -z "$(ls -A $RPM_DIR/*.rpm 2>/dev/null)" ]; then
  error "No RPM files found in $RPM_DIR. Please copy Docker RPMs to the rpms/ folder."
fi

# Install all RPMs at once (handles dependencies automatically)
rpm -ivh --nodeps $RPM_DIR/*.rpm || warn "Some RPMs may already be installed, continuing..."

success "Docker RPMs installed"

# ── Step 3: Start Docker service ──────────────────────────────────────────────
log "Starting Docker service..."
systemctl enable docker
systemctl start docker
sleep 3

# Verify Docker is running
docker info > /dev/null 2>&1 || error "Docker failed to start. Check: systemctl status docker"
success "Docker is running"

# ── Step 4: Load Docker images from .tar files ────────────────────────────────
log "Loading Docker images from tar files..."

IMAGES_DIR="$SCRIPT_DIR/images"

if [ ! -d "$IMAGES_DIR" ]; then
  error "images/ directory not found at $IMAGES_DIR"
fi

for tar_file in "$IMAGES_DIR"/*.tar; do
  if [ -f "$tar_file" ]; then
    log "Loading image: $(basename $tar_file)"
    docker load < "$tar_file"
    success "Loaded: $(basename $tar_file)"
  fi
done

# Verify all 3 required images are loaded
docker image inspect loomin-frontend:latest > /dev/null 2>&1 || error "loomin-frontend:latest image not found"
docker image inspect loomin-backend:latest > /dev/null 2>&1  || error "loomin-backend:latest image not found"
docker image inspect ollama/ollama:latest > /dev/null 2>&1   || error "ollama/ollama:latest image not found"
success "All 3 Docker images loaded"

# ── Step 5: Install Docker Compose plugin ─────────────────────────────────────
log "Checking Docker Compose..."
docker compose version > /dev/null 2>&1 || error "Docker Compose plugin not found. Make sure docker-compose-plugin RPM is in rpms/ folder."
success "Docker Compose is available"

# ── Step 6: Verify Ollama model blobs exist ───────────────────────────────────
log "Checking Ollama model files..."

MODELS_DIR="$SCRIPT_DIR/ollama-models"

if [ ! -d "$MODELS_DIR" ]; then
  error "ollama-models/ directory not found. Please copy Ollama model blobs to deploy/ollama-models/"
fi

# Check that blobs directory exists and has files
if [ -z "$(ls -A $MODELS_DIR/blobs 2>/dev/null)" ]; then
  error "No model blobs found in $MODELS_DIR/blobs/. See deploy/ollama-models/README.md for instructions."
fi

success "Ollama model files found"

# ── Step 7: Create models_cache directory for embedding model ─────────────────
log "Setting up embedding model cache..."

MODELS_CACHE_DIR="$MODELS_DIR/models_cache"

if [ ! -d "$MODELS_CACHE_DIR" ]; then
  error "models_cache/ not found in $MODELS_DIR. Please copy the sentence-transformers model cache. See deploy/ollama-models/README.md"
fi

success "Embedding model cache found"

# ── Step 8: Start all containers ──────────────────────────────────────────────
log "Starting Loomin-Docs containers..."

cd "$SCRIPT_DIR"
docker compose -f docker-compose.yml up -d

success "Containers started"

# ── Step 9: Wait for health check ─────────────────────────────────────────────
log "Waiting for backend to be ready (this may take 30-60 seconds)..."

MAX_WAIT=120
ELAPSED=0
INTERVAL=5

while [ $ELAPSED -lt $MAX_WAIT ]; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
  if [ "$STATUS" = "200" ]; then
    success "Backend is healthy"
    break
  fi
  sleep $INTERVAL
  ELAPSED=$((ELAPSED + INTERVAL))
  log "Still waiting... (${ELAPSED}s elapsed)"
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
  warn "Backend health check timed out. Check logs: docker compose logs backend"
fi

# ── Step 10: Final status ──────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  Loomin-Docs is running!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "  Frontend:  ${CYAN}http://localhost:3000${NC}"
echo -e "  Backend:   ${CYAN}http://localhost:8000${NC}"
echo -e "  API Docs:  ${CYAN}http://localhost:8000/docs${NC}"
echo ""
echo -e "  To check logs:   ${YELLOW}docker compose logs -f${NC}"
echo -e "  To stop:         ${YELLOW}docker compose down${NC}"
echo ""