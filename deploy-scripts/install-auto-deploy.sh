#!/bin/bash

# ShiftPilot Auto-Deploy Installation Script
# Run this on your Vultr server to set up automatic deployments

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}ShiftPilot Auto-Deploy Setup${NC}"
echo "=============================="
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo -e "${RED}Please do NOT run this script as root.${NC}"
    echo "Run as your regular user; it will prompt for sudo when needed."
    exit 1
fi

# Get current directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

echo "Repository directory: $REPO_DIR"
echo ""

# Prompt for branch
read -p "Which branch to auto-deploy? (default: main): " DEPLOY_BRANCH
DEPLOY_BRANCH=${DEPLOY_BRANCH:-main}

echo ""
echo -e "${YELLOW}Configuring auto-deploy for branch: $DEPLOY_BRANCH${NC}"

# Update auto-deploy.sh with correct paths
sed -i "s|REPO_DIR=\"/path/to/wip-scheduler\"|REPO_DIR=\"$REPO_DIR\"|g" "$REPO_DIR/auto-deploy.sh"
sed -i "s|BRANCH=\"main\"|BRANCH=\"$DEPLOY_BRANCH\"|g" "$REPO_DIR/auto-deploy.sh"

# Make script executable
chmod +x "$REPO_DIR/auto-deploy.sh"

echo -e "${GREEN}✓ Auto-deploy script configured${NC}"

# Create log directory
sudo mkdir -p /var/log
sudo touch /var/log/shiftpilot-deploy.log
sudo chown $USER:$USER /var/log/shiftpilot-deploy.log

echo -e "${GREEN}✓ Log file created at /var/log/shiftpilot-deploy.log${NC}"

# Ask if user wants systemd timer
read -p "Install systemd timer for automatic checks? (y/n): " INSTALL_TIMER

if [[ $INSTALL_TIMER =~ ^[Yy]$ ]]; then
    # Update service file with correct user and paths
    sed -i "s|User=YOUR_USERNAME|User=$USER|g" "$SCRIPT_DIR/shiftpilot-deploy.service"
    sed -i "s|WorkingDirectory=/path/to/wip-scheduler|WorkingDirectory=$REPO_DIR|g" "$SCRIPT_DIR/shiftpilot-deploy.service"
    sed -i "s|ExecStart=/bin/bash /path/to/wip-scheduler/auto-deploy.sh|ExecStart=/bin/bash $REPO_DIR/auto-deploy.sh|g" "$SCRIPT_DIR/shiftpilot-deploy.service"

    # Copy systemd files
    sudo cp "$SCRIPT_DIR/shiftpilot-deploy.service" /etc/systemd/system/
    sudo cp "$SCRIPT_DIR/shiftpilot-deploy.timer" /etc/systemd/system/

    # Reload systemd
    sudo systemctl daemon-reload

    # Enable and start timer
    sudo systemctl enable shiftpilot-deploy.timer
    sudo systemctl start shiftpilot-deploy.timer

    echo -e "${GREEN}✓ Systemd timer installed and started${NC}"
    echo ""
    echo "The deployment script will now run every 5 minutes."
    echo ""
    echo "Useful commands:"
    echo "  Check timer status:    sudo systemctl status shiftpilot-deploy.timer"
    echo "  View logs:             sudo journalctl -u shiftpilot-deploy.service -f"
    echo "  Manual trigger:        sudo systemctl start shiftpilot-deploy.service"
    echo "  Stop timer:            sudo systemctl stop shiftpilot-deploy.timer"
    echo "  Disable timer:         sudo systemctl disable shiftpilot-deploy.timer"
else
    echo ""
    echo -e "${YELLOW}Systemd timer not installed.${NC}"
    echo "You can run the deployment manually: $REPO_DIR/auto-deploy.sh"
    echo ""
    echo "Or add a cron job:"
    echo "  crontab -e"
    echo "  */5 * * * * $REPO_DIR/auto-deploy.sh"
fi

echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Test the deployment script manually:"
echo "  $REPO_DIR/auto-deploy.sh"
