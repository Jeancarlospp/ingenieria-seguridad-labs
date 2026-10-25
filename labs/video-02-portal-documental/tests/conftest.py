import sqlite3
from pathlib import Path

import pytest

from app import create_app


@pytest.fixture
def app(tmp_path):
    instance = tmp_path / "instance"

    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "clave-exclusiva-de-pruebas",
        "INSTANCE_PATH": str(instance),
        "DATABASE": str(instance / "test.sqlite"),
    })

    result = application.test_cli_runner().invoke(
        args=["seed-documents"]
    )

    assert result.exit_code == 0, result.output

    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def login(client):
    def perform(username):
        # Abre el formulario para obtener su token CSRF real.
        client.get("/ingresar")

        with client.session_transaction() as current_session:
            token = current_session["csrf_token"]

        response = client.post(
            "/ingresar",
            data={
                "username": username,
                "password": "Alameda2026!",
                "csrf_token": token,
            },
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/documentos")

        return response

    return perform


@pytest.fixture
def csrf_token(client):
    def current_token():
        with client.session_transaction() as current_session:
            return current_session["csrf_token"]

    return current_token


@pytest.fixture
def document_snapshot(app):
    def snapshot(document_id):
        with sqlite3.connect(
            app.config["DATABASE"]
        ) as connection:
            connection.row_factory = sqlite3.Row
            record = connection.execute(
                "SELECT * FROM documents WHERE id = ?",
                (document_id,),
            ).fetchone()

        if record is None:
            return None

        metadata = dict(record)
        path = (
            Path(app.instance_path)
            / "documents"
            / metadata["storage_name"]
        )

        return {
            "metadata": metadata,
            "path": path,
            "content": path.read_bytes(),
        }

    return snapshot