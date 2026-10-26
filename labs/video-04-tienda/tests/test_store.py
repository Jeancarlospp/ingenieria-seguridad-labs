import sqlite3
import pytest
from app import create_app

@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING":True,"SECRET_KEY":"solo-pruebas","INSTANCE_PATH":str(tmp_path),"DATABASE":str(tmp_path/"test.sqlite")})

@pytest.fixture
def client(app):
    c=app.test_client(); c.get("/"); return c

def send(client, **changes):
    data=dict(product_id=1,quantity=1,unit_price=50,customer_name="Ana Torres",customer_email="ana@example.test")
    data.update(changes)
    with client.session_transaction() as s: token=s["csrf_token"]
    return client.post("/api/pedidos",json=data,headers={"X-CSRF-Token":token})

def test_normal_purchase(client):
    r=send(client); assert r.status_code==201
    assert r.json["total"]=="50.00"
    assert "$50.00" in client.get(r.json["order_url"]).text

def test_manipulated_price_is_not_trusted(client,app):
    r=send(client,unit_price=1); assert r.status_code==201
    assert r.json["total"]=="50.00"
    with sqlite3.connect(app.config["DATABASE"]) as db:
        assert db.execute("SELECT total_cents FROM orders").fetchone()[0]==5000

@pytest.mark.parametrize("price",[0,-1,"NaN","not-a-price",None,True])
def test_catalog_price_is_authoritative(client,price):
    r=send(client,unit_price=price)
    assert r.status_code==201 and r.json["total"]=="50.00"

@pytest.mark.parametrize("quantity",[0,-1,6,1.5,True,"1",None])
def test_invalid_quantity(client,quantity):
    assert send(client,quantity=quantity).status_code==400

@pytest.mark.parametrize("product_id",[0,999])
def test_unknown_product(client,product_id):
    assert send(client,product_id=product_id).status_code==404

def test_quantity_total(client):
    assert send(client,quantity=3).json["total"]=="150.00"

def test_csrf(client):
    assert client.post("/api/pedidos",json={}).status_code==400

def test_private_orders(app,client):
    r=send(client); other=app.test_client()
    assert other.get(r.json["order_url"]).status_code==404
    assert r.json["order_id"][:8].upper() not in other.get("/pedidos").text

def test_cart_and_pages(client):
    with client.session_transaction() as s: token=s["csrf_token"]
    assert client.get("/checkout").status_code==302
    assert client.post("/carrito",data={"csrf_token":token,"product_id":1,"quantity":1}).status_code==302
    for url in ["/","/productos/1","/carrito","/checkout","/pedidos"]:
        assert client.get(url).status_code==200

def test_customer_validation(client):
    assert send(client,customer_name="").status_code==400
    assert send(client,customer_email="incorrecto").status_code==400

def test_prices_for_other_products(client):
    assert send(client,product_id=2,unit_price=1).json["total"]=="75.00"
    assert send(client,product_id=3,unit_price=1).json["total"]=="30.00"

def test_order_values_are_snapshots(client,app):
    r=send(client)
    with sqlite3.connect(app.config["DATABASE"]) as db: db.execute("UPDATE products SET price_cents=6000 WHERE id=1")
    assert "$50.00" in client.get(r.json["order_url"]).text
    assert send(client).json["total"]=="60.00"
