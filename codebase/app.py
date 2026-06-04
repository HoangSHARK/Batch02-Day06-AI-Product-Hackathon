"""
FPT Long Châu Clone - Flask Backend
====================================
"""
import os
import json
import re
import httpx
from flask import Flask, request, jsonify, render_template, Response
from dotenv import load_dotenv

# Load .env
load_dotenv()

# ============================================================
# APP CONFIGURATION
# ============================================================
app = Flask(__name__, template_folder="templates", static_folder="static")

LONGCHAU_BASE = "https://nhathuoclongchau.com.vn"
PROXY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ============================================================
# DATA LOADING
# ============================================================
def _load_json(filename):
    path = os.path.join(os.path.dirname(__file__), filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return []

PRODUCTS = _load_json("products.json")
STORES = _load_json("stores.json")


# ============================================================
# GEMINI AI
# ============================================================
GEMINI_AVAILABLE = False
gemini_client = None

try:
    from google import genai
    _api_key = os.environ.get("GEMINI_API_KEY")
    if not _api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")
    gemini_client = genai.Client(api_key=_api_key)
    GEMINI_AVAILABLE = True
    print("✅ Gemini API (google-genai) ready")
except Exception as e:
    print(f"⚠️ Gemini unavailable: {e}")


def call_gemini(system_prompt, user_message, history=None):
    """Call Gemini 2.5 Flash with system prompt, history, and user message."""
    if not GEMINI_AVAILABLE:
        return None
    try:
        # Build contents with history context (only for continuity, not re-answering)
        contents = []
        if history:
            # Use last 6 messages
            recent = history[-6:]
            skip_indices = set()
            # Identify safety warnings, refusals, or blocked queries in history
            for idx, h in enumerate(recent):
                content = h.get("content", "")
                role = h.get("role", "user")
                
                # 1. Skip if user message itself is a blocked query
                if role == "user":
                    blocked, _ = check_safety(content)
                    if blocked:
                        skip_indices.add(idx)
                        # Also skip the following model response if there is one
                        if idx + 1 < len(recent) and recent[idx+1].get("role") == "model":
                            skip_indices.add(idx + 1)
                            
                # 2. Skip if model response contains warning or refusal keywords (case-insensitive)
                if role == "model":
                    content_lower = content.lower()
                    refusal_kws = [
                        "cảnh báo", "ngoài phạm vi", "dược sĩ", "bác sĩ", "y tế", "1800 6928", 
                        "hạn chế", "không thể đưa ra", "không thể tư vấn", "mèo cắn", "chó cắn", 
                        "vắc-xin", "vắc xin", "tiêm ngừa", "bị dại"
                    ]
                    if any(k in content_lower for k in refusal_kws):
                        skip_indices.add(idx)
                        # Also skip the preceding user question that caused this warning/refusal
                        if idx > 0 and recent[idx-1].get("role") == "user":
                            skip_indices.add(idx-1)
            
            for idx, h in enumerate(recent):
                if idx in skip_indices:
                    continue
                role = h.get("role", "user")
                text = h.get("content", "")
                # Skip if this is the same as current message (avoid double)
                if role == "user" and text.strip() == user_message.strip():
                    continue
                if role == "user":
                    contents.append({"role": "user", "parts": [{"text": text}]})
                else:
                    contents.append({"role": "model", "parts": [{"text": text}]})
        # Add current message with focus instruction
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        # Add focus rule to system prompt
        focused_prompt = system_prompt + "\n\nQUAN TRỌNG: CHỈ trả lời câu hỏi MỚI NHẤT của người dùng. Dùng lịch sử chat chỉ để hiểu ngữ cảnh, KHÔNG lặp lại hay trả lời lại các câu hỏi cũ."

        resp = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config={"system_instruction": focused_prompt, "temperature": 0.7, "max_output_tokens": 1500},
        )
        return resp.text
    except Exception as e:
        print(f"Gemini error: {e}")
        return None

# ============================================================
# HELPERS
# ============================================================
def format_price(price):
    """Format price value safely, returning 'Liên hệ' if null or invalid."""
    if price is None:
        return "Liên hệ"
    try:
        if isinstance(price, str):
            if not price.strip() or price.lower() == "null":
                return "Liên hệ"
            price = float(price.replace(",", "").replace(".", "").replace("đ", "").strip())
        return f"{int(price):,}đ"
    except Exception:
        return "Liên hệ"


def find_products(query, category=None, max_results=5):
    """Search products by keyword scoring."""
    q = query.lower()
    scored = []
    for p in PRODUCTS:
        if category and p.get("category") != category:
            continue
        score = 0
        name = p.get("name", "").lower()
        if q in name:          score += 10
        if q in p.get("brand", "").lower():       score += 5
        if q in p.get("ingredients", "").lower():  score += 3
        if q in p.get("uses", "").lower():         score += 2
        for w in q.split():
            if len(w) > 2 and w in name:           score += 2
        if score > 0:
            scored.append((p, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in scored[:max_results]]


def find_stores(query):
    """Find stores by district / keyword."""
    q = query.lower()
    districts = ["cầu giấy", "đống đa", "hai bà trưng", "thanh xuân", "quận 1", "quận 3", "phú nhuận", "bình thạnh"]
    found = next((d for d in districts if d in q), None)
    matches = []
    for s in STORES:
        if found and found in s.get("district", "").lower():
            matches.append(s)
        elif not found and (q in s.get("address", "").lower() or q in s.get("name", "").lower()):
            matches.append(s)
    return matches[:3], found


def check_safety(message):
    """Return (is_blocked, reason) for prescription / diagnostic queries."""
    msg = message.lower()
    rx_kws = ["ciprofloxacin", "amoxicillin", "isotretinoin", "clindamycin",
              "kháng sinh", "kê đơn", "đặc trị", "thuốc ngủ", "thuốc tránh thai khẩn cấp", "steroid", "cortico"]
    diag_kws = ["đau bụng uống gì", "sốt phát ban", "sốt cao", "triệu chứng bệnh",
                "chẩn đoán bệnh", "kê đơn thuốc", "nhiễm trùng", "ho ra máu", "đi ngoài ra máu",
                "mèo cắn", "chó cắn", "chuột cắn", "rắn cắn", "bị cắn", "tiêm dại", "vắc xin dại", "vắc-xin dại", "tiêm ngừa dại"]
    for kw in rx_kws:
        if kw in msg:
            return True, kw
    for kw in diag_kws:
        if kw in msg:
            return True, kw
    return False, ""


def fetch_live_product(slug):
    """Fetch full product data from Long Chau via __NEXT_DATA__."""
    try:
        url = f"{LONGCHAU_BASE}/{slug}"
        r = httpx.get(url, headers=PROXY_HEADERS, timeout=15, follow_redirects=True)
        if r.status_code != 200:
            return None
        m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', r.text, re.DOTALL)
        if not m:
            return None
        pp = json.loads(m.group(1)).get("props", {}).get("pageProps", {}).get("product", {})
        if not pp:
            return None

        prices = pp.get("prices", [])
        ings = pp.get("ingredient", [])
        ing_names = list({i["name"] for i in ings if i.get("name")}) if isinstance(ings, list) else []

        # Also extract content (long description sections from the page)
        content = json.loads(m.group(1)).get("props", {}).get("pageProps", {}).get("content", {})

        return {
            "name": pp.get("webName") or pp.get("name", ""),
            "slug": pp.get("slug", slug),
            "price": prices[0].get("price", 0) if prices else 0,
            "unit": prices[0].get("measureUnitName", "Hộp") if prices else "Hộp",
            "specs": prices[0].get("productSpecs", "") if prices else "",
            "brand": pp["brand"].get("name", "") if isinstance(pp.get("brand"), dict) else str(pp.get("brand", "")),
            "brandOrigin": pp.get("brandOrigin", ""),
            "producer": pp.get("producer", ""),
            "categories": [c.get("name", "") for c in pp.get("categories", [])],
            "category": pp["categories"][-1]["name"] if pp.get("categories") else "",
            "ingredients": ", ".join(ing_names[:15]),
            "shortDescription": pp.get("shortDescription", ""),
            "description": pp.get("description", ""),
            "usage": pp.get("usage", ""),
            "dosage": pp.get("dosage", ""),
            "indications": pp.get("indications", ""),
            "contraindication": pp.get("contraindication", ""),
            "adverseEffect": pp.get("adverseEffect", ""),
            "warning": pp.get("warning", ""),
            "specification": pp.get("specification", ""),
            "dosageForm": pp.get("dosageForm", ""),
            "is_prescription": bool(pp.get("prescription")),
            "objectUse": pp.get("objectUse", ""),
            "registNum": pp.get("registNum", ""),
            "image": pp.get("primaryImage", {}).get("url", ""),
            "content": content,  # full CMS content blocks
        }
    except Exception as e:
        print(f"Live fetch error: {e}")
        return None

import hashlib

CACHE_DIR = os.path.join(os.path.dirname(__file__), "static_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def get_cached_asset(path):
    try:
        h = hashlib.md5(path.encode("utf-8")).hexdigest()
        cache_path = os.path.join(CACHE_DIR, h)
        meta_path = cache_path + ".meta"
        if os.path.exists(cache_path) and os.path.exists(meta_path):
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            with open(cache_path, "rb") as f:
                content = f.read()
            return content, meta.get("content-type", "application/octet-stream"), meta.get("status", 200)
    except:
        pass
    return None

def save_cached_asset(path, content, content_type, status):
    if status != 200 or not content:
        return
    try:
        h = hashlib.md5(path.encode("utf-8")).hexdigest()
        cache_path = os.path.join(CACHE_DIR, h)
        meta_path = cache_path + ".meta"
        with open(cache_path, "wb") as f:
            f.write(content)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"content-type": content_type, "status": status}, f)
    except Exception as e:
        print(f"Error saving asset cache: {e}")


# ============================================================
# PROXY ROUTES (forward CSS/JS/assets from Long Chau)
# ============================================================
def _proxy(path, method="GET"):
    if method == "GET":
        cached = get_cached_asset(path)
        if cached:
            content, ct, status = cached
            resp = Response(content, status=status, content_type=ct)
            resp.headers["Access-Control-Allow-Origin"] = "*"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
            resp.headers["X-Cache"] = "HIT"
            return resp

    try:
        url = f"{LONGCHAU_BASE}/{path}"
        if method == "POST":
            r = httpx.post(url, headers=PROXY_HEADERS, timeout=15, follow_redirects=True)
        else:
            r = httpx.get(url, headers=PROXY_HEADERS, timeout=20, follow_redirects=True)
        ct = r.headers.get("content-type", "application/octet-stream")
        content = r.content

        # Rewrite absolute Long Chau URLs to relative in CSS/JS/HTML files
        if any(x in ct for x in ["css", "javascript", "text"]) or path.endswith((".css", ".js")):
            text = content.decode("utf-8", errors="ignore")
            text = text.replace("https://nhathuoclongchau.com.vn/", "/")
            text = text.replace("https://nhathuoclongchau.com.vn", "")
            text = text.replace("http://nhathuoclongchau.com.vn/", "/")
            text = text.replace("http://nhathuoclongchau.com.vn", "")
            content = text.encode("utf-8")

        if method == "GET" and r.status_code == 200:
            save_cached_asset(path, content, ct, r.status_code)

        resp = Response(content, status=r.status_code, content_type=ct)
        # Add CORS headers to all proxy responses
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["X-Cache"] = "MISS"
        return resp
    except Exception as e:
        print(f"Proxy error for {path}: {e}")
        return Response("", status=502)

@app.route("/_next/<path:p>")
def proxy_next(p):     return _proxy(f"_next/{p}")

@app.route("/cdn-cgi/<path:p>", methods=["GET", "POST"])
def proxy_cdn(p):      return _proxy(f"cdn-cgi/{p}", method=request.method)

@app.route("/script/<path:p>")
def proxy_script(p):   return _proxy(f"script/{p}")

@app.route("/estore-images/<path:p>")
def proxy_images(p):   return _proxy(f"estore-images/{p}")

@app.route("/favicon.ico")
def favicon():         return _proxy("favicon.ico?v=3")

# ============================================================
# PAGE ROUTES
# ============================================================
@app.route("/")
def home():
    return render_template("index.html")


def save_products_db():
    """Save PRODUCTS list back to products.json."""
    try:
        path = os.path.join(os.path.dirname(__file__), "products.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(PRODUCTS, f, ensure_ascii=False, indent=2)
        print("💾 Saved updated products database to products.json")
    except Exception as e:
        print(f"Error saving products database: {e}")


@app.route("/product/<path:slug>")
def product_page(slug):
    """Full product detail page with live data + AI chat panel."""
    # Fix spaces in slug
    slug = slug.replace(" ", "-")
    
    # 1. Look in local database PRODUCTS first
    local_prod = None
    for p in PRODUCTS:
        if p.get("slug", "") == slug or slug in p.get("slug", ""):
            local_prod = p
            break
            
    # If we have local product AND it already has detailed data (e.g., description or producer)
    if local_prod and (local_prod.get("description") or local_prod.get("producer") or local_prod.get("dosageForm")):
        print(f"⚡ Cache Hit: Loaded details for {slug} from local database")
        return render_template("product_detail.html", product=local_prod)
        
    # 2. Cache miss: Fetch live product details from network
    print(f"🌐 Cache Miss: Fetching live details for {slug} from network")
    product = fetch_live_product(slug)
    
    if product:
        # Update local PRODUCTS list in-memory & save back to products.json
        if local_prod:
            local_prod.update(product)
        else:
            PRODUCTS.append(product)
        save_products_db()
    else:
        # Fallback to whatever basic data we have locally
        product = local_prod or {"name": slug, "slug": slug}
        
    return render_template("product_detail.html", product=product)


# Catch-all: redirect direct product URLs (e.g. /thuoc/xxx.html) to /product/
@app.route("/<path:slug>")
def catch_all(slug):
    """Catch direct product URLs and redirect to /product/ route."""
    if slug.endswith(".html"):
        slug = slug.replace(" ", "-")
        return product_page(slug)
    # For non-product URLs, return 404
    return Response("Not Found", status=404)
# ============================================================
# REST API ROUTES
# ============================================================
@app.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(PRODUCTS[:24])
    results = [p for p in PRODUCTS
               if q.lower() in p.get("name","").lower()
               or q.lower() in p.get("brand","").lower()
               or q.lower() in p.get("category","").lower()
               or q.lower() in p.get("ingredients","").lower()
               or q.lower() in p.get("uses","").lower()]
    return jsonify(results[:50])


@app.route("/api/stores")
def api_stores():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(STORES)
    results = [s for s in STORES
               if q.lower() in s.get("name","").lower()
               or q.lower() in s.get("address","").lower()
               or q.lower() in s.get("district","").lower()]
    return jsonify(results)


@app.route("/api/product-detail")
def api_product_detail():
    slug = request.args.get("slug", "").strip()
    if not slug:
        return jsonify({"error": "Missing slug"}), 400
    data = fetch_live_product(slug)
    return jsonify(data) if data else (jsonify({"error": "Not found"}), 404)

# ============================================================
# AI CHAT API
# ============================================================
SAFETY_MSG = "⚠️ **CẢNH BÁO Y TẾ:** Câu hỏi liên quan đến thuốc kê đơn hoặc chẩn đoán y tế. Vui lòng liên hệ **Dược sĩ Long Châu** qua hotline **1800 6928**."

@app.route("/api/product-chat", methods=["POST"])
def api_product_chat():
    """AI chat about a specific product (product detail page)."""
    data = request.json or {}
    message = data.get("message", "").strip()
    product_info = data.get("product", {})
    history = data.get("history", [])  # [{role: "user"/"bot", content: "..."}]
    if not message:
        return jsonify({"error": "Empty message"}), 400

    # 1. Block if product category is "Thuốc"
    category = product_info.get("category", "")
    is_rx = product_info.get("is_prescription", False)
    if category == "Thuốc" or is_rx:
        return jsonify({"status": "blocked", "message": SAFETY_MSG, "action": "handover"})

    # 2. Block if message violates safety check
    blocked, _ = check_safety(message)
    if blocked:
        return jsonify({"status": "blocked", "message": SAFETY_MSG, "action": "handover"})

    if GEMINI_AVAILABLE:
        try:
            # Build comprehensive context from ALL product data
            field_map = {
                "Tên": ["name"],
                "Giá": [],  # handled separately
                "Thương hiệu": ["brand"],
                "Danh mục": ["category"],
                "Thành phần": ["ingredients", "ingredient"],
                "Công dụng": ["uses", "indications", "indication", "effect"],
                "Cách dùng": ["usage", "dosage", "howToUse"],
                "Liều dùng": ["dosage"],
                "Chống chỉ định": ["contraindication", "contraindications"],
                "Tác dụng phụ": ["adverseEffect", "sideEffect", "sideEffects"],
                "Cảnh báo": ["warning", "warnings", "precaution", "precautions"],
                "Đối tượng sử dụng": ["objectUse", "targetUser"],
                "Quy cách": ["specs", "specification", "packagingSize"],
                "Xuất xứ": ["brandOrigin", "origin"],
                "Nhà sản xuất": ["producer", "manufacturer"],
                "Bảo quản": ["preservation", "storage"],
                "Mô tả": ["description", "shortDescription"],
            }
            ctx_parts = []
            for label, keys in field_map.items():
                for key in keys:
                    val = product_info.get(key)
                    if val and str(val).strip():
                        ctx_parts.append(f"- {label}: {val}")
                        break
            # Add price manually
            price = product_info.get("price")
            unit = product_info.get("unit", "")
            ctx_parts.append(f"- Giá: {format_price(price)} / {unit or 'Hộp'}")

            # Also grab nested content fields
            content = product_info.get("content", {})
            if isinstance(content, dict):
                for ckey, cval in content.items():
                    if cval and isinstance(cval, str) and len(cval) > 10:
                        clean_key = ckey.replace("_", " ").title()
                        if clean_key.lower() not in ["seo", "approver", "notecate"]:
                            ctx_parts.append(f"- {clean_key}: {cval[:500]}")

            ctx = "\n".join(ctx_parts) if ctx_parts else "Không có thông tin sản phẩm"

            related = find_products(product_info.get("name", "") or message, max_results=3)
            rel_ctx = "\n".join(f"- {r['name']} | {format_price(r.get('price'))}/{r.get('unit', 'Hộp')}" for r in related)

            sys_prompt = (
                "Bạn là NEO - Trợ lý AI Nhà thuốc FPT Long Châu.\n"
                "Người dùng đang xem sản phẩm bên dưới và hỏi về nó.\n\n"
                "QUY TẮC:\n"
                "1. Trả lời dựa trên THÔNG TIN SẢN PHẨM bên dưới. Nếu thông tin CÓ trong data → trả lời chính xác.\n"
                "2. Trả lời ngắn gọn, chính xác, tiếng Việt.\n"
                "3. KHÔNG kê đơn thuốc, KHÔNG chẩn đoán bệnh.\n"
                "4. Nếu câu hỏi KHÔNG liên quan đến sản phẩm → từ chối lịch sự.\n"
                "5. Chỉ khi thông tin THỰC SỰ KHÔNG CÓ trong data → nói 'Thông tin này chưa có. Vui lòng liên hệ 1800 6928.'\n\n"
                f"THÔNG TIN SẢN PHẨM:\n{ctx}\n\nSẢN PHẨM TƯƠNG TỰ:\n{rel_ctx}"
            )
            ai = call_gemini(sys_prompt, message, history)
            matched_products = []
            if ai:
                for p in PRODUCTS:
                    if p.get("name", "") in ai:
                        matched_products.append(p)
                if "[HANDOVER]" in ai:
                    return jsonify({"status": "blocked", "message": ai.replace("[HANDOVER]", "").strip(), "action": "handover", "products": matched_products})
                return jsonify({"status": "success", "message": ai, "products": matched_products})
        except Exception as e:
            print(f"Product chat error: {e}")

    return jsonify({"status": "success", "message": f"Cảm ơn bạn! Gọi **1800 6928** để Dược sĩ tư vấn chi tiết nhé.", "products": []})


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """General AI chatbot (homepage)."""
    data = request.json or {}
    message = data.get("message", "").strip()
    history = data.get("history", [])  # [{role: "user"/"bot", content: "..."}]
    if not message:
        return jsonify({"error": "Empty message"}), 400

    # Safety guardrail
    blocked, _ = check_safety(message)
    if blocked:
        return jsonify({"status": "blocked", "message": SAFETY_MSG, "action": "handover"})

    # Try Gemini
    if GEMINI_AVAILABLE:
        try:
            prods = find_products(message, max_results=5)

            # If user asks about a specific medicine, block and handover
            is_asking_about_medicine = False
            for p in prods:
                if p.get("category") == "Thuốc" and p.get("name", "").lower() in message.lower():
                    is_asking_about_medicine = True
                    break

            if is_asking_about_medicine:
                return jsonify({"status": "blocked", "message": SAFETY_MSG, "action": "handover"})

            stores, _ = find_stores(message)
            prod_ctx = "\n".join(f"- {p['name']} | {format_price(p.get('price'))}/{p.get('unit', 'Hộp')} | {p.get('brand', '')}" for p in prods)
            store_ctx = "\n".join(f"- {s['name']} | {s['address']} | {s['phone']}" for s in stores)

            sys_prompt = (
                "Bạn là NEO - Trợ lý AI Nhà thuốc FPT Long Châu.\n\n"
                "PHẠM VI HỖ TRỢ (CHỈ trả lời trong phạm vi này):\n"
                "- Tư vấn và gợi ý các sản phẩm thuộc danh mục Dược mỹ phẩm, Thực phẩm chức năng, Chăm sóc cá nhân (như sữa rửa mặt, kem chống nắng, vitamin, collagen, tắm gội em bé...) CÓ trong danh sách bên dưới.\n"
                "- Tìm nhà thuốc Long Châu gần nhất.\n"
                "- FAQ: chính sách đổi trả, tích điểm, hotline tổng đài.\n\n"
                "QUY TẮC BẮT BUỘC:\n"
                "1. CHỈ tư vấn và gợi ý các sản phẩm CÓ TRONG danh sách bên dưới. KHÔNG bịa đặt sản phẩm.\n"
                "2. Trả lời NGẮN GỌN, thân thiện, súc tích (tối đa 5-6 dòng), ghi rõ tên sản phẩm + giá bán.\n"
                "3. KHÔNG kê đơn thuốc, KHÔNG chẩn đoán bệnh lý y khoa lâm sàng.\n"
                "4. Được phép hướng dẫn cách sử dụng và công dụng của các sản phẩm skincare/vitamin/TPCN/tắm gội bé.\n"
                "5. Đối với sữa công thức / sữa bột cho trẻ em (baby milk/formula): Hệ thống hiện không kinh doanh mặt hàng này trong danh mục. Hãy lịch sự thông báo cho khách hàng và gợi ý các sản phẩm tắm gội chăm sóc bé hiện có trong danh sách (như sữa tắm gội Lactacyd Baby, Cetaphil Baby, Bimunica...). KHÔNG coi đây là câu hỏi y tế phức tạp và KHÔNG thêm thẻ [HANDOVER] cho câu hỏi về sữa công thức.\n"
                "6. Nếu câu hỏi về sản phẩm thuộc danh mục \"Thuốc\" (Medicines) hoặc câu hỏi y tế lâm sàng phức tạp (bệnh lý, kê đơn) → từ chối lịch sự và thêm thẻ [HANDOVER] vào cuối câu trả lời.\n"
                "7. Nếu câu hỏi hoàn toàn NGOÀI phạm vi (thời tiết, ca nhạc, tin tức...) → từ chối lịch sự: 'Câu hỏi này nằm ngoài phạm vi tư vấn của NEO. Vui lòng liên hệ Dược sĩ qua hotline 1800 6928 để được hỗ trợ.'\n\n"
                f"SẢN PHẨM HIỆN CÓ:\n{prod_ctx}\n\nCỬA HÀNG:\n{store_ctx}"
            )
            ai = call_gemini(sys_prompt, message, history)
            print(f"🤖 Chatbot response: {ai}", flush=True)
            matched_products = []
            if ai:
                for p in PRODUCTS:
                    if p.get("name", "") in ai:
                        matched_products.append(p)
                        if len(matched_products) >= 3:
                            break
                if "[HANDOVER]" in ai:
                    return jsonify({"status": "blocked", "message": ai.replace("[HANDOVER]", "").strip(), "action": "handover", "products": matched_products})
                return jsonify({"status": "success", "message": ai, "products": matched_products})
        except Exception as e:
            print(f"Chat error: {e}")

    # Local NLU fallback
    msg = message.lower()

    # Store locator
    stores, district = find_stores(message)
    store_kws = ["cửa hàng", "nhà thuốc", "địa chỉ", "ở đâu", "gần đây", "chi nhánh"]
    if any(k in msg for k in store_kws) or stores:
        if stores:
            lines = [f"{i}. **{s['name']}**\n   📍 {s['address']}\n   ⏰ {s['hours']}\n   📞 {s['phone']}" for i, s in enumerate(stores, 1)]
            return jsonify({"status": "success", "message": f"Nhà thuốc gần bạn:\n\n" + "\n\n".join(lines)})
        return jsonify({"status": "success", "message": "Vui lòng cho biết **Quận/Huyện** để NEO tìm nhà thuốc nhé!"})

    # Skincare
    skin_kws = ["sữa rửa mặt", "kem chống nắng", "skincare", "da dầu", "da mụn", "nhạy cảm", "collagen", "dưỡng da", "trị mụn"]
    if any(k in msg for k in skin_kws):
        prods = find_products(message, category="Dược mỹ phẩm") or find_products(message)
        if prods:
            lines = [f"📦 **{p['name']}**\n   • Giá: **{format_price(p.get('price'))}** / {p.get('unit', 'Hộp')}\n   • Công dụng: {p.get('uses', '')}" for p in prods[:3]]
            return jsonify({"status": "success", "message": "Gợi ý cho bạn:\n\n" + "\n\n".join(lines), "products": prods[:3]})

    # FAQ
    faqs = [
        (["đổi trả", "trả hàng"], "Đổi trả trong **30 ngày** với sản phẩm còn nguyên bao bì."),
        (["tích điểm", "thành viên"], "10.000đ = 1 điểm, quy đổi voucher trên app Long Châu."),
        (["hotline", "tổng đài", "liên hệ"], "📞 Tổng đài: **1800 6928** (miễn phí)\n📧 cskh@nhathuoclongchau.com.vn"),
    ]
    for patterns, reply in faqs:
        if any(p in msg for p in patterns):
            return jsonify({"status": "success", "message": reply})

    # Default
    return jsonify({"status": "success", "message": (
        "Chào bạn! Tôi là **NEO** 🌟\n\n"
        "1. **Tư vấn sản phẩm:** skincare, vitamin, collagen...\n"
        "2. **Tìm nhà thuốc:** nhập quận/huyện\n"
        "3. **FAQ:** đổi trả, tích điểm, hotline\n\n"
        "Hãy hỏi tôi nhé!"
    )})

# ============================================================
# FEEDBACK API
# ============================================================
FEEDBACK_FILE = os.path.join(os.path.dirname(__file__), "feedback_log.json")

@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    """Save user feedback when AI answers incorrectly."""
    data = request.json or {}
    feedback_type = data.get("type", "negative")  # "positive" or "negative"
    user_message = data.get("user_message", "")
    bot_response = data.get("bot_response", "")
    page = data.get("page", "homepage")
    product_name = data.get("product_name", "")
    user_comment = data.get("comment", "")

    if not user_message and not bot_response:
        return jsonify({"error": "No data"}), 400

    from datetime import datetime
    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": feedback_type,
        "page": page,
        "product": product_name,
        "user_message": user_message,
        "bot_response": bot_response,
        "user_comment": user_comment,
    }

    # Load existing feedback
    feedbacks = []
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                feedbacks = json.load(f)
        except:
            feedbacks = []

    feedbacks.append(entry)

    # Save
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(feedbacks, f, ensure_ascii=False, indent=2)

    print(f"📝 Feedback [{feedback_type}]: {user_message[:50]}...")
    return jsonify({"status": "saved", "total_feedbacks": len(feedbacks)})

# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    print(f"📦 {len(PRODUCTS)} products | 🏪 {len(STORES)} stores loaded")
    app.run(host="0.0.0.0", port=5000, debug=True)

