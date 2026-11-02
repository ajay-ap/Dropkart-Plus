from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import sqlite3
import uuid
import random
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
# Allow up to 60MB payload for multiple product images and review videos
app.config['MAX_CONTENT_LENGTH'] = 60 * 1024 * 1024
CORS(app)

DB_FILE = 'dropkart_enterprise_v5.db'

DEFAULT_SMTP_GMAIL = ""      # e.g. "ajayprajapati78308@gmail.com"
DEFAULT_SMTP_APP_PASS = ""   # e.g. "abcd efgh ijkl mnop"


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def get_config_dict(conn):
    rows = conn.execute("SELECT config_key, config_val FROM platform_config").fetchall()
    return {r['config_key']: r['config_val'] for r in rows}


def send_email_notification(to_email, subject, html_body, plain_otp=None):
    conn = get_db_connection()
    cfg = get_config_dict(conn)
    conn.close()

    smtp_user = (cfg.get('smtp_gmail_user') or DEFAULT_SMTP_GMAIL or '').strip()
    smtp_pass = (cfg.get('smtp_gmail_pass') or DEFAULT_SMTP_APP_PASS or '').replace(" ", "").strip()

    print("\n" + "=" * 70)
    print(f"📧 EMAIL TO      : {to_email}")
    print(f"📌 SUBJECT       : {subject}")
    if plain_otp:
        print(f"🔐 GENERATED OTP : {plain_otp}")
    print("=" * 70 + "\n")

    if not smtp_user or not smtp_pass:
        return False, "Simulated Mode (Add Gmail & 16-char App Password in Admin Tab 6 for real Gmail inbox delivery)"

    try:
        msg = MIMEMultipart()
        msg['From'] = f"DropKart Plus <{smtp_user}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=12)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True, f"Sent to {to_email} via Gmail SMTP"
    except Exception as e:
        print("❌ Gmail SMTP Error:", str(e))
        return False, f"SMTP Error: {str(e)}"


def init_db():
    conn = get_db_connection()

    # 1. Users Table (Supports Customer & Delivery Agent registration)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            mobile TEXT UNIQUE NOT NULL,
            email TEXT DEFAULT '',
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'Customer',
            saved_pincode TEXT DEFAULT '400612',
            saved_address TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Persistent User Carts Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS user_carts (
            user_id TEXT PRIMARY KEY,
            cart_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 3. Shops Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS shops (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            city TEXT NOT NULL,
            pincode TEXT NOT NULL,
            gstin TEXT NOT NULL,
            upi_id TEXT DEFAULT '8689863793@fam',
            fee_utr TEXT NOT NULL,
            fee_paid_paise INTEGER DEFAULT 2500,
            kyc_status TEXT DEFAULT 'PENDING_APPROVAL',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 4. Products Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            shop_id TEXT NOT NULL,
            owner_id TEXT DEFAULT 'u_admin',
            title TEXT NOT NULL,
            brand TEXT NOT NULL,
            category TEXT NOT NULL,
            price_paise INTEGER NOT NULL,
            mrp_paise INTEGER NOT NULL,
            images_json TEXT NOT NULL,
            mod_status TEXT DEFAULT 'APPROVED',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 5. Product Reviews Table (Star rating + multiple images & videos)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS product_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            reviewer_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT NOT NULL,
            media_json TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 6. Orders Table (Includes Delivery Boy Issue Photo Upload & Admin Return Processing)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            tracking_no TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            customer_mobile TEXT NOT NULL,
            buyer_email TEXT NOT NULL,
            delivery_address TEXT NOT NULL,
            buyer_pincode TEXT NOT NULL,
            seller_pincode TEXT NOT NULL,
            shop_id TEXT DEFAULT 'shop_1',
            items_json TEXT NOT NULL,
            subtotal_paise INTEGER NOT NULL,
            delivery_fee_paise INTEGER NOT NULL,
            total_paise INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            utr_reference TEXT NOT NULL,
            order_status TEXT DEFAULT 'PENDING_UTR',
            delivery_otp TEXT DEFAULT '',
            delivery_agent_id TEXT DEFAULT '',
            delivery_agent_name TEXT DEFAULT '',
            vendor_payout_status TEXT DEFAULT 'UNSETTLED',
            issue_status TEXT DEFAULT 'NONE',
            issue_note TEXT DEFAULT '',
            issue_image TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 7. Double-Entry Ledger Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ledger_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference_id TEXT NOT NULL,
            account_name TEXT NOT NULL,
            debit_paise INTEGER DEFAULT 0,
            credit_paise INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 8. Customer Grievances Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS grievances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_no TEXT UNIQUE NOT NULL,
            user_id TEXT DEFAULT '',
            tracking_no TEXT NOT NULL,
            customer_name TEXT NOT NULL,
            issue_text TEXT NOT NULL,
            status TEXT DEFAULT 'OPEN',
            admin_remark TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 9. Platform Config Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS platform_config (
            config_key TEXT PRIMARY KEY,
            config_val TEXT NOT NULL
        )
    ''')

    # 10. Email OTP Table
    conn.execute('''
        CREATE TABLE IF NOT EXISTS email_otps (
            email TEXT PRIMARY KEY,
            otp_code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Seed Default Accounts
    conn.execute('''
        INSERT OR IGNORE INTO users (id, full_name, username, mobile, email, password_hash, role, saved_pincode, saved_address)
        VALUES ('u_admin', 'Ajay Prajapati (Admin)', 'admin', '8689863793', 'ajayprajapati78308@gmail.com', 'ajay@#1234', 'Super admin', '400612', 'Diva East, Thane - 400612')
    ''')
    conn.execute('''
        INSERT OR IGNORE INTO users (id, full_name, username, mobile, email, password_hash, role, saved_pincode, saved_address)
        VALUES ('u_delivery', 'Ramesh Kumar (Delivery Boy)', 'delivery', '9876543210', 'delivery@dropkart.pro', '123456', 'Delivery Agent', '400612', 'Thane Logistics Hub')
    ''')

    default_configs = [
        ('local_shipping_paise', '3000'),
        ('regional_shipping_paise', '5000'),
        ('national_shipping_paise', '9000'),
        ('commission_pct', '10'),
        ('shop_fee_paise', '2500'),
        ('smtp_gmail_user', DEFAULT_SMTP_GMAIL),
        ('smtp_gmail_pass', DEFAULT_SMTP_APP_PASS)
    ]
    for k, v in default_configs:
        conn.execute("INSERT OR IGNORE INTO platform_config (config_key, config_val) VALUES (?, ?)", (k, str(v)))

    # Seed Demo Verified Shops
    conn.execute('''
        INSERT OR IGNORE INTO shops (id, owner_id, name, category, city, pincode, gstin, upi_id, fee_utr, fee_paid_paise, kyc_status)
        VALUES ('shop_1', 'u_system_1', 'TechZone Official', 'Electronics', 'Mumbai', '400001', '27AABCT1122F1Z5', '8689863793@fam', 'INIT_FEE_001', 2500, 'VERIFIED')
    ''')
    conn.execute('''
        INSERT OR IGNORE INTO shops (id, owner_id, name, category, city, pincode, gstin, upi_id, fee_utr, fee_paid_paise, kyc_status)
        VALUES ('shop_2', 'u_system_2', 'UrbanWeave Studio', 'Fashion', 'Thane', '400612', '27AABCU3344F1Z2', '8689863793@fam', 'INIT_FEE_002', 2500, 'VERIFIED')
    ''')
    conn.execute('''
        INSERT OR IGNORE INTO shops (id, owner_id, name, category, city, pincode, gstin, upi_id, fee_utr, fee_paid_paise, kyc_status)
        VALUES ('shop_3', 'u_system_3', 'Lumen Smart Home', 'Workspace', 'Pune', '411001', '27AABCL5566F1Z9', '8689863793@fam', 'INIT_FEE_003', 2500, 'VERIFIED')
    ''')

    # Seed Demo Products
    default_products = [
        (
            'p_101', 'shop_1', 'u_system_1',
            'AeroPods Pro ANC Wireless Earbuds (42dB Active Noise Cancellation)',
            'AeroAcoustics', 'Electronics', 189900, 299900,
            json.dumps([
                'https://images.unsplash.com/photo-1590658268037-6bf12165a8df?auto=format&fit=crop&w=700&q=80',
                'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=700&q=80'
            ]),
            'APPROVED'
        ),
        (
            'p_102', 'shop_2', 'u_system_2',
            'Oversized Heavyweight Streetwear Cargo Jacket (380 GSM)',
            'UrbanWeave', 'Fashion', 225000, 349900,
            json.dumps([
                'https://images.unsplash.com/photo-1551028719-00167b16eac5?auto=format&fit=crop&w=700&q=80',
                'https://images.unsplash.com/photo-1523381210434-271e8be1f52b?auto=format&fit=crop&w=700&q=80'
            ]),
            'APPROVED'
        ),
        (
            'p_103', 'shop_1', 'u_system_1',
            'Mechanical RGB 75% Hot-Swap Wireless Gasket Keyboard',
            'KeyForge', 'Electronics', 349900, 499900,
            json.dumps([
                'https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=700&q=80',
                'https://images.unsplash.com/photo-1511467687858-23d96c32e4ae?auto=format&fit=crop&w=700&q=80'
            ]),
            'APPROVED'
        ),
        (
            'p_104', 'shop_3', 'u_system_3',
            'Anodized Aluminum Ergonomic Laptop Cooling Stand',
            'LumenDesk', 'Workspace', 119900, 199900,
            json.dumps([
                'https://images.unsplash.com/photo-1527864550417-7fd91fc51a46?auto=format&fit=crop&w=700&q=80'
            ]),
            'APPROVED'
        )
    ]
    for pid, sid, oid, title, brand, cat, price, mrp, imgs_json, st in default_products:
        conn.execute('''
            INSERT OR IGNORE INTO products (id, shop_id, owner_id, title, brand, category, price_paise, mrp_paise, images_json, mod_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pid, sid, oid, title, brand, cat, price, mrp, imgs_json, st))

    # Seed Initial Sample Review
    existing_rev = conn.execute("SELECT COUNT(*) as c FROM product_reviews").fetchone()['c']
    if existing_rev == 0:
        conn.execute('''
            INSERT INTO product_reviews (product_id, user_id, reviewer_name, rating, comment, media_json)
            VALUES ('p_101', 'u_admin', 'Tanveer S.', 5, 'Awesome ANC quality and super fast delivery in Thane!', ?)
        ''', (json.dumps([{"type": "image", "url": "https://images.unsplash.com/photo-1590658268037-6bf12165a8df?auto=format&fit=crop&w=400&q=80"}]),))

    conn.commit()
    conn.close()


init_db()


@app.route('/')
def serve_frontend():
    for filename in ['mini v1.3.html', 'mini v1.2.html', 'index.html', 'mini v1.html']:
        if os.path.exists(filename):
            return send_file(filename)
    return "Frontend HTML file not found.", 404


# ==============================================================================
# UNIFIED BOOTSTRAP ENDPOINT (SUPPORTS REAL-TIME POLLING + SAVED USER CART)
# ==============================================================================
@app.route('/api/bootstrap', methods=['GET'])
def api_bootstrap():
    user_id = (request.args.get('user_id') or '').strip()
    role = (request.args.get('role') or 'Guest').strip()

    conn = get_db_connection()
    shops = [dict(r) for r in conn.execute("SELECT * FROM shops ORDER BY created_at ASC").fetchall()]
    products_raw = [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()]
    reviews_raw = [dict(r) for r in conn.execute("SELECT * FROM product_reviews ORDER BY id DESC").fetchall()]
    cfg_raw = get_config_dict(conn)

    config = {
        "local_shipping_paise": int(cfg_raw.get('local_shipping_paise') or 3000),
        "regional_shipping_paise": int(cfg_raw.get('regional_shipping_paise') or 5000),
        "national_shipping_paise": int(cfg_raw.get('national_shipping_paise') or 9000),
        "commission_pct": int(cfg_raw.get('commission_pct') or 10),
        "shop_fee_paise": int(cfg_raw.get('shop_fee_paise') or 2500),
        "smtp_gmail_user": cfg_raw.get('smtp_gmail_user') or '',
        "smtp_configured": bool((cfg_raw.get('smtp_gmail_user') or '').strip() and (cfg_raw.get('smtp_gmail_pass') or '').strip())
    }

    # Group reviews by product_id
    reviews_by_prod = {}
    for rv in reviews_raw:
        try:
            media_list = json.loads(rv['media_json'] or '[]')
        except Exception:
            media_list = []
        reviews_by_prod.setdefault(rv['product_id'], []).append({
            "id": rv['id'],
            "userId": rv['user_id'],
            "reviewerName": rv['reviewer_name'],
            "rating": rv['rating'],
            "comment": rv['comment'],
            "media": media_list,
            "createdAt": rv['created_at']
        })

    products = []
    for p in products_raw:
        try:
            imgs = json.loads(p['images_json'])
        except Exception:
            imgs = ['https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=700&q=80']
        prod_revs = reviews_by_prod.get(p['id'], [])
        products.append({
            "id": p['id'],
            "shopId": p['shop_id'],
            "ownerId": p['owner_id'],
            "title": p['title'],
            "brand": p['brand'],
            "category": p['category'],
            "pricePaise": p['price_paise'],
            "mrpPaise": p['mrp_paise'],
            "images": imgs if imgs else ['https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=700&q=80'],
            "modStatus": p['mod_status'],
            "reviews": prod_revs
        })

    # Load database-persisted cart for this user
    saved_cart = None
    if user_id:
        cart_row = conn.execute("SELECT cart_json FROM user_carts WHERE user_id = ?", (user_id,)).fetchone()
        if cart_row:
            try:
                saved_cart = json.loads(cart_row['cart_json'])
            except Exception:
                saved_cart = []
        else:
            saved_cart = []

    orders = []
    ledger = []
    grievances = []

    if role == 'Super admin':
        orders_raw = conn.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
        ledger = [dict(r) for r in conn.execute("SELECT * FROM ledger_entries ORDER BY id DESC").fetchall()]
        grievances = [dict(r) for r in conn.execute("SELECT * FROM grievances ORDER BY id DESC").fetchall()]
        for r in orders_raw:
            d = dict(r)
            d['items'] = json.loads(d['items_json']) if d['items_json'] else []
            orders.append(d)

    elif role == 'Delivery Agent':
        orders_raw = conn.execute('''
            SELECT * FROM orders
            WHERE order_status IN ('PENDING_PICKUP', 'AGENT_ASSIGNED', 'OUT_FOR_DELIVERY', 'DELIVERED', 'ISSUE_REPORTED', 'RETURN_PROCESSED')
            ORDER BY created_at DESC
        ''').fetchall()
        for r in orders_raw:
            d = dict(r)
            d['items'] = json.loads(d['items_json']) if d['items_json'] else []
            d['delivery_otp'] = ''  # Hidden from Delivery Boy
            orders.append(d)

    elif user_id:
        orders_raw = conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
        grievances = [dict(r) for r in conn.execute("SELECT * FROM grievances WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()]
        for r in orders_raw:
            d = dict(r)
            d['items'] = json.loads(d['items_json']) if d['items_json'] else []
            orders.append(d)

    conn.close()

    return jsonify({
        "shops": shops,
        "products": products,
        "orders": orders,
        "ledger": ledger,
        "grievances": grievances,
        "config": config,
        "saved_cart": saved_cart
    })


# ==============================================================================
# DATABASE-PERSISTED USER CART SYNC ROUTE
# ==============================================================================
@app.route('/api/cart/sync', methods=['POST'])
def sync_user_cart():
    data = request.json
    user_id = (data.get('user_id') or '').strip()
    cart_items = data.get('cart') or []
    if not user_id:
        return jsonify({"success": False}), 400

    conn = get_db_connection()
    conn.execute('''
        INSERT OR REPLACE INTO user_carts (user_id, cart_json, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (user_id, json.dumps(cart_items)))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ==============================================================================
# AUTHENTICATION, DELIVERY BOY SIGNUP & FORGOT/REPLACE PASSWORD
# ==============================================================================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    full_name = (data.get('full_name') or '').strip()
    username = (data.get('username') or '').strip()
    mobile = (data.get('mobile') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    requested_role = (data.get('role') or 'Customer').strip()

    role = 'Delivery Agent' if requested_role == 'Delivery Agent' else 'Customer'

    if not full_name or not username or not mobile or not password:
        return jsonify({"success": False, "error_message": "Name, Username, Mobile, and Password are required."}), 400

    conn = get_db_connection()
    try:
        existing = conn.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?) OR mobile = ? OR (email != '' AND LOWER(email) = LOWER(?))",
            (username, mobile, email)
        ).fetchone()
        if existing:
            return jsonify({"success": False, "error_message": "Username, Mobile, or Email already registered!"}), 400

        user_id = f"u_{uuid.uuid4().hex[:8]}"
        conn.execute('''
            INSERT INTO users (id, full_name, username, mobile, email, password_hash, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, full_name, username, mobile, email, password, role))
        conn.commit()

        new_user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return jsonify({"success": True, "user_data": dict(new_user)})
    finally:
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    identifier = (data.get('username_or_email') or '').strip()
    password = data.get('password') or ''

    conn = get_db_connection()
    user = conn.execute('''
        SELECT * FROM users
        WHERE (LOWER(username) = LOWER(?) OR mobile = ? OR (email != '' AND LOWER(email) = LOWER(?)))
        AND password_hash = ?
    ''', (identifier, identifier, identifier, password)).fetchone()

    saved_cart = []
    if user:
        cart_row = conn.execute("SELECT cart_json FROM user_carts WHERE user_id = ?", (user['id'],)).fetchone()
        if cart_row:
            try:
                saved_cart = json.loads(cart_row['cart_json'])
            except Exception:
                saved_cart = []
    conn.close()

    if user:
        return jsonify({"success": True, "user_data": dict(user), "saved_cart": saved_cart})
    return jsonify({"success": False, "error_message": "Invalid credentials. Check username/mobile/email and password."}), 401


@app.route('/api/auth/replace-password', methods=['POST'])
def replace_password():
    data = request.json
    identifier = (data.get('identifier') or '').strip()
    current_password = data.get('current_password') or ''
    new_password = data.get('new_password') or ''

    if not identifier or not current_password or not new_password:
        return jsonify({"success": False, "error_message": "Please fill in Identifier, Current Password, and New Password."}), 400

    conn = get_db_connection()
    try:
        user = conn.execute('''
            SELECT * FROM users
            WHERE (LOWER(username) = LOWER(?) OR mobile = ? OR (email != '' AND LOWER(email) = LOWER(?)))
        ''', (identifier, identifier, identifier)).fetchone()

        if not user:
            return jsonify({"success": False, "error_message": "Account not found with that Username, Mobile, or Email."}), 404

        if user['password_hash'] != current_password:
            return jsonify({"success": False, "error_message": "Current password does not match!"}), 401

        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_password, user['id']))
        conn.commit()
        return jsonify({"success": True, "message": "Password replaced successfully! You can now log in with your new password."})
    finally:
        conn.close()


@app.route('/api/auth/send-email-otp', methods=['POST'])
def send_email_otp():
    data = request.json
    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({"success": False, "error_message": "Please enter a valid Gmail address."}), 400

    otp_code = str(random.randint(100000, 999999))
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO email_otps (email, otp_code) VALUES (?, ?)", (email, otp_code))
    conn.commit()
    conn.close()

    html_body = f"""
    <div style="font-family:sans-serif; padding:20px; border:1px solid #e5e7eb; border-radius:12px;">
        <h2 style="color:#2874F0;">DropKart Plus — Email Verification OTP</h2>
        <p>Your 6-digit OTP to verify your Gmail address is:</p>
        <h1 style="letter-spacing:4px; background:#F0F5FF; padding:12px 20px; display:inline-block; border-radius:8px;">{otp_code}</h1>
    </div>
    """
    sent_real, mode_msg = send_email_notification(email, f"DropKart Verification OTP: {otp_code}", html_body, plain_otp=otp_code)

    return jsonify({
        "success": True,
        "sent_real_email": sent_real,
        "demo_otp": otp_code,
        "delivery_mode": mode_msg
    })


@app.route('/api/user/verify-and-save-email', methods=['POST'])
def verify_and_save_email():
    data = request.json
    user_id = data.get('user_id')
    email = (data.get('email') or '').strip().lower()
    entered_otp = (data.get('otp') or '').strip()

    conn = get_db_connection()
    try:
        otp_row = conn.execute("SELECT otp_code FROM email_otps WHERE email = ?", (email,)).fetchone()
        if not otp_row or otp_row['otp_code'] != entered_otp:
            return jsonify({"success": False, "error_message": "Incorrect 6-digit Email OTP!"}), 400

        taken = conn.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?) AND id != ?", (email, user_id)).fetchone()
        if taken:
            return jsonify({"success": False, "error_message": "This email is already linked to another user."}), 400

        conn.execute("UPDATE users SET email = ? WHERE id = ?", (email, user_id))
        conn.commit()
        updated_user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return jsonify({"success": True, "user_data": dict(updated_user)})
    finally:
        conn.close()


# ==============================================================================
# PRODUCT REVIEWS WITH STAR RATING, IMAGES & VIDEOS
# ==============================================================================
@app.route('/api/products/review', methods=['POST'])
def add_product_review():
    data = request.json
    product_id = (data.get('product_id') or '').strip()
    user_id = (data.get('user_id') or '').strip()
    reviewer_name = (data.get('reviewer_name') or 'Verified Buyer').strip()
    rating = int(data.get('rating') or 5)
    comment = (data.get('comment') or '').strip()
    media = data.get('media') or []

    if not product_id or not comment:
        return jsonify({"success": False, "error_message": "Please write a review comment."}), 400

    conn = get_db_connection()
    conn.execute('''
        INSERT INTO product_reviews (product_id, user_id, reviewer_name, rating, comment, media_json)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (product_id, user_id, reviewer_name, max(1, min(5, rating)), comment, json.dumps(media)))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ==============================================================================
# SELLER HUB: ₹25 SHOP REGISTRATION & PRODUCT PUBLISHING
# ==============================================================================
@app.route('/api/shops/create', methods=['POST'])
def create_shop():
    data = request.json
    owner_id = (data.get('owner_id') or '').strip()
    name = (data.get('name') or '').strip()
    category = (data.get('category') or 'Electronics').strip()
    city = (data.get('city') or 'Mumbai').strip()
    pincode = (data.get('pincode') or '400001').strip()
    gstin = (data.get('gstin') or '27AABCE1234F1Z5').strip().upper()
    upi_id = (data.get('upi_id') or '8689863793@fam').strip()
    fee_utr = (data.get('fee_utr') or '').strip()

    if not owner_id:
        return jsonify({"success": False, "error_message": "Please login first to register your shop."}), 400
    if len(fee_utr) != 12 or not fee_utr.isdigit():
        return jsonify({"success": False, "error_message": "Valid 12-Digit UTR for the ₹25 Shop Registration Fee is required."}), 400

    conn = get_db_connection()
    try:
        dup_utr = conn.execute("SELECT id FROM shops WHERE fee_utr = ?", (fee_utr,)).fetchone()
        if dup_utr:
            return jsonify({"success": False, "error_message": "This ₹25 UTR has already been used."}), 400

        shop_id = f"shop_{uuid.uuid4().hex[:6]}"
        conn.execute('''
            INSERT INTO shops (id, owner_id, name, category, city, pincode, gstin, upi_id, fee_utr, fee_paid_paise, kyc_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 2500, 'PENDING_APPROVAL')
        ''', (shop_id, owner_id, name, category, city, pincode, gstin, upi_id, fee_utr))

        conn.execute('''
            INSERT INTO ledger_entries (reference_id, account_name, debit_paise, credit_paise)
            VALUES (?, 'Shop_Registration_Fee_Escrow', 2500, 0)
        ''', (shop_id,))
        conn.execute('''
            INSERT INTO ledger_entries (reference_id, account_name, debit_paise, credit_paise)
            VALUES (?, 'Platform_Shop_Onboarding_Revenue', 0, 2500)
        ''', (shop_id,))

        conn.commit()
        new_shop = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
        return jsonify({"success": True, "shop": dict(new_shop)})
    finally:
        conn.close()


@app.route('/api/products/create', methods=['POST'])
def create_product():
    data = request.json
    owner_id = (data.get('owner_id') or '').strip()
    shop_id = (data.get('shop_id') or '').strip()
    title = (data.get('title') or '').strip()
    category = (data.get('category') or '').strip()
    price_paise = int(data.get('price_paise') or 0)
    mrp_paise = int(data.get('mrp_paise') or price_paise)
    images = data.get('images') or []

    if not images:
        images = ['https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=700&q=80']

    conn = get_db_connection()
    try:
        shop = conn.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
        if not shop:
            return jsonify({"success": False, "error_message": "Shop not found."}), 404
        if shop['owner_id'] != owner_id and owner_id != 'u_admin':
            return jsonify({"success": False, "error_message": "You can only upload products to your own verified shop!"}), 403
        if shop['kyc_status'] != 'VERIFIED':
            return jsonify({"success": False, "error_message": f"Your shop '{shop['name']}' is waiting for Admin KYC approval."}), 400

        prod_id = f"p_{uuid.uuid4().hex[:6]}"
        brand = shop['name'].split(' ')[0]
        final_category = category if category else shop['category']

        conn.execute('''
            INSERT INTO products (id, shop_id, owner_id, title, brand, category, price_paise, mrp_paise, images_json, mod_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'APPROVED')
        ''', (prod_id, shop_id, owner_id, title, brand, final_category, price_paise, mrp_paise, json.dumps(images)))
        conn.commit()
        return jsonify({"success": True, "product_id": prod_id})
    finally:
        conn.close()


# ==============================================================================
# CUSTOMER CHECKOUT & GRIEVANCES
# ==============================================================================
@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.json
    user_id = data.get('user_id')
    customer_name = (data.get('customer_name') or '').strip()
    customer_mobile = (data.get('customer_mobile') or '').strip()
    buyer_email = (data.get('buyer_email') or '').strip().lower()
    delivery_address = (data.get('shipping_address') or '').strip()
    buyer_pincode = (data.get('buyer_pincode') or '400612').strip()
    seller_pincode = (data.get('seller_pincode') or '400001').strip()
    shop_id = data.get('shop_id') or 'shop_1'
    items = data.get('items') or []
    subtotal_paise = int(data.get('subtotal_paise') or 0)
    delivery_fee_paise = int(data.get('delivery_fee_paise') or 0)
    total_paise = int(data.get('total_paise') or 0)
    payment_method = (data.get('payment_method') or 'QR').upper()
    utr_id = (data.get('utr_id') or '').strip()

    if not buyer_email or '@' not in buyer_email:
        return jsonify({"success": False, "error_message": "Verified Gmail is mandatory before ordering!"}), 400

    conn = get_db_connection()
    try:
        dup = conn.execute("SELECT id FROM orders WHERE utr_reference = ?", (utr_id,)).fetchone()
        if dup:
            return jsonify({"success": False, "error_message": "Idempotency Block: This 12-digit UTR was already used!"}), 400

        order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
        tracking_no = f"TRK-2026-{random.randint(1000, 9999)}"

        conn.execute('''
            INSERT INTO orders (
                id, tracking_no, user_id, customer_name, customer_mobile, buyer_email,
                delivery_address, buyer_pincode, seller_pincode, shop_id, items_json,
                subtotal_paise, delivery_fee_paise, total_paise,
                payment_method, utr_reference, order_status, delivery_otp, vendor_payout_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_UTR', '', 'UNSETTLED')
        ''', (
            order_id, tracking_no, user_id, customer_name, customer_mobile, buyer_email,
            delivery_address, buyer_pincode, seller_pincode, shop_id, json.dumps(items),
            subtotal_paise, delivery_fee_paise, total_paise,
            payment_method, utr_id
        ))
        # Clear persistent cart in DB if they checked out their cart
        if data.get('clear_cart'):
            conn.execute("INSERT OR REPLACE INTO user_carts (user_id, cart_json) VALUES (?, '[]')", (user_id,))
        conn.commit()
        return jsonify({"success": True, "tracking_number": tracking_no})
    finally:
        conn.close()


@app.route('/api/grievances/create', methods=['POST'])
def create_grievance():
    data = request.json
    user_id = (data.get('user_id') or '').strip()
    tracking_no = (data.get('tracking_no') or '').strip().upper()
    customer_name = (data.get('customer_name') or 'Customer').strip()
    issue_text = (data.get('issue_text') or '').strip()

    if not tracking_no or not issue_text:
        return jsonify({"success": False, "error_message": "Tracking ID and Issue Description are required."}), 400

    ticket_no = f"GRV-{random.randint(1000, 9999)}"
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO grievances (ticket_no, user_id, tracking_no, customer_name, issue_text, status)
        VALUES (?, ?, ?, ?, ?, 'OPEN')
    ''', (ticket_no, user_id, tracking_no, customer_name, issue_text))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "ticket_no": ticket_no})


# ==============================================================================
# MASTER ADMIN ROUTES (INCLUDES DELIVERY BOY ISSUE RETURN PROCESSING)
# ==============================================================================
@app.route('/api/admin/verify-utr', methods=['POST'])
def admin_verify_utr():
    data = request.json
    tracking_no = data.get('tracking_no')

    conn = get_db_connection()
    try:
        order = conn.execute("SELECT * FROM orders WHERE tracking_no = ?", (tracking_no,)).fetchone()
        if not order:
            return jsonify({"success": False, "error_message": "Order not found."}), 404
        if order['order_status'] != 'PENDING_UTR':
            return jsonify({"success": False, "error_message": "Order UTR is already processed."}), 400

        cfg = get_config_dict(conn)
        comm_pct = int(cfg.get('commission_pct') or 10) / 100.0
        delivery_otp = str(random.randint(100000, 999999))

        conn.execute('''
            UPDATE orders
            SET order_status = 'PENDING_PICKUP', delivery_otp = ?
            WHERE tracking_no = ?
        ''', (delivery_otp, tracking_no))

        total_paise = order['total_paise']
        tcs_paise = int(round(total_paise * 0.005))
        comm_paise = int(round(total_paise * comm_pct))
        vendor_paise = total_paise - tcs_paise - comm_paise

        ledger_rows = [
            (tracking_no, 'Escrow_Bank_UTR_Verified', total_paise, 0),
            (tracking_no, 'Vendor_Net_Payable_Escrow', 0, vendor_paise),
            (tracking_no, f'Platform_Commission_{int(comm_pct*100)}%', 0, comm_paise),
            (tracking_no, 'GST_TCS_Sec52_0.5%', 0, tcs_paise)
        ]
        for ref, acc, deb, cred in ledger_rows:
            conn.execute(
                "INSERT INTO ledger_entries (reference_id, account_name, debit_paise, credit_paise) VALUES (?, ?, ?, ?)",
                (ref, acc, deb, cred)
            )
        conn.commit()

        email_html = f"""
        <div style="font-family:sans-serif; padding:20px; border:1px solid #e5e7eb; border-radius:12px;">
            <h2 style="color:#16A34A;">✅ Payment UTR Verified — Order Confirmed!</h2>
            <p>Hello <strong>{order['customer_name']}</strong>, your UTR <strong>{order['utr_reference']}</strong> for order <strong>{tracking_no}</strong> has been verified by Admin.</p>
            <p>Share this secret <strong>6-Digit Delivery OTP</strong> with the Delivery Boy ONLY when your package arrives at your doorstep:</p>
            <h1 style="letter-spacing:4px; background:#DCFCE7; color:#166534; padding:12px 20px; display:inline-block; border-radius:8px;">{delivery_otp}</h1>
        </div>
        """
        sent_real, mode_msg = send_email_notification(order['buyer_email'], f"Order {tracking_no} Confirmed — Delivery OTP: {delivery_otp}", email_html, plain_otp=delivery_otp)

        return jsonify({"success": True, "delivery_otp": delivery_otp, "email_status": mode_msg, "sent_real": sent_real})
    finally:
        conn.close()


@app.route('/api/admin/reject-order', methods=['POST'])
def admin_reject_order():
    data = request.json
    tracking_no = data.get('tracking_no')

    conn = get_db_connection()
    try:
        order = conn.execute("SELECT * FROM orders WHERE tracking_no = ?", (tracking_no,)).fetchone()
        if not order:
            return jsonify({"success": False, "error_message": "Order not found."}), 404

        conn.execute("UPDATE orders SET order_status = 'REJECTED_REFUNDED', delivery_otp = '' WHERE tracking_no = ?", (tracking_no,))
        conn.execute('''
            INSERT INTO ledger_entries (reference_id, account_name, debit_paise, credit_paise)
            VALUES (?, 'Order_Cancelled_Or_Refunded', ?, ?)
        ''', (tracking_no, order['total_paise'], order['total_paise']))
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


@app.route('/api/admin/process-return', methods=['POST'])
def admin_process_return():
    data = request.json
    tracking_no = data.get('tracking_no')

    conn = get_db_connection()
    try:
        order = conn.execute("SELECT * FROM orders WHERE tracking_no = ?", (tracking_no,)).fetchone()
        if not order:
            return jsonify({"success": False, "error_message": "Order not found."}), 404

        conn.execute('''
            UPDATE orders
            SET order_status = 'RETURN_PROCESSED', issue_status = 'RETURN_APPROVED', delivery_otp = ''
            WHERE tracking_no = ?
        ''', (tracking_no,))
        conn.execute('''
            INSERT INTO ledger_entries (reference_id, account_name, debit_paise, credit_paise)
            VALUES (?, 'RTO_Return_Refund_Processed', ?, ?)
        ''', (tracking_no, order['total_paise'], order['total_paise']))
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


@app.route('/api/admin/shop-kyc', methods=['POST'])
def admin_shop_kyc():
    data = request.json
    shop_id = data.get('shop_id')
    decision = data.get('decision')

    conn = get_db_connection()
    conn.execute("UPDATE shops SET kyc_status = ? WHERE id = ?", (decision, shop_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/admin/settle-payout', methods=['POST'])
def admin_settle_payout():
    data = request.json
    tracking_no = data.get('tracking_no')

    conn = get_db_connection()
    try:
        order = conn.execute("SELECT * FROM orders WHERE tracking_no = ?", (tracking_no,)).fetchone()
        if not order or order['order_status'] != 'DELIVERED':
            return jsonify({"success": False, "error_message": "Order must be DELIVERED before settling vendor payout."}), 400
        if order['vendor_payout_status'] == 'PAID':
            return jsonify({"success": False, "error_message": "Vendor payout already settled."}), 400

        cfg = get_config_dict(conn)
        comm_pct = int(cfg.get('commission_pct') or 10) / 100.0
        total_paise = order['total_paise']
        net_vendor_paise = total_paise - int(round(total_paise * 0.005)) - int(round(total_paise * comm_pct))

        conn.execute("UPDATE orders SET vendor_payout_status = 'PAID' WHERE tracking_no = ?", (tracking_no,))
        conn.execute('''
            INSERT INTO ledger_entries (reference_id, account_name, debit_paise, credit_paise)
            VALUES (?, 'Vendor_UPI_Settlement_Disbursed', ?, 0)
        ''', (tracking_no, net_vendor_paise))
        conn.execute('''
            INSERT INTO ledger_entries (reference_id, account_name, debit_paise, credit_paise)
            VALUES (?, 'Escrow_Bank_Outflow', 0, ?)
        ''', (tracking_no, net_vendor_paise))
        conn.commit()
        return jsonify({"success": True, "settled_paise": net_vendor_paise})
    finally:
        conn.close()


@app.route('/api/admin/moderate-product', methods=['POST'])
def admin_moderate_product():
    data = request.json
    product_id = data.get('product_id')
    mod_status = data.get('mod_status')

    conn = get_db_connection()
    conn.execute("UPDATE products SET mod_status = ? WHERE id = ?", (mod_status, product_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/admin/resolve-grievance', methods=['POST'])
def admin_resolve_grievance():
    data = request.json
    ticket_no = data.get('ticket_no')
    admin_remark = (data.get('admin_remark') or 'Resolved by Grievance Officer').strip()

    conn = get_db_connection()
    conn.execute("UPDATE grievances SET status = 'RESOLVED', admin_remark = ? WHERE ticket_no = ?", (admin_remark, ticket_no))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route('/api/admin/update-config', methods=['POST'])
def admin_update_config():
    data = request.json
    local_inr = int(data.get('local_inr', 30))
    regional_inr = int(data.get('regional_inr', 50))
    national_inr = int(data.get('national_inr', 90))
    commission_pct = int(data.get('commission_pct', 10))
    smtp_gmail_user = (data.get('smtp_gmail_user') or '').strip()
    smtp_gmail_pass = (data.get('smtp_gmail_pass') or '').strip()

    conn = get_db_connection()
    updates = [
        ('local_shipping_paise', str(local_inr * 100)),
        ('regional_shipping_paise', str(regional_inr * 100)),
        ('national_shipping_paise', str(national_inr * 100)),
        ('commission_pct', str(commission_pct)),
        ('smtp_gmail_user', smtp_gmail_user)
    ]
    if smtp_gmail_pass:
        updates.append(('smtp_gmail_pass', smtp_gmail_pass))

    for k, v in updates:
        conn.execute("INSERT OR REPLACE INTO platform_config (config_key, config_val) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


# ==============================================================================
# DELIVERY BOY LOGISTICS ROUTES (ACCEPT -> IN HAND -> OTP OR REPORT ISSUE PHOTO)
# ==============================================================================
@app.route('/api/delivery/accept', methods=['POST'])
def delivery_accept():
    data = request.json
    tracking_no = (data.get('tracking_no') or '').strip()
    agent_id = (data.get('agent_id') or 'u_delivery').strip()
    agent_name = (data.get('agent_name') or 'Ramesh Kumar').strip()

    conn = get_db_connection()
    try:
        order = conn.execute("SELECT * FROM orders WHERE tracking_no = ?", (tracking_no,)).fetchone()
        if not order or order['order_status'] != 'PENDING_PICKUP':
            return jsonify({"success": False, "error_message": "Order is not available for pickup."}), 400

        conn.execute('''
            UPDATE orders
            SET order_status = 'AGENT_ASSIGNED', delivery_agent_id = ?, delivery_agent_name = ?
            WHERE tracking_no = ?
        ''', (agent_id, agent_name, tracking_no))
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


@app.route('/api/delivery/pickup', methods=['POST'])
def delivery_pickup():
    data = request.json
    tracking_no = (data.get('tracking_no') or '').strip()

    conn = get_db_connection()
    try:
        order = conn.execute("SELECT * FROM orders WHERE tracking_no = ?", (tracking_no,)).fetchone()
        if not order or order['order_status'] != 'AGENT_ASSIGNED':
            return jsonify({"success": False, "error_message": "Order must be accepted before marking in-hand."}), 400

        conn.execute('''
            UPDATE orders
            SET order_status = 'OUT_FOR_DELIVERY'
            WHERE tracking_no = ?
        ''', (tracking_no,))
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


@app.route('/api/delivery/report-issue', methods=['POST'])
def delivery_report_issue():
    data = request.json
    tracking_no = (data.get('tracking_no') or '').strip()
    issue_note = (data.get('issue_note') or 'Damaged/defective package reported by Delivery Boy').strip()
    issue_image = (data.get('issue_image') or '').strip()

    if not tracking_no or not issue_image:
        return jsonify({"success": False, "error_message": "Please upload a photo of the product issue first."}), 400

    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE orders
            SET order_status = 'ISSUE_REPORTED', issue_status = 'REPORTED_BY_AGENT', issue_note = ?, issue_image = ?
            WHERE tracking_no = ?
        ''', (issue_note, issue_image, tracking_no))
        conn.commit()
        return jsonify({"success": True})
    finally:
        conn.close()


@app.route('/api/delivery/verify-otp', methods=['POST'])
def delivery_verify_otp():
    data = request.json
    tracking_no = (data.get('tracking_no') or '').strip()
    entered_otp = (data.get('otp') or '').strip()

    conn = get_db_connection()
    try:
        order = conn.execute("SELECT * FROM orders WHERE tracking_no = ?", (tracking_no,)).fetchone()
        if not order:
            return jsonify({"success": False, "error_message": "Order not found."}), 404
        if order['order_status'] == 'DELIVERED':
            return jsonify({"success": False, "error_message": "Order is already Delivered."}), 400
        if order['order_status'] != 'OUT_FOR_DELIVERY':
            return jsonify({"success": False, "error_message": "First mark the product as 'Product is in Hand' before entering OTP!"}), 400
        if order['delivery_otp'] != entered_otp:
            return jsonify({"success": False, "error_message": "Incorrect Customer OTP! Ask the customer for the 6-digit OTP shown on their My Orders page."}), 400

        conn.execute("UPDATE orders SET order_status = 'DELIVERED' WHERE tracking_no = ?", (tracking_no,))
        conn.commit()
        return jsonify({"success": True, "tracking_no": tracking_no})
    finally:
        conn.close()


if __name__ == '__main__':
    app.run(port=5000, debug=True)