#!/usr/bin/env python3
"""Herramienta local. La clave privada nunca se envía al portal."""
import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.signatures import canonical, fingerprint, verify


def main():
    parser = argparse.ArgumentParser(description="Firma y verificación de aprobaciones de Alameda")
    sub = parser.add_subparsers(dest="command", required=True)
    keygen = sub.add_parser("crear-clave")
    keygen.add_argument("private")
    keygen.add_argument("public")
    sign = sub.add_parser("firmar")
    sign.add_argument("request")
    sign.add_argument("pdf")
    sign.add_argument("private")
    sign.add_argument("output")
    check = sub.add_parser("verificar")
    check.add_argument("receipt")
    check.add_argument("pdf")
    check.add_argument("public")
    check.add_argument("--usuario", required=True)
    args = parser.parse_args()
    if args.command == "crear-clave":
        if Path(args.private).resolve() == Path(args.public).resolve():
            raise ValueError("Las rutas de las claves deben ser distintas")
        if Path(args.private).exists() or Path(args.public).exists():
            raise ValueError("No se sobrescriben claves existentes")
        key = Ed25519PrivateKey.generate()
        data = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        with open(args.private, "xb", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            stream.write(data)
        with open(args.public, "xb") as stream:
            stream.write(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
        print("Claves creadas. Mantén la clave privada bajo tu custodia.")
    elif args.command == "firmar":
        payload = json.loads(Path(args.request).read_text())
        key = serialization.load_pem_private_key(Path(args.private).read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey) or fingerprint(key.public_key()) != payload["key_fingerprint"]:
            raise ValueError("La clave no corresponde a la solicitud")
        if payload["format"] != "alameda-approval-v1" or payload["action"] != "APPROVE":
            raise ValueError("Tipo de solicitud desconocido")
        if hashlib.sha256(Path(args.pdf).read_bytes()).hexdigest() != payload["sha256"]:
            raise ValueError("El PDF no corresponde a la versión solicitada")
        print(f"Aprobador: {payload['username']} | Documento: {payload['document_id']} | {payload['title']}")
        print(f"SHA-256: {payload['sha256']}")
        if input("¿Confirmas la aprobación de esta versión? Escribe APROBAR: ") != "APROBAR":
            raise ValueError("Aprobación cancelada")
        envelope = {"payload":payload, "signature":base64.b64encode(key.sign(canonical(payload))).decode()}
        with open(args.output, "x") as stream:
            json.dump(envelope,stream,ensure_ascii=False,indent=2)
        print("Solicitud firmada. Presenta este archivo en el portal.")
    else:
        payload = verify(json.loads(Path(args.receipt).read_text()), Path(args.public).read_text())
        if payload["username"] != args.usuario or payload["format"] != "alameda-approval-v1" or payload["action"] != "APPROVE":
            raise ValueError("La identidad o el tipo de comprobante no corresponde")
        if hashlib.sha256(Path(args.pdf).read_bytes()).hexdigest() != payload["sha256"]:
            raise ValueError("Firma válida, pero el PDF NO coincide con la versión aprobada")
        print(f"Firma válida. PDF coincidente. Aprobador: {payload['username']}. Documento: {payload['document_id']}.")
        print("La firma prueba la declaración firmada; consulta el portal para confirmar su registro y estado actual.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Verificación u operación rechazada: {error}", file=sys.stderr)
        sys.exit(1)
