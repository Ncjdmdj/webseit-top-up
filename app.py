import os, hmac, hashlib, time, sqlite3, logging
from contextlib import contextmanager
from functools import wraps
import requests
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from itsdangerous import URLSafeTimedSerializer, BadSignature
from apscheduler.schedulers.background import BackgroundScheduler
try:
    from dotenv import load_dotenv; load_dotenv()  # must run BEFORE importing khpay
except ImportError:
    pass
import khpay
from supplier import supplier_topup, supplier_status

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("shop")

BOT_TOKEN = os.environ["BOT_TOKEN"]
SECRET = os.environ["SECRET_KEY"]
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}
DB_PATH = os.environ.get("DB_PATH", "shop.db")
SUPPLIER_URL = os.environ.get("SUPPLIER_URL", "")
SUPPLIER_KEY = os.environ.get("SUPPLIER_KEY", "")
DEFAULT_MARGIN = 15.0
DEV_MODE = os.environ.get("DEV_MODE") == "1"  # LOCAL TESTING ONLY, never enable in production

app = Flask(__name__)
CORS(app, origins=os.environ.get("FRONTEND_ORIGIN", "*").split(","))
ser = URLSafeTimedSerializer(SECRET)

# game id -> info; packs = (name, cost USD, supplier product code)
CATALOG = {
    "ml": {"name": "Mobile Legends KH", "emoji": "⚔️", "flag": "🇰🇭", "colors": "#1d3fa8,#6a1b9a",
           "packs": [("86 Diamonds", 1.2, "ML86"), ("172 Diamonds", 2.4, "ML172"), ("257 Diamonds", 3.5, "ML257"), ("706 Diamonds", 9.4, "ML706")]},
    "mlph": {"name": "MobileLegend PH", "emoji": "🏹", "flag": "🇵🇭", "colors": "#0d47a1,#00838f",
             "packs": [("86 Diamonds", 1.15, "MLPH86"), ("172 Diamonds", 2.3, "MLPH172"), ("429 Diamonds", 5.6, "MLPH429")]},
    "ff": {"name": "Free Fire", "emoji": "🔥", "colors": "#bf360c,#f9a825",
           "packs": [("100 Diamonds", 0.9, "FF100"), ("310 Diamonds", 2.7, "FF310"), ("520 Diamonds", 4.4, "FF520"), ("1060 Diamonds", 8.8, "FF1060")]},
    "pubg": {"name": "PUBG Mobile", "emoji": "🎯", "colors": "#5d4037,#827717",
             "packs": [("60 UC", 0.95, "UC60"), ("325 UC", 4.7, "UC325"), ("660 UC", 9.3, "UC660")]},
    "kh": {"name": "ព្រី ភ្លើង kh", "emoji": "💎", "colors": "#0277bd,#1a237e",
           "packs": [("Weekly Pass", 1.5, "KHW"), ("Monthly Pass", 7.2, "KHM")]},
    "tk": {"name": "Ticket Kakura", "emoji": "🎫", "colors": "#880e4f,#4a148c",
           "packs": [("1 Ticket", 1.0, "TK1"), ("5 Tickets", 4.6, "TK5")]},
    "rb": {"name": "Roblox", "emoji": "🧱", "colors": "#37474f,#212121", "maint": True,
           "packs": [("400 Robux", 4.5, "RB400"), ("800 Robux", 8.9, "RB800")]},
}

# ---------- database (money stored as integer cents) ----------
@contextmanager
def db():
    c = sqlite3.connect(DB_PATH, timeout=15)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT, wallet INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS deposits(txn TEXT PRIMARY KEY, user_id INTEGER, cents INTEGER, status TEXT, created INTEGER);
        CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, game_id TEXT, game_name TEXT,
          pack_idx INTEGER, pack_name TEXT, code TEXT, player_id TEXT, price INTEGER, cost INTEGER,
          status TEXT, note TEXT, created INTEGER);
        CREATE TABLE IF NOT EXISTS pricing(k TEXT PRIMARY KEY, v REAL);
        """)
        try:
            c.execute("ALTER TABLE orders ADD COLUMN supplier_code TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists


def getp(c, k, default):
    r = c.execute("SELECT v FROM pricing WHERE k=?", (k,)).fetchone()
    return r["v"] if r else default


def cost_usd(c, gid, i): return getp(c, f"cost:{gid}:{i}", CATALOG[gid]["packs"][i][1])
def margin(c, gid): return getp(c, f"margin:{gid}", DEFAULT_MARGIN)
def sell_cents(c, gid, i): return round(cost_usd(c, gid, i) * (1 + margin(c, gid) / 100) * 100)


def err(msg, code=400):
    return jsonify(error=msg), code


# ---------- auth ----------
def verify_telegram(data):
    data = dict(data)
    h = data.pop("hash", None)
    if not h:
        return False
    s = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    calc = hmac.new(key, s.encode(), hashlib.sha256).hexdigest()
    try:
        fresh = time.time() - int(data.get("auth_date", 0)) < 86400
    except ValueError:
        return False
    return hmac.compare_digest(calc, h) and fresh


def auth_required(f):
    @wraps(f)
    def w(*a, **kw):
        t = request.headers.get("Authorization", "").replace("Bearer ", "")
        try:
            g.uid = ser.loads(t, max_age=30 * 86400)["uid"]
        except (BadSignature, KeyError):
            return err("សូមចូលគណនីឡើងវិញ", 401)
        return f(*a, **kw)
    return w


def admin_required(f):
    @wraps(f)
    @auth_required
    def w(*a, **kw):
        if g.uid not in ADMIN_IDS:
            return err("forbidden", 403)
        return f(*a, **kw)
    return w


def user_json(c, uid):
    u = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return {"id": u["id"], "name": u["name"], "wallet": u["wallet"] / 100, "admin": u["id"] in ADMIN_IDS}


@app.post("/api/auth/telegram")
def auth_telegram():
    d = request.get_json(silent=True) or {}
    if not verify_telegram(d):
        return err("Telegram login មិនត្រឹមត្រូវ", 401)
    uid = int(d["id"])
    name = (d.get("first_name") or d.get("username") or "User")[:60]
    with db() as c:
        c.execute("INSERT INTO users(id,name) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name", (uid, name))
        u = user_json(c, uid)
    return jsonify(token=ser.dumps({"uid": uid}), user=u)


@app.get("/api/me")
@auth_required
def me():
    with db() as c:
        return jsonify(user=user_json(c, g.uid))


# ---------- catalog ----------
@app.get("/api/games")
def games():
    out = []
    with db() as c:
        for gid, gm in CATALOG.items():
            out.append({"id": gid, "name": gm["name"], "emoji": gm["emoji"], "flag": gm.get("flag"),
                        "colors": gm["colors"], "maint": gm.get("maint", False),
                        "packs": [{"name": p[0], "price": sell_cents(c, gid, i) / 100} for i, p in enumerate(gm["packs"])]})
    return jsonify(games=out)


# ---------- wallet / KHQR ----------
def credit(txn):
    """Credit exactly once per transaction (status flip + wallet update in one DB transaction)."""
    with db() as c:
        cur = c.execute("UPDATE deposits SET status='paid' WHERE txn=? AND status='pending'", (txn,))
        if cur.rowcount == 1:
            r = c.execute("SELECT user_id,cents FROM deposits WHERE txn=?", (txn,)).fetchone()
            c.execute("UPDATE users SET wallet=wallet+? WHERE id=?", (r["cents"], r["user_id"]))
            log.info("credited txn=%s user=%s cents=%s", txn, r["user_id"], r["cents"])


@app.post("/api/wallet/khqr")
@auth_required
def khqr():
    try:
        amount = float((request.get_json(silent=True) or {}).get("amount"))
    except (TypeError, ValueError):
        return err("ចំនួនទឹកប្រាក់មិនត្រឹមត្រូវ")
    if not 1 <= amount <= 500:
        return err("ចំនួនត្រូវនៅចន្លោះ $1 ដល់ $500")
    res = khpay.create_khpay_qr(f"DEP{g.uid}-{int(time.time())}", amount)
    if not res["success"]:
        log.warning("khpay failed: %s", res["message"])
        return err("បង្កើត KHQR មិនបាន សូមព្យាយាមម្តងទៀត", 502)
    with db() as c:
        c.execute("INSERT INTO deposits VALUES(?,?,?,?,?)", (res["transaction_id"], g.uid, round(amount * 100), "pending", int(time.time())))
    return jsonify(txn=res["transaction_id"], qr_url=res["qr_url"], payment_url=res["payment_url"])


@app.get("/api/wallet/deposit/<txn>")
@auth_required
def deposit_status(txn):
    with db() as c:
        r = c.execute("SELECT * FROM deposits WHERE txn=? AND user_id=?", (txn, g.uid)).fetchone()
    if not r:
        return err("not found", 404)
    if r["status"] == "pending" and khpay.check_khpay_paid(txn):
        credit(txn)
    with db() as c:
        st = c.execute("SELECT status FROM deposits WHERE txn=?", (txn,)).fetchone()["status"]
        return jsonify(status=st, wallet=user_json(c, g.uid)["wallet"])


# ---------- orders ----------
@app.post("/api/orders")
@auth_required
def create_order():
    d = request.get_json(silent=True) or {}
    gm = CATALOG.get(d.get("game_id"))
    pid = str(d.get("player_id", "")).strip()
    idx = d.get("pack")
    if not gm or gm.get("maint"):
        return err("ហ្គេមនេះមិនអាចទិញបានឥឡូវ")
    if not isinstance(idx, int) or not 0 <= idx < len(gm["packs"]):
        return err("កញ្ចប់មិនត្រឹមត្រូវ")
    if not pid or len(pid) > 40:
        return err("សូមបញ្ចូល User ID")
    gid = d["game_id"]
    with db() as c:
        price = sell_cents(c, gid, idx)  # price always computed on the server
        cost = round(cost_usd(c, gid, idx) * 100)
        cur = c.execute("UPDATE users SET wallet=wallet-? WHERE id=? AND wallet>=?", (price, g.uid, price))
        if cur.rowcount != 1:
            return err("សមតុល្យមិនគ្រប់គ្រាន់", 402)
        p = gm["packs"][idx]
        oid = c.execute("INSERT INTO orders(user_id,game_id,game_name,pack_idx,pack_name,code,player_id,price,cost,status,note,created) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (g.uid, gid, gm["name"], idx, p[0], p[2], pid, price, cost, "pending", "", int(time.time()))).lastrowid
        wallet = user_json(c, g.uid)["wallet"]
    return jsonify(order_id=oid, wallet=wallet)


@app.get("/api/orders")
@auth_required
def my_orders():
    with db() as c:
        rows = c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT 100", (g.uid,)).fetchall()
    return jsonify(orders=[{"id": r["id"], "game": r["game_name"], "pack": r["pack_name"], "player_id": r["player_id"],
                            "price": r["price"] / 100, "status": r["status"], "created": r["created"]} for r in rows])


# ---------- supplier: see supplier.py ----------


def finish(oid, result, note):
    """Apply a supplier result to an order that is currently 'processing'."""
    with db() as c:
        if result == "ok":
            c.execute("UPDATE orders SET status='success',note=? WHERE id=? AND status='processing'", (note, oid))
        elif result == "pending":
            c.execute("UPDATE orders SET supplier_code=? WHERE id=? AND status='processing'", (note, oid))
        elif result == "fail":
            if c.execute("UPDATE orders SET status='failed',note=? WHERE id=? AND status='processing'", (note, oid)).rowcount == 1:
                o = c.execute("SELECT user_id,price FROM orders WHERE id=?", (oid,)).fetchone()
                c.execute("UPDATE users SET wallet=wallet+? WHERE id=?", (o["price"], o["user_id"]))  # refund once
        else:
            c.execute("UPDATE orders SET status='review',note=? WHERE id=? AND status='processing'", (note, oid))


def job_orders():
    with db() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM orders WHERE status='pending' ORDER BY id LIMIT 10")]
    for oid in ids:
        with db() as c:  # claim the order so it is never sent twice
            if c.execute("UPDATE orders SET status='processing' WHERE id=? AND status='pending'", (oid,)).rowcount != 1:
                continue
            o = c.execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
        result, note = supplier_topup(o)
        finish(oid, result, note)


def job_supplier():
    """Poll orders the supplier accepted but has not completed yet."""
    with db() as c:
        rows = c.execute("SELECT id,supplier_code FROM orders WHERE status='processing' AND supplier_code IS NOT NULL ORDER BY id LIMIT 20").fetchall()
    for r in rows:
        result, note = supplier_status(r["supplier_code"])
        if result != "pending":
            finish(r["id"], result, note)


def job_deposits():
    with db() as c:
        rows = c.execute("SELECT txn,created FROM deposits WHERE status='pending'").fetchall()
    for r in rows:
        if khpay.check_khpay_paid(r["txn"]):
            credit(r["txn"])
        elif time.time() - r["created"] > 3600:
            with db() as c:
                c.execute("UPDATE deposits SET status='expired' WHERE txn=? AND status='pending'", (r["txn"],))


# ---------- admin ----------
@app.get("/api/admin/stats")
@admin_required
def stats():
    with db() as c:
        r = c.execute("SELECT COUNT(*) n, COALESCE(SUM(price),0) rev, COALESCE(SUM(price-cost),0) pr FROM orders WHERE status='success'").fetchone()
        review = c.execute("SELECT COUNT(*) n FROM orders WHERE status='review'").fetchone()["n"]
    return jsonify(orders=r["n"], revenue=r["rev"] / 100, profit=r["pr"] / 100, review=review)


@app.get("/api/admin/pricing")
@admin_required
def get_pricing():
    out = []
    with db() as c:
        for gid, gm in CATALOG.items():
            out.append({"id": gid, "name": gm["name"], "emoji": gm["emoji"], "margin": margin(c, gid),
                        "packs": [{"name": p[0], "cost": cost_usd(c, gid, i), "price": sell_cents(c, gid, i) / 100} for i, p in enumerate(gm["packs"])]})
    return jsonify(games=out)


@app.put("/api/admin/pricing")
@admin_required
def set_pricing():
    d = request.get_json(silent=True) or {}
    gid = d.get("game_id")
    if gid not in CATALOG:
        return err("game")
    try:
        with db() as c:
            if "margin" in d:
                m = float(d["margin"])
                if not 0 <= m <= 500:
                    return err("margin 0-500")
                c.execute("INSERT OR REPLACE INTO pricing VALUES(?,?)", (f"margin:{gid}", m))
            if "index" in d and "cost" in d:
                i, v = int(d["index"]), float(d["cost"])
                if not (0 <= i < len(CATALOG[gid]["packs"]) and v >= 0):
                    return err("cost")
                c.execute("INSERT OR REPLACE INTO pricing VALUES(?,?)", (f"cost:{gid}:{i}", v))
    except (TypeError, ValueError):
        return err("invalid number")
    return jsonify(ok=True)

# ---------- dev mode (local testing only) ----------
if DEV_MODE:
    @app.post("/api/dev/login")
    def dev_login():
        admin = bool((request.get_json(silent=True) or {}).get("admin"))
        uid = next(iter(ADMIN_IDS), 1) if admin else 999999
        with db() as c:
            c.execute("INSERT INTO users(id,name) VALUES(?,?) ON CONFLICT(id) DO NOTHING", (uid, "Dev Admin" if admin else "Dev User"))
            u = user_json(c, uid)
        return jsonify(token=ser.dumps({"uid": uid}), user=u)

    @app.post("/api/dev/credit")
    @auth_required
    def dev_credit():
        with db() as c:
            c.execute("UPDATE users SET wallet=wallet+1000 WHERE id=?", (g.uid,))
            return jsonify(wallet=user_json(c, g.uid)["wallet"])


init_db()
if not os.environ.get("NO_SCHEDULER"):
    sch = BackgroundScheduler(timezone="UTC")
    sch.add_job(job_deposits, "interval", seconds=8, max_instances=1)
    sch.add_job(job_orders, "interval", seconds=10, max_instances=1)
    sch.add_job(job_supplier, "interval", seconds=15, max_instances=1)
    sch.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))