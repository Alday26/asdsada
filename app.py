from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import mysql.connector
import re
from flask_cors import CORS
from werkzeug.utils import secure_filename
import uuid
import os
from PIL import Image  # pillow (pip install pillow)
from datetime import datetime
from authlib.integrations.flask_client import OAuth
import smtplib
import random
from email.mime.text import MIMEText
import requests
from decimal import Decimal
import secrets

active_tokens = {}


app = Flask(__name__,static_url_path='/static')
CORS(app)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")
oauth = OAuth(app)


google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    access_token_url='https://oauth2.googleapis.com/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'}
)
def get_db_connection():
    host = os.environ.get("MYSQLHOST") or os.environ.get("DB_HOST", "localhost")
    port = int(os.environ.get("MYSQLPORT") or os.environ.get("DB_PORT", 3306))
    user = os.environ.get("MYSQLUSER") or os.environ.get("DB_USER", "root")
    password = os.environ.get("MYSQLPASSWORD") or os.environ.get("DB_PASSWORD", "")
    database = os.environ.get("MYSQLDATABASE") or os.environ.get("DB_NAME", "railway")
    print(f"Connecting to {host}:{port} db={database} user={user}")
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )


UPLOAD_FOLDER = os.path.join("static", "images")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "jfif"}

UPLOAD_FOLDER = "static/proof_deliveries"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file):
    upload_dir = os.path.join("static", "images")

    # create folder ONLY if missing (safe)
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4().hex}{ext}"

    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    # return WEB PATH (IMPORTANT)
    return f"/static/images/{filename}"


@app.route("/")
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    user_id = session.get("user_id")
    selected_category = request.args.get("category")
    search_query = request.args.get("search", "").strip()

    # 🌟 Featured products (respect search if provided)
    featured_sql = """
        SELECT p.*, u.username AS seller_name, u.id AS seller_id, u.store_name
        FROM products p
        JOIN users u ON p.user_id = u.id
        WHERE p.is_deleted = 0 AND p.is_featured = 1
    """
    featured_params = []

    if search_query:
        like = f"%{search_query}%"
        featured_sql += " AND (p.name LIKE %s OR p.description LIKE %s OR u.username LIKE %s OR u.store_name LIKE %s)"
        featured_params.extend([like, like, like, like])

    featured_sql += " ORDER BY p.total_purchases DESC"

    cursor.execute(featured_sql, featured_params)
    featured_products = cursor.fetchall()

    # Add variants & fallback image for featured
    for product in featured_products:
        cursor.execute("SELECT * FROM product_variants WHERE product_id=%s", (product["id"],))
        variants = cursor.fetchall()
        product["variants"] = variants

        if not product.get("image_url"):
            for v in variants:
                if v.get("image_url"):
                    product["image_url"] = v["image_url"]
                    break

    # 🛒 Normal products (with category + search filter + liked status)
    filters = ["p.is_deleted = 0"]
    params = [user_id or 0]

    if selected_category:
        filters.append("p.category = %s")
        params.append(selected_category)

    if search_query:
        like = f"%{search_query}%"
        filters.append("(p.name LIKE %s OR p.description LIKE %s OR u.username LIKE %s OR u.store_name LIKE %s)")
        params.extend([like, like, like, like])

    where_clause = " AND ".join(filters)

    cursor.execute(f"""
        SELECT p.*, u.username AS seller_name, u.id AS seller_id, u.store_name,
               CASE WHEN pl.user_id IS NOT NULL THEN 1 ELSE 0 END AS is_liked
        FROM products p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN product_likes pl ON pl.product_id = p.id AND pl.user_id = %s
        WHERE {where_clause}
        ORDER BY is_liked DESC, p.created_at DESC
    """, params)

    products = cursor.fetchall()

    # Add variants & fallback image
    for product in products:
        cursor.execute("SELECT * FROM product_variants WHERE product_id=%s", (product["id"],))
        variants = cursor.fetchall()
        product["variants"] = variants

        if not product.get("image_url"):
            for v in variants:
                if v.get("image_url"):
                    product["image_url"] = v["image_url"]
                    break

    # 🔔 Notification logic
    has_activity = False
    if user_id:
        if session.get("is_seller"):
            cursor.execute("""
                SELECT COUNT(*) AS cnt
                FROM orders o
                JOIN products p ON o.product_id = p.id
                WHERE p.user_id = %s
                  AND o.status IN ('pending', 'approved')
                  AND o.seller_notified = 0
            """, (user_id,))
            has_activity = cursor.fetchone()["cnt"] > 0
        else:
            cursor.execute("""
                SELECT COUNT(*) AS cnt
                FROM orders
                WHERE buyer_id = %s
                  AND status IN ('pending', 'approved')
                  AND buyer_notified = 0
            """, (user_id,))
            has_activity = cursor.fetchone()["cnt"] > 0

    conn.close()

    return render_template(
        "index.html",
        products=products,
        featured_products=featured_products,
        has_activity=has_activity,
        selected_category=selected_category
    )
@app.route("/api/home", methods=["GET"])
def api_home():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    user_id = request.args.get("user_id")  # from mobile
    selected_category = request.args.get("category")
    search_query = request.args.get("search", "").strip()

    # 🌟 Featured products
    featured_sql = """
        SELECT p.*, u.username AS seller_name, u.id AS seller_id, u.store_name
        FROM products p
        JOIN users u ON p.user_id = u.id
        WHERE p.is_deleted = 0 AND p.is_featured = 1
    """
    featured_params = []

    if search_query:
        like = f"%{search_query}%"
        featured_sql += " AND (p.name LIKE %s OR p.description LIKE %s OR u.username LIKE %s OR u.store_name LIKE %s)"
        featured_params.extend([like, like, like, like])

    featured_sql += " ORDER BY p.total_purchases DESC"

    cursor.execute(featured_sql, featured_params)
    featured_products = cursor.fetchall()

    for product in featured_products:
        cursor.execute("SELECT * FROM product_variants WHERE product_id=%s", (product["id"],))
        variants = cursor.fetchall()
        product["variants"] = variants

        if not product.get("image_url"):
            for v in variants:
                if v.get("image_url"):
                    product["image_url"] = v["image_url"]
                    break

    # 🛒 Normal products
    filters = ["p.is_deleted = 0"]
    params = [user_id or 0]

    if selected_category:
        filters.append("p.category = %s")
        params.append(selected_category)

    if search_query:
        like = f"%{search_query}%"
        filters.append("(p.name LIKE %s OR p.description LIKE %s OR u.username LIKE %s OR u.store_name LIKE %s)")
        params.extend([like, like, like, like])

    where_clause = " AND ".join(filters)

    cursor.execute(f"""
        SELECT p.*, u.username AS seller_name, u.id AS seller_id, u.store_name,
               CASE WHEN pl.user_id IS NOT NULL THEN 1 ELSE 0 END AS is_liked
        FROM products p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN product_likes pl ON pl.product_id = p.id AND pl.user_id = %s
        WHERE {where_clause}
        ORDER BY is_liked DESC, p.created_at DESC
    """, params)

    products = cursor.fetchall()

    for product in products:
        cursor.execute("SELECT * FROM product_variants WHERE product_id=%s", (product["id"],))
        variants = cursor.fetchall()
        product["variants"] = variants

        if not product.get("image_url"):
            for v in variants:
                if v.get("image_url"):
                    product["image_url"] = v["image_url"]
                    break

    conn.close()

    return jsonify({
        "products": products,
        "featured_products": featured_products
    })


@app.route('/auth/google/callback')
def authorize_google():
    token = google.authorize_access_token()
    resp = google.get('userinfo', token=token)
    user_info = resp.json()
    # user_info contains 'email', 'name', 'picture', etc.
    session['user'] = user_info
    return f"Hello, {user_info['name']}! You are logged in with Google."
# Store links in a simple table: reference_links (id, link)
@app.route("/send_otp", methods=["POST"])
def send_otp():
    # Get JSON body safely
    data = request.get_json(silent=True) or {}
    email = data.get("email")

    if not email:
        return jsonify({"status": "error", "message": "Email is required"}), 400

    otp = str(random.randint(100000, 999999))
    session["otp"] = otp
    session["otp_email"] = email

    # Gmail SMTP (requires App Password)
    sender_email = os.environ.get("MAIL_SENDER", "YOUR_EMAIL@gmail.com")
    sender_password = os.environ.get("MAIL_PASSWORD", "YOUR_APP_PASSWORD")

    msg = MIMEText(f"Your OTP code is: {otp}")
    msg["Subject"] = "Verify your email"
    msg["From"] = sender_email
    msg["To"] = email

    try:
        # Use STARTTLS like in /send_verification_code for better compatibility
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email, msg.as_string())
        server.quit()
        return jsonify({"status": "success", "message": "OTP sent! Please check your email (Inbox/Spam)."})
    except Exception as e:
        # Log full error on server and surface a generic message to client
        print("Failed to send email:", e)
        return jsonify({"status": "error", "message": "Failed to send OTP. Please try again later."}), 500
    
@app.route("/seller_sales", methods=["GET", "POST"])
def seller_sales():
    if "user_id" not in session:
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    seller_id = session["user_id"]
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Updated: use p.user_id (if your products table uses that for seller reference)
    query = """
        SELECT 
            o.id AS order_id,
            o.quantity,
            o.delivered_at,
            p.name AS product_name,
            p.price AS product_price,
            u.username AS buyer_name,
            o.image_url
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN users u ON o.buyer_id = u.id
        WHERE p.user_id = %s 
          AND o.delivery_status = 'delivered'
    """
    params = [seller_id]

    if start_date and end_date:
        query += " AND DATE(o.delivered_at) BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    query += " ORDER BY o.delivered_at DESC"

    cursor.execute(query, params)
    sales = cursor.fetchall()

    # Aggregate stats for template (avoid complex Jinja expressions)
    if sales:
        total_sales = sum(float(row["product_price"]) * int(row["quantity"]) for row in sales)
        total_orders = len(sales)
        total_items_sold = sum(int(row["quantity"]) for row in sales)
        unique_customers = len({row["buyer_name"] for row in sales})
        avg_order_value = total_sales / total_orders if total_orders else 0.0
    else:
        total_sales = 0.0
        total_orders = 0
        total_items_sold = 0
        unique_customers = 0
        avg_order_value = 0.0

    cursor.close()
    conn.close()

    return render_template(
        "seller_sales.html",
        sales=sales,
        total_sales=total_sales,
        start_date=start_date,
        end_date=end_date,
        total_orders=total_orders,
        total_items_sold=total_items_sold,
        unique_customers=unique_customers,
        avg_order_value=avg_order_value,
    )

@app.route("/api/seller_sales", methods=["GET"])
def api_seller_sales():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please log in first."
        }), 401

    seller_id = session["user_id"]

    # GET params (better for Flutter than POST form)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT 
            o.id AS order_id,
            o.quantity,
            o.delivered_at,
            p.name AS product_name,
            p.price AS product_price,
            u.username AS buyer_name,
            o.image_url
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN users u ON o.buyer_id = u.id
        WHERE p.user_id = %s 
          AND o.delivery_status = 'delivered'
    """

    params = [seller_id]

    if start_date and end_date:
        query += " AND DATE(o.delivered_at) BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    query += " ORDER BY o.delivered_at DESC"

    cursor.execute(query, params)
    sales = cursor.fetchall()

    # 📊 STATS
    if sales:
        total_sales = sum(float(row["product_price"]) * int(row["quantity"]) for row in sales)
        total_orders = len(sales)
        total_items_sold = sum(int(row["quantity"]) for row in sales)
        unique_customers = len({row["buyer_name"] for row in sales})
        avg_order_value = total_sales / total_orders if total_orders else 0.0
    else:
        total_sales = 0.0
        total_orders = 0
        total_items_sold = 0
        unique_customers = 0
        avg_order_value = 0.0

    conn.close()

    return jsonify({
        "success": True,
        "filters": {
            "start_date": start_date,
            "end_date": end_date
        },
        "stats": {
            "total_sales": total_sales,
            "total_orders": total_orders,
            "total_items_sold": total_items_sold,
            "unique_customers": unique_customers,
            "avg_order_value": avg_order_value
        },
        "sales": sales
    })

@app.route("/admin_sales", methods=["GET", "POST"])
def admin_sales():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("login"))

    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT 
            o.id AS order_id,
            o.quantity,
            o.delivered_at,
            p.name AS product_name,
            p.price AS product_price,
            s.username AS seller_name,
            u.username AS buyer_name
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN users u ON o.buyer_id = u.id
        JOIN users s ON p.user_id = s.id   -- seller reference
        WHERE o.delivery_status = 'delivered'
    """

    params = []
    if start_date and end_date:
        query += " AND DATE(o.delivered_at) BETWEEN %s AND %s"
        params.extend([start_date, end_date])

    query += " ORDER BY o.delivered_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Use Decimal for all money math
    total_commission = Decimal("0.00")
    for r in rows:
        price = Decimal(r["product_price"])
        qty = Decimal(r["quantity"])
        r["total_price"] = price * qty
        r["admin_fee"] = r["total_price"] * Decimal("0.05")
        total_commission += r["admin_fee"]

    cursor.close()
    conn.close()

    return render_template(
        "admin_sales.html",
        sales=rows,
        total_commission=total_commission,
        start_date=start_date,
        end_date=end_date
    )

@app.route('/send_verification_code', methods=['POST'])
def send_verification_code():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'success': False, 'message': 'Email is required.'})

    # Generate 6-digit code
    code = str(random.randint(100000, 999999))
    session['verification_code'] = code
    session['verification_email'] = email

    # Send email via Gmail SMTP (use app password)
    try:
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587
        sender_email = 'your_email@gmail.com'
        sender_password = 'your_app_password'
        subject = "Your Verification Code"
        body = f"Your verification code is: {code}"
        message = f"Subject: {subject}\n\n{body}"

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email, message)
        server.quit()
        return jsonify({'success': True, 'message': 'Verification code sent! Check your email.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to send email: {str(e)}'})

@app.route("/reference_links", methods=["GET", "POST"])
def reference_links():
    if request.method == "POST":
        link = request.form.get("link")
        if link:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("INSERT INTO reference_links (link) VALUES (%s)", (link,))
            conn.commit()
            conn.close()
            flash("Link added successfully!", "success")
        return redirect(url_for("reference_links"))

    # Fetch all links
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM reference_links ORDER BY id DESC")
    links = cursor.fetchall()
    conn.close()

    return render_template("reference_links.html", links=links)

@app.route("/toggle_like/<int:product_id>", methods=["POST"])
def toggle_like(product_id):
    if "user_id" not in session:
        return jsonify({"success": False, "message": "Login required"}), 401

    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id FROM product_likes WHERE user_id=%s AND product_id=%s",
                   (user_id, product_id))
    like = cursor.fetchone()

    if like:
        cursor.execute("DELETE FROM product_likes WHERE id=%s", (like["id"],))
        liked = False
        message = "Product removed from your liked list."
    else:
        cursor.execute("INSERT INTO product_likes (user_id, product_id) VALUES (%s,%s)",
                       (user_id, product_id))
        liked = True
        message = "Product added to your liked list."

    conn.commit()
    conn.close()

    return jsonify({"success": True, "liked": liked, "message": message})


@app.route("/admin/toggle_featured/<int:product_id>", methods=["POST"])
def toggle_featured(product_id):
    data = request.get_json()
    is_featured = 1 if data.get("is_featured") else 0

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE products SET is_featured=%s WHERE id=%s", (is_featured, product_id))
    conn.commit()
    conn.close()

    return {"message": "Product featured status updated."}

@app.route("/notify_seller_order/<int:order_id>", methods=["POST"])
def notify_seller_order(order_id):
    if "user_id" not in session or not session.get("is_seller"):
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Update seller_notified safely
    cursor.execute("""
        UPDATE orders o
        JOIN products p ON o.product_id = p.id
        SET o.seller_notified = 1
        WHERE o.id = %s AND p.user_id = %s
    """, (order_id, session["user_id"]))
    
    conn.commit()
    conn.close()

    flash("You have acknowledged the order update.", "success")
    # Redirect to homepage so the notification disappears
    return redirect(url_for("index"))


@app.route("/admin/orders")
def admin_orders():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied. Admins only.", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
    SELECT o.id, o.quantity, o.status, o.payment_method,
           p.name AS product_name, p.price,
           u.username AS buyer_name, v.color
    FROM orders o
    JOIN products p ON o.product_id = p.id
    JOIN users u ON o.buyer_id = u.id
    JOIN product_variants v ON o.variant_id = v.id
    WHERE o.status IN ('pending', 'approved')  -- exclude canceled orders
    ORDER BY o.id DESC
    """)
    orders = cursor.fetchall()
    conn.close()

    # Filter out any canceled orders
    orders = [o for o in orders if o['status'].lower() != 'cancelled']

    return render_template("admin_order.html", orders=orders)

@app.route("/seller/reported_orders")
def seller_reported_orders():
    if "user_id" not in session or not session.get("is_seller"):
        flash("Access denied", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT o.id AS order_id, o.quantity, o.status, p.name AS product_name, p.image_url, u.username AS buyer_name,
               r.reason AS report_reason, r.report_id
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN users u ON o.buyer_id = u.id
        JOIN reports r ON o.id = r.order_id
        WHERE o.seller_id=%s AND o.report_status='reported'
        ORDER BY r.created_at DESC
    """, (session["user_id"],))

    reported_orders = cursor.fetchall()
    conn.close()
    return render_template("seller_reported_orders.html", reported_orders=reported_orders)

@app.route("/seller/redeliver/<int:order_id>")
def seller_redeliver_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE orders 
        SET report_status='redelivering', status='out-for-delivery'
        WHERE id=%s
    """, (order_id,))
    conn.commit()
    conn.close()
    flash("Order marked for redelivery!", "success")
    return redirect(url_for("seller_reported_orders"))

@app.route("/seller/report_chat/<int:report_id>")
def view_report_chat(report_id):
    if "user_id" not in session or not session.get("is_seller"):
        flash("Access denied", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT r.report_id, r.reason, r.created_at, u.username AS buyer_name, o.product_id, p.name AS product_name
        FROM reports r
        JOIN orders o ON r.order_id = o.id
        JOIN users u ON r.buyer_id = u.id
        JOIN products p ON o.product_id = p.id
        WHERE r.report_id=%s
    """, (report_id,))
    report = cursor.fetchone()
    conn.close()

    if not report:
        flash("Report not found.", "error")
        return redirect(url_for("seller_reported_orders"))

    return render_template("seller_report_chat.html", report=report)


@app.route("/admin/approve_order/<int:order_id>")
def admin_approve_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Mark order as approved
    cursor.execute("UPDATE orders SET status='approved' WHERE id=%s", (order_id,))
    conn.commit()

    # Fetch order details
    cursor.execute("""
        SELECT o.buyer_id, o.product_id, p.user_id AS seller_id, o.quantity
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.id=%s
    """, (order_id,))
    result = cursor.fetchone()

    if result:
        buyer_id = result["buyer_id"]
        seller_id = result["seller_id"]
        product_id = result["product_id"]
        quantity = result["quantity"]

        # Mark notifications
        cursor.execute("UPDATE orders SET buyer_notified=1, seller_notified=1 WHERE id=%s", (order_id,))
        conn.commit()

        # OPTIONAL STEP:
        # You can keep a purchase counter inside the product table
        cursor.execute("""
            UPDATE products 
            SET total_purchases = COALESCE(total_purchases, 0) + %s
            WHERE id=%s
        """, (quantity, product_id))
        conn.commit()

    conn.close()
    flash("Order approved. Buyer and Seller have been notified.", "success")
    return redirect(url_for("admin_orders"))


@app.route("/admin/decline_order/<int:order_id>")
def admin_decline_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Step 1: Fetch variant_id and quantity before updating status
    cursor.execute("""
        SELECT variant_id, quantity, buyer_id 
        FROM orders 
        WHERE id=%s AND status IN ('pending', 'approved')
    """, (order_id,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        flash("Order cannot be declined or already processed.", "error")
        return redirect(url_for("admin_orders"))

    variant_id = order["variant_id"]
    quantity = order["quantity"]
    buyer_id = order["buyer_id"]

    # Step 2: Restore stock
    cursor.execute("""
        UPDATE product_variants 
        SET stock = stock + %s 
        WHERE id = %s
    """, (quantity, variant_id))

    # Step 3: Update order status and notify buyer
    cursor.execute("""
        UPDATE orders 
        SET status='declined', buyer_notified=1 
        WHERE id=%s
    """, (order_id,))

    conn.commit()
    conn.close()

    flash("Order declined. Buyer has been notified. Stock has been restored.", "error")
    return redirect(url_for("admin_orders"))

@app.route("/seller/deliver_to_rider/<int:order_id>")
def seller_deliver_to_rider(order_id):
    # Ensure the user is logged in and is a seller
    if "user_id" not in session or not session.get("is_seller"):
        flash("You must be logged in as a seller to deliver orders.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Change the order to shipped for buyer, ready for delivery for riders
    cursor.execute("""
        UPDATE orders
        SET status = 'shipped',
            delivery_status = 'ready_for_delivery'
        WHERE id = %s
          AND status = 'approved'
    """, (order_id,))

    if cursor.rowcount > 0:
        flash("✅ Success Deliver! Order is now shipped and available for riders.", "success")
    else:
        flash("⚠️ Order cannot be delivered. Make sure it’s approved.", "warning")

    conn.commit()
    conn.close()

    return redirect(url_for("seller_orders"))

@app.route("/seller/redeliver_to_rider/<int:order_id>")
def seller_redeliver_to_rider(order_id):
    if "user_id" not in session or not session.get("is_seller"):
        flash("You must be a seller to redeliver orders.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # ✅ Reset delivery status and clear the rider assignment
    cursor.execute("""
        UPDATE orders
        SET delivery_status = 'ready_for_delivery',
            rider_id = NULL,
            status = 'shipped'       -- notify buyer as shipped again
        WHERE id = %s
          AND delivery_status = 'returned_to_seller'
    """, (order_id,))

    if cursor.rowcount == 0:
        flash("Order cannot be redelivered. Please check its status.", "warning")
    else:
        flash("Order has been sent back to the rider queue for redelivery.", "success")

    conn.commit()
    conn.close()

    return redirect(url_for("seller_orders"))


@app.route("/rider/accept/<int:order_id>")
def rider_accept(order_id):
    if "role" not in session or session["role"] != "rider":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Assign rider if order is still available
    cursor.execute("""
        UPDATE orders
        SET rider_id = %s, delivery_status = 'out_for_delivery'
        WHERE id = %s AND delivery_status = 'ready_for_delivery'
    """, (session["user_id"], order_id))

    if cursor.rowcount == 0:
        flash("This order has already been taken by another rider.", "warning")
    else:
        flash("You have accepted the delivery!", "success")

    conn.commit()
    conn.close()

    return redirect(url_for("rider_dashboard"))


# This route could be triggered when seller marks an order as delivered
@app.route("/order/deliver/<int:order_id>")
def deliver_order(order_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch order
    cursor.execute("SELECT variant_id, quantity FROM orders WHERE id=%s", (order_id,))
    order = cursor.fetchone()
    if not order:
        flash("Order not found.", "error")
        conn.close()
        return redirect(url_for("seller_dashboard"))

    variant_id, quantity = order

    # Reduce stock
    cursor.execute("UPDATE product_variants SET stock = stock - %s WHERE id=%s", (quantity, variant_id))

    # Update order status
    cursor.execute("UPDATE orders SET status='delivered' WHERE id=%s", (order_id,))
    conn.commit()
    conn.close()
    flash("Order delivered and stock updated.", "success")
    return redirect(url_for("seller_dashboard"))

@app.route("/seller/acknowledge_order/<int:order_id>")
def seller_acknowledge_order(order_id):
    if "user_id" not in session or not session.get("is_seller"):
        flash("Access denied. Sellers only.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Step 1: Check if order exists and belongs to this seller
    cursor.execute("""
        SELECT o.id, o.buyer_id, o.product_id, o.quantity, p.user_id AS seller_id
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.id=%s AND p.user_id=%s AND o.status='pending'
    """, (order_id, session["user_id"]))
    order = cursor.fetchone()

    if not order:
        conn.close()
        flash("Order not found or already processed.", "error")
        return redirect(url_for("seller_orders"))

    # ✅ Step 2: Approve (acknowledge) the order
    cursor.execute("""
        UPDATE orders
        SET status='approved', buyer_notified=1
        WHERE id=%s
    """, (order_id,))
    conn.commit()

    # ✅ Step 3: Update optional product counter
    cursor.execute("""
        UPDATE products
        SET total_purchases = COALESCE(total_purchases, 0) + %s
        WHERE id=%s
    """, (order["quantity"], order["product_id"]))
    conn.commit()

    conn.close()

    flash("Order acknowledged and approved. Buyer has been notified.", "success")
    return redirect(url_for("seller_orders"))

@app.route("/seller/orders")
def seller_orders():
    if "user_id" not in session or not session.get("is_seller"):
        flash("Please login as a seller to view your orders.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            o.id AS order_id,
            u.username AS buyer_name,
            p.name AS product_name,
            o.image_url,
            v.color,
            o.quantity,
            o.seller_notified,
            o.status,
            o.delivery_status,
            p.price,
            o.delivered_at   -- optional if you want the timestamp
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN product_variants v ON o.variant_id = v.id
        JOIN users u ON o.buyer_id = u.id
        WHERE p.user_id = %s
        ORDER BY o.id DESC
    """, (session["user_id"],))

    orders = cursor.fetchall()
    conn.close()

    return render_template("seller_order.html", orders=orders)


@app.route("/add_to_cart/<int:product_id>/<int:variant_id>", methods=["POST"])
def add_to_cart(product_id, variant_id):
    if "user_id" not in session:
        return "login_required", 401

    quantity = int(request.form.get("quantity", 1))
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check stock
    cursor.execute("SELECT stock FROM product_variants WHERE id=%s", (variant_id,))
    variant = cursor.fetchone()
    if not variant or variant[0] < quantity:
        conn.close()
        return "not_enough_stock", 409

    # Check if already in cart
    cursor.execute("""
        SELECT quantity FROM cart 
        WHERE user_id=%s AND product_id=%s AND variant_id=%s
    """, (session["user_id"], product_id, variant_id))
    existing = cursor.fetchone()

    if existing:
        conn.close()
        return "already_in_cart", 409

    # Insert new cart item
    cursor.execute("""
        INSERT INTO cart (user_id, product_id, variant_id, quantity)
        VALUES (%s, %s, %s, %s)
    """, (session["user_id"], product_id, variant_id, quantity))

    conn.commit()
    conn.close()
    return "added", 200

@app.route("/api/cart/add", methods=["POST"])
def api_add_to_cart():
    try:
        data = request.get_json()

        user_id = data.get("user_id")
        product_id = data.get("product_id")
        variant_id = data.get("variant_id")
        quantity = int(data.get("quantity", 1))

        if not all([user_id, product_id, variant_id]):
            return jsonify({
                "success": False,
                "message": "Missing required fields"
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # ✅ CHECK STOCK
        cursor.execute(
            "SELECT stock FROM product_variants WHERE id=%s",
            (variant_id,)
        )
        variant = cursor.fetchone()

        if not variant:
            conn.close()
            return jsonify({
                "success": False,
                "message": "Variant not found"
            }), 404

        if variant[0] < quantity:
            conn.close()
            return jsonify({
                "success": False,
                "message": "Not enough stock"
            }), 409

        # ✅ CHECK IF ALREADY IN CART
        cursor.execute("""
            SELECT quantity FROM cart 
            WHERE user_id=%s AND product_id=%s AND variant_id=%s
        """, (user_id, product_id, variant_id))

        existing = cursor.fetchone()

        if existing:
            conn.close()
            return jsonify({
                "success": False,
                "message": "Already in cart"
            }), 409

        # ✅ INSERT
        cursor.execute("""
            INSERT INTO cart (user_id, product_id, variant_id, quantity)
            VALUES (%s, %s, %s, %s)
        """, (user_id, product_id, variant_id, quantity))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Added to cart"
        }), 200

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    
@app.route("/api/add_product", methods=["POST"])
def api_add_product():
    try:
        user_id = request.form.get("user_id")
        name = request.form.get("name")
        description = request.form.get("description")
        price = request.form.get("price")

        if not all([user_id, name, price]):
            return jsonify({
                "success": False,
                "message": "Missing required fields"
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ✅ GET CATEGORY
        cursor.execute("""
            SELECT seller_category 
            FROM users 
            WHERE id = %s AND is_seller = 1
        """, (user_id,))
        user = cursor.fetchone()

        if not user or not user["seller_category"]:
            conn.close()
            return jsonify({
                "success": False,
                "message": "Seller category not found"
            }), 400

        category = user["seller_category"]

        # ✅ INSERT PRODUCT
        cursor.execute("""
            INSERT INTO products (user_id, name, description, price, category)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, name, description, price, category))

        product_id = cursor.lastrowid

        # ✅ VARIANTS
        colors = request.form.getlist("variant_color[]")
        stocks = request.form.getlist("variant_stock[]")
        images = request.files.getlist("variant_image[]")

        import os, uuid
        upload_dir = "static/images"
        os.makedirs(upload_dir, exist_ok=True)

        for i in range(len(colors)):
            image_path = None

            if i < len(images) and images[i]:
                ext = os.path.splitext(images[i].filename)[1]
                filename = f"{uuid.uuid4().hex}{ext}"
                filepath = os.path.join(upload_dir, filename)

                images[i].save(filepath)

                # ✅ SAVE FULL PATH (IMPORTANT)
                image_path = f"/static/images/{filename}"

            cursor.execute("""
                INSERT INTO product_variants (product_id, color, stock, image_url)
                VALUES (%s, %s, %s, %s)
            """, (product_id, colors[i], stocks[i], image_path))

        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Product added successfully"
        })

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500
    
@app.route("/api/seller/category", methods=["GET"])
def get_seller_category():
    user_id = request.args.get("user_id")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT is_seller, seller_category 
        FROM users 
        WHERE id = %s
    """, (user_id,))

    user = cursor.fetchone()
    conn.close()

    print("🔥 USER:", user)

    if user and user["is_seller"] == 1:
        return jsonify({
            "seller_category": user["seller_category"]
        })

    return jsonify({"seller_category": ""})

@app.route("/checkout", methods=["POST"])
def checkout():
    if "user_id" not in session:
        flash("Please login to checkout.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- Fetch user info ---
    cursor.execute("""
        SELECT email, phone_number, region, province, municipality, barangay, street_name, house_number
        FROM users WHERE id=%s
    """, (session["user_id"],))
    user_info = cursor.fetchone()
    conn.close()

    if not user_info:
        flash("User not found.", "error")
        return redirect(url_for("login"))

    # --- Convert PSGC codes to names ---
    user_info['region'] = get_location_name(user_info.get('region'), 'region')
    user_info['province'] = get_location_name(user_info.get('province'), 'province')
    user_info['municipality'] = get_location_name(user_info.get('municipality'), 'municipality')
    # barangay stored as name
    user_info['address'] = f"{user_info['region']}, {user_info['province']}, {user_info['municipality']}, {user_info['barangay']}, {user_info['street_name']} {user_info['house_number']}"
    user_info['phone'] = user_info.get('phone_number', 'N/A')

    # --- Fetch items for checkout ---
    product_id = request.form.get("product_id")
    variant_id = request.form.get("variant_id")
    quantity = request.form.get("quantity", type=int, default=1)
    cart_ids = request.form.getlist("cart_ids")
    quantities = request.form.getlist("quantities")

    items = []
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Single product
    if product_id and variant_id:
        cursor.execute("""
            SELECT p.id AS product_id, p.name AS product_name, p.price,
                   v.id AS variant_id, v.color, v.stock, v.image_url
            FROM products p
            JOIN product_variants v ON v.product_id = p.id
            WHERE p.id=%s AND v.id=%s
        """, (product_id, variant_id))
        row = cursor.fetchone()
        if row:
            row['quantity'] = quantity
            row['price'] = float(row['price'])
            items.append(row)

    # Cart checkout
    elif cart_ids:
        qty_dict = {int(cid): int(qty) for cid, qty in zip(cart_ids, quantities)}
        format_strings = ','.join(['%s'] * len(cart_ids))
        cursor.execute(f"""
            SELECT c.id AS cart_id, c.quantity, p.id AS product_id, p.name AS product_name, p.price,
                   v.id AS variant_id, v.color, v.stock, v.image_url
            FROM cart c
            JOIN products p ON c.product_id = p.id
            JOIN product_variants v ON c.variant_id = v.id
            WHERE c.user_id=%s AND c.id IN ({format_strings})
        """, [session["user_id"]] + cart_ids)
        rows = cursor.fetchall()
        for item in rows:
            if item['cart_id'] in qty_dict:
                item['quantity'] = qty_dict[item['cart_id']]
            item['price'] = float(item['price'])
            items.append(item)

    conn.close()

    if not items:
        flash("No items found for checkout.", "error")
        return redirect(url_for("cart"))

    return render_template(
        "checkout.html",
        items=items,
        user_info=user_info
    )

@app.route("/api/checkout", methods=["POST"])
def api_checkout():
    data = request.get_json()

    user_id = data.get("user_id")
    cart_items = data.get("items", [])

    if not user_id:
        return jsonify({"success": False, "message": "Missing user_id"}), 400

    if not cart_items:
        return jsonify({"success": False, "message": "No items"}), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # --- Get user info ---
    cursor.execute("""
        SELECT email, phone_number, region, province, municipality, barangay, street_name, house_number
        FROM users WHERE id=%s
    """, (user_id,))
    user_info = cursor.fetchone()

    conn.close()

    if not user_info:
        return jsonify({"success": False, "message": "User not found"}), 404

    # --- Format address ---
    user_info["address"] = f"{user_info.get('region')}, {user_info.get('province')}, {user_info.get('municipality')}, {user_info.get('barangay')}, {user_info.get('street_name')} {user_info.get('house_number')}"
    user_info["phone"] = user_info.get("phone_number")

    # --- Return checkout preview ---
    return jsonify({
        "success": True,
        "user_info": user_info,
        "items": cart_items
    })

@app.route("/checkout_now")
def checkout_now():
    if "user_id" not in session:
        flash("Please login to checkout.", "error")
        return redirect(url_for("login"))

    order_item = session.get("order_now")
    if not order_item:
        flash("No item to checkout.", "error")
        return redirect(url_for("index"))

    items = [order_item]  # reuse your template logic
    return render_template("checkout.html", items=items)

@app.route("/cancel_order/<int:order_id>", methods=["POST"])
def cancel_order(order_id):
    if "user_id" not in session:
        flash("Please login to cancel orders.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch variant_id and quantity before cancelling
    cursor.execute("""
        SELECT variant_id, quantity 
        FROM orders 
        WHERE id=%s AND buyer_id=%s AND status IN ('pending', 'approved')
    """, (order_id, session["user_id"]))
    order = cursor.fetchone()

    if not order:
        conn.close()
        flash("Order cannot be cancelled.", "error")
        return redirect(url_for("my_orders"))

    variant_id, quantity = order

    # Update order status to 'cancelled'
    cursor.execute("""
        UPDATE orders 
        SET status='cancelled' 
        WHERE id=%s
    """, (order_id,))

    # Restore stock
    cursor.execute("""
        UPDATE product_variants 
        SET stock = stock + %s 
        WHERE id=%s
    """, (quantity, variant_id))

    conn.commit()
    conn.close()

    flash("Order cancelled successfully. Stock has been restored.", "success")
    return redirect(url_for("my_orders"))

import os

@app.route("/my_orders")
def my_orders():
    if "user_id" not in session:
        flash("Please login to view your orders.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            o.id, 
            p.name AS product_name, 
            p.price, 
            v.color, 
            COALESCE(o.image_url, v.image_url) AS image_url,
            o.quantity, 
            o.payment_method, 
            o.status, 
            o.buyer_notified,
            o.delivery_status,

            o.proof_image,   -- ✅ DELIVERY PROOF ADDED

            r.id AS review_id,
            r.rating,
            r.comment
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN product_variants v ON o.variant_id = v.id
        LEFT JOIN reviews r 
            ON r.order_id = o.id AND r.buyer_id = o.buyer_id
        WHERE o.buyer_id = %s
          AND (
                o.status IN ('pending', 'approved', 'shipped', 'ready_to_delivery', 'delivered')
                OR o.delivery_status IN ('returned_to_seller', 'ready_for_delivery', 'out_for_delivery', 'delivered')
              )
        ORDER BY o.id DESC
    """, (session["user_id"],))

    orders = cursor.fetchall()
    conn.close()

    # normalize data
    for order in orders:
        order["reviewed"] = bool(order.get("review_id"))

        # fix image URL
        if order.get("image_url") and not str(order["image_url"]).startswith("http"):
            order["image_url"] = request.host_url.strip("/") + order["image_url"]

        # fix proof image URL
        if order.get("proof_image") and not str(order["proof_image"]).startswith("http"):
            order["proof_image"] = request.host_url.strip("/") + order["proof_image"]

    return render_template("my_orders.html", orders=orders)

@app.route("/api/my_orders")
def api_my_orders():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "message": "User ID required"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            o.id,
            o.product_id,
            o.variant_id,
            o.quantity,
            o.total_price,
            o.shipping_fee,
            o.payment_method,
            o.status,
            o.delivery_status,
            o.address,
            o.created_at,

            o.proof_image,   -- ✅ ADD THIS LINE

            p.name AS product_name,
            p.price AS product_price,

            v.color,
            COALESCE(o.image_url, v.image_url) AS image_url,

            r.id AS review_id,
            r.rating,
            r.comment

        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN product_variants v ON o.variant_id = v.id
        LEFT JOIN reviews r 
            ON r.order_id = o.id AND r.buyer_id = o.buyer_id

        WHERE o.buyer_id = %s
        ORDER BY o.id DESC
    """, (user_id,))

    orders = cursor.fetchall()
    cursor.close()
    conn.close()

    for order in orders:
        order["reviewed"] = bool(order["review_id"])

        price = float(order["product_price"] or 0)
        qty = int(order["quantity"] or 1)
        shipping = float(order["shipping_fee"] or 0)

        if not order["total_price"] or float(order["total_price"]) == 0:
            order["total_price"] = (price * qty) + shipping

        BASE = "https://web-production-1592e.up.railway.app"

        # fix image_url
        if order["image_url"] and not str(order["image_url"]).startswith("http"):
            order["image_url"] = BASE + str(order["image_url"])

        # fix proof image URL
        if order.get("proof_image") and not str(order["proof_image"]).startswith("http"):
            order["proof_image"] = BASE + str(order["proof_image"])

    return jsonify({
        "success": True,
        "orders": orders
    })

@app.route("/my_orders/delivered")
def my_orders_delivered():
    if "user_id" not in session:
        flash("Please login to view your delivered orders.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            o.id,
            p.id AS product_id,
            p.name AS product_name,
            v.color,
            COALESCE(o.image_url, v.image_url) AS image_url,
            o.quantity,
            o.delivery_status,
            r.id AS review_id,
            r.rating,
            r.comment
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN product_variants v ON o.variant_id = v.id
        LEFT JOIN reviews r ON r.order_id = o.id AND r.buyer_id = %s
        WHERE o.buyer_id = %s
          AND o.delivery_status = 'delivered'
        ORDER BY o.id DESC
    """, (session["user_id"], session["user_id"]))

    delivered_orders = cursor.fetchall()

    # Add a flag for template rendering
    for order in delivered_orders:
        order['reviewed'] = order['review_id'] is not None

    conn.close()

    return render_template("my_orders_delivered.html", orders=delivered_orders)

@app.route("/submit_review/<int:order_id>", methods=["POST"])
def submit_review(order_id):
    if "user_id" not in session:
        flash("Please login to submit a review.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # ✅ Make sure the order exists and belongs to this user
    cursor.execute("""
        SELECT product_id 
        FROM orders 
        WHERE id = %s AND buyer_id = %s
    """, (order_id, session["user_id"]))
    order = cursor.fetchone()

    if not order:
        flash("Invalid order or you cannot review this order.", "error")
        conn.close()
        return redirect(url_for("my_orders_delivered"))

    product_id = order[0]
    rating = int(request.form.get("rating"))
    comment = request.form.get("comment")

    # ✅ Insert review (order_id is included now)
    cursor.execute("""
        INSERT INTO reviews (order_id, product_id, buyer_id, rating, comment)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            rating = VALUES(rating),
            comment = VALUES(comment)
    """, (order_id, product_id, session["user_id"], rating, comment))

    conn.commit()
    conn.close()

    flash("Thank you for your review!", "success")
    return redirect(url_for("my_orders_delivered"))



@app.route("/notify_order/<int:order_id>", methods=["POST"])
def notify_order(order_id):
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Mark this order as notified
    cursor.execute("UPDATE orders SET buyer_notified = 1 WHERE id = %s AND buyer_id = %s",
                   (order_id, session["user_id"]))
    conn.commit()
    conn.close()

    flash("You have acknowledged the order update.", "success")
    return redirect(url_for("index"))



def get_address_from_coords(lat, lon):
    """Fetch a readable address using OpenStreetMap’s Nominatim API."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
        headers = {"User-Agent": "EcomsApp/1.0 (contact@example.com)"}
        res = requests.get(url, headers=headers, timeout=3)
        if res.status_code == 200:
            data = res.json()
            return data.get("display_name", f"{lat}, {lon}")
    except Exception as e:
        print("Error fetching address:", e)
    return f"{lat}, {lon}"


@app.route("/complete_payment", methods=["POST"])
def complete_payment():
    if "user_id" not in session:
        flash("Please login to complete payment.", "error")
        return redirect(url_for("login"))

    cart_ids = request.form.getlist("cart_ids")
    quantities = request.form.getlist("quantities")
    payment_method = request.form.get("payment_method")
    latitude = request.form.get("latitude")
    longitude = request.form.get("longitude")

    if not cart_ids or not payment_method:
        flash("Incomplete checkout data.", "error")
        return redirect(url_for("cart"))

    if not latitude or not longitude:
        flash("Please pin your delivery location before completing checkout.", "error")
        return redirect(url_for("checkout"))

    try:
        qty_dict = {int(cid): int(qty) for cid, qty in zip(cart_ids, quantities)}
    except ValueError:
        flash("Invalid quantity value.", "error")
        return redirect(url_for("cart"))

    # Get a human-readable address from the pinned coordinates (same for all items in this checkout)
    address = get_address_from_coords(latitude, longitude)

    conn = get_db_connection()
    cursor = conn.cursor()

    for cart_id in cart_ids:
        qty = qty_dict.get(int(cart_id), 1)

        cursor.execute("SELECT product_id, variant_id FROM cart WHERE id=%s AND user_id=%s",
                       (cart_id, session["user_id"]))
        row = cursor.fetchone()
        if not row:
            continue

        product_id, variant_id = row

        cursor.execute("SELECT image_url, stock FROM product_variants WHERE id=%s", (variant_id,))
        variant_row = cursor.fetchone()
        if not variant_row:
            continue

        image_full = variant_row[0] or None
        image_filename = image_full.split('/')[-1] if image_full else None
        current_stock = variant_row[1]

        if current_stock < qty:
            flash(f"Not enough stock for product variant {variant_id}. Available: {current_stock}", "error")
            continue

        # Insert order with location + resolved address
        cursor.execute("""
            INSERT INTO orders (buyer_id, product_id, variant_id, image_url, quantity,
                                payment_method, status, latitude, longitude, address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (session["user_id"], product_id, variant_id, image_filename, qty,
              payment_method, "pending", latitude, longitude, address))

        cursor.execute("UPDATE product_variants SET stock = stock - %s WHERE id=%s", (qty, variant_id))
        cursor.execute("DELETE FROM cart WHERE id=%s AND user_id=%s", (cart_id, session["user_id"]))

    conn.commit()
    conn.close()

    flash("Payment submitted! Your delivery location has been saved.", "success")
    return redirect(url_for("my_orders"))
@app.route("/api/complete_payment", methods=["POST"])
def api_complete_payment():
    data = request.get_json()

    print("=== RAW REQUEST ===")
    print(data)

    if not data:
        return jsonify({
            "success": False,
            "message": "No JSON received"
        }), 400

    user_id = data.get("user_id")
    items = data.get("items", [])
    payment_method = data.get("payment_method", "cod")
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    print("user_id:", user_id)
    print("items:", items)

    # ================= VALIDATION =================
    if not user_id:
        return jsonify({
            "success": False,
            "message": "Missing user_id"
        }), 400

    if not items:
        return jsonify({
            "success": False,
            "message": "No checkout items"
        }), 400

    if latitude is None or longitude is None:
        return jsonify({
            "success": False,
            "message": "Missing delivery location"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # ================= ADDRESS =================
    try:
        address = get_address_from_coords(latitude, longitude)
        if not address:
            address = f"{latitude}, {longitude}"
    except Exception as e:
        print("Address lookup failed:", e)
        address = f"{latitude}, {longitude}"

    # ================= SHIPPING FEE =================
    shipping_fee = 50

    # ================= PROCESS ITEMS =================
    for item in items:

        print("PROCESSING ITEM:", item)

        cart_id = item.get("cart_id")
        product_id = item.get("product_id")
        variant_id = item.get("variant_id")
        qty = int(item.get("quantity", 1))
        image = item.get("image_url")

        # ---------- VALIDATE ----------
        if not product_id:
            conn.close()
            return jsonify({
                "success": False,
                "message": "Missing product_id"
            }), 400

        if not variant_id:
            conn.close()
            return jsonify({
                "success": False,
                "message": f"Missing variant_id for product {product_id}"
            }), 400

        # ---------- CHECK STOCK ----------
        cursor.execute("""
            SELECT stock
            FROM product_variants
            WHERE id=%s
        """, (variant_id,))

        stock_row = cursor.fetchone()

        if not stock_row:
            conn.close()
            return jsonify({
                "success": False,
                "message": f"Variant not found: {variant_id}"
            }), 400

        current_stock = stock_row[0]

        if current_stock < qty:
            conn.close()
            return jsonify({
                "success": False,
                "message": f"Not enough stock for variant {variant_id}"
            }), 400

        # ---------- INSERT ORDER ----------
        cursor.execute("""
            INSERT INTO orders
            (
                buyer_id,
                product_id,
                variant_id,
                image_url,
                quantity,
                payment_method,
                shipping_fee,
                status,
                latitude,
                longitude,
                address
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            user_id,
            product_id,
            variant_id,
            image,
            qty,
            payment_method,
            shipping_fee,
            "pending",
            latitude,
            longitude,
            address
        ))

        # ---------- REDUCE STOCK ----------
        cursor.execute("""
            UPDATE product_variants
            SET stock = stock - %s
            WHERE id=%s
        """, (qty, variant_id))

        # ---------- REMOVE FROM CART ----------
        if cart_id:
            cursor.execute("""
                DELETE FROM cart
                WHERE id=%s AND user_id=%s
            """, (cart_id, user_id))

    # ================= SAVE =================
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Order placed successfully",
        "shipping_fee": shipping_fee,
        "delivery_address": address
    })

@app.route('/view_delivery_location/<int:order_id>')
def view_delivery_location(order_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT o.id AS order_id, o.latitude, o.longitude, o.address,
               p.name AS product_name, u.username AS buyer_name
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN users u ON o.buyer_id = u.id
        WHERE o.id = %s
    """
    cursor.execute(query, (order_id,))
    order = cursor.fetchone()

    cursor.close()
    conn.close()

    if not order:
        flash("Order not found.", "danger")
        return redirect(url_for('rider_dashboard'))

    if not order['latitude'] or not order['longitude']:
        flash("This order doesn't have location data.", "warning")
        return redirect(url_for('rider_dashboard'))

    return render_template('view_delivery_location.html', order=order)



@app.route("/admin/purchases")
def admin_purchases():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            p.id,
            p.name,
            u.username AS seller_name,
            p.total_purchases,
            COUNT(DISTINCT o.buyer_id) AS unique_buyers,
            p.is_featured
        FROM products p
        JOIN users u ON p.user_id = u.id
        JOIN orders o ON p.id = o.product_id
        WHERE o.status = 'approved' AND p.is_deleted = 0
        GROUP BY p.id, p.name, u.username, p.total_purchases, p.is_featured
        ORDER BY p.total_purchases DESC
    """)
    products = cursor.fetchall()
    conn.close()

    return render_template("admin_purchases.html", products=products)



@app.route("/order_now/<int:product_id>/<int:variant_id>", methods=["POST"])
def order_now(product_id, variant_id):
    if "user_id" not in session:
        flash("Please login to order.", "error")
        return redirect(url_for("login"))

    quantity = request.form.get("quantity", 1)
    try:
        quantity = int(quantity)
        if quantity < 1:
            quantity = 1
    except ValueError:
        quantity = 1

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch product + variant info
    cursor.execute("""
        SELECT p.id AS product_id, p.name AS product_name, p.price,
               v.id AS variant_id, v.color, v.image_url, v.stock
        FROM products p
        JOIN product_variants v ON v.id=%s
        WHERE p.id=%s
    """, (variant_id, product_id))
    item = cursor.fetchone()
    conn.close()

    if not item:
        flash("Product not found.", "error")
        return redirect(url_for("index"))

    # Store the single-item order in session for checkout
    session["order_now"] = {
        "product_id": item["product_id"],
        "variant_id": item["variant_id"],
        "quantity": quantity,
        "image_url": item["image_url"].split('/')[-1] if item["image_url"] else None,
        "price": item["price"],
        "color": item["color"],
        "product_name": item["product_name"]
    }

    return redirect(url_for("checkout_now"))



@app.route("/checkout_order_now", methods=["GET", "POST"])
def checkout_order_now():
    if "user_id" not in session:
        flash("Please login to checkout.", "error")
        return redirect(url_for("login"))

    order_item = session.get('order_now_item')
    if not order_item:
        flash("No item to checkout.", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT p.id AS product_id, p.name AS product_name, p.price,
               v.id AS variant_id, v.color, v.stock, v.image_url
        FROM products p
        JOIN product_variants v ON v.product_id = p.id
        WHERE p.id=%s AND v.id=%s
    """, (order_item['product_id'], order_item['variant_id']))
    item = cursor.fetchone()
    conn.close()

    if item:
        item['quantity'] = order_item['quantity']

    return render_template("checkout.html", items=[item])


@app.route("/cart")
def cart():
    if "user_id" not in session:
        flash("Please login to view your cart.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Remove cart items where the product is deleted or missing
    cursor.execute("""
        DELETE c
        FROM cart c
        LEFT JOIN products p ON c.product_id = p.id
        WHERE c.user_id=%s AND (p.id IS NULL OR p.is_deleted=1)
    """, (user_id,))
    conn.commit()

    # Fetch remaining cart items
    cursor.execute("""
        SELECT c.id as cart_id, c.quantity, p.name, p.price, v.color, v.stock, v.image_url
        FROM cart c
        JOIN products p ON c.product_id = p.id
        JOIN product_variants v ON c.variant_id = v.id
        WHERE c.user_id=%s
    """, (user_id,))
    items = cursor.fetchall()
    conn.close()

    return render_template("cart.html", items=items)

@app.route("/api/cart", methods=["GET"])
def api_cart():
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({
            "success": False,
            "message": "Missing user_id"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 🧹 Clean invalid cart items
        cursor.execute("""
            DELETE c
            FROM cart c
            LEFT JOIN products p ON c.product_id = p.id
            WHERE c.user_id=%s
            AND (p.id IS NULL OR p.is_deleted=1)
        """, (user_id,))
        conn.commit()

        # 🛒 Get ONLY THIS USER'S CART
        cursor.execute("""
    SELECT 
        c.id as cart_id,
        c.quantity,
        p.id as product_id,
        p.name,
        p.price,
        v.id as variant_id,   -- ✅ THIS WAS MISSING
        v.color,
        v.stock,
        v.image_url
    FROM cart c
    JOIN products p ON c.product_id = p.id
    JOIN product_variants v ON c.variant_id = v.id
    WHERE c.user_id=%s
    ORDER BY c.id DESC
""", (user_id,))

        items = cursor.fetchall()

        return jsonify({
            "success": True,
            "items": items
        })

    finally:
        conn.close()

@app.route("/remove_from_cart/<int:cart_id>")
def remove_from_cart(cart_id):
    if "user_id" not in session:
        flash("Please login first.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM cart WHERE id=%s AND user_id=%s", (cart_id, session["user_id"]))
    conn.commit()
    conn.close()

    flash("Item removed from cart.", "info")
    return redirect(url_for("cart"))


@app.route("/send_message/<int:product_id>/<int:seller_id>", methods=["POST"])
def send_message(product_id, seller_id):
    if "user_id" not in session:
        flash("Please login to send messages.", "error")
        return redirect(url_for("login"))

    message = request.form["message"]
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO messages (product_id, sender_id, receiver_id, message)
        VALUES (%s, %s, %s, %s)
    """, (product_id, session["user_id"], seller_id, message))
    conn.commit()
    conn.close()

    flash("Message sent to seller!", "success")
    return redirect(url_for("product_detail", product_id=product_id))

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch product
    cursor.execute("""
        SELECT p.*, u.username, u.id AS seller_id
        FROM products p
        JOIN users u ON p.user_id = u.id
        WHERE p.id = %s
    """, (product_id,))
    product = cursor.fetchone()

    if not product:
        conn.close()
        flash("Product not found.", "error")
        return redirect(url_for("index"))

    # Fetch product variants
    cursor.execute("""
        SELECT id, color, stock, image_url
        FROM product_variants
        WHERE product_id = %s
    """, (product_id,))
    variants = cursor.fetchall()

    # ✅ Fetch reviews for this product
    cursor.execute("""
        SELECT r.rating, r.comment, r.created_at, u.username
        FROM reviews r
        JOIN users u ON r.buyer_id = u.id
        WHERE r.product_id = %s
        ORDER BY r.created_at DESC
    """, (product_id,))
    reviews = cursor.fetchall()

    # ✅ Compute average rating
    avg_rating = round(sum([r["rating"] for r in reviews]) / len(reviews), 1) if reviews else None

    # ✅ Check if current user can leave a review
    can_review = False
    eligible_order_id = None
    if "user_id" in session:
        cursor.execute("""
            SELECT o.id
            FROM orders o
            WHERE o.buyer_id = %s
              AND o.product_id = %s
              AND o.delivery_status = 'delivered'
              AND NOT EXISTS (
                  SELECT 1 FROM reviews r
                  WHERE r.order_id = o.id AND r.buyer_id = %s
              )
            LIMIT 1
        """, (session["user_id"], product_id, session["user_id"]))
        order = cursor.fetchone()
        if order:
            can_review = True
            eligible_order_id = order["id"]

    conn.close()

    return render_template(
        "product_detail.html",
        product=product,
        variants=variants,
        reviews=reviews,
        avg_rating=avg_rating,
        can_review=can_review,
        eligible_order_id=eligible_order_id
    )

@app.route("/api/product/<int:product_id>")
def api_product_detail(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # PRODUCT INFO
    cursor.execute("""
        SELECT p.*, u.username, u.id AS seller_id
        FROM products p
        JOIN users u ON p.user_id = u.id
        WHERE p.id = %s
    """, (product_id,))
    product = cursor.fetchone()

    if not product:
        conn.close()
        return jsonify({"success": False, "message": "Product not found"}), 404

    # VARIANTS
    cursor.execute("""
        SELECT id, color, stock, image_url
        FROM product_variants
        WHERE product_id = %s
    """, (product_id,))
    variants = cursor.fetchall()

    # REVIEWS
    cursor.execute("""
        SELECT r.rating, r.comment, r.created_at, u.username
        FROM reviews r
        JOIN users u ON r.buyer_id = u.id
        WHERE r.product_id = %s
        ORDER BY r.created_at DESC
    """, (product_id,))
    reviews = cursor.fetchall()

    # AVG RATING
    avg_rating = None
    if reviews:
        avg_rating = round(sum(r["rating"] for r in reviews) / len(reviews), 1)

    # BASE URL
    BASE_URL = "https://web-production-1592e.up.railway.app"

    # FIX PRODUCT IMAGE
    cursor.execute("""
        SELECT image_url
        FROM product_variants
        WHERE product_id = %s
        LIMIT 1
    """, (product_id,))
    img = cursor.fetchone()

    image_url = None
    if img and img["image_url"]:
        image_url = img["image_url"].lstrip("/")
        if not image_url.startswith("http"):
            image_url = f"{BASE_URL}/{image_url}"

    product["image_url"] = image_url

    conn.close()

    return jsonify({
        "success": True,
        "product": product,
        "variants": variants,
        "reviews": reviews,
        "avg_rating": avg_rating
    })

@app.route("/api/products", methods=["GET"])
def api_products():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            p.id,
            p.name,
            p.description,
            p.price,
            u.username AS seller_name
        FROM products p
        JOIN users u ON p.user_id = u.id
        WHERE p.is_deleted = 0
        ORDER BY p.id DESC
    """)

    products = cursor.fetchall()

    BASE_URL = "https://web-production-1592e.up.railway.app"

    for p in products:
        # get FIRST variant image (your real image source)
        cursor.execute("""
            SELECT image_url
            FROM product_variants
            WHERE product_id = %s
              AND image_url IS NOT NULL
            LIMIT 1
        """, (p["id"],))

        variant = cursor.fetchone()

        image_url = None
        if variant and variant["image_url"]:
            image_url = variant["image_url"]

        # fix URL
        if image_url:
            image_url = image_url.lstrip("/")  # remove leading slash
            if not image_url.startswith("http"):
                image_url = f"{BASE_URL}/{image_url}"

        p["image_url"] = image_url

    conn.close()

    return jsonify({
        "success": True,
        "products": products
    })

@app.route("/chat/<int:product_id>/<int:other_user_id>", methods=["GET", "POST"])
def chat(product_id, other_user_id):
    if "user_id" not in session:
        flash("Please login to access chat.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get product info
    cursor.execute("SELECT * FROM products WHERE id=%s", (product_id,))
    product = cursor.fetchone()

    # Fetch conversation between logged in user and other user
    cursor.execute("""
        SELECT m.*, u.username AS sender_name
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        WHERE m.product_id=%s 
          AND ((m.sender_id=%s AND m.receiver_id=%s) OR (m.sender_id=%s AND m.receiver_id=%s))
        ORDER BY m.created_at ASC
    """, (product_id, session["user_id"], other_user_id, other_user_id, session["user_id"]))
    messages = cursor.fetchall()

    if request.method == "POST":
        msg = request.form["message"]
        cursor.execute("""
            INSERT INTO messages (product_id, sender_id, receiver_id, message)
            VALUES (%s, %s, %s, %s)
        """, (product_id, session["user_id"], other_user_id, msg))
        conn.commit()
        return redirect(url_for("chat", product_id=product_id, other_user_id=other_user_id))

    conn.close()
    return render_template("chat.html", product=product, messages=messages, other_user_id=other_user_id)




@app.route("/seller_dashboard")
def seller_dashboard():
    # Ensure the user is logged in as a seller
    if "user_id" not in session or not session.get("is_seller"):
        flash("You must be a seller to access this page.", "error")
        return redirect(url_for("index"))

    selected_category = request.args.get("category")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 🟢 Fetch the seller's store name
    cursor.execute("SELECT store_name FROM users WHERE id = %s", (session["user_id"],))
    seller = cursor.fetchone()
    store_name = seller["store_name"] if seller and seller["store_name"] else "Your Store"

    # 🟢 Fetch products (JOIN users for store_name)
    if selected_category:
        cursor.execute("""
            SELECT p.*, u.store_name
            FROM products p
            JOIN users u ON p.user_id = u.id
            WHERE p.user_id=%s AND p.is_deleted=0 AND p.category=%s
            ORDER BY p.name
        """, (session["user_id"], selected_category))
    else:
        cursor.execute("""
            SELECT p.*, u.store_name
            FROM products p
            JOIN users u ON p.user_id = u.id
            WHERE p.user_id=%s AND p.is_deleted=0
            ORDER BY p.category, p.name
        """, (session["user_id"],))
    products = cursor.fetchall()

    out_of_stock_products = []

    # 🟢 Process each product’s variants and stock
    for product in products:
        cursor.execute("SELECT * FROM product_variants WHERE product_id=%s", (product["id"],))
        variants = cursor.fetchall()

        for v in variants:
            v["full_url"] = url_for('static', filename=f'images/{v["image_url"]}') if v.get("image_url") else None

        product["variants"] = variants
        product["image_url"] = next((v["full_url"] for v in variants if v.get("full_url")), None)

        if any(v["stock"] <= 0 for v in variants):
            out_of_stock_products.append(product["id"])

    # 🟢 Fetch chats for this seller’s active products
    cursor.execute("""
        SELECT m.sender_id AS buyer_id, u.username AS buyer_name,
               m.product_id, p.name AS product_name,
               m.message AS last_message, m.created_at AS last_time
        FROM messages m
        JOIN users u ON m.sender_id = u.id
        JOIN products p ON m.product_id = p.id
        WHERE m.receiver_id = %s
          AND p.is_deleted = 0
          AND m.id = (
              SELECT MAX(id) FROM messages 
              WHERE sender_id = m.sender_id 
                AND product_id = m.product_id
                AND receiver_id = %s
          )
        ORDER BY m.created_at DESC
    """, (session["user_id"], session["user_id"]))
    chats = cursor.fetchall()

    conn.close()

    return render_template(
        "seller_dashboard.html",
        products=products,
        chats=chats,
        selected_category=selected_category,
        out_of_stock_products=out_of_stock_products,
        store_name=store_name
    )

from flask import jsonify, request

@app.route("/api/seller/dashboard", methods=["GET"])
def api_seller_dashboard():

    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 🟢 Seller info
    cursor.execute("SELECT store_name FROM users WHERE id = %s", (user_id,))
    seller = cursor.fetchone()
    store_name = seller["store_name"] if seller and seller["store_name"] else "Your Store"

    # 🟢 Products
    cursor.execute("""
        SELECT * FROM products
        WHERE user_id=%s AND is_deleted=0
    """, (user_id,))
    
    products = cursor.fetchall()

    # ✅ ATTACH IMAGE FROM product_variants (IMPORTANT FIX)
    for product in products:
        cursor.execute("""
            SELECT image_url 
            FROM product_variants 
            WHERE product_id=%s AND image_url IS NOT NULL 
            LIMIT 1
        """, (product["id"],))

        variant = cursor.fetchone()

        if variant and variant["image_url"]:
            product["image_url"] = request.host_url + "static/images/" + variant["image_url"]
        else:
            product["image_url"] = ""

    conn.close()

    return jsonify({
        "store_name": store_name,
        "products": products,
        "chats": []
    })

@app.route("/store/<int:seller_id>")
def view_store(seller_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get store info
    cursor.execute("SELECT username, store_name FROM users WHERE id = %s", (seller_id,))
    seller = cursor.fetchone()

    if not seller:
        flash("Store not found.", "error")
        return redirect(url_for("index"))

    # Fetch seller's products
    cursor.execute("""
        SELECT p.*, u.store_name, u.username AS seller_name
        FROM products p
        JOIN users u ON p.user_id = u.id
        WHERE p.user_id = %s AND p.is_deleted = 0
        ORDER BY p.category, p.name
    """, (seller_id,))
    products = cursor.fetchall()

    # Add variant info
    for product in products:
        cursor.execute("SELECT * FROM product_variants WHERE product_id=%s", (product["id"],))
        variants = cursor.fetchall()
        product["variants"] = variants

        if not product.get("image_url"):
            for v in variants:
                if v.get("image_url"):
                    product["image_url"] = v["image_url"]
                    break

    conn.close()

    return render_template("view_store.html", seller=seller, products=products)




@app.route("/add_product", methods=["GET", "POST"])
def add_product():
    if "user_id" not in session or not session.get("is_seller"):
        flash("You must be a seller to add products.", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch seller details (allowed category)
    cursor.execute(
        "SELECT seller_category FROM users WHERE id = %s",
        (session["user_id"],)
    )
    seller = cursor.fetchone()

    if not seller:
        flash("Seller not found.", "error")
        conn.close()
        return redirect(url_for("index"))

    allowed_category = seller["seller_category"]

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]
        category = request.form["category"]

        # ✅ Validate category
        if category != allowed_category:
            flash(f"You can only add products in your registered category: {allowed_category}.", "error")
            conn.close()
            return redirect(url_for("add_product"))

        variant_colors = request.form.getlist("variant_color[]")
        variant_stocks = request.form.getlist("variant_stock[]")
        variant_images = request.files.getlist("variant_image[]")

        # ✅ Insert main product (no store_name)
        cursor.execute(
            """
            INSERT INTO products (user_id, name, description, price, category)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (session["user_id"], name, description, price, category)
        )
        product_id = cursor.lastrowid

        # ✅ Insert variants
        for i, (color, stock) in enumerate(zip(variant_colors, variant_stocks)):
            image_file = variant_images[i] if i < len(variant_images) else None
            image_url = None

            if image_file and image_file.filename:
                filename = save_image(image_file)  # your existing image save function
                image_url = filename

            cursor.execute(
                "INSERT INTO product_variants (product_id, color, stock, image_url) VALUES (%s, %s, %s, %s)",
                (product_id, color, stock, image_url)
            )

        conn.commit()
        conn.close()

        flash("Product added successfully!", "success")
        return redirect(url_for("seller_dashboard"))

    conn.close()
    return render_template("add_product.html", allowed_category=allowed_category)



@app.route("/variant_stock/<int:variant_id>")
def variant_stock(variant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT stock, image_url, price FROM product_variants WHERE id=%s", (variant_id,))
    variant = cursor.fetchone()
    conn.close()

    if variant:
        return jsonify({
            "stock": variant["stock"],
            "image_url": variant["image_url"],
            "price": variant["price"]
        })
    return jsonify({"error": "Variant not found"}), 404

@app.route("/api/variant_stock/<int:variant_id>", methods=["GET"])
def api_variant_stock(variant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT stock, image_url
            FROM product_variants
            WHERE id = %s
        """, (variant_id,))
        
        variant = cursor.fetchone()

        if not variant:
            return jsonify({
                "success": False,
                "message": "Variant not found"
            }), 404

        return jsonify({
            "success": True,
            "stock": variant["stock"],
            "image_url": variant["image_url"]
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:
        conn.close()

@app.route("/api/product_variants/<int:product_id>", methods=["GET"])
def get_product_variants(product_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT id, color, stock, image_url
        FROM product_variants
        WHERE product_id = %s
    """, (product_id,))

    variants = cursor.fetchall()
    conn.close()

    return jsonify({
        "success": True,
        "variants": variants
    })

@app.route("/seller/edit_product/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    if "user_id" not in session or not session.get("is_seller"):
        flash("Only sellers can edit products.", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get the seller's category (from users table)
    cursor.execute("SELECT seller_category FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()
    allowed_category = user["seller_category"] if user else None

    # Get main product
    cursor.execute("SELECT * FROM products WHERE id=%s AND user_id=%s", (product_id, session["user_id"]))
    product = cursor.fetchone()

    if not product:
        conn.close()
        flash("Product not found or not yours.", "error")
        return redirect(url_for("seller_dashboard"))

    # Get product variants
    cursor.execute("SELECT * FROM product_variants WHERE product_id=%s", (product_id,))
    variants = cursor.fetchall()

    if request.method == "POST":
        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]

        # ✅ Always enforce seller_category (don’t take from form)
        category = allowed_category  

        variant_ids = request.form.getlist("variant_id[]")
        variant_colors = request.form.getlist("variant_color[]")
        variant_stocks = request.form.getlist("variant_stock[]")
        variant_files = request.files.getlist("variant_image[]")

        # Delete removed variants
        delete_ids = request.form.getlist("delete_variant_ids[]")
        if delete_ids:
            cursor.execute(
                f"DELETE FROM product_variants WHERE id IN ({','.join(['%s']*len(delete_ids))})",
                tuple(delete_ids)
            )

        # Update main product
        cursor.execute("""
            UPDATE products
            SET name=%s, description=%s, price=%s, category=%s
            WHERE id=%s AND user_id=%s
        """, (name, description, price, category, product_id, session["user_id"]))

        # Update or insert variants
        for i, (vid, color, stock) in enumerate(zip(variant_ids, variant_colors, variant_stocks)):
            file = variant_files[i] if i < len(variant_files) else None

            if file and file.filename:
                filename = save_image(file)
                image_url = filename
            else:
                image_url = None if vid == "new" else variants[i]["image_url"]

            if vid == "new":
                cursor.execute("""
                    INSERT INTO product_variants (product_id, color, stock, image_url)
                    VALUES (%s, %s, %s, %s)
                """, (product_id, color, stock, image_url))
            else:
                cursor.execute("""
                    UPDATE product_variants
                    SET color=%s, stock=%s, image_url=%s
                    WHERE id=%s AND product_id=%s
                """, (color, stock, image_url, vid, product_id))

        conn.commit()
        conn.close()
        flash("Product updated successfully!", "success")
        return redirect(url_for("seller_dashboard"))

    conn.close()
    return render_template("edit_product.html", product=product, variants=variants, allowed_category=allowed_category)

@app.route("/api/seller/edit_product/<int:product_id>", methods=["GET"])
def get_edit_product(product_id):
    if "user_id" not in session or not session.get("is_seller"):
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # GET PRODUCT
    cursor.execute("""
        SELECT * FROM products
        WHERE id=%s AND user_id=%s
    """, (product_id, session["user_id"]))
    product = cursor.fetchone()

    if not product:
        conn.close()
        return jsonify({"error": "Product not found"}), 404

    # GET VARIANTS
    cursor.execute("""
        SELECT * FROM product_variants
        WHERE product_id=%s
    """, (product_id,))
    variants = cursor.fetchall()

    # GET SELLER CATEGORY
    cursor.execute("""
        SELECT seller_category FROM users WHERE id=%s
    """, (session["user_id"],))
    user = cursor.fetchone()

    conn.close()

    return jsonify({
        "product": product,
        "variants": variants,
        "allowed_category": user["seller_category"] if user else ""
    })


@app.route("/api/seller/edit_product/<int:product_id>", methods=["GET", "POST"])
def api_edit_product(product_id):

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ================= GET =================
    if request.method == "GET":

        user_id = request.args.get("user_id")

        if not user_id:
            conn.close()
            return jsonify({"error": "Missing user_id"}), 401

        cursor.execute("""
            SELECT * FROM products
            WHERE id=%s AND user_id=%s
        """, (product_id, user_id))
        product = cursor.fetchone()

        if not product:
            conn.close()
            return jsonify({"error": "Product not found"}), 404

        cursor.execute("""
            SELECT * FROM product_variants
            WHERE product_id=%s
        """, (product_id,))
        variants = cursor.fetchall()

        conn.close()

        return jsonify({
            "product": product,
            "variants": variants,
            "allowed_category": product["category"]
        })

    # ================= POST =================
    if request.method == "POST":

        user_id = request.form.get("user_id")

        if not user_id:
            conn.close()
            return jsonify({"error": "Missing user_id"}), 401

        cursor.execute("""
            SELECT * FROM products
            WHERE id=%s AND user_id=%s
        """, (product_id, user_id))
        product = cursor.fetchone()

        if not product:
            conn.close()
            return jsonify({"error": "Product not found"}), 404

        name = request.form.get("name")
        description = request.form.get("description")
        price = request.form.get("price")

        variant_ids = request.form.getlist("variant_id[]")
        colors = request.form.getlist("variant_color[]")
        stocks = request.form.getlist("variant_stock[]")

        cursor.execute("""
            UPDATE products
            SET name=%s, description=%s, price=%s
            WHERE id=%s AND user_id=%s
        """, (name, description, price, product_id, user_id))

        files = request.files.getlist("variant_image[]")

        for i in range(len(colors)):
            vid = variant_ids[i]
            color = colors[i]
            stock = stocks[i]
            file = files[i] if i < len(files) else None

            image_url = None
            if file and file.filename:
                image_url = save_image(file)

            if vid == "new":
                cursor.execute("""
                    INSERT INTO product_variants
                    (product_id, color, stock, image_url)
                    VALUES (%s, %s, %s, %s)
                """, (product_id, color, stock, image_url))
            else:
                if image_url:
                    cursor.execute("""
                        UPDATE product_variants
                        SET color=%s, stock=%s, image_url=%s
                        WHERE id=%s AND product_id=%s
                    """, (color, stock, image_url, vid, product_id))
                else:
                    cursor.execute("""
                        UPDATE product_variants
                        SET color=%s, stock=%s
                        WHERE id=%s AND product_id=%s
                    """, (color, stock, vid, product_id))

        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "Updated successfully"})
@app.route("/seller/delete_product/<int:product_id>")
def delete_product(product_id):
    if "user_id" not in session or not session.get("is_seller"):
        flash("Only sellers can delete products.", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Check if product has ongoing orders
    cursor.execute("UPDATE products SET is_deleted=1, is_featured=0 WHERE id=%s", (product_id,))

    cursor.execute("""
        SELECT COUNT(*) AS count
        FROM orders
        WHERE product_id=%s
          AND status IN ('pending', 'approved')
    """, (product_id,))
    result = cursor.fetchone()

    if result["count"] > 0:
        flash("Cannot delete this product. There are ongoing orders.", "error")
        conn.close()
        return redirect(url_for("seller_dashboard"))

    # Soft delete → mark product as archived
    cursor.execute("""
        UPDATE products
        SET is_deleted = 1
        WHERE id=%s AND user_id=%s
    """, (product_id, session["user_id"]))

    conn.commit()
    conn.close()

    flash("Product archived successfully!", "success")
    return redirect(url_for("seller_dashboard"))

@app.route("/apply_seller", methods=["GET", "POST"])
def apply_seller():
    if "user_id" not in session or session.get("role") != "user":
        flash("Only normal users can apply to become sellers.", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch current user info
    cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()

    # ✅ Check if profile info is complete
    if not user["email"] or not user["address"] or not user["phone"]:
        conn.close()
        flash("Please complete your profile (email, address, phone) before applying as a seller.", "error")
        return redirect(url_for("profile"))

    if request.method == "POST":
        email = request.form["email"]
        address = request.form["address"]
        phone = request.form["phone"]
        store_name = request.form["store_name"]
        product_genre = request.form["product_genre"]

        # Insert new seller application
        cursor.execute("""
            INSERT INTO seller_applications 
            (user_id, email, address, phone, store_name, product_genre, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
        """, (session["user_id"], email, address, phone, store_name, product_genre))
        conn.commit()
        conn.close()

        flash("Your application has been submitted. Please wait for admin approval.", "success")
        return redirect(url_for("profile"))

    conn.close()
    return render_template("apply_seller.html", user=user)

@app.route("/admin_dashboard")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied. Admins only.", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch seller applications, excluding rejected ones
    cursor.execute("""
        SELECT sa.id, u.username, u.email, sa.store_name, sa.product_genre, sa.status
        FROM seller_applications sa
        JOIN users u ON sa.user_id = u.id
        WHERE sa.status != 'rejected'
    """)
    applications = cursor.fetchall()
    conn.close()

    return render_template("admin_dashboard.html", applications=applications)

@app.route("/api/admin_dashboard", methods=["GET"])
def api_admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        return jsonify({
            "success": False,
            "message": "Access denied. Admins only."
        }), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT sa.id, u.username, u.email,
                   sa.store_name, sa.product_genre, sa.status
            FROM seller_applications sa
            JOIN users u ON sa.user_id = u.id
            WHERE sa.status != 'rejected'
        """)

        applications = cursor.fetchall()
        conn.close()

        return jsonify({
            "success": True,
            "applications": applications
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route("/admin/approve/<int:app_id>")
def approve_seller(app_id):
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied. Admins only.", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get user_id of the application
    cursor.execute("SELECT user_id FROM seller_applications WHERE id=%s", (app_id,))
    app = cursor.fetchone()

    if app:
        user_id = app[0]
        cursor.execute("UPDATE users SET is_seller=1 WHERE id=%s", (user_id,))
        cursor.execute("UPDATE seller_applications SET status='approved' WHERE id=%s", (app_id,))
        conn.commit()
        flash("Seller approved successfully!", "success")
    else:
        flash("Application not found.", "error")

    conn.close()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/reject/<int:app_id>")
def reject_seller(app_id):
    if "user_id" not in session or session.get("role") != "admin":
        flash("Access denied. Admins only.", "error")
        return redirect(url_for("index"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE seller_applications SET status='rejected' WHERE id=%s", (app_id,))
    conn.commit()
    conn.close()
    flash("Seller application rejected.", "info")
    return redirect(url_for("admin_dashboard"))

@app.route("/check_current_password")
def check_current_password():
    if "user_id" not in session:
        return {"valid": False}  # Not logged in

    current_password = request.args.get("current_password", "")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT password FROM users WHERE id=%s", (session["user_id"],))
    user_data = cursor.fetchone()
    conn.close()

    if user_data and user_data["password"] == current_password:
        return {"valid": True}
    return {"valid": False}
def get_location_name(code, level='region'):
    if not code:
        return ''
    url = f"https://psgc.gitlab.io/api/{level}s/{code}/"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            return data.get('name', code)
    except:
        pass
    return code
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        flash("Please log in to access profile.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()

    if not user:
        flash("User not found.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        # --- Upload new profile image ---
        if "upload_image" in request.form:
            file = request.files.get("profile_image")
            if not file or file.filename == "":
                flash("No file selected.", "error")
            else:
                upload_dir = "static/images"
                os.makedirs(upload_dir, exist_ok=True)
                ext = os.path.splitext(file.filename)[1]
                filename = f"{uuid.uuid4().hex}{ext}"
                file_path = os.path.join(upload_dir, filename)
                file.save(file_path)

                # Delete old image if exists
                old_image = user.get("profile_picture")
                if old_image and os.path.exists(old_image):
                    try:
                        os.remove(old_image)
                    except Exception as e:
                        print(f"Error removing old image: {e}")

                cursor.execute("UPDATE users SET profile_picture=%s WHERE id=%s",
                               (file_path, session["user_id"]))
                conn.commit()
                flash("Profile image updated!", "success")
                return redirect(url_for("profile"))

        # --- Remove profile image ---
        elif "remove_image" in request.form:
            old_image = user.get("profile_picture")
            if old_image:
                if os.path.exists(old_image):
                    try:
                        os.remove(old_image)
                    except Exception as e:
                        print(f"Error removing image file: {e}")
            web_path = f"/static/images/{filename}"

            cursor.execute(
                "UPDATE users SET profile_picture=%s WHERE id=%s",
                (web_path, session["user_id"])
            )
            conn.commit()
            flash("Profile image removed!", "success")
            return redirect(url_for("profile"))

    conn.close()

    # Map PSGC codes to names
    user['region_name'] = get_location_name(user.get('region'), 'region')
    user['province_name'] = get_location_name(user.get('province'), 'province')
    user['municipality_name'] = get_location_name(user.get('municipality'), 'municipality')
    user['barangay_name'] = user.get('barangay')

    # **Map DB field to template field**
    user['profile_image'] = user.get('profile_picture')  # <-- key line

    return render_template("profile.html", user=user)

@app.route("/api/profile", methods=["GET"])
def api_profile():
    user_id = request.args.get("user_id")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    conn.close()

    if not user:
        return jsonify({
            "success": False,
            "message": "User not found"
        }), 404

    user['region_name'] = get_location_name(user.get('region'), 'region')
    user['province_name'] = get_location_name(user.get('province'), 'province')
    user['municipality_name'] = get_location_name(user.get('municipality'), 'municipality')
    user['barangay_name'] = user.get('barangay')
    user['profile_image'] = user.get('profile_picture')

    return jsonify({
        "success": True,
        "user": user
    })

from flask import jsonify, session, request
import os
import uuid

@app.route("/api/profile", methods=["GET"])
def api_get_profile():
    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Not logged in"
        }), 401

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE id=%s", (session["user_id"],))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({
            "success": False,
            "message": "User not found"
        }), 404

    # Map location names (same logic as your web)
    user["region_name"] = get_location_name(user.get("region"), "region")
    user["province_name"] = get_location_name(user.get("province"), "province")
    user["municipality_name"] = get_location_name(user.get("municipality"), "municipality")
    user["barangay_name"] = user.get("barangay")

    # Fix image field for Flutter
    user["profile_image"] = user.get("profile_picture")

    return jsonify({
        "success": True,
        "user": user
    }), 200

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        import os, uuid, re

        # -----------------------------
        # Names
        # -----------------------------
        lastname = request.form["lastname"]
        firstname = request.form["firstname"]
        middlename = request.form["middlename"]

        # -----------------------------
        # Email & OTP
        # -----------------------------
        email = request.form["email"]
        otp_input = request.form["otp"]

        # -----------------------------
        # Optional phone
        # -----------------------------
        phone_number = request.form.get("phone_number", None)

                # -----------------------------
        # Category & Store Name
        # -----------------------------
        category = request.form["category"]
        seller_category = request.form.get("seller_category")  
        store_name = request.form.get("store_name")  # NEW

        if category == "user":
            role = "user"
            is_seller = 0
        elif category == "rider":
            role = "rider"
            is_seller = 0
        elif category == "seller":
            role = "user"
            is_seller = 1
            if not seller_category:
                flash("Seller must select a product category.", "error")
                return redirect(url_for("register"))
            if not store_name or store_name.strip() == "":
                flash("Seller must provide a store name.", "error")
                return redirect(url_for("register"))
        else:
            role = "user"
            is_seller = 0

        # -----------------------------
        # Password
        # -----------------------------
        password = request.form["password"]

        # -----------------------------
        # Location
        # -----------------------------
        region = request.form["region"]
        province = request.form["province"]
        municipality = request.form["municipality"]
        barangay = request.form["barangay"]
        street_name = request.form["street_name"]
        house_number = request.form["house_number"]

        # -----------------------------
        # Save uploads
        # -----------------------------
        upload_dir = "static/images"
        os.makedirs(upload_dir, exist_ok=True)

        def save_file(file):
            if file and file.filename != "":
                ext = os.path.splitext(file.filename)[1]
                filename = f"{uuid.uuid4().hex}{ext}"
                file.save(os.path.join(upload_dir, filename))
                return filename
            return None

        profile_filename = save_file(request.files.get("profile_picture"))

        uploaded_docs = {}
        if category == "user":
            uploaded_docs['valid_id'] = save_file(request.files.get("valid_id"))
            if not uploaded_docs['valid_id']:
                flash("Valid ID is required!", "error")
                return redirect(url_for("register"))
        elif category == "seller":
            uploaded_docs['valid_id'] = save_file(request.files.get("valid_id"))
            uploaded_docs['business_permit'] = save_file(request.files.get("business_permit"))
            if not uploaded_docs['valid_id'] or not uploaded_docs['business_permit']:
                flash("Valid ID and Business Permit are required!", "error")
                return redirect(url_for("register"))
        elif category == "rider":
            uploaded_docs['driver_license'] = save_file(request.files.get("driver_license"))
            uploaded_docs['motor_registration'] = save_file(request.files.get("motor_registration"))
            uploaded_docs['ocr_image'] = save_file(request.files.get("ocr_image"))
            if not all(uploaded_docs.values()):
                flash("All rider documents are required!", "error")
                return redirect(url_for("register"))

        # -----------------------------
        # Verify OTP
        # -----------------------------
        if session.get("otp") != otp_input or session.get("otp_email") != email:
            flash("Invalid OTP!", "error")
            return redirect(url_for("register"))

        # -----------------------------
        # Validate password
        # -----------------------------
        errors = []
        if len(password) < 7: errors.append("Password must be at least 7 characters.")
        if not re.search(r"[A-Z]", password): errors.append("Password must contain an uppercase letter.")
        if not re.search(r"\d", password): errors.append("Password must contain a number.")
        if errors:
            for e in errors: flash(e, "error")
            return redirect(url_for("register"))

        # -----------------------------
        # Save to DB
        # -----------------------------
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Check email
        cursor.execute("SELECT id FROM users WHERE BINARY email=%s", (email,))
        if cursor.fetchone():
            conn.close()
            flash("Email already registered!", "error")
            return redirect(url_for("register"))

        # -----------------------------
        # Generate unique username
        # -----------------------------
        base_username = f"{firstname.lower()}.{lastname.lower()}"
        username = base_username
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
        while cursor.fetchone():
            username = f"{base_username}.{uuid.uuid4().hex[:4]}"
            cursor.execute("SELECT id FROM users WHERE username=%s", (username,))

        try:
            cursor.execute("""
    INSERT INTO users
    (username, lastname, firstname, middlename, email, phone_number, password, role, is_seller,
     region, province, municipality, barangay, street_name, house_number,
     profile_picture, valid_id, business_permit, driver_license, motor_registration, ocr_image,
     seller_category, store_name)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
""", (
    username, lastname, firstname, middlename, email, phone_number, password, role, is_seller,
    region, province, municipality, barangay, street_name, house_number,
    profile_filename,
    uploaded_docs.get('valid_id'),
    uploaded_docs.get('business_permit'),
    uploaded_docs.get('driver_license'),
    uploaded_docs.get('motor_registration'),
    uploaded_docs.get('ocr_image'),
    seller_category,
    store_name  # NEW
))

            
            conn.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
        finally:
            conn.close()

    return render_template("register.html")

@app.route("/api/register", methods=["POST"])
def api_register():

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ================= FORM DATA =================
    lastname = request.form["lastname"]
    firstname = request.form["firstname"]
    middlename = request.form.get("middlename", "")

    email = request.form["email"]
    password = request.form["password"]
    phone_number = request.form.get("phone")

    category = request.form["category"]
    seller_category = request.form.get("seller_category")
    store_name = request.form.get("store_name")

    # ================= FILES =================
    profile_picture = request.files.get("profile_picture")
    valid_id = request.files.get("valid_id")
    business_permit = request.files.get("business_permit")
    driver_license = request.files.get("driver_license")
    motor_registration = request.files.get("motor_registration")
    ocr_image = request.files.get("ocr_image")

    # ================= ROLE LOGIC =================
    if category == "seller":
        role = "user"
        is_seller = 1
        category_db = "seller"

    elif category == "rider":
        role = "rider"
        is_seller = 0
        category_db = "rider"

    else:
        role = "user"
        is_seller = 0
        category_db = "user"

    # ================= CHECK EMAIL =================
    cursor.execute(
        "SELECT id FROM users WHERE BINARY email=%s",
        (email,)
    )

    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "message": "Email already exists"}), 400

    # ================= USERNAME =================
    import uuid
    import os
    from werkzeug.utils import secure_filename

    base_username = f"{firstname.lower()}.{lastname.lower()}"
    username = base_username

    cursor.execute("SELECT id FROM users WHERE username=%s", (username,))
    while cursor.fetchone():
        username = f"{base_username}.{uuid.uuid4().hex[:4]}"
        cursor.execute("SELECT id FROM users WHERE username=%s", (username,))

    # ================= UPLOAD FOLDER =================
    UPLOAD_FOLDER = "static/images"
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # ================= SAVE FILE FUNCTION =================
    def save_file(file):
        if file:
            ext = os.path.splitext(file.filename)[1]  # .jpg .png
            filename = f"{uuid.uuid4().hex}{ext}"

            path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(path)

            return filename   # ✅ ONLY filename saved in DB

        return ""

    # ================= SAVE FILES =================
    profile_picture_filename = save_file(profile_picture)
    valid_id_filename = save_file(valid_id)
    business_permit_filename = save_file(business_permit)
    driver_license_filename = save_file(driver_license)
    motor_registration_filename = save_file(motor_registration)
    ocr_image_filename = save_file(ocr_image)

    # ================= INSERT USER =================
    cursor.execute("""
        INSERT INTO users (
            username,
            lastname,
            firstname,
            middlename,
            email,
            phone_number,
            password,
            role,
            is_seller,
            category,
            seller_category,
            store_name,
            profile_picture,
            valid_id,
            business_permit,
            driver_license,
            motor_registration,
            ocr_image
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        username,
        lastname,
        firstname,
        middlename,
        email,
        phone_number,
        password,
        role,
        is_seller,
        category_db,
        seller_category,
        store_name,
        profile_picture_filename,
        valid_id_filename,
        business_permit_filename,
        driver_license_filename,
        motor_registration_filename,
        ocr_image_filename
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "User registered successfully"
    })

@app.route("/check_username")
def check_username():
    username = request.args.get("username", "")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM users WHERE BINARY username=%s", (username,))
    exists = cursor.fetchone() is not None
    conn.close()

    return {"available": not exists}

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]  # changed from username
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Use BINARY for case-sensitive comparison
        cursor.execute(
            "SELECT * FROM users WHERE BINARY email=%s AND BINARY password=%s",
            (email, password)
        )

        user = cursor.fetchone()
        conn.close()

        if user:
            # Check if user is approved by admin
            if user["is_approved"] == 0:
                flash("Your account is pending admin approval. Please wait.", "error")
                return redirect(url_for("login"))

            # Set session variables
            session["user_id"] = user["id"]
            session["email"] = user["email"]  # store email instead of username
            session["is_seller"] = user["is_seller"]
            session["role"] = user["role"]
            session["username"] = f"{user['firstname']} {user['lastname']}"  # full name
            flash("Login successful!", "success")

            # Redirect based on role
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            elif user["role"] == "rider":
                return redirect(url_for("rider_dashboard"))
            else:
                return redirect(url_for("index"))
        else:
            flash("Invalid email or password. (Case-sensitive)", "error")

    return render_template("login.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        data = request.get_json()

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({
                "success": False,
                "message": "Missing email or password"
            }), 400

        # ✅ INCLUDE is_seller + role
        cursor.execute("""
            SELECT 
                id,
                email,
                category,
                firstname,
                lastname,
                is_approved,
                username,
                is_seller,
                role,
                store_name,
                profile_picture
            FROM users
            WHERE BINARY email = %s
            AND BINARY password = %s
        """, (email, password))

        user = cursor.fetchone()

        if not user:
            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401

        # ✅ CHECK APPROVAL
        if int(user["is_approved"]) == 0:
            return jsonify({
                "success": False,
                "message": "Account pending admin approval"
            }), 403

        # ✅ FIX PROFILE IMAGE URL
        profile_picture = user.get("profile_picture")

        if profile_picture:
            profile_picture = f"/static/images/{profile_picture}"

        # ✅ RESPONSE
        return jsonify({
            "success": True,
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "email": user["email"],
                "category": user.get("category", ""),
                "username": (
                    user["username"]
                    or f"{user['firstname']} {user['lastname']}".strip()
                ),

                # IMPORTANT
                "is_seller": int(user.get("is_seller", 0)),
                "role": user.get("role", "user"),

                # EXTRA
                "store_name": user.get("store_name", ""),
                "profile_picture": profile_picture
            }
        })

    except Exception as e:
        print("LOGIN ERROR:", e)

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()

def get_user_from_token(request):
    token = request.headers.get("Authorization")

    if not token:
        return None

    return active_tokens.get(token)
@app.route("/admin/user_approvals", methods=["GET", "POST"])
def user_approvals():
    # Only allow admin
    if session.get("role") != "admin":
        flash("Access denied!", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Handle POST actions (Approve / Decline)
    if request.method == "POST":
        user_id = request.form.get("user_id")
        action = request.form.get("action")
        if user_id and action:
            if action == "approve":
                cursor.execute("UPDATE users SET is_approved = 1 WHERE id = %s", (user_id,))
                flash("User approved successfully.", "success")
            elif action == "decline":
                cursor.execute("UPDATE users SET is_approved = -1 WHERE id = %s", (user_id,))
                flash("User declined.", "error")
            conn.commit()
            return redirect(url_for("user_approvals"))

    # Fetch all users pending approval (is_approved = 0)
    cursor.execute("""
        SELECT id, firstname, middlename, lastname, email, role, is_seller,
               seller_category, store_name,
               profile_picture, valid_id, business_permit,
               driver_license, motor_registration, ocr_image
        FROM users
        WHERE is_approved = 0
        ORDER BY id ASC
    """)
    users = cursor.fetchall()
    conn.close()

    return render_template("admin_user_approvals.html", users=users)



@app.route("/admin/create_rider", methods=["GET", "POST"])
def create_rider():
    if "role" not in session or session["role"] != "admin":
        flash("Unauthorized access.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, 'rider')",
                       (username, password))
        conn.commit()
        conn.close()

        flash("Rider account created successfully!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("create_rider.html")

@app.route("/rider/dashboard")
def rider_dashboard():
    if "user_id" not in session or session.get("role") != "rider":
        flash("You must be logged in as a rider.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Available orders (not yet claimed)
    cursor.execute("""
        SELECT o.id AS order_id, o.quantity, o.delivery_status,
               u.username AS buyer_name,
               COALESCE(o.address, u.address) AS address,
               COALESCE(u.phone, u.phone_number) AS phone,
               p.name AS product_name, p.price, o.image_url
        FROM orders o
        JOIN users u ON o.buyer_id = u.id
        JOIN products p ON o.product_id = p.id
        WHERE o.delivery_status = 'ready_for_delivery'
          AND o.rider_id IS NULL
        ORDER BY o.id DESC
    """)
    available_orders = cursor.fetchall()

    # Orders claimed by the logged-in rider (ACTIVE only)
    cursor.execute("""
        SELECT o.id AS order_id, o.quantity, o.delivery_status,
               u.username AS buyer_name,
               COALESCE(o.address, u.address) AS address,
               COALESCE(u.phone, u.phone_number) AS phone,
               p.name AS product_name, p.price, o.image_url
        FROM orders o
        JOIN users u ON o.buyer_id = u.id
        JOIN products p ON o.product_id = p.id
        WHERE o.rider_id = %s
          AND o.delivery_status IN ('out_for_delivery', 'ready_for_delivery')
        ORDER BY o.id DESC
    """, (session["user_id"],))
    my_deliveries = cursor.fetchall()

    conn.close()

    return render_template(
        "rider_dashboard.html",
        available_orders=available_orders,
        my_deliveries=my_deliveries
    )

@app.route("/api/rider/dashboard")
def api_rider_dashboard():

    rider_id = request.args.get("rider_id")

    if not rider_id:
        return jsonify({
            "success": False,
            "message": "Rider ID required"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ================= AVAILABLE ORDERS =================
    cursor.execute("""
        SELECT 
            o.id AS order_id,
            o.quantity,
            o.delivery_status,
            o.address,
            o.latitude,
            o.longitude,
            o.shipping_fee,
            o.image_url,

            u.username AS buyer_name,
            COALESCE(u.phone, u.phone_number) AS phone,

            p.name AS product_name,
            p.price

        FROM orders o

        JOIN users u
            ON o.buyer_id = u.id

        JOIN products p
            ON o.product_id = p.id

        WHERE o.delivery_status = 'ready_for_delivery'
        AND o.rider_id IS NULL

        ORDER BY o.id DESC
    """)

    available_orders = cursor.fetchall()

    # ================= MY DELIVERIES =================
    cursor.execute("""
        SELECT 
            o.id AS order_id,
            o.quantity,
            o.delivery_status,
            o.address,
            o.latitude,
            o.longitude,
            o.shipping_fee,
            o.image_url,

            u.username AS buyer_name,
            COALESCE(u.phone, u.phone_number) AS phone,

            p.name AS product_name,
            p.price

        FROM orders o

        JOIN users u
            ON o.buyer_id = u.id

        JOIN products p
            ON o.product_id = p.id

        WHERE o.rider_id = %s

        AND o.delivery_status IN (
            'ready_for_delivery',
            'out_for_delivery'
        )

        ORDER BY o.id DESC
    """, (rider_id,))

    my_deliveries = cursor.fetchall()

    # ================= IMAGE FIX =================
    BASE = "https://web-production-1592e.up.railway.app"

    for order in available_orders:
        if order["image_url"] and not str(order["image_url"]).startswith("http"):
            order["image_url"] = BASE + str(order["image_url"])

    for order in my_deliveries:
        if order["image_url"] and not str(order["image_url"]).startswith("http"):
            order["image_url"] = BASE + str(order["image_url"])

    conn.close()

    return jsonify({
        "success": True,
        "available_orders": available_orders,
        "my_deliveries": my_deliveries
    })

# ================= FORMAT HELPER =================
def format_dt_human(dt):
    if not dt:
        return ""
    try:
        return dt.strftime("%b %d, %Y - %I:%M %p").lstrip("0").replace(" 0", " ")
    except:
        return str(dt)

app.jinja_env.filters['human_datetime'] = format_dt_human
@app.route("/rider/history")
def rider_history():
    if "user_id" not in session or session.get("role") != "rider":
        flash("You must be logged in as a rider.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Delivered orders for this rider, newest first
    cursor.execute("""
        SELECT o.id AS order_id,
               p.name AS product_name,
               v.color AS variant,
               o.quantity,
               p.price AS unit_price,
               (p.price * o.quantity) AS total_price,
               u.username AS buyer_name,
               o.delivered_at
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN product_variants v ON o.variant_id = v.id
        JOIN users u ON o.buyer_id = u.id
        WHERE o.rider_id = %s
          AND o.delivery_status = 'delivered'
        ORDER BY o.delivered_at DESC
    """, (session["user_id"],))

    history = cursor.fetchall()
    conn.close()

    return render_template("rider_history.html", history=history)


@app.route("/rider/claim/<int:order_id>")
def rider_claim(order_id):
    if "user_id" not in session or session.get("role") != "rider":
        flash("You must be logged in as a rider.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # ✅ Rider just claims it; still in ready_for_delivery state
    cursor.execute("""
        UPDATE orders
        SET rider_id = %s,
            delivery_status = 'ready_for_delivery',
            status = 'ready_to_delivery'
        WHERE id = %s
          AND delivery_status = 'ready_for_delivery'
          AND rider_id IS NULL
    """, (session["user_id"], order_id))

    if cursor.rowcount == 0:
        flash("Sorry, this delivery has already been claimed.", "warning")
    else:
        flash("You have claimed this delivery! Order is now ready for delivery.", "success")

    conn.commit()
    conn.close()
    return redirect(url_for("rider_dashboard"))

@app.route("/api/rider/claim", methods=["POST"])
def api_rider_claim():
    data = request.get_json() or request.form

    order_id = data.get("order_id")
    rider_id = data.get("rider_id")

    if not order_id or not rider_id:
        return jsonify({
            "success": False,
            "message": "Missing order_id or rider_id"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE orders
        SET rider_id = %s,
            delivery_status = 'ready_for_delivery',
            status = 'ready_to_delivery'
        WHERE id = %s
          AND delivery_status = 'ready_for_delivery'
          AND rider_id IS NULL
    """, (rider_id, order_id))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Already claimed or unavailable"
        })

    conn.close()

    return jsonify({
        "success": True,
        "message": "Delivery claimed successfully"
    })

@app.route("/seller/completed_orders")
def seller_completed_orders():
    if "user_id" not in session or not session.get("is_seller"):
        flash("Please login as a seller to view your completed orders.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Fetch only orders that belong to this seller and are marked as delivered
    cursor.execute("""
        SELECT 
            o.id AS order_id,
            u.username AS buyer_name,
            p.name AS product_name,
            o.image_url,
            v.color,
            o.quantity,
            o.payment_method,
            o.status,
            o.delivery_status,
            p.price
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN product_variants v ON o.variant_id = v.id
        JOIN users u ON o.buyer_id = u.id
        WHERE p.user_id = %s
          AND o.delivery_status = 'delivered'
        ORDER BY o.id DESC
    """, (session["user_id"],))

    completed_orders = cursor.fetchall()

    # Aggregate stats for template
    if completed_orders:
        total_completed_orders = len(completed_orders)
        total_items_sold = sum(int(row["quantity"]) for row in completed_orders)
        unique_customers = len({row["buyer_name"] for row in completed_orders})
        total_revenue = sum(float(row["price"]) * int(row["quantity"]) for row in completed_orders)
    else:
        total_completed_orders = 0
        total_items_sold = 0
        unique_customers = 0
        total_revenue = 0.0

    conn.close()

    return render_template(
        "seller_completed_orders.html",
        orders=completed_orders,
        total_completed_orders=total_completed_orders,
        total_items_sold=total_items_sold,
        unique_customers=unique_customers,
        total_revenue=total_revenue,
    )

@app.route("/api/completed_orders")
def completed_orders_api():
    seller_id = request.args.get("seller_id")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT 
            o.id AS order_id,
            u.name AS buyer_name,
            p.name AS product_name,
            oi.color,
            oi.quantity,
            p.price,
            pv.image_url
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        JOIN products p ON oi.product_id = p.id
        LEFT JOIN product_variants pv 
            ON pv.product_id = p.id AND pv.color = oi.color
        JOIN users u ON o.user_id = u.id
        WHERE p.user_id = %s
        AND o.status = 'completed'
        ORDER BY o.id DESC
    """, (seller_id,))

    orders = cursor.fetchall()

    # ===== FIX IMAGE URL =====
    for o in orders:
        if o["image_url"]:
            o["image_url"] = f"http://192.168.1.249:5000/uploads/{o['image_url']}"
        else:
            o["image_url"] = None

    # ===== STATS =====
    total_orders = len(set(o["order_id"] for o in orders))
    total_items = sum(o["quantity"] for o in orders)
    unique_customers = len(set(o["buyer_name"] for o in orders))
    total_revenue = sum(o["price"] * o["quantity"] for o in orders)

    conn.close()

    return jsonify({
        "orders": orders,
        "total_orders": total_orders,
        "total_items": total_items,
        "unique_customers": unique_customers,
        "total_revenue": total_revenue
    })

@app.route("/rider/complete/<int:order_id>")
def rider_complete(order_id):
    if "user_id" not in session or session.get("role") != "rider":
        flash("You must be logged in as a rider.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # ✅ Mark as delivered and add timestamp
    cursor.execute("""
        UPDATE orders
        SET delivery_status = 'delivered',
            delivered_at = %s
        WHERE id = %s
          AND rider_id = %s
          AND delivery_status = 'out_for_delivery'
    """, (datetime.now(), order_id, session["user_id"]))

    if cursor.rowcount == 0:
        flash("Unable to mark as delivered. Check the current status.", "warning")
    else:
        flash("Order marked as delivered. Buyer has been notified.", "success")

    conn.commit()
    conn.close()
    return redirect(url_for("rider_dashboard"))


@app.route("/api/rider/complete_delivery", methods=["POST"])
def api_rider_complete_delivery():

    order_id = request.form.get("order_id")
    rider_id = request.form.get("rider_id")
    file = request.files.get("proof_image")

    if not order_id or not rider_id:
        return jsonify({
            "success": False,
            "message": "Order ID and Rider ID required"
        }), 400

    if not file:
        return jsonify({
            "success": False,
            "message": "Proof image required"
        }), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    file.save(filepath)

    image_url = f"/static/proof_deliveries/{filename}"

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            UPDATE orders
            SET delivery_status = 'delivered',
                delivered_at = NOW(),
                proof_image = %s
            WHERE id = %s
              AND rider_id = %s
              AND delivery_status = 'out_for_delivery'
        """, (
            image_url,
            order_id,
            rider_id
        ))

        conn.commit()

        if cursor.rowcount == 0:
            return jsonify({
                "success": False,
                "message": "Invalid order or already completed"
            }), 400

        return jsonify({
            "success": True,
            "message": "Delivery completed with proof",
            "image_url": image_url
        })

    except Exception as e:
        conn.rollback()
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

    finally:
        cursor.close()
        conn.close()

@app.route("/rider/return_to_seller/<int:order_id>")
def rider_return_to_seller(order_id):
    # Ensure the user is a rider
    if "user_id" not in session or session.get("role") != "rider":
        flash("You must be logged in as a rider.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Update the delivery status back to 'returned_to_seller'
    cursor.execute("""
        UPDATE orders
        SET delivery_status = 'returned_to_seller',
            rider_id = NULL  -- Unassign the rider so the seller can manage it again
        WHERE id = %s
          AND rider_id = %s
          AND delivery_status = 'out_for_delivery'
    """, (order_id, session["user_id"]))

    if cursor.rowcount == 0:
        flash("⚠️ Unable to return this order. Check its current status.", "warning")
    else:
        flash("✅ Order returned to the seller successfully.", "success")

    conn.commit()
    conn.close()

    return redirect(url_for("rider_dashboard"))


@app.route("/seller/decline_order/<int:order_id>")
def seller_decline_order(order_id):
    if "user_id" not in session or not session.get("is_seller"):
        flash("Access denied. Sellers only.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Step 1: Fetch order details (only if still pending)
    cursor.execute("""
        SELECT o.id, o.variant_id, o.quantity, p.user_id AS seller_id
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.id=%s AND p.user_id=%s AND o.status='pending'
    """, (order_id, session["user_id"]))
    order = cursor.fetchone()

    if not order:
        conn.close()
        flash("Order cannot be declined or already processed.", "error")
        return redirect(url_for("seller_orders"))

    # ✅ Step 2: Restore stock
    cursor.execute("""
        UPDATE product_variants
        SET stock = stock + %s
        WHERE id = %s
    """, (order["quantity"], order["variant_id"]))

    # ✅ Step 3: Update order status and notify buyer
    cursor.execute("""
        UPDATE orders
        SET status='declined', buyer_notified=1
        WHERE id=%s
    """, (order_id,))
    conn.commit()
    conn.close()

    flash("Order declined. Buyer has been notified and stock restored.", "error")
    return redirect(url_for("seller_orders"))


@app.route("/rider/out_for_delivery/<int:order_id>")
def rider_out_for_delivery(order_id):
    if "user_id" not in session or session.get("role") != "rider":
        flash("You must be logged in as a rider.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Rider changes delivery status to out_for_delivery
    cursor.execute("""
        UPDATE orders
        SET delivery_status = 'out_for_delivery'
        WHERE id = %s
          AND rider_id = %s
          AND delivery_status = 'ready_for_delivery'
    """, (order_id, session["user_id"]))

    if cursor.rowcount == 0:
        flash("Unable to update. Check if the order is ready for delivery.", "warning")
    else:
        flash("Buyer has been informed: Product is now out for delivery.", "success")

    conn.commit()
    conn.close()
    return redirect(url_for("rider_dashboard"))

@app.route("/rider/start_delivery/<int:order_id>")
def rider_start_delivery(order_id):
    if "user_id" not in session or session.get("role") != "rider":
        flash("You must be logged in as a rider.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    # ✅ Change status to Out for Delivery
    cursor.execute("""
        UPDATE orders
        SET delivery_status = 'out_for_delivery'
        WHERE id = %s
          AND rider_id = %s
          AND delivery_status = 'ready_for_delivery'
    """, (order_id, session["user_id"]))

    if cursor.rowcount == 0:
        flash("Unable to mark as Out for Delivery. Check order status.", "warning")
    else:
        flash("Order is now Out for Delivery.", "success")

    conn.commit()
    conn.close()

    return redirect(url_for("rider_dashboard"))

@app.route("/api/rider/start_delivery", methods=["POST"])
def api_rider_start_delivery():
    data = request.get_json()

    order_id = data.get("order_id")
    rider_id = data.get("rider_id")

    if not order_id or not rider_id:
        return jsonify({
            "success": False,
            "message": "Missing data"
        }), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE orders
        SET delivery_status = 'out_for_delivery'
        WHERE id = %s
          AND rider_id = %s
          AND delivery_status = 'ready_for_delivery'
    """, (order_id, rider_id))

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return jsonify({
            "success": False,
            "message": "Unable to update order status"
        }), 400

    conn.close()

    return jsonify({
        "success": True,
        "message": "Order is now Out for Delivery"
    })

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("index"))

@app.route('/api/test')
def api_test():
    return jsonify({
        "message": "API is working",
        "DB_HOST": os.environ.get("DB_HOST", "NOT SET"),
        "DB_PORT": os.environ.get("DB_PORT", "NOT SET"),
        "DB_USER": os.environ.get("DB_USER", "NOT SET"),
        "DB_NAME": os.environ.get("DB_NAME", "NOT SET"),
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)