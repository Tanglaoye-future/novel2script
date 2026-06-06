"""/health 与 / 端点冒烟测试。"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "novel2script"


def test_root_returns_hint():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "novel2script" in resp.json()["message"].lower()
