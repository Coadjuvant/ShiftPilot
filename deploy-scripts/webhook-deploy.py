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
SECRET = os.environ.get('WEBHOOK_SECRET', '')
DEPLOY_SCRIPT = os.environ.get('DEPLOY_SCRIPT', '/opt/shiftpilot/auto-deploy.sh')
EXPECTED_REPOSITORY = os.environ.get('DEPLOY_REPOSITORY', 'Coadjuvant/ShiftPilot')
EXPECTED_REF = 'refs/heads/' + os.environ.get('DEPLOY_BRANCH', 'main')

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
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
        if not 0 < content_length <= 1048576:
            self.send_error(413, 'Invalid payload size')
            return
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
            if self.headers.get('X-GitHub-Event') == 'push' and repo_name == EXPECTED_REPOSITORY and ref == EXPECTED_REF:
                branch = ref.split('/')[-1]
                logging.info(f"Triggering deployment for {branch}")

                # Run deployment script in background
                result = subprocess.run(
                    ['/bin/bash', DEPLOY_SCRIPT],
                    capture_output=True,
                    text=True,
                    timeout=600
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
        if len(SECRET) < 32:
            return False
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
    server = HTTPServer((os.environ.get('WEBHOOK_BIND', '127.0.0.1'), PORT), WebhookHandler)
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

    if len(SECRET) < 32:
        logging.error('WEBHOOK_SECRET must be configured with at least 32 characters')
        exit(1)

    run_server()
