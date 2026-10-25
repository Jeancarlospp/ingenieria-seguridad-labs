import base64
import json
import sqlite3
import subprocess
import sys
from io import BytesIO
from pathlib import Path
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.signatures import canonical

@pytest.fixture
def signing_key(app, tmp_path):
    key = Ed25519PrivateKey.generate()
    path = tmp_path / "public.pem"
    path.write_bytes(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    result = app.test_cli_runner().invoke(args=["register-signing-key", "elena", str(path)])
    assert result.exit_code == 0, result.output
    return key, path

def prepare(client, token):
    return client.post("/documentos/102/aprobacion/preparar", data={"csrf_token":token()})

def signed(payload, key):
    return {"payload":payload, "signature":base64.b64encode(key.sign(canonical(payload))).decode()}

def submit(client, token, envelope):
    return client.post("/documentos/102/aprobacion", data={"csrf_token":token(), "receipt":(BytesIO(json.dumps(envelope).encode()), "firma.json")})

def test_roundtrip_audit_cli_and_tampering(app, client, login, csrf_token, signing_key, document_snapshot, tmp_path):
    login("elena")
    assert client.get("/documentos/102/aprobacion").status_code == 200
    payload = prepare(client, csrf_token).get_json()
    pdf = tmp_path / "acta.pdf"; pdf.write_bytes(document_snapshot(102)["content"])
    req = tmp_path / "request.json"; req.write_text(json.dumps(payload))
    private = tmp_path / "private.pem"
    private.write_bytes(signing_key[0].private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    receipt = tmp_path / "receipt.json"
    signcmd = [sys.executable,"tools/firma.py","firmar",str(req),str(pdf),str(private),str(receipt)]
    result = subprocess.run(signcmd,input="APROBAR\n",capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
    envelope = json.loads(receipt.read_text())
    assert submit(client,csrf_token,envelope).status_code == 302
    assert client.get("/documentos/102/aprobacion/comprobante").get_json() == envelope
    assert "Aprobada" in client.get("/documentos/102/aprobacion").get_data(as_text=True)
    with sqlite3.connect(app.config["DATABASE"]) as db:
        row = db.execute("SELECT actor,origin,document_id,result,correlation_id,occurred_at FROM audit_events WHERE action='APPROVE'").fetchone()
    assert row[:4] == ("elena","127.0.0.1",102,"SUCCESS")
    assert len(row[4]) == 36 and row[5].endswith("+00:00")
    cmd = [sys.executable,"tools/firma.py","verificar",str(receipt),str(pdf),str(signing_key[1]),"--usuario","elena"]
    assert subprocess.run(cmd,capture_output=True).returncode == 0
    pdf.write_bytes(pdf.read_bytes()+b"alterado")
    bad = subprocess.run(cmd,capture_output=True,text=True)
    assert bad.returncode == 1 and "NO coincide" in bad.stderr
    pdf.write_bytes(document_snapshot(102)["content"])
    envelope["payload"]["username"] = "marco"; receipt.write_text(json.dumps(envelope))
    assert subprocess.run(cmd,capture_output=True).returncode == 1

@pytest.mark.parametrize("username",["ana","marco"])
@pytest.mark.parametrize("suffix",["","/preparar","/comprobante"])
def test_approval_permissions(client,login,csrf_token,username,suffix):
    login(username)
    path = "/documentos/102/aprobacion"+suffix
    result = client.post(path,data={"csrf_token":csrf_token()}) if suffix=="/preparar" else client.get(path)
    assert result.status_code == 403

@pytest.mark.parametrize("kind",["other_key","identity","hash","expired","changed_pdf","malformed"])
def test_invalid_evidence(app,client,login,csrf_token,signing_key,document_snapshot,kind):
    login("elena")
    payload = prepare(client,csrf_token).get_json()
    envelope = signed(payload,signing_key[0])
    if kind=="other_key": envelope=signed(payload,Ed25519PrivateKey.generate())
    if kind=="identity": envelope["payload"]["username"]="marco"
    if kind=="hash":
        payload["sha256"]="0"*64; envelope=signed(payload,signing_key[0])
    if kind=="expired":
        with sqlite3.connect(app.config["DATABASE"]) as db: db.execute("UPDATE approval_requests SET expires_at='2000-01-01T00:00:00+00:00'")
    if kind=="changed_pdf": document_snapshot(102)["path"].write_bytes(document_snapshot(101)["content"])
    if kind=="malformed": envelope={"payload":[]}
    assert submit(client,csrf_token,envelope).status_code == 400
    with sqlite3.connect(app.config["DATABASE"]) as db: assert db.execute("SELECT COUNT(*) FROM approvals").fetchone()[0] == 0

def test_replay(client,login,csrf_token,signing_key):
    login("elena")
    envelope=signed(prepare(client,csrf_token).get_json(),signing_key[0])
    assert submit(client,csrf_token,envelope).status_code == 302
    assert submit(client,csrf_token,envelope).status_code == 400

def test_document_update_invalidates_current_status(client,login,csrf_token,signing_key,document_snapshot):
    login("elena")
    assert submit(client,csrf_token,signed(prepare(client,csrf_token).get_json(),signing_key[0])).status_code == 302
    assert client.post("/documentos/102/sustituir",data={"csrf_token":csrf_token(),"file":(BytesIO(document_snapshot(101)["content"]),"nuevo.pdf")}).status_code == 302
    assert "requiere nueva aprobación" in client.get("/documentos/102/aprobacion").get_data(as_text=True)

def test_missing_key_and_csrf(client,login,csrf_token):
    login("elena")
    assert prepare(client,csrf_token).status_code == 400
    assert client.post("/documentos/102/aprobacion/preparar").status_code == 400

def test_no_key_rebinding(app,signing_key):
    assert app.test_cli_runner().invoke(args=["register-signing-key","elena",str(signing_key[1])]).exit_code == 0
    signing_key[1].write_bytes(Ed25519PrivateKey.generate().public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
    assert app.test_cli_runner().invoke(args=["register-signing-key","elena",str(signing_key[1])]).exit_code != 0
