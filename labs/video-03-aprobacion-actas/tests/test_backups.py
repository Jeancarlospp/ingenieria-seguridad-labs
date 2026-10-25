import hashlib
import json
from io import BytesIO
from pathlib import Path

import pytest


@pytest.fixture
def backup_name(app):
    result = app.test_cli_runner().invoke(
        args=["backup-document", "102"]
    )

    assert result.exit_code == 0, result.output

    return result.output.strip().split("Respaldo creado: ", 1)[1]


def restore(app, backup_name):
    return app.test_cli_runner().invoke(
        args=["restore-document", backup_name]
    )


def test_backup_contains_original_file_and_metadata(
    app, backup_name, document_snapshot
):
    original = document_snapshot(102)
    folder = Path(app.instance_path) / "backups" / backup_name

    content = (folder / "document.pdf").read_bytes()
    manifest = json.loads(
        (folder / "manifest.json").read_text(encoding="utf-8")
    )

    assert content == original["content"]
    assert manifest["format"] == "alameda-document-backup-v1"
    assert manifest["document"] == original["metadata"]
    assert manifest["sha256"] == hashlib.sha256(content).hexdigest()


def test_restore_deleted_document_preserves_content_and_permissions(
    app,
    client,
    login,
    csrf_token,
    document_snapshot,
    backup_name,
):
    original = document_snapshot(102)
    login("elena")

    response = client.post(
        "/documentos/102/eliminar",
        data={"csrf_token": csrf_token()},
    )

    assert response.status_code == 302
    assert document_snapshot(102) is None

    result = restore(app, backup_name)

    assert result.exit_code == 0, result.output

    recovered = document_snapshot(102)

    assert recovered["content"] == original["content"]

    for field in (
        "id",
        "title",
        "subject_id",
        "owner_id",
        "audience",
        "original_name",
        "size_bytes",
        "created_at",
        "updated_at",
    ):
        assert recovered["metadata"][field] == original["metadata"][field]

    assert client.get("/documentos/102").status_code == 200

    client.post(
        "/salir",
        data={"csrf_token": csrf_token()},
    )
    login("ana")

    assert client.get("/documentos/102").status_code == 403
    assert client.get("/documentos/102/archivo").status_code == 403


def test_restore_replaced_document_recovers_original(
    app,
    client,
    login,
    csrf_token,
    document_snapshot,
    backup_name,
):
    original = document_snapshot(102)
    replacement = document_snapshot(101)["content"]

    login("elena")

    response = client.post(
        "/documentos/102/sustituir",
        data={
            "csrf_token": csrf_token(),
            "file": (
                BytesIO(replacement),
                "version-distinta.pdf",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 302

    modified = document_snapshot(102)
    assert modified["content"] == replacement

    result = restore(app, backup_name)

    assert result.exit_code == 0, result.output
    assert document_snapshot(102)["content"] == original["content"]
    assert not modified["path"].exists()

    # Restaurar no consume ni elimina la copia de respaldo.
    backup_file = (
        Path(app.instance_path)
        / "backups"
        / backup_name
        / "document.pdf"
    )
    assert backup_file.read_bytes() == original["content"]


def test_corrupted_backup_does_not_overwrite_active_document(
    app, backup_name, document_snapshot
):
    before = document_snapshot(102)

    backup_file = (
        Path(app.instance_path)
        / "backups"
        / backup_name
        / "document.pdf"
    )
    backup_file.write_bytes(backup_file.read_bytes() + b"alterado")

    result = restore(app, backup_name)

    assert result.exit_code != 0
    assert document_snapshot(102) == before


def test_incompatible_backup_does_not_overwrite_active_document(
    app, backup_name, document_snapshot
):
    before = document_snapshot(102)

    manifest_path = (
        Path(app.instance_path)
        / "backups"
        / backup_name
        / "manifest.json"
    )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    manifest["format"] = "formato-no-compatible"

    manifest_path.write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    result = restore(app, backup_name)

    assert result.exit_code != 0
    assert document_snapshot(102) == before


@pytest.mark.parametrize(
    "invalid_name",
    [
        "../documents",
        "/tmp/archivo",
        "102-no-valido",
    ],
)
def test_invalid_backup_name_is_rejected(
    app, document_snapshot, invalid_name
):
    before = document_snapshot(102)

    result = restore(app, invalid_name)

    assert result.exit_code != 0
    assert document_snapshot(102) == before


def test_cannot_backup_missing_document(app):
    result = app.test_cli_runner().invoke(
        args=["backup-document", "999"]
    )

    assert result.exit_code != 0
    assert "El documento no existe" in result.output