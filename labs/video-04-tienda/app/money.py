from decimal import Decimal, InvalidOperation


def price_to_cents(value):
    """Solo importes positivos, finitos, con hasta dos decimales."""
    if isinstance(value, bool) or value is None:
        raise ValueError("Importe no válido")
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or not Decimal("0") < amount <= Decimal("100000"):
            raise ValueError("Importe fuera de rango")
        cents = amount * 100
        if cents != cents.to_integral_value():
            raise ValueError("El importe tiene más de dos decimales")
        return int(cents)
    except (InvalidOperation, TypeError) as error:
        raise ValueError("Importe no válido") from error
