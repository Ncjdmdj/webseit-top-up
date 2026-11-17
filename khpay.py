import os, time, logging, requests

log = logging.getLogger(__name__)
KHPAY_API_KEY = os.environ.get("KHPAY_API_KEY", "")
KHPAY_BASE_URL = os.environ.get("KHPAY_BASE_URL", "https://khpay.site/api/v1")
KHPAY_EXPIRES_IN = int(os.environ.get("KHPAY_EXPIRES_IN", "600"))
_blocked_until = 0


def _headers():
    return {"Authorization": f"Bearer {KHPAY_API_KEY}", "Content-Type": "application/json",
            "Accept": "application/json", "User-Agent": "MyGameShop/1.0"}


def _call(method, url, **kw):
    global _blocked_until
    if time.time() < _blocked_until:
        return None, "KHPay blocked by Cloudflare, retrying later"
    try:
        r = requests.request(method, url, headers=_headers(), timeout=25, **kw)
    except Exception as e:
        return None, str(e)[:200]
    t = r.text[:500].lower()
    if r.status_code in (403, 503) and ("just a moment" in t or "cloudflare" in t):
        _blocked_until = time.time() + 300
        log.error("Cloudflare blocked this server IP. Ask KHPay to whitelist it.")
        return None, "IP blocked by Cloudflare - contact KHPay"
    try:
        return r.json(), None
    except ValueError:
        return None, f"HTTP {r.status_code} non-JSON"


def create_khpay_qr(order_ref, amount):
    if not KHPAY_API_KEY:
        return {"success": False, "message": "KHPAY_API_KEY not set"}
    body = {"amount": f"{float(amount):.2f}", "currency": "USD",
            "note": order_ref, "expires_in": KHPAY_EXPIRES_IN}
    d, err = _call("POST", f"{KHPAY_BASE_URL}/qr/generate", json=body)
    if err:
        return {"success": False, "message": err}
    if not d.get("success"):
        return {"success": False, "message": f"{d.get('error_code', '')}: {d.get('error', d)}"[:200]}
    data = d.get("data") or {}
    txn = data.get("transaction_id")
    return {"success": bool(txn), "transaction_id": txn,
            "qr_url": data.get("qr_image") or data.get("qr_url"),
            "payment_url": data.get("payment_url"),
            "message": "" if txn else "transaction_id missing"}


def check_khpay_paid(transaction_id):
    d, err = _call("GET", f"{KHPAY_BASE_URL}/qr/check/{transaction_id}")
    if err or not d or not d.get("success"):
        return False
    data = d.get("data") or {}
    return bool(data.get("paid")) or str(data.get("action") or "").lower() == "approved"
