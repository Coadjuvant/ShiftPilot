# ShiftPilot Auto-Deployment

Automated deployment scripts for your Vultr server. These scripts monitor your GitHub repository for changes and automatically pull and rebuild when new commits are detected.

## Quick Start

### 1. Initial Setup on Vultr Server

```bash
# Clone your repo (if not already done)
cd /home/your-user
git clone https://github.com/Coadjuvant/ShiftPilot.git
cd ShiftPilot

# Make installation script executable
chmod +x deploy-scripts/install-auto-deploy.sh

# Run the installation
./deploy-scripts/install-auto-deploy.sh
```

The installer will:
- Configure the auto-deploy script with your paths
- Create log files
- Optionally set up automatic checks every 5 minutes

### 2. Manual Deployment

To manually trigger a deployment check:

```bash
./auto-deploy.sh
```

## How It Works

### Auto-Deploy Script (`auto-deploy.sh`)

1. **Fetch** - Checks GitHub for new commits
2. **Compare** - Compares local and remote commits
3. **Pull** - If changes exist, pulls the latest code
4. **Rebuild** - Rebuilds Docker containers or runs build commands
5. **Restart** - Restarts services
6. **Log** - Records all actions to `/var/log/shiftpilot-deploy.log`

### Safety Features

- **Lock file** - Prevents multiple deployments from running simultaneously
- **Stashing** - Saves any local changes before pulling
- **Error handling** - Exits cleanly on errors
- **Logging** - Comprehensive logs for troubleshooting

## Deployment Methods

### Option 1: Systemd Timer (Recommended)

Automatically checks every 5 minutes:

```bash
# Enable the timer (done by installer)
sudo systemctl enable shiftpilot-deploy.timer
sudo systemctl start shiftpilot-deploy.timer

# Check status
sudo systemctl status shiftpilot-deploy.timer

# View logs
sudo journalctl -u shiftpilot-deploy.service -f
```

### Option 2: Cron Job

Add to crontab for periodic checks:

```bash
crontab -e
```

Add this line (checks every 5 minutes):
```
*/5 * * * * /path/to/ShiftPilot/auto-deploy.sh
```

For every 10 minutes:
```
*/10 * * * * /path/to/ShiftPilot/auto-deploy.sh
```

For hourly:
```
0 * * * * /path/to/ShiftPilot/auto-deploy.sh
```

### Option 3: GitHub Webhook

For instant deployments when you push to GitHub:

1. Create a webhook endpoint on your server
2. Configure GitHub webhook to hit your endpoint
3. Endpoint triggers `auto-deploy.sh`

(Webhook setup requires additional security considerations)

## Monitoring

### View Deployment Logs

```bash
# Tail the log file
tail -f /var/log/shiftpilot-deploy.log

# View last 50 lines
tail -n 50 /var/log/shiftpilot-deploy.log

# Search for errors
grep ERROR /var/log/shiftpilot-deploy.log
```

### Check Timer Status

```bash
# See when next deployment check will run
systemctl list-timers | grep shiftpilot

# View timer status
sudo systemctl status shiftpilot-deploy.timer

# View service status
sudo systemctl status shiftpilot-deploy.service
```

## Configuration

### Change Check Frequency

Edit `/etc/systemd/system/shiftpilot-deploy.timer`:

```ini
# Every 10 minutes
OnCalendar=*:0/10

# Every hour at :00
OnCalendar=hourly

# Every 30 minutes
OnCalendar=*:0/30
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart shiftpilot-deploy.timer
```

### Change Deployment Branch

Edit `auto-deploy.sh`:
```bash
BRANCH="dev"  # Change from "main" to "dev"
```

## Troubleshooting

### Deployment Not Running

```bash
# Check if timer is active
sudo systemctl is-active shiftpilot-deploy.timer

# Check for errors
sudo journalctl -u shiftpilot-deploy.service --since "1 hour ago"

# Manually test the script
./auto-deploy.sh
```

### Docker Issues

```bash
# Check if containers are running
docker-compose ps

# View container logs
docker-compose logs -f

# Rebuild manually
docker-compose down
docker-compose up -d --build
```

### Permission Issues

```bash
# Make script executable
chmod +x auto-deploy.sh

# Fix log file permissions
sudo chown $USER:$USER /var/log/shiftpilot-deploy.log
```

## Stopping Auto-Deployment

### Temporarily Stop

```bash
# Stop the timer
sudo systemctl stop shiftpilot-deploy.timer
```

### Permanently Disable

```bash
# Disable and stop
sudo systemctl disable shiftpilot-deploy.timer
sudo systemctl stop shiftpilot-deploy.timer
```

### Remove Completely

```bash
sudo systemctl stop shiftpilot-deploy.timer
sudo systemctl disable shiftpilot-deploy.timer
sudo rm /etc/systemd/system/shiftpilot-deploy.timer
sudo rm /etc/systemd/system/shiftpilot-deploy.service
sudo systemctl daemon-reload
```

## Best Practices

1. **Test First** - Run `./auto-deploy.sh` manually before enabling automation
2. **Monitor Logs** - Check `/var/log/shiftpilot-deploy.log` regularly
3. **Staged Deployments** - Consider deploying to `dev` branch first
4. **Notifications** - Set up alerts for deployment failures
5. **Backup** - Keep database backups before major deployments

## Security Notes

- The script runs as your user (not root)
- Lock files prevent concurrent deployments
- Logs contain commit messages and deployment status
- Never commit sensitive credentials to the repository
- Use environment variables for secrets

## Support

If deployments fail:
1. Check `/var/log/shiftpilot-deploy.log`
2. Run `./auto-deploy.sh` manually to see errors
3. Verify GitHub connectivity: `git fetch origin`
4. Check Docker status: `docker-compose ps`
