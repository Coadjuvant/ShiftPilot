from starlette.requests import Request


def request(peer, headers):
    return Request({"type": "http", "client": (peer, 1234), "headers": [(k.encode(), v.encode()) for k,v in headers.items()]})


def test_direct_clients_cannot_spoof_rate_limit_address(monkeypatch):
    from backend.api import request_context
    monkeypatch.setattr(request_context, "TRUSTED_PROXY_CIDRS", ["127.0.0.1/32"])
    req = request("198.51.100.1", {"cf-connecting-ip": "1.1.1.1", "x-forwarded-for": "8.8.8.8"})
    assert request_context.client_ip(req) == "198.51.100.1"


def test_trusted_proxy_uses_last_untrusted_hop(monkeypatch):
    from backend.api import request_context
    monkeypatch.setattr(request_context, "TRUSTED_PROXY_CIDRS", ["127.0.0.1/32", "172.16.0.0/12"])
    req = request("172.19.0.4", {"x-forwarded-for": "8.8.8.8, 198.51.100.2, 127.0.0.1"})
    assert request_context.client_ip(req) == "198.51.100.2"
