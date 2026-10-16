import io
import time
import zipfile

import jwt
import pytest
from fastapi.testclient import TestClient

import hesba_payments as payments


client = TestClient(payments.APP)
TEST_SECRET = "unit-test-only-secret-value-longer-than-32-chars"


def _zip_bytes():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("hesba-kit/README_AR.md", "اختبار")
        archive.writestr("hesba-kit/template.md", "قالب")
    return buffer.getvalue()


def _download_token(secret=TEST_SECRET, *, product_id=None, exp=None):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": product_id or payments.PRODUCT_ID,
            "order_id": "ORDERTEST20261016",
            "iat": now - 1,
            "exp": exp or now + 300,
        },
        secret,
        algorithm="HS256",
    )


def _provider_order(status, custom_id, *, completed=False):
    unit = {
        "reference_id": payments.PRODUCT_ID,
        "custom_id": custom_id,
        "amount": {"currency_code": "USD", "value": "5.99"},
    }
    if completed:
        unit["payments"] = {
            "captures": [{
                "id": "CAPTURE-TEST",
                "status": "COMPLETED",
                "amount": {"currency_code": "USD", "value": "5.99"},
            }]
        }
    return {"id": "ORDERTEST20261016", "status": status, "purchase_units": [unit]}


def test_public_config_keeps_checkout_disabled_without_live_credentials(monkeypatch):
    monkeypatch.setenv("PAYPAL_MODE", "sandbox")
    monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("HESBA_DOWNLOAD_SECRET", TEST_SECRET)
    monkeypatch.setattr(payments, "product_pack_valid", lambda: True)

    response = client.get("/api/config")
    assert response.status_code == 200
    result = response.json()
    assert result["checkout_enabled"] is False
    assert result["paypal_client_id"] is None
    assert result["price"] == "5.99"
    assert result["currency"] == "USD"


def test_create_order_fails_closed_when_checkout_is_disabled(monkeypatch):
    monkeypatch.setattr(payments, "payment_configured", lambda: False)
    response = client.post("/api/orders", json={"product_id": payments.PRODUCT_ID})
    assert response.status_code == 503
    assert response.json()["detail"] == "checkout_not_configured"


def test_download_requires_authorization_header(monkeypatch):
    response = client.post("/api/download")
    assert response.status_code == 401
    assert response.json()["detail"] == "download_token_required"


def test_download_rejects_invalid_or_expired_tokens(monkeypatch):
    monkeypatch.setenv("HESBA_DOWNLOAD_SECRET", TEST_SECRET)
    monkeypatch.setattr(payments, "load_product_pack", _zip_bytes)

    invalid = client.post(
        "/api/download",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert invalid.status_code == 403

    expired = _download_token(exp=int(time.time()) - 30)
    expired_response = client.post(
        "/api/download",
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert expired_response.status_code == 403

    wrong_product = _download_token(product_id="another-product")
    wrong_product_response = client.post(
        "/api/download",
        headers={"Authorization": f"Bearer {wrong_product}"},
    )
    assert wrong_product_response.status_code == 403


def test_verified_download_returns_zip_with_no_cache_headers(monkeypatch):
    monkeypatch.setenv("HESBA_DOWNLOAD_SECRET", TEST_SECRET)
    payload = _zip_bytes()
    monkeypatch.setattr(payments, "load_product_pack", lambda: payload)
    token = _download_token()

    response = client.post(
        "/api/download",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert "hesba-freelancer-desk-kit-v1.zip" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content == payload


def test_capture_returns_a_token_not_a_token_bearing_url(monkeypatch):
    monkeypatch.setenv("HESBA_DOWNLOAD_SECRET", TEST_SECRET)
    monkeypatch.setattr(payments, "payment_configured", lambda: True)
    custom_id = payments.make_custom_id(int(time.time()))
    approved = _provider_order("APPROVED", custom_id)
    completed = _provider_order("COMPLETED", custom_id, completed=True)

    def fake_paypal_request(method, path, body=None, request_id=None):
        if method == "GET":
            return approved
        assert method == "POST"
        assert path.endswith("/capture")
        return completed

    monkeypatch.setattr(payments, "paypal_request", fake_paypal_request)
    response = client.post(
        "/api/orders/capture",
        json={"order_id": "ORDERTEST20261016"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert "download_token" in payload
    assert "download_url" not in payload

    claims = jwt.decode(
        payload["download_token"],
        TEST_SECRET,
        algorithms=["HS256"],
        options={"require": ["sub", "iat", "exp"]},
    )
    assert claims["sub"] == payments.PRODUCT_ID
    assert claims["order_id"] == "ORDERTEST20261016"


def test_download_cors_allows_authorization_header():
    response = client.options(
        "/api/download",
        headers={
            "Origin": "https://hesba-income-tools.onrender.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "https://hesba-income-tools.onrender.com"
    assert "authorization" in response.headers.get("access-control-allow-headers", "").lower()



def test_reissue_download_for_completed_order_and_matching_payer_email(monkeypatch):
    monkeypatch.setenv("HESBA_DOWNLOAD_SECRET", TEST_SECRET)
    monkeypatch.setattr(payments, "payment_configured", lambda: True)
    monkeypatch.setattr(payments, "enforce_rate_limit", lambda *args, **kwargs: None)
    old_custom_id = payments.make_custom_id(int(time.time()) - 90 * 24 * 60 * 60)
    order = _provider_order("COMPLETED", old_custom_id, completed=True)
    order["payer"] = {"email_address": "Buyer@example.com"}
    monkeypatch.setattr(payments, "paypal_request", lambda method, path, body=None, request_id=None: order)

    response = client.post(
        "/api/orders/reissue-download",
        json={"order_id": "ORDERTEST20261016", "payer_email": "buyer@example.com"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "COMPLETED"
    assert "download_token" in payload
    claims = jwt.decode(
        payload["download_token"],
        TEST_SECRET,
        algorithms=["HS256"],
        options={"require": ["sub", "iat", "exp"]},
    )
    assert claims["sub"] == payments.PRODUCT_ID
    assert claims["order_id"] == "ORDERTEST20261016"


def test_reissue_download_rejects_payer_email_mismatch(monkeypatch):
    monkeypatch.setenv("HESBA_DOWNLOAD_SECRET", TEST_SECRET)
    monkeypatch.setattr(payments, "payment_configured", lambda: True)
    monkeypatch.setattr(payments, "enforce_rate_limit", lambda *args, **kwargs: None)
    order = _provider_order("COMPLETED", payments.make_custom_id(int(time.time())), completed=True)
    order["payer"] = {"email_address": "buyer@example.com"}
    monkeypatch.setattr(payments, "paypal_request", lambda method, path, body=None, request_id=None: order)

    response = client.post(
        "/api/orders/reissue-download",
        json={"order_id": "ORDERTEST20261016", "payer_email": "attacker@example.com"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "order_owner_verification_failed"


def test_reissue_download_rejects_unpaid_or_approved_order(monkeypatch):
    monkeypatch.setenv("HESBA_DOWNLOAD_SECRET", TEST_SECRET)
    monkeypatch.setattr(payments, "payment_configured", lambda: True)
    monkeypatch.setattr(payments, "enforce_rate_limit", lambda *args, **kwargs: None)
    order = _provider_order("APPROVED", payments.make_custom_id(int(time.time())))
    order["payer"] = {"email_address": "buyer@example.com"}
    monkeypatch.setattr(payments, "paypal_request", lambda method, path, body=None, request_id=None: order)

    response = client.post(
        "/api/orders/reissue-download",
        json={"order_id": "ORDERTEST20261016", "payer_email": "buyer@example.com"},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "payment_not_completed"


def test_reissue_download_remains_closed_when_checkout_is_disabled(monkeypatch):
    monkeypatch.setattr(payments, "payment_configured", lambda: False)
    response = client.post(
        "/api/orders/reissue-download",
        json={"order_id": "ORDERTEST20261016", "payer_email": "buyer@example.com"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "checkout_not_configured"
