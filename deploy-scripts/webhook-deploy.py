#!/usr/bin/env python3
"""
ShiftPilot GitHub Webhook Deployment Server
Listens for GitHub push events and triggers auto-deployment

Usage:
    python3 webhook-deploy.py

Set WEBHOOK_SECRET in environment or update SECRET below
"""

import os
import hmac
import hashlib
import subprocess
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

# Configuration
PORT = 9000
SECRET = os.environ.get('WEBHOOK_SECRET', 'change-this-secret-key')
DEPLOY_SCRIPT = '/path/to/wip-scheduler/auto-deploy.sh'  # UPDATE THIS PATH

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/shiftpilot-webhook.log'),
        logging.StreamHandler()
    ]
)

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Handle POST requests from GitHub"""
        if self.path != '/deploy':
            self.send_response(404)
            self.end_headers()
            return

        # Verify GitHub signature
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        signature = self.headers.get('X-Hub-Signature-256', '')

        if not self.verify_signature(post_data, signature):
            logging.warning('Invalid signature received')
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b'Invalid signature')
            return

        # Parse payload
        try:
            payload = json.loads(post_data)
            ref = payload.get('ref', '')
            repo_name = payload.get('repository', {}).get('full_name', 'unknown')

            logging.info(f"Webhook received from {repo_name}: {ref}")

            # Only deploy for main/dev branch pushes
            if ref in ['refs/heads/main', 'refs/heads/dev']:
                branch = ref.split('/')[-1]
                logging.info(f"Triggering deployment for {branch}")

                # Run deployment script in background
                result = subprocess.run(
                    ['/bin/bash', DEPLOY_SCRIPT],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    logging.info(f"Deployment completed successfully")
                    response = {'status': 'success', 'message': 'Deployment triggered'}
                else:
                    logging.error(f"Deployment failed: {result.stderr}")
                    response = {'status': 'error', 'message': result.stderr}

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
            else:
                logging.info(f"Ignoring push to {ref}")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Branch ignored')

        except Exception as e:
            logging.error(f"Error processing webhook: {str(e)}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode())

    def verify_signature(self, payload, signature):
        """Verify GitHub webhook signature"""
        if not signature:
            return False

        expected_signature = 'sha256=' + hmac.new(
            SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    def log_message(self, format, *args):
        """Override to use logging instead of print"""
        logging.info(f"{self.address_string()} - {format % args}")


def run_server():
    """Start the webhook server"""
    server = HTTPServer(('0.0.0.0', PORT), WebhookHandler)
    logging.info(f"Webhook server started on port {PORT}")
    logging.info(f"Deployment script: {DEPLOY_SCRIPT}")
    logging.info("Waiting for GitHub webhooks...")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("Shutting down webhook server")
        server.shutdown()


if __name__ == '__main__':
    # Verify deploy script exists
    if not os.path.exists(DEPLOY_SCRIPT):
        logging.error(f"Deploy script not found: {DEPLOY_SCRIPT}")
        logging.error("Please update DEPLOY_SCRIPT in webhook-deploy.py")
        exit(1)

    if SECRET == 'change-this-secret-key':
        logging.warning("WARNING: Using default secret key!")
        logging.warning("Set WEBHOOK_SECRET environment variable or update SECRET in script")

    run_server()
