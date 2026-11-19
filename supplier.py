import os, re, sys, json, logging, requests

log = logging.getLogger("supplier")

BASE = (os.environ.get("KHMER_TOPUP_BASE_URL") or os.environ.get("SUPPLIER_URL")
        or "https://khmer-topup.com/api/v1").rstrip("/")
API_KEY = os.environ.get("KHMER_TOPUP_API_KEY") or os.environ.get("SUPPLIER_KEY", "")
DEV_MODE = os.environ.get("DEV_MODE") == "1"  # LOCAL TESTING ONLY

# Shop pack code (3rd value in CATALOG) -> supplier package_id (integer).
# Find ids by running:  python supplier.py
PACKAGE_IDS = {
    # "ML86": 101,
    # "ML172": 102,
}

IN_PROGRESS = {"processing", "pending", "accepted"}


class SupplierError(Exception):
    def __init__(self, msg, status=None):
        super().__init__(msg)
        self.status = status

    @property
    def definite(self):
        """True when the supplier clearly rejected the order (safe to refund)."""
        return self.status is not None and 400 <= self.status < 500 and self.status not in (408, 409, 429)


class KhmerTopUp:
    def __init__(self):
        self.headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json",
                        "Accept": "application/json"}

    def _request(self, method, path, **kw):
        try:
            r = requests.request(method, BASE + path, headers=self.headers, timeout=25, **kw)
        except requests.RequestException as e:
            raise SupplierError(f"Network error: {e}") from e
        try:
            data = r.json()
        except ValueError as e:
            raise SupplierError(f"Non-JSON response (HTTP {r.status_code})", r.status_code) from e
        if not r.ok:
            raise SupplierError(f"HTTP {r.status_code}: {data.get('error', data)}", r.status_code)
        return data

    def me(self): return self._request("GET", "/me")
    def games(self): return self._request("GET", "/games").get("games", [])

    def check(self, slug, player_id, server_id=None):
        p = {"slug": slug, "player_id": player_id}
        if server_id: p["server_id"] = server_id
        return self._request("GET", "/check", params=p)

    def create_order(self, package_id, player_id, server_id, reference):
        body = {"package_id": int(package_id), "player_id": str(player_id), "reference": reference}
        if server_id: body["server_id"] = str(server_id)
        return self._request("POST", "/orders", json=body)

    def order_status(self, order_code): return self._request("GET", f"/orders/{order_code}")


client = KhmerTopUp()


def parse_player(raw):
    """'12345678 (1234)' -> ('12345678', '1234'); '12345678' -> ('12345678', None)"""
    raw = str(raw).strip()
    m = re.fullmatch(r"(\d+)\s*[\(\s,:/\-]\s*(\d+)\)?", raw)
    return (m.group(1), m.group(2)) if m else (raw, None)


def package_id(code):
    if code in PACKAGE_IDS:
        return PACKAGE_IDS[code]
    return int(code) if str(code).isdigit() else None


def _map(res, code=None):
    """Supplier response -> ('ok'|'fail'|'pending'|'unknown', note)"""
    st = str(res.get("status", "")).lower()
    code = res.get("order_code") or code
    if st == "completed":
        return "ok", str(code or "")
    if st == "refunded":
        return "fail", "supplier refunded"
    if st in IN_PROGRESS and code:
        return "pending", str(code)
    if st in IN_PROGRESS:
        return "unknown", f"no order_code: {str(res)[:150]}"
    return "unknown", f"status={st}: {str(res)[:150]}"


def supplier_topup(o):
    """Place the order. Returns (result, note); for 'pending', note is the supplier order_code."""
    if DEV_MODE:
        return "ok", "dev"
    if not API_KEY:
        return "unknown", "KHMER_TOPUP_API_KEY not set"
    pid = package_id(o["code"])
    if pid is None:
        return "unknown", f"no package_id for {o['code']} (edit PACKAGE_IDS)"
    player, server = parse_player(o["player_id"])
    try:
        res = client.create_order(pid, player, server, f"ORD{o['id']}")
    except SupplierError as e:
        log.warning("create_order ORD%s failed: %s", o["id"], e)
        return ("fail" if e.definite else "unknown"), str(e)[:200]
    log.info("create_order ORD%s -> %s", o["id"], str(res)[:200])
    return _map(res)


def supplier_status(order_code):
    """Poll an accepted order. Network errors just mean 'still pending'."""
    if DEV_MODE:
        return "ok", "dev"
    try:
        return _map(client.order_status(order_code), order_code)
    except SupplierError as e:
        log.warning("order_status %s: %s", order_code, e)
        return "pending", str(order_code)


if __name__ == "__main__":  # python supplier.py  -> shows balance + games/packages
    try:
        from dotenv import load_dotenv; load_dotenv()
    except ImportError:
        pass
    print("me:", json.dumps(client.me(), ensure_ascii=False, indent=1))
    print("games:", json.dumps(client.games(), ensure_ascii=False, indent=1)[:6000])
