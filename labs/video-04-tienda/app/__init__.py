import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for
from .pricing import calculate_unit_price


PRODUCTS = [
    (1, "Auriculares A1", "Tu música. Sin distracciones.", "Un sonido equilibrado y una forma de escuchar más tuya. Diseño envolvente, almohadillas suaves y hasta 30 horas de autonomía.", "AUDIO", 5000, "headphones.svg", "Grafito"),
    (2, "Teclado K1", "Cada idea empieza aquí.", "Perfil bajo, pulsación precisa y un escritorio con más espacio para lo importante. Conexión USB-C y distribución compacta.", "ESCRITORIO", 7500, "keyboard.svg", "Piedra"),
    (3, "Mouse M1", "Precisión en cada movimiento.", "Una silueta cómoda, desplazamiento silencioso y el equilibrio entre ligereza y control. Conexión inalámbrica.", "ESCRITORIO", 3000, "mouse.svg", "Arcilla"),
]


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True, instance_path=(test_config or {}).get("INSTANCE_PATH"))
    app.config.from_mapping(SECRET_KEY=os.environ.get("SECRET_KEY"),
        DATABASE=str(Path(app.instance_path) / "forma.sqlite"),
        SESSION_COOKIE_NAME="forma_store_session", SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax", MAX_CONTENT_LENGTH=16384)
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Falta configurar SECRET_KEY")
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys=ON")
        return g.db

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with app.app_context():
        db = get_db()
        db.executescript((Path(app.root_path)/"schema.sql").read_text())
        db.executemany("""INSERT OR IGNORE INTO products
            (id,name,subtitle,description,category,price_cents,image,color)
            VALUES (?,?,?,?,?,?,?,?)""", PRODUCTS)
        db.commit()

    def product_by_id(product_id):
        row = get_db().execute("SELECT * FROM products WHERE id=? AND active=1", (product_id,)).fetchone()
        if row is None:
            abort(404, description="Este producto no está disponible.")
        return row

    @app.before_request
    def prepare_session():
        if request.endpoint in ("static", "health"):
            return
        session.setdefault("visitor_id", uuid.uuid4().hex)
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        if request.method == "POST":
            received = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
            if not isinstance(received, str) or not secrets.compare_digest(received, session["csrf_token"]):
                abort(400, description="La sesión del formulario ha caducado. Recarga e inténtalo de nuevo.")

    @app.after_request
    def response_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "private, no-store"
        return response

    @app.template_filter("money")
    def money(cents):
        return f"${cents / 100:,.2f}"

    @app.context_processor
    def common():
        return {"cart_count":session.get("cart", {}).get("quantity", 0)}

    @app.get("/salud")
    def health():
        return {"status":"ok"}

    @app.get("/")
    def catalog():
        products = get_db().execute("SELECT * FROM products WHERE active=1 ORDER BY id").fetchall()
        return render_template("catalog.html", products=products, featured=products[0])

    @app.get("/productos/<int:product_id>")
    def product(product_id):
        return render_template("product.html", product=product_by_id(product_id))

    @app.post("/carrito")
    def add_to_cart():
        try:
            product_id = int(request.form.get("product_id", ""))
            quantity = int(request.form.get("quantity", "1"))
        except ValueError:
            abort(400, description="Selecciona un producto y una cantidad válidos.")
        product_by_id(product_id)
        if not 1 <= quantity <= 5:
            abort(400, description="Puedes reservar entre una y cinco unidades.")
        session["cart"] = {"product_id":product_id, "quantity":quantity}
        return redirect(url_for("cart"))

    @app.get("/carrito")
    def cart():
        selected = session.get("cart")
        product = product_by_id(selected["product_id"]) if selected else None
        return render_template("cart.html", product=product, quantity=selected["quantity"] if selected else 0)

    @app.post("/carrito/vaciar")
    def empty_cart():
        session.pop("cart", None)
        return redirect(url_for("cart"))

    @app.get("/checkout")
    def checkout():
        selected = session.get("cart")
        if not selected:
            return redirect(url_for("cart"))
        return render_template("checkout.html", product=product_by_id(selected["product_id"]), quantity=selected["quantity"])

    @app.post("/api/pedidos")
    def create_order():
        if not request.is_json:
            abort(415, description="El formato del pedido no es válido.")
        data = request.get_json()
        if not isinstance(data, dict):
            abort(400, description="El pedido no es válido.")
        product_id, quantity = data.get("product_id"), data.get("quantity")
        if type(product_id) is not int or type(quantity) is not int or not 1 <= quantity <= 5:
            abort(400, description="Revisa el producto y la cantidad del pedido.")
        product = product_by_id(product_id)
        name, email = data.get("customer_name"), data.get("customer_email")
        if (not isinstance(name, str) or not 2 <= len(name.strip()) <= 100
            or not isinstance(email, str) or len(email) > 254
            or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email)):
            abort(400, description="Revisa tu nombre y correo electrónico.")
        try:
            # La regla de precios se mantiene aislada para revisar su origen.
            unit_price_cents = calculate_unit_price(product, data.get("unit_price"))
        except ValueError:
            abort(400, description="El importe del pedido no es válido.")
        order_id = uuid.uuid4().hex[:12]
        db = get_db()
        db.execute("""INSERT INTO orders
            (id,visitor_id,created_at,customer_name,customer_email,product_id,product_name,quantity,unit_price_cents,total_cents)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", (order_id, session["visitor_id"],
            datetime.now(timezone.utc).isoformat(timespec="seconds"),name.strip(),email,
            product["id"],product["name"],quantity,unit_price_cents,unit_price_cents*quantity))
        db.commit()
        session["customer"] = {"name":name.strip(), "email":email}
        return jsonify(order_id=order_id, product=product["name"], quantity=quantity,
            unit_price=f"{unit_price_cents/100:.2f}", total=f"{unit_price_cents*quantity/100:.2f}",
            currency="USD", status="pending_payment", order_url=url_for("order", order_id=order_id)), 201

    @app.get("/pedidos")
    def orders():
        rows = get_db().execute("SELECT * FROM orders WHERE visitor_id=? ORDER BY rowid DESC", (session["visitor_id"],)).fetchall()
        return render_template("orders.html", orders=rows)

    @app.get("/pedidos/<order_id>")
    def order(order_id):
        row = get_db().execute("SELECT * FROM orders WHERE id=? AND visitor_id=?", (order_id,session["visitor_id"])).fetchone()
        if row is None:
            abort(404, description="No encontramos este pedido en tu sesión.")
        return render_template("order.html", order=row)

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    @app.errorhandler(415)
    def error_page(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), error.code
        return render_template("error.html", error=error), error.code

    return app
