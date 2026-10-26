"""El catálogo del servidor es la fuente de precios de los pedidos."""


def calculate_unit_price(product, submitted_price):
    # El comprador elige producto y cantidad; el servidor decide el precio.
    return product["price_cents"]
