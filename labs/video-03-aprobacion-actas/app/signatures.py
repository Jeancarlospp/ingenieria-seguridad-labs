"""Formato estable de comprobantes. La confianza proviene de una clave externa."""
import base64
import hashlib
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


def canonical(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_public(pem):
    key = serialization.load_pem_public_key(pem.encode("ascii"))
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("Se requiere una clave Ed25519")
    return key


def fingerprint(key):
    raw = key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return hashlib.sha256(raw).hexdigest()


def verify(envelope, public_pem):
    if set(envelope) != {"payload", "signature"}:
        raise ValueError("Formato de comprobante incorrecto")
    key = load_public(public_pem)
    if envelope["payload"]["key_fingerprint"] != fingerprint(key):
        raise ValueError("La clave no corresponde al aprobador")
    signature = base64.b64decode(envelope["signature"], validate=True)
    key.verify(signature, canonical(envelope["payload"]))
    return envelope["payload"]
