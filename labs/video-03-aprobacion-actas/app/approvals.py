import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click
from flask import abort, flash, g, redirect, render_template, request, session, url_for, Response
from .signatures import canonical, fingerprint, load_public, verify


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def document_hash(app, document):
    path = Path(app.instance_path) / "documents" / document["storage_name"]
    if not path.is_file():
        abort(404)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(app, get_db, authorized_document, login_required):
    def audit(action, result, document_id=None, actor=None, commit=True):
        db = get_db()
        user = getattr(g, "user", None)
        db.execute("""INSERT INTO audit_events
            (occurred_at, actor, origin, action, document_id, result, correlation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", (
            now(), actor or (user["username"] if user else "anonymous"),
            request.remote_addr or "unknown", action, document_id, result,
            getattr(g, "correlation_id", str(uuid.uuid4())),
        ))
        if commit:
            db.commit()

    app.extensions["audit_event"] = audit

    @app.before_request
    def correlation():
        g.correlation_id = str(uuid.uuid4())

    @app.after_request
    def record_response(response):
        if response.status_code in (400, 403) and request.path.startswith("/documentos/"):
            args = request.view_args or {}
            audit(request.endpoint or "REQUEST", "DENIED", args.get("document_id"))
        if response.status_code == 302 and request.method == "POST":
            actions = {"document_replace":"REPLACE", "document_delete":"DELETE", "document_upload":"UPLOAD"}
            if request.endpoint in actions:
                audit(actions[request.endpoint], "SUCCESS", (request.view_args or {}).get("document_id"))
        response.headers["X-Request-ID"] = getattr(g, "correlation_id", "")
        return response

    @app.get("/documentos/<int:document_id>/aprobacion")
    @login_required
    def approval(document_id):
        doc = authorized_document(document_id, "replace")
        db = get_db()
        latest = db.execute("SELECT * FROM approvals WHERE document_id=? ORDER BY rowid DESC LIMIT 1", (document_id,)).fetchone()
        current_hash = document_hash(app, doc)
        key = db.execute("SELECT fingerprint FROM signing_keys WHERE username=?", (g.user["username"],)).fetchone()
        events = db.execute("SELECT * FROM audit_events WHERE document_id=? ORDER BY id DESC LIMIT 20", (document_id,)).fetchall()
        return render_template("documents/approval.html", document=doc, approval=latest,
            current=bool(latest and latest["document_hash"] == current_hash), key=key, events=events)

    @app.post("/documentos/<int:document_id>/aprobacion/preparar")
    @login_required
    def prepare_approval(document_id):
        doc = authorized_document(document_id, "replace")
        db = get_db()
        key = db.execute("SELECT * FROM signing_keys WHERE username=?", (g.user["username"],)).fetchone()
        if key is None:
            abort(400, description="No hay una clave de firma registrada para tu cuenta.")
        nonce = secrets.token_urlsafe(32)
        issued = now()
        expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(timespec="seconds")
        payload = dict(format="alameda-approval-v1", action="APPROVE", document_id=document_id,
            title=doc["title"], sha256=document_hash(app, doc), username=g.user["username"],
            full_name=g.user["full_name"], issued_at=issued, expires_at=expires,
            nonce=nonce, key_fingerprint=key["fingerprint"])
        db.execute("INSERT INTO approval_requests (nonce,user_id,document_id,payload,expires_at) VALUES (?,?,?,?,?)",
            (nonce,g.user["id"],document_id,canonical(payload).decode(),expires))
        db.commit()
        audit("PREPARE_APPROVAL", "SUCCESS", document_id)
        return Response(canonical(payload), mimetype="application/json", headers={
            "Content-Disposition": f"attachment; filename=solicitud-{document_id}.json", "Cache-Control":"no-store"})

    @app.post("/documentos/<int:document_id>/aprobacion")
    @login_required
    def submit_approval(document_id):
        doc = authorized_document(document_id, "replace")
        db = get_db()
        try:
            upload = request.files.get("receipt")
            if not upload:
                raise ValueError()
            raw = upload.read(65537)
            if len(raw) > 65536:
                raise ValueError()
            envelope = json.loads(raw)
            key = db.execute("SELECT * FROM signing_keys WHERE username=?", (g.user["username"],)).fetchone()
            if key is None:
                raise ValueError()
            payload = verify(envelope, key["public_pem"])
            pending = db.execute("SELECT * FROM approval_requests WHERE nonce=?", (payload["nonce"],)).fetchone()
            if (not pending or pending["consumed"] or pending["user_id"] != g.user["id"]
                or pending["document_id"] != document_id or pending["expires_at"] < now()
                or pending["payload"] != canonical(payload).decode()
                or payload["sha256"] != document_hash(app, doc)):
                raise ValueError()
        except Exception as error:
            from werkzeug.exceptions import HTTPException
            if isinstance(error, HTTPException):
                raise
            audit("APPROVE", "INVALID_EVIDENCE", document_id)
            abort(400, description="La aprobación no es válida, ha caducado o el documento cambió. Prepara una nueva solicitud.")
        approval_id = str(uuid.uuid4())
        try:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute("UPDATE approval_requests SET consumed=1 WHERE nonce=? AND consumed=0", (payload["nonce"],)).rowcount
            if changed != 1:
                db.rollback()
                abort(400, description="Esta solicitud ya fue utilizada.")
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?)", (approval_id, document_id, g.user["id"], payload["sha256"], now(), canonical(envelope).decode()))
            audit("APPROVE", "SUCCESS", document_id, commit=False)
            db.commit()
        except Exception:
            db.rollback()
            raise
        flash("Aprobación registrada. El comprobante corresponde a la versión revisada.", "success")
        return redirect(url_for("approval", document_id=document_id))

    @app.get("/documentos/<int:document_id>/aprobacion/comprobante")
    @login_required
    def approval_receipt(document_id):
        authorized_document(document_id, "replace")
        row = get_db().execute("SELECT receipt FROM approvals WHERE document_id=? ORDER BY rowid DESC LIMIT 1", (document_id,)).fetchone()
        if not row:
            abort(404)
        audit("DOWNLOAD_RECEIPT", "SUCCESS", document_id)
        return Response(row["receipt"], mimetype="application/json", headers={
            "Content-Disposition":f"attachment; filename=comprobante-{document_id}.json", "Cache-Control":"no-store"})

    @app.cli.command("register-signing-key")
    @click.argument("username")
    @click.argument("pem_file", type=click.Path(exists=True, dir_okay=False))
    def register_key(username, pem_file):
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not user or user["role"] != "teacher":
            raise click.ClickException("La cuenta debe ser un docente existente.")
        try:
            pem = Path(pem_file).read_text()
            key = load_public(pem)
        except Exception as error:
            raise click.ClickException("Clave pública Ed25519 no válida.") from error
        existing = db.execute("SELECT fingerprint FROM signing_keys WHERE username=?", (username,)).fetchone()
        if existing:
            if existing["fingerprint"] == fingerprint(key):
                click.echo(f"La clave de {username} ya está registrada.")
                return
            raise click.ClickException("La cuenta ya tiene otra clave; no se sustituye automáticamente.")
        try:
            db.execute("INSERT INTO signing_keys VALUES (?,?,?)", (username,pem,fingerprint(key)))
            db.commit()
        except Exception as error:
            db.rollback()
            raise click.ClickException("La clave ya está asociada o no pudo registrarse.") from error
        click.echo(f"Clave registrada para {username}: {fingerprint(key)}")
