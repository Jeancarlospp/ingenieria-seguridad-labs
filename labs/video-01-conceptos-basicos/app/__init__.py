import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        LAB_MODE=os.environ.get("LAB_MODE", "protected"),
        DATABASE=str(Path(app.instance_path) / "portal.sqlite"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    if test_config:
        app.config.update(test_config)

    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Debes configurar SECRET_KEY.")

    if app.config["LAB_MODE"] not in {"vulnerable", "protected"}:
        raise RuntimeError("LAB_MODE debe ser vulnerable o protected.")

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

    def init_db():
        db = get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                career TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS grades (
                id INTEGER PRIMARY KEY,
                student_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                score REAL NOT NULL CHECK(score BETWEEN 0 AND 10),
                FOREIGN KEY(student_id) REFERENCES students(id)
            );
        """)

        students = [
            (1001, "ana", "Ana Torres"),
            (1002, "luis", "Luis Mendoza"),
        ]

        for student_id, username, name in students:
            exists = db.execute(
                "SELECT id FROM students WHERE id = ?",
                (student_id,),
            ).fetchone()

            if exists is None:
                db.execute(
                    """
                    INSERT INTO students
                        (id, username, password_hash, name, career)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        student_id,
                        username,
                        generate_password_hash("Laboratorio123!"),
                        name,
                        "Ingeniería de Software",
                    ),
                )

                grades = (
                    [
                        ("Ingeniería de la Seguridad", 8.5),
                        ("Bases de Datos", 9.0),
                        ("Redes", 8.0),
                    ]
                    if student_id == 1001
                    else [
                        ("Ingeniería de la Seguridad", 7.0),
                        ("Bases de Datos", 8.0),
                        ("Redes", 9.5),
                    ]
                )

                db.executemany(
                    """
                    INSERT INTO grades (student_id, subject, score)
                    VALUES (?, ?, ?)
                    """,
                    [
                        (student_id, subject, score)
                        for subject, score in grades
                    ],
                )

        db.commit()

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "student_id" not in session:
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped

    @app.context_processor
    def laboratory_context():
        return {"lab_mode": app.config["LAB_MODE"]}

    @app.route("/")
    def index():
        if "student_id" in session:
            return redirect(
                url_for("student", student_id=session["student_id"])
            )
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None

        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            user = get_db().execute(
                "SELECT * FROM students WHERE username = ?",
                (username,),
            ).fetchone()

            if user and check_password_hash(
                user["password_hash"], password
            ):
                session.clear()
                session["student_id"] = user["id"]
                session["student_name"] = user["name"]

                return redirect(
                    url_for("student", student_id=user["id"])
                )

            error = "Usuario o contraseña incorrectos."

        return render_template("login.html", error=error)

    @app.route("/estudiante/<int:student_id>")
    @login_required
    def student(student_id):
        # CONTROL: el servidor comprueba quién solicita el expediente.
        if app.config["LAB_MODE"] == "protected":
            if student_id != session["student_id"]:
                app.logger.warning(
                    "Acceso bloqueado: usuario=%s expediente=%s",
                    session["student_id"],
                    student_id,
                )
                abort(403)

        # En modo vulnerable se omite la comprobación anterior.
        student_record = get_db().execute(
            """
            SELECT id, name, career
            FROM students
            WHERE id = ?
            """,
            (student_id,),
        ).fetchone()

        if student_record is None:
            abort(404)

        grades = get_db().execute(
            """
            SELECT subject, score
            FROM grades
            WHERE student_id = ?
            ORDER BY id
            """,
            (student_id,),
        ).fetchall()

        return render_template(
            "student.html",
            student=student_record,
            grades=grades,
        )

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.errorhandler(403)
    def forbidden(error):
        return render_template(
            "error.html",
            code=403,
            title="Acceso denegado",
            message="No tienes permiso para consultar este expediente.",
        ), 403

    @app.errorhandler(404)
    def not_found(error):
        return render_template(
            "error.html",
            code=404,
            title="Expediente no encontrado",
            message="El recurso solicitado no existe.",
        ), 404

    with app.app_context():
        init_db()

    return app