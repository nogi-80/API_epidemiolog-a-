import os
from pathlib import Path

TEST_DATA_DIR = Path(__file__).parent / "data"
BLACKLIST_FILE = TEST_DATA_DIR / "blacklist.txt"
if BLACKLIST_FILE.exists():
    BLACKLIST_FILE.unlink()

os.environ.setdefault("DATA_DIR", str(TEST_DATA_DIR))
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("BLACKLIST_FILE", str(BLACKLIST_FILE))

import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _login():
    r = client.post("/login", json={"email": "admin@admin.com", "password": "Admin123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_logout():
    token = _login()
    r = client.post("/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_diseases_requires_auth():
    r = client.get("/diseases")
    assert r.status_code in (401, 403)


def test_diseases():
    token = _login()
    r = client.get("/diseases", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert {"code": "B50", "name": "Malaria"} in r.json()


def test_disease_codes_search():
    token = _login()
    r = client.get("/disease-codes?q=malaria", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert any(d["code"] == "B50" for d in data)


def test_years():
    token = _login()
    r = client.get("/years", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert 2025 in r.json()


def test_map():
    token = _login()
    r = client.get("/map?year=2025&code=B50", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    geo = r.json()
    assert geo["type"] == "FeatureCollection"
    props = geo["features"][0]["properties"]
    assert "TIA" in props


def test_top():
    token = _login()
    r = client.get("/top?year=2025&code=B50&metric=tia", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data[0]["ubigeo"] in ["160101", "160102"]


def test_export():
    token = _login()
    r = client.get("/export?year=2025&code=B50&format=csv", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.text.startswith("ANO,UBIGEO,CASOS")
