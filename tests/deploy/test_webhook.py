import hashlib
import hmac
import importlib.util
from pathlib import Path


def test_webhook_rejects_missing_default_or_invalid_secrets(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "deploy-scripts/webhook-deploy.py"
    spec = importlib.util.spec_from_file_location("webhook_deploy_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    handler = object.__new__(module.WebhookHandler)
    body = b'{"ref":"refs/heads/main"}'
    monkeypatch.setattr(module, "SECRET", "change-this-secret-key")
    signature = "sha256=" + hmac.new(module.SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert not handler.verify_signature(body, signature)
    monkeypatch.setattr(module, "SECRET", "a-test-webhook-secret-with-more-than-32-characters")
    signature = "sha256=" + hmac.new(module.SECRET.encode(), body, hashlib.sha256).hexdigest()
    assert handler.verify_signature(body, signature)
    assert not handler.verify_signature(body + b"tampered", signature)
