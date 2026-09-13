"""
Module      : smoke_test_fastapi.py
Date        : 2026-09-11
Author      : Dhruv
Modification History:
    2026-09-11 - Created for FastAPI verification. Tests all endpoints end-to-end:
                 Swagger docs, auth lifecycle, portfolio, watchlist, admin panel.
Synopsis:
    Automated smoke tests for TradeSage AI FastAPI application. Adheres to
    CHARUSAT v1.0 testing standards.
"""

import os
import sys
import uuid
import pytest

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from fastapi.testclient import TestClient
from main import app
from models import initDb

client = TestClient(app)


def setup_module():
    """Initializes database tables before testing."""
    initDb()


def test_docs_and_openapi():
    """Verifies Swagger UI and OpenAPI schemas are served with HTTP 200."""
    resDocs = client.get("/docs")
    assert resDocs.status_code == 200
    assert "swagger" in resDocs.text.lower() or "html" in resDocs.text.lower()

    resOpenApi = client.get("/openapi.json")
    assert resOpenApi.status_code == 200
    schema = resOpenApi.json()
    assert schema["info"]["title"] == "TradeSage AI — Trading Intelligence Terminal API"
    assert "paths" in schema


def test_static_dashboard():
    """Verifies static dashboard is accessible."""
    resStatic = client.get("/static/dashboard.html")
    assert resStatic.status_code == 200
    assert "TradeSage" in resStatic.text


def test_auth_and_portfolio_flow():
    """Tests full authenticated lifecycle: register -> login -> add holding -> get portfolio -> logout."""
    testEmail = f"trader_{uuid.uuid4().hex[:8]}@test.com"
    testPassword = "Password123!"

    # 1. Register
    resReg = client.post("/api/register", json={"email": testEmail, "password": testPassword})
    assert resReg.status_code == 201
    userData = resReg.json()
    assert userData["email"] == testEmail
    assert "userId" in userData

    # 2. Login
    resLogin = client.post("/api/login", json={"email": testEmail, "password": testPassword})
    assert resLogin.status_code == 200
    assert "session" in client.cookies

    # 3. Portfolio empty check
    resPort = client.get("/api/portfolio")
    assert resPort.status_code == 200
    portData = resPort.json()
    assert portData["totalPnl"] == 0.0
    assert isinstance(portData["holdings"], list)

    # 4. Add holding
    resHolding = client.post("/api/holdings", json={
        "assetSymbol": "AAPL",
        "assetType": "stock",
        "quantity": 10.0,
        "buyPrice": 150.0,
        "buyDate": "2026-08-01"
    })
    assert resHolding.status_code == 201
    assert "holdingId" in resHolding.json()

    # 5. Portfolio comparison (stocks vs crypto)
    resComp = client.get("/api/portfolio/comparison")
    assert resComp.status_code == 200
    compData = resComp.json()
    assert "stock" in compData
    assert "crypto" in compData

    # 6. Watchlist flow
    resAddWatch = client.post("/api/watchlist", json={"assetSymbol": "MSFT", "assetType": "stock"})
    assert resAddWatch.status_code == 201
    watchlistId = resAddWatch.json()["watchlistId"]

    resGetWatch = client.get("/api/watchlist")
    assert resGetWatch.status_code == 200
    assert any(item["assetSymbol"] == "MSFT" for item in resGetWatch.json())

    resDelWatch = client.delete(f"/api/watchlist/{watchlistId}")
    assert resDelWatch.status_code == 200

    # 7. Admin panel endpoints
    resAdminAssets = client.get("/api/admin/tracked-assets")
    assert resAdminAssets.status_code == 200

    resAddAsset = client.post("/api/admin/tracked-assets", json={"assetSymbol": f"TEST_{uuid.uuid4().hex[:4]}", "assetType": "stock"})
    assert resAddAsset.status_code == 201
    assetId = resAddAsset.json()["trackedAssetId"]

    resDelAsset = client.delete(f"/api/admin/tracked-assets/{assetId}")
    assert resDelAsset.status_code == 200

    resConfig = client.get("/api/admin/config")
    assert resConfig.status_code == 200
    assert "retrainIntervalDays" in resConfig.json()

    resSetConfig = client.post("/api/admin/config", json={"retrainIntervalDays": 3})
    assert resSetConfig.status_code == 200
    assert resSetConfig.json()["retrainIntervalDays"] == 3

    resHealth = client.get("/api/admin/health")
    assert resHealth.status_code == 200

    # 8. Logout
    resLogout = client.post("/api/logout")
    assert resLogout.status_code == 200


if __name__ == "__main__":
    test_docs_and_openapi()
    print("test_docs_and_openapi passed!")
    test_static_dashboard()
    print("test_static_dashboard passed!")
    test_auth_and_portfolio_flow()
    print("test_auth_and_portfolio_flow passed!")
    print("ALL FASTAPI SMOKE TESTS PASSED!")
