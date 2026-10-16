import base64
from collections import defaultdict, deque
import hashlib
import hmac
import json
import os
import time
from threading import Lock
import urllib.error
import urllib.parse
import urllib.request
import io
import zipfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from decimal import Decimal, InvalidOperation
from pathlib import Path

import jwt
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

APP = FastAPI(title="Hesba Payments", version="0.1.0")
SITE_ORIGINS = {
    "https://hesba-income-tools.onrender.com",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
}
APP.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(SITE_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

PRODUCT_ID = "hesba-freelancer-kit-v1"
PRODUCT_PRICE = Decimal("5.99")
PRODUCT_CURRENCY = "USD"
PRODUCT_NAME = "Hesba Freelancer Desk Kit (Arabic)"
SITE_URL = "https://hesba-income-tools.onrender.com"
DOWNLOAD_TTL_SECONDS = 15 * 60

_RATE_WINDOW_SECONDS = 60
_RATE_LIMITS: dict[str, deque[float]] = defaultdict(deque)
_RATE_LOCK = Lock()


def enforce_rate_limit(request: Request, bucket: str, max_requests: int) -> None:
    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}:{bucket}"
    now = time.monotonic()
    with _RATE_LOCK:
        events = _RATE_LIMITS[key]
        while events and now - events[0] >= _RATE_WINDOW_SECONDS:
            events.popleft()
        if len(events) >= max_requests:
            raise HTTPException(
                status_code=429,
                detail="rate_limit_exceeded",
                headers={"Retry-After": str(_RATE_WINDOW_SECONDS)},
            )
        events.append(now)
        if len(_RATE_LIMITS) > 5000:
            stale_keys = [k for k, q in _RATE_LIMITS.items() if not q or now - q[-1] >= _RATE_WINDOW_SECONDS]
            for stale_key in stale_keys[:1000]:
                _RATE_LIMITS.pop(stale_key, None)


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def download_secret() -> str:
    secret = env("HESBA_DOWNLOAD_SECRET")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="checkout_not_configured")
    return secret


def paypal_base() -> str:
    return "https://api-m.paypal.com" if env("PAYPAL_MODE").lower() == "live" else "https://api-m.sandbox.paypal.com"


def encrypted_product_payload() -> bytes:
    """Load the current encrypted kit only when all fixed chunks are present."""
    asset_root = Path(__file__).resolve().parent / "hesba"
    part_dir = asset_root / "kit-v2-parts"
    parts = sorted(part_dir.glob("part*.b64")) if part_dir.exists() else []
    if len(parts) == 8:
        encoded = "".join(p.read_text(encoding="ascii").strip() for p in parts)
    else:
        encoded = (asset_root / "kit-v1.aesgcm.b64").read_text(encoding="ascii").strip()
    return base64.b64decode(encoded, validate=True)


def product_pack_status() -> str:
    key_text = env("HESBA_KIT_KEY")
    if not key_text:
        return "key_missing"
    try:
        key = base64.b64decode(key_text, validate=True)
    except Exception:
        return "key_invalid"
    if len(key) != 32:
        return "key_invalid_length"
    try:
        packed = encrypted_product_payload()
    except FileNotFoundError:
        return "asset_missing"
    except Exception:
        return "ciphertext_invalid"
    if len(packed) < 29:
        return "ciphertext_too_short"
    try:
        content = AESGCM(key).decrypt(packed[:12], packed[12:], b"hesba-kit-v1")
    except Exception:
        return "decryption_failed"
    if not content.startswith(bytes((80, 75, 3, 4))):
        return "not_zip"
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            if archive.testzip() is not None:
                return "archive_integrity_failed"
            if "hesba-kit/trackers/hesba-business-tracker.xlsx" not in names:
                return "workbook_missing"
            if sum(n.startswith("hesba-kit/templates/") and n.endswith(".md") for n in names) < 12:
                return "templates_missing"
            if sum(n.startswith("hesba-kit/trackers/") and n.endswith(".csv") for n in names) < 3:
                return "trackers_missing"
            if "hesba-kit/README_AR.md" not in names:
                return "readme_missing"
    except Exception:
        return "archive_invalid"
    return "valid"


def load_product_pack() -> bytes:
    status = product_pack_status()
    if status != "valid":
        raise ValueError(status)
    key = base64.b64decode(env("HESBA_KIT_KEY"), validate=True)
    packed = encrypted_product_payload()
    return AESGCM(key).decrypt(packed[:12], packed[12:], b"hesba-kit-v1")

def product_pack_valid() -> bool:
    return product_pack_status() == "valid"

def payment_configured() -> bool:
    # Never expose a live checkout unless production PayPal credentials and the product asset are configured.
    return bool(
        env("PAYPAL_MODE").lower() == "live"
        and env("PAYPAL_CLIENT_ID")
        and env("PAYPAL_CLIENT_SECRET")
        and len(env("HESBA_DOWNLOAD_SECRET")) >= 32
        and product_pack_valid()
    )


def paypal_request(method: str, path: str, body: dict | None = None, request_id: str | None = None) -> dict:
    client_id, secret = env("PAYPAL_CLIENT_ID"), env("PAYPAL_CLIENT_SECRET")
    if not client_id or not secret:
        raise HTTPException(status_code=503, detail="checkout_not_configured")
    token_url = paypal_base() + "/v1/oauth2/token"
    basic = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    token_request = urllib.request.Request(
        token_url,
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Authorization": f"Basic {basic}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(token_request, timeout=15) as response:
            access_token = json.loads(response.read())["access_token"]
    except Exception:
        # Do not surface provider body or credentials to clients.
        raise HTTPException(status_code=502, detail="payment_provider_auth_failed")

    raw = json.dumps(body, separators=(",", ":")).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json", "Accept": "application/json"}
    if request_id:
        headers["PayPal-Request-Id"] = request_id
    request = urllib.request.Request(paypal_base() + path, data=raw, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = response.read()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        # Keep provider diagnostics in server logs only; never echo raw order/customer data.
        status = exc.code
        if status in (400, 401, 403, 404, 409, 422):
            raise HTTPException(status_code=409 if status in (400, 409, 422) else 502, detail="payment_provider_rejected_request")
        raise HTTPException(status_code=502, detail="payment_provider_unavailable")
    except Exception:
        raise HTTPException(status_code=502, detail="payment_provider_unavailable")


def make_custom_id(timestamp: int) -> str:
    secret = download_secret().encode()
    payload = json.dumps({"p": "kit1", "v": "5.99", "c": "USD", "t": timestamp}, separators=(",", ":"), sort_keys=True).encode()
    packed = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(hmac.new(secret, payload, hashlib.sha256).digest()).decode().rstrip("=")
    value = packed + "." + signature
    if len(value) > 127:
        raise HTTPException(status_code=500, detail="order_metadata_error")
    return value


def verify_custom_id(value: str) -> bool:
    try:
        packed, signature = value.split(".", 1)
        payload = base64.urlsafe_b64decode(packed + "=" * (-len(packed) % 4))
        supplied_sig = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        expected_sig = hmac.new(download_secret().encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(supplied_sig, expected_sig):
            return False
        claims = json.loads(payload)
        if claims.get("p") != "kit1" or claims.get("v") != "5.99" or claims.get("c") != "USD":
            return False
        age = int(time.time()) - int(claims["t"])
        return -60 <= age <= 3 * 60 * 60
    except Exception:
        return False


def find_own_purchase_unit(order: dict) -> dict:
    units = order.get("purchase_units") or []
    if len(units) != 1:
        raise HTTPException(status_code=409, detail="order_mismatch")
    unit = units[0]
    if unit.get("reference_id") != PRODUCT_ID or not verify_custom_id(unit.get("custom_id", "")):
        raise HTTPException(status_code=409, detail="order_mismatch")
    amount = unit.get("amount") or {}
    if amount.get("currency_code") != PRODUCT_CURRENCY or amount.get("value") != str(PRODUCT_PRICE):
        raise HTTPException(status_code=409, detail="order_mismatch")
    return unit


class CreateOrderInput(BaseModel):
    product_id: str = Field(default=PRODUCT_ID, max_length=80)


class CaptureOrderInput(BaseModel):
    order_id: str = Field(min_length=8, max_length=40, pattern=r"^[A-Z0-9]+$")


@APP.get("/")
def root():
    return {
        "service": "hesba-payments-api",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
    }


@APP.get("/health")
def health():
    return {
        "status": "ok",
        "service": "hesba-payments-api",
        "checkout_configured": payment_configured(),
        "product_pack_valid": product_pack_valid(),
        "product_pack_issue": product_pack_status(),
        "paypal_mode": env("PAYPAL_MODE", "sandbox").lower() if env("PAYPAL_MODE", "sandbox").lower() in {"sandbox", "live"} else "sandbox",
        "version": "0.1.0",
    }


@APP.get("/api/config")
def public_config():
    ready = payment_configured()
    return {
        "checkout_enabled": ready,
        "paypal_client_id": env("PAYPAL_CLIENT_ID") if ready else None,
        "currency": PRODUCT_CURRENCY,
        "price": str(PRODUCT_PRICE),
        "product_name": PRODUCT_NAME,
        "product_pack_valid": product_pack_valid(),
        "product_pack_issue": product_pack_status(),
        "message": None if ready else "الدفع الإلكتروني لم يُفعّل بعد.",
    }


@APP.post("/api/orders")
def create_order(data: CreateOrderInput, request: Request):
    enforce_rate_limit(request, "create_order", 8)
    if data.product_id != PRODUCT_ID:
        raise HTTPException(status_code=404, detail="product_not_found")
    if not payment_configured():
        raise HTTPException(status_code=503, detail="checkout_not_configured")
    stamp = int(time.time())
    payload = {
        "intent": "CAPTURE",
        "purchase_units": [{
            "reference_id": PRODUCT_ID,
            "custom_id": make_custom_id(stamp),
            "description": PRODUCT_NAME,
            "amount": {"currency_code": PRODUCT_CURRENCY, "value": str(PRODUCT_PRICE)},
        }],
        "application_context": {
            "brand_name": "Hesba",
            "user_action": "PAY_NOW",
            "shipping_preference": "NO_SHIPPING",
            "return_url": SITE_URL + "/?checkout=approved",
            "cancel_url": SITE_URL + "/?checkout=cancelled",
        },
    }
    order = paypal_request("POST", "/v2/checkout/orders", payload, request_id=hashlib.sha256(f"{stamp}:{request.client.host if request.client else 'unknown'}".encode()).hexdigest()[:32])
    if not order.get("id"):
        raise HTTPException(status_code=502, detail="payment_provider_invalid_response")
    return {"id": order["id"]}


@APP.post("/api/orders/capture")
def capture_order(data: CaptureOrderInput, request: Request):
    enforce_rate_limit(request, "capture_order", 12)
    if not payment_configured():
        raise HTTPException(status_code=503, detail="checkout_not_configured")
    order_id = data.order_id
    # Inspect the order first to make sure it belongs to this product and was created by this server.
    order = paypal_request("GET", "/v2/checkout/orders/" + urllib.parse.quote(order_id, safe=""))
    find_own_purchase_unit(order)
    if order.get("status") == "COMPLETED":
        captured = order
    else:
        if order.get("status") != "APPROVED":
            raise HTTPException(status_code=409, detail="order_not_approved")
        captured = paypal_request("POST", "/v2/checkout/orders/" + urllib.parse.quote(order_id, safe="") + "/capture", {}, request_id=hashlib.sha256((order_id + ":capture").encode()).hexdigest()[:32])
    unit = find_own_purchase_unit(captured)
    payments = ((unit.get("payments") or {}).get("captures") or [])
    completed = any(p.get("status") == "COMPLETED" and (p.get("amount") or {}).get("currency_code") == PRODUCT_CURRENCY and (p.get("amount") or {}).get("value") == str(PRODUCT_PRICE) for p in payments)
    if not completed:
        raise HTTPException(status_code=409, detail="payment_not_completed")
    token = jwt.encode(
        {"sub": PRODUCT_ID, "order_id": order_id, "iat": int(time.time()), "exp": int(time.time()) + DOWNLOAD_TTL_SECONDS},
        download_secret(),
        algorithm="HS256",
    )
    return {"status": "COMPLETED", "download_token": token, "download_expires_in": DOWNLOAD_TTL_SECONDS}


@APP.post("/api/download")
def download_product(request: Request, authorization: str | None = Header(default=None)):
    enforce_rate_limit(request, "download", 20)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="download_token_required")
    token = authorization[7:].strip()
    try:
        claims = jwt.decode(token, download_secret(), algorithms=["HS256"], options={"require": ["sub", "iat", "exp"]})
        if claims.get("sub") != PRODUCT_ID or not claims.get("order_id"):
            raise ValueError("wrong product")
    except Exception:
        raise HTTPException(status_code=403, detail="download_link_invalid_or_expired")
    try:
        content = load_product_pack()
    except Exception:
        raise HTTPException(status_code=503, detail="product_file_not_configured")
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="hesba-freelancer-desk-kit-v1.zip"',
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )
