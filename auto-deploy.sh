#!/bin/bash

# ShiftPilot Auto-Deployment Script
# Checks for GitHub changes, pulls, and rebuilds if needed

set -e  # Exit on error

# Configuration
REPO_DIR="/opt/shiftpilot"  # UPDATE THIS to your server repo path
BRANCH="main"  # or "dev" - whichever branch you deploy from
LOG_FILE="/var/log/shiftpilot-deploy.log"
LOCK_FILE="/tmp/shiftpilot-deploy.lock"

# Colors for output
RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
NC=$'\033[0m' # No Color

# Logging function
log() {
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Check if script is already running
if [ -f "$LOCK_FILE" ]; then
    log "${YELLOW}Deployment already in progress. Exiting.${NC}"
    exit 0
fi

# Create lock file
touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

log "${GREEN}=== Starting auto-deployment check ===${NC}"

# Navigate to repo directory
cd "$REPO_DIR" || {
    log "${RED}ERROR: Could not navigate to $REPO_DIR${NC}"
    exit 1
}

# Fetch latest changes from remote
log "Fetching latest changes from GitHub..."
git fetch origin "$BRANCH" 2>&1 | tee -a "$LOG_FILE"

# Check if there are new commits
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" = "$REMOTE" ]; then
    log "${GREEN}No changes detected. Repository is up to date.${NC}"
    exit 0
fi

log "${YELLOW}Changes detected! Starting deployment...${NC}"

# Stash any local changes (just in case)
if ! git diff-index --quiet HEAD --; then
    log "Stashing local changes..."
    git stash
fi

# Pull latest changes
log "Pulling latest changes from $BRANCH..."
git pull origin "$BRANCH" 2>&1 | tee -a "$LOG_FILE"

# Check if docker-compose.yml exists
if [ -f "docker-compose.yml" ]; then
    log "Rebuilding and restarting Docker containers..."

    # Stop containers
    docker-compose down 2>&1 | tee -a "$LOG_FILE"

    # Rebuild and start
    docker-compose up -d --build 2>&1 | tee -a "$LOG_FILE"

    # Wait for services to be healthy
    log "Waiting for services to start..."
    sleep 10

    # Check if containers are running
    if docker-compose ps | grep -q "Up"; then
        log "${GREEN}Docker containers successfully restarted${NC}"
    else
        log "${RED}WARNING: Some containers may not be running properly${NC}"
        docker-compose ps | tee -a "$LOG_FILE"
    fi
else
    log "${YELLOW}No docker-compose.yml found. Running manual build...${NC}"

    # Build frontend if package.json exists
    if [ -f "frontend/package.json" ]; then
        log "Building frontend..."
        cd frontend
        npm install 2>&1 | tee -a "$LOG_FILE"
        npm run build 2>&1 | tee -a "$LOG_FILE"
        cd ..
    fi

    # Install backend dependencies if requirements.txt exists
    if [ -f "backend/requirements.txt" ]; then
        log "Installing backend dependencies..."
        cd backend
        pip install -r requirements.txt 2>&1 | tee -a "$LOG_FILE"
        cd ..
    fi

    # Restart backend service (adjust service name as needed)
    if systemctl is-active --quiet shiftpilot-backend; then
        log "Restarting backend service..."
        sudo systemctl restart shiftpilot-backend 2>&1 | tee -a "$LOG_FILE"
    fi
fi

# Log the deployed commit
DEPLOYED_COMMIT=$(git rev-parse --short HEAD)
log "${GREEN}=== Deployment completed successfully ===${NC}"
log "Deployed commit: $DEPLOYED_COMMIT"
log "Commit message: $(git log -1 --pretty=%B)"

# Optional: Send notification (uncomment if you want)
# curl -X POST -H 'Content-type: application/json' \
#   --data "{\"text\":\"ShiftPilot deployed: $DEPLOYED_COMMIT\"}" \
#   YOUR_WEBHOOK_URL

exit 0
