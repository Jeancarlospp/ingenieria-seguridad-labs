import click
import os
import secrets
import sqlite3
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    abort,
    g,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from .permissions import can_access_document, can_upload_document
from .storage import InvalidDocument, save_pdf
from datetime import datetime, timezone

def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        instance_path=(test_config or {}).get("INSTANCE_PATH"),
    )

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        DATABASE=str(Path(app.instance_path) / "aprobaciones.sqlite"),
        SESSION_COOKIE_NAME="alameda_aprobaciones_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    )

    if test_config:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Falta configurar SECRET_KEY.")

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")

        return g.db

    @app.teardown_appcontext
    def close_db(error=None):
        db = g.pop("db", None)

        if db is not None:
            db.close()

    def initialize_database():
        db = get_db()
        schema_path = Path(app.root_path) / "schema.sql"
        db.executescript(schema_path.read_text(encoding="utf-8"))

        accounts = [
            (1, "ana", "Ana Torres", "student"),
            (2, "luis", "Luis Mendoza", "student"),
            (3, "elena", "Elena Vargas", "teacher"),
            (4, "marco", "Marco Salazar", "teacher"),
        ]

        for user_id, username, name, role in accounts:
            existing = db.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if existing is None:
                db.execute(
                    """
                    INSERT OR IGNORE INTO users
                        (id, username, password_hash, full_name, role)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        username,
                        generate_password_hash("Alameda2026!"),
                        name,
                        role,
                    ),
                )

        db.executemany(
            "INSERT OR IGNORE INTO subjects (id, name) VALUES (?, ?)",
            [
                (1, "Matemáticas"),
                (2, "Ciencias Naturales"),
            ],
        )

        db.executemany(
            """
            INSERT OR IGNORE INTO user_subjects (user_id, subject_id)
            VALUES (?, ?)
            """,
            [
                (1, 1),  # Ana: Matemáticas.
                (2, 2),  # Luis: Ciencias Naturales.
                (3, 1),  # Elena: Matemáticas.
                (4, 2),  # Marco: Ciencias Naturales.
            ],
        )

        db.commit()

    @app.before_request
    def load_user_and_check_form():
        g.user = None

        if user_id := session.get("user_id"):
            g.user = get_db().execute(
                """
                SELECT id, username, full_name, role
                FROM users
                WHERE id = ?
                """,
                (user_id,),
            ).fetchone()

            if g.user is None:
                session.clear()

        if request.method == "POST":
            expected = session.get("csrf_token")
            received = request.form.get("csrf_token")

            if (
                not isinstance(expected, str)
                or not isinstance(received, str)
                or not secrets.compare_digest(expected, received)
            ):
                abort(400, description=(
                    "El formulario ha caducado o no es válido. "
                    "Recarga la página e inténtalo de nuevo."
                ))

    @app.context_processor
    def template_helpers():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)

        return {"csrf_token": session["csrf_token"]}

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("login"))

            return view(*args, **kwargs)

        return wrapped

    @app.get("/")
    def index():
        endpoint = "documents" if g.user else "login"
        return redirect(url_for(endpoint))

    @app.route("/ingresar", methods=["GET", "POST"])
    def login():
        if g.user is not None:
            return redirect(url_for("documents"))

        error = None
        username = ""

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            user = get_db().execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            ).fetchone()

            if user and check_password_hash(
                user["password_hash"], password
            ):
                app.extensions["audit_event"]("LOGIN", "SUCCESS", actor=user["username"])
                session.clear()
                session["user_id"] = user["id"]
                session["csrf_token"] = secrets.token_urlsafe(32)

                return redirect(url_for("documents"))

            app.extensions["audit_event"]("LOGIN", "FAILED", actor=username[:100] or "anonymous")
            error = "Usuario o contraseña incorrectos."

        return render_template(
            "auth/login.html",
            error=error,
            username=username,
        )

    @app.post("/salir")
    @login_required
    def logout():
        session.clear()
        return redirect(url_for("login"))

    def assigned_subject_ids():
        rows = get_db().execute(
            """
            SELECT subject_id
            FROM user_subjects
            WHERE user_id = ?
            """,
            (g.user["id"],),
        ).fetchall()

        return {row["subject_id"] for row in rows}

    def authorized_document(document_id, action):
        document = get_db().execute(
            """
            SELECT documents.*,
                   subjects.name AS subject_name,
                   users.full_name AS owner_name
            FROM documents
            JOIN subjects ON subjects.id = documents.subject_id
            JOIN users ON users.id = documents.owner_id
            WHERE documents.id = ?
            """,
            (document_id,),
        ).fetchone()

        if document is None:
            abort(404)

        if not can_access_document(
            g.user,
            document,
            assigned_subject_ids(),
            action,
        ):
            abort(403)

        return document

    @app.get("/documentos")
    @login_required
    def documents():
        db = get_db()
        query = request.args.get("q", "").strip()
        subject_value = request.args.get("subject", "").strip()
        selected_subject = None

        if subject_value:
            try:
                selected_subject = int(subject_value)
            except ValueError:
                abort(400, description="La asignatura no es válida.")

        subjects = db.execute(
            """
            SELECT subjects.id, subjects.name
            FROM subjects
            JOIN user_subjects
                ON subjects.id = user_subjects.subject_id
            WHERE user_subjects.user_id = ?
            ORDER BY subjects.name
            """,
            (g.user["id"],),
        ).fetchall()

        sql = """
            SELECT documents.*,
                   subjects.name AS subject_name,
                   users.full_name AS owner_name
            FROM documents
            JOIN subjects ON subjects.id = documents.subject_id
            JOIN users ON users.id = documents.owner_id
            JOIN user_subjects
                ON user_subjects.subject_id = documents.subject_id
            WHERE user_subjects.user_id = ?
        """
        parameters = [g.user["id"]]

        if g.user["role"] != "teacher":
            sql += " AND documents.audience = ?"
            parameters.append("students")

        if query:
            sql += " AND documents.title LIKE ?"
            parameters.append(f"%{query}%")

        if selected_subject is not None:
            sql += " AND documents.subject_id = ?"
            parameters.append(selected_subject)

        sql += " ORDER BY documents.updated_at DESC, documents.id DESC"

        records = db.execute(sql, parameters).fetchall()

        return render_template(
            "documents/list.html",
            subjects=subjects,
            documents=records,
            query=query,
            selected_subject=selected_subject,
        )

    @app.get("/documentos/<int:document_id>")
    @login_required
    def document_detail(document_id):
        document = authorized_document(document_id, "view")

        can_manage = can_access_document(
            g.user,
            document,
            assigned_subject_ids(),
            "replace",
        )

        return render_template(
            "documents/detail.html",
            document=document,
            can_manage=can_manage,
        )

    @app.get("/documentos/<int:document_id>/archivo")
    @login_required
    def document_file(document_id):
        document = authorized_document(document_id, "download")

        response = send_from_directory(
            str(Path(app.instance_path) / "documents"),
            document["storage_name"],
            download_name=document["original_name"],
            mimetype="application/pdf",
            as_attachment=request.args.get("download") == "1",
            conditional=False,
            etag=False,
            max_age=0,
        )

        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"

        return response

    @app.route("/documentos/nuevo", methods=["GET", "POST"])
    @login_required
    def document_upload():
        if g.user["role"] != "teacher":
            abort(403)

        db = get_db()

        subjects = db.execute(
            """
            SELECT subjects.id, subjects.name
            FROM subjects
            JOIN user_subjects
                ON subjects.id = user_subjects.subject_id
            WHERE user_subjects.user_id = ?
            ORDER BY subjects.name
            """,
            (g.user["id"],),
        ).fetchall()

        values = {
            "title": "",
            "subject_id": "",
            "audience": "students",
        }
        error = None

        if request.method == "POST":
            values = {
                "title": request.form.get("title", "").strip(),
                "subject_id": request.form.get(
                    "subject_id", ""
                ).strip(),
                "audience": request.form.get("audience", ""),
            }

            try:
                subject_id = int(values["subject_id"])
            except ValueError:
                subject_id = None

            if not values["title"] or len(values["title"]) > 180:
                error = "Escribe un título de entre 1 y 180 caracteres."

            elif subject_id is None:
                error = "Selecciona una asignatura."

            elif not can_upload_document(
                g.user,
                subject_id,
                assigned_subject_ids(),
            ):
                abort(403)

            elif values["audience"] not in {"students", "teachers"}:
                error = "Selecciona una audiencia válida."

            else:
                storage = Path(app.instance_path) / "documents"

                try:
                    saved = save_pdf(
                        request.files.get("file"),
                        storage,
                    )
                except InvalidDocument as invalid:
                    error = str(invalid)
                else:
                    timestamp = datetime.now(
                        timezone.utc
                    ).isoformat(timespec="seconds")

                    try:
                        cursor = db.execute(
                            """
                            INSERT INTO documents (
                                title, subject_id, owner_id, audience,
                                storage_name, original_name, size_bytes,
                                created_at, updated_at
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                values["title"],
                                subject_id,
                                g.user["id"],
                                values["audience"],
                                saved["storage_name"],
                                saved["original_name"],
                                saved["size_bytes"],
                                timestamp,
                                timestamp,
                            ),
                        )
                        document_id = cursor.lastrowid
                        db.commit()

                    except Exception:
                        db.rollback()
                        (
                            storage / saved["storage_name"]
                        ).unlink(missing_ok=True)
                        raise

                    flash(
                        "Documento publicado correctamente.",
                        "success",
                    )

                    return redirect(url_for(
                        "document_detail",
                        document_id=document_id,
                    ))

        return render_template(
            "documents/upload.html",
            subjects=subjects,
            values=values,
            error=error,
        ), 400 if error else 200
    @app.route(
        "/documentos/<int:document_id>/sustituir",
        methods=["GET", "POST"],
    )
    @login_required
    def document_replace(document_id):
        document = authorized_document(document_id, "replace")
        error = None

        if request.method == "POST":
            storage = Path(app.instance_path) / "documents"

            try:
                saved = save_pdf(
                    request.files.get("file"),
                    storage,
                )
            except InvalidDocument as invalid:
                error = str(invalid)
            else:
                db = get_db()
                timestamp = datetime.now(
                    timezone.utc
                ).isoformat(timespec="seconds")

                try:
                    db.execute(
                        """
                        UPDATE documents
                        SET storage_name = ?,
                            original_name = ?,
                            size_bytes = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            saved["storage_name"],
                            saved["original_name"],
                            saved["size_bytes"],
                            timestamp,
                            document_id,
                        ),
                    )
                    db.commit()

                except Exception:
                    db.rollback()
                    (
                        storage / saved["storage_name"]
                    ).unlink(missing_ok=True)
                    raise

                # El archivo anterior se retira después de guardar
                # correctamente la referencia al nuevo.
                try:
                    (
                        storage / document["storage_name"]
                    ).unlink(missing_ok=True)
                except OSError:
                    app.logger.exception(
                        "No se pudo retirar el archivo anterior "
                        "del documento %s",
                        document_id,
                    )

                flash("Archivo sustituido correctamente.", "success")

                return redirect(url_for(
                    "document_detail",
                    document_id=document_id,
                ))

        return render_template(
            "documents/replace.html",
            document=document,
            error=error,
        ), 400 if error else 200

    @app.route(
        "/documentos/<int:document_id>/eliminar",
        methods=["GET", "POST"],
    )
    @login_required
    def document_delete(document_id):
        document = authorized_document(document_id, "delete")

        if request.method == "POST":
            db = get_db()

            try:
                db.execute(
                    "DELETE FROM documents WHERE id = ?",
                    (document_id,),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise

            # La descarga deja de estar disponible al retirar
            # el registro que autoriza y localiza el archivo.
            storage = Path(app.instance_path) / "documents"

            try:
                (
                    storage / document["storage_name"]
                ).unlink(missing_ok=True)
            except OSError:
                app.logger.exception(
                    "No se pudo retirar el archivo "
                    "del documento eliminado %s",
                    document_id,
                )

            flash("Documento eliminado correctamente.", "success")
            return redirect(url_for("documents"))

        return render_template(
            "documents/delete.html",
            document=document,
        )

    @app.errorhandler(400)
    def bad_request(error):
        return render_template(
            "error.html",
            code=400,
            title="No se pudo procesar la solicitud",
            message=error.description,
        ), 400

    @app.errorhandler(403)
    def forbidden(error):
        return render_template(
            "error.html",
            code=403,
            title="Acceso denegado",
            message="No tienes permiso para acceder a este recurso.",
        ), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template(
            "error.html",
            code=404,
            title="Página no encontrada",
            message="La página solicitada no está disponible.",
        ), 404

    @app.errorhandler(413)
    def too_large(error):
        return render_template(
            "error.html",
            code=413,
            title="Archivo demasiado grande",
            message="La solicitud supera el tamaño máximo permitido.",
        ), 413

    @app.cli.command("seed-documents")
    def seed_initial_documents():
        from .seed_documents import seed_documents

        storage = Path(app.instance_path) / "documents"

        created = seed_documents(
            get_db(),
            storage,
        )

        print(f"Documentos creados: {created}")
    @app.cli.command("backup-document")
    @click.argument("document_id", type=int)
    def backup_document_command(document_id):
        from .backups import BackupError, create_document_backup

        try:
            backup_name = create_document_backup(
                get_db(),
                app.instance_path,
                document_id,
            )
        except BackupError as error:
            raise click.ClickException(str(error)) from error

        click.echo(f"Respaldo creado: {backup_name}")

    @app.cli.command("restore-document")
    @click.argument("backup_name")
    def restore_document_command(backup_name):
        from .backups import BackupError, restore_document_backup

        try:
            document_id, cleanup_warning = restore_document_backup(
                get_db(),
                app.instance_path,
                backup_name,
            )
        except BackupError as error:
            raise click.ClickException(str(error)) from error

        click.echo(f"Documento restaurado: {document_id}")

        if cleanup_warning:
            click.echo(
                "Aviso: quedó un archivo anterior pendiente de limpieza."
            )

    from .approvals import install
    install(app, get_db, authorized_document, login_required)

    with app.app_context():
        initialize_database()

    return app