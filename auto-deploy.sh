#!/bin/bash

# ShiftPilot Auto-Deployment Script
# Checks for GitHub changes, pulls, and rebuilds if needed

set -e  # Exit on error

# Configuration
REPO_DIR="/opt/shiftpilot"  # UPDATE THIS to your server repo path
BRANCH="main"  # or "dev" - whichever branch you deploy from
LOG_FILE="/var/log/shiftpilot-deploy.log"
LOCK_FILE="/tmp/shiftpilot-deploy.lock"

# Enable color unless explicitly disabled.
if [ -n "${NO_COLOR:-}" ]; then
    USE_COLOR=0
else
    USE_COLOR=1
fi

# Colors for output
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'
NC=$'\033[0m'

log_line() {
    local level="$1"
    local color="$2"
    shift 2
    local message="$*"
    local timestamp
    timestamp="$(date +'%Y-%m-%d %H:%M:%S')"
    local plain="[$timestamp] [$level] $message"

    mkdir -p "$(dirname "$LOG_FILE")"
    echo "$plain" >> "$LOG_FILE"

    if [ "$USE_COLOR" -eq 1 ]; then
        printf "%b\n" "${color}${plain}${NC}"
    else
        printf "%s\n" "$plain"
    fi
}

log_info() { log_line "INFO" "$CYAN" "$*"; }
log_warn() { log_line "WARN" "$YELLOW" "$*"; }
log_error() { log_line "ERROR" "$RED" "$*"; }
log_success() { log_line "SUCCESS" "$GREEN" "$*"; }

# Check if script is already running
if [ -f "$LOCK_FILE" ]; then
    log_warn "Deployment already in progress. Exiting."
    exit 0
fi

# Create lock file
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log_success "=== Starting auto-deployment check ==="

# Navigate to repo directory
cd "$REPO_DIR" || {
    log_error "Could not navigate to $REPO_DIR"
    exit 1
}

# Fetch latest changes from remote
log_info "Fetching latest changes from GitHub..."
git fetch origin "$BRANCH" 2>&1 | tee -a "$LOG_FILE"

# Check if there are new commits
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" = "$REMOTE" ]; then
    log_success "No changes detected. Repository is up to date."
    exit 0
fi

log_warn "Changes detected! Starting deployment..."

# Stash any local changes (just in case)
if ! git diff-index --quiet HEAD --; then
    log_warn "Stashing local changes..."
    git stash
fi

# Pull latest changes
log_info "Pulling latest changes from $BRANCH..."
git pull origin "$BRANCH" 2>&1 | tee -a "$LOG_FILE"

# Check if docker-compose.yml exists
if [ -f "docker-compose.yml" ]; then
    log_info "Rebuilding and restarting Docker containers..."

    # Capture git commit and date for version display
    GIT_COMMIT=$(git rev-parse --short HEAD)
    GIT_DATE=$(git log -1 --format=%cd --date=format:%Y%m%d)
    export VITE_APP_BUILD="$GIT_DATE.$GIT_COMMIT"
    export VITE_APP_VERSION="$GIT_COMMIT"
    export VITE_GIT_COMMIT="$GIT_COMMIT"
    log_info "Building with version: $GIT_DATE.$GIT_COMMIT"

    # Stop containers
    docker-compose down 2>&1 | tee -a "$LOG_FILE"

    # Rebuild and start
    docker-compose up -d --build 2>&1 | tee -a "$LOG_FILE"

    # Wait for services to be healthy
    log_info "Waiting for services to start..."
    sleep 10

    # Check if containers are running
    if docker-compose ps | grep -q "Up"; then
        log_success "Docker containers successfully restarted"
    else
        log_warn "Some containers may not be running properly"
        docker-compose ps | tee -a "$LOG_FILE"
    fi
else
    log_warn "No docker-compose.yml found. Running manual build..."

    # Build frontend if package.json exists
    if [ -f "frontend/package.json" ]; then
        log_info "Building frontend..."
        cd frontend
        npm install 2>&1 | tee -a "$LOG_FILE"
        npm run build 2>&1 | tee -a "$LOG_FILE"
        cd ..
    fi

    # Install backend dependencies if requirements.txt exists
    if [ -f "backend/requirements.txt" ]; then
        log_info "Installing backend dependencies..."
        cd backend
        pip install -r requirements.txt 2>&1 | tee -a "$LOG_FILE"
        cd ..
    fi

    # Restart backend service (adjust service name as needed)
    if systemctl is-active --quiet shiftpilot-backend; then
        log_info "Restarting backend service..."
        sudo systemctl restart shiftpilot-backend 2>&1 | tee -a "$LOG_FILE"
    fi
fi

# Log the deployed commit
DEPLOYED_COMMIT=$(git rev-parse --short HEAD)
log_success "=== Deployment completed successfully ==="
log_info "Deployed commit: $DEPLOYED_COMMIT"
log_info "Commit message: $(git log -1 --pretty=%B)"

# Optional: Send notification (uncomment if you want)
# curl -X POST -H 'Content-type: application/json' \
#   --data "{\"text\":\"ShiftPilot deployed: $DEPLOYED_COMMIT\"}" \
#   YOUR_WEBHOOK_URL

exit 0
