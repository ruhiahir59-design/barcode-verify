"""
VerifyChain — Fake Product Identification System
Real barcode + QR scanning, Open Food Facts API, blockchain verification.
Deploy-ready for Render.com
"""
import hashlib, json, os, requests
from datetime import datetime
from functools import wraps
from urllib.parse import quote

import qrcode
from flask import Flask, render_template, request, url_for, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "verifychain-secret-2024")

ADMIN_USERNAME  = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD  = os.environ.get("ADMIN_PASS", "verify123")

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
DATA_DIR        = os.path.join(BASE_DIR, "data")
BLOCKCHAIN_FILE = os.path.join(DATA_DIR, "blockchain.json")
QR_DIR          = os.path.join(BASE_DIR, "static", "qrcodes")

# ── Storage ──────────────────────────────────────────────────────────────────
def ensure_storage():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(QR_DIR, exist_ok=True)
    if not os.path.exists(BLOCKCHAIN_FILE):
        with open(BLOCKCHAIN_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def read_chain():
    ensure_storage()
    try:
        with open(BLOCKCHAIN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []

def write_chain(chain):
    with open(BLOCKCHAIN_FILE, "w", encoding="utf-8") as f:
        json.dump(chain, f, indent=2)

# ── Hashing ───────────────────────────────────────────────────────────────────
def sha256_block(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

# ── Integrity ─────────────────────────────────────────────────────────────────
def check_chain_integrity(chain):
    results = []
    for i, block in enumerate(chain):
        payload  = {k: v for k, v in block.items() if k != "hash"}
        expected = sha256_block(payload)
        hash_ok  = block.get("hash") == expected
        prev_ok  = (block.get("previous_hash") == "0"*64) if i == 0 \
                   else (block.get("previous_hash") == chain[i-1].get("hash"))
        issues   = []
        if not hash_ok: issues.append("Block hash mismatch — data may have been tampered")
        if not prev_ok: issues.append("Previous hash mismatch — chain link broken")
        results.append({"block": block, "hash_ok": hash_ok, "prev_ok": prev_ok,
                        "valid": hash_ok and prev_ok, "issues": issues})
    return results

# ── Auth ──────────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ── QR ────────────────────────────────────────────────────────────────────────
def verification_url_for_qr(product_id: str) -> str:
    base = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if base:
        return f"{base}/verify/{quote(product_id, safe='')}"
    return url_for("verify_page", product_id=product_id, _external=True)

def make_qr_png(product_id: str) -> str:
    verify_url = verification_url_for_qr(product_id)
    img = qrcode.make(verify_url)
    filename = f"{product_id}.png"
    img.save(os.path.join(QR_DIR, filename))
    return filename

# ── Open Food Facts API ───────────────────────────────────────────────────────
def fetch_product_info(barcode: str) -> dict:
    """Fetch product info from Open Food Facts for real barcodes."""
    try:
        url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
        resp = requests.get(url, timeout=6,
                            headers={"User-Agent": "VerifyChain/1.0"})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == 1:
                p = data.get("product", {})
                return {
                    "found":        True,
                    "name":         p.get("product_name") or p.get("product_name_en") or "Unknown",
                    "brand":        p.get("brands", "Unknown"),
                    "category":     p.get("categories", "").split(",")[0].strip() if p.get("categories") else "Unknown",
                    "country":      p.get("countries", "Unknown"),
                    "quantity":     p.get("quantity", ""),
                    "image":        p.get("image_front_url", ""),
                    "ingredients":  p.get("ingredients_text", "")[:200] if p.get("ingredients_text") else "",
                    "nutriscore":   p.get("nutriscore_grade", "").upper(),
                    "barcode":      barcode,
                }
    except Exception:
        pass
    return {"found": False, "barcode": barcode}

# ════════════════════════════════════════════════════════════════════════════
# ROUTES
# ════════════════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    chain = read_chain()
    return render_template("index.html", total=len(chain),
                           manufacturers=len(set(b.get("manufacturer","") for b in chain)))

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","").strip()
        if u == ADMIN_USERNAME and p == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            session["admin_user"] = u
            return redirect(url_for("admin"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/admin", methods=["GET","POST"])
@login_required
def admin():
    message = error = qr_file = block_info = None
    if request.method == "POST":
        pid  = request.form.get("product_id","").strip()
        name = request.form.get("name","").strip()
        mfg  = request.form.get("manufacturer","").strip()
        if not pid or not name or not mfg:
            error = "Please fill all fields."
        else:
            chain = read_chain()
            if any(b.get("product_id") == pid for b in chain):
                error = "This Product ID is already registered."
            else:
                prev_hash = chain[-1]["hash"] if chain else "0"*64
                body = {
                    "block_number":  len(chain)+1,
                    "product_id":    pid,
                    "name":          name,
                    "manufacturer":  mfg,
                    "timestamp":     datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "previous_hash": prev_hash,
                }
                body["hash"] = sha256_block(body)
                chain.append(body)
                write_chain(chain)
                qr_file    = make_qr_png(pid)
                block_info = body
                message    = "Product added to the chain and QR generated."
    return render_template("admin.html", message=message, error=error,
                           qr_file=qr_file, block_info=block_info)

@app.route("/dashboard")
def dashboard():
    chain = read_chain()
    return render_template("dashboard.html", chain=chain, total=len(chain),
                           manufacturers=len(set(b.get("manufacturer","") for b in chain)),
                           latest=chain[-1] if chain else None)

@app.route("/integrity")
def integrity():
    chain          = read_chain()
    results        = check_chain_integrity(chain)
    all_ok         = all(r["valid"] for r in results)
    tampered_count = sum(1 for r in results if not r["valid"])
    return render_template("integrity.html", results=results, all_ok=all_ok,
                           total=len(results), tampered_count=tampered_count)

@app.route("/scan")
def scan():
    return render_template("scan.html")

# ── Real barcode lookup API endpoint ─────────────────────────────────────────
@app.route("/api/lookup/<barcode>")
def api_lookup(barcode):
    """Called by JS scanner. Returns blockchain + internet product info as JSON."""
    barcode = barcode.strip()
    chain   = read_chain()

    # Check our blockchain
    blockchain_result = next((b for b in chain if b.get("product_id") == barcode), None)

    # Fetch from Open Food Facts
    internet_result = fetch_product_info(barcode)

    return jsonify({
        "barcode":    barcode,
        "blockchain": blockchain_result,
        "internet":   internet_result,
    })

@app.route("/verify/<product_id>")
def verify_page(product_id):
    pid              = product_id.strip()
    chain            = read_chain()
    blockchain_result = next((b for b in chain if b.get("product_id") == pid), None)
    internet_result  = fetch_product_info(pid)
    return render_template("result.html", product_id=pid,
                           genuine=blockchain_result is not None,
                           block=blockchain_result,
                           internet=internet_result)

if __name__ == "__main__":
    ensure_storage()
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
