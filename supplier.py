import os, logging, requests

log = logging.getLogger("supplier")

SUPPLIER_URL = os.environ.get("SUPPLIER_URL", "").rstrip("/")
SUPPLIER_KEY = os.environ.get("SUPPLIER_KEY", "")
DEV_MODE = os.environ.get("DEV_MODE") == "1"  # LOCAL TESTING ONLY

# game id in your shop -> game id at the supplier (check the supplier's docs)
GAME_MAP = {"ml": "mlbb", "mlph": "mlbb_ph", "ff": "ff", "pubg": "pubg"}


def supplier_topup(o):
    """Send one order to the supplier.
    Returns ('ok'|'fail'|'unknown', note).
    'unknown' = timeout/ambiguous -> manual review, never auto-refund."""
    if DEV_MODE:
        return "ok", "dev"
    if not SUPPLIER_URL or not SUPPLIER_KEY:
        return "unknown", "SUPPLIER_URL / SUPPLIER_KEY not set"
    payload = {
        "api_key": SUPPLIER_KEY,
        "game_id": GAME_MAP.get(o["game_id"], o["game_id"]),
        "user_id": o["player_id"],
        "product_code": o["code"],
        "ref": f"ORD{o['id']}",
    }
    try:
        r = requests.post(f"{SUPPLIER_URL}/order", json=payload, timeout=30)
        d = r.json()
    except Exception as e:
        log.warning("supplier error order=%s: %s", o["id"], e)
        return "unknown", str(e)[:200]
    log.info("supplier order=%s http=%s resp=%s", o["id"], r.status_code, str(d)[:200])
    if d.get("success") is True:
        return "ok", str(d.get("order_id") or "")[:100]
    if d.get("success") is False:
        return "fail", str(d.get("message") or d.get("error") or d)[:200]
    return "unknown", str(d)[:200]