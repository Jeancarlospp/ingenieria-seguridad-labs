import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path


class BackupError(ValueError):
    pass


DOCUMENT_FIELDS = (
    "id",
    "title",
    "subject_id",
    "owner_id",
    "audience",
    "storage_name",
    "original_name",
    "size_bytes",
    "created_at",
    "updated_at",
)


def file_hash(path):
    digest = hashlib.sha256()

    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(65536), b""):
            digest.update(block)

    return digest.hexdigest()


def create_document_backup(db, instance_path, document_id):
    instance = Path(instance_path)

    record = db.execute(
        "SELECT * FROM documents WHERE id = ?",
        (document_id,),
    ).fetchone()

    if record is None:
        raise BackupError("El documento no existe.")

    source = (
        instance / "documents" / record["storage_name"]
    )

    if not source.is_file():
        raise BackupError("No se encuentra el archivo del documento.")

    backup_name = f"{document_id}-{uuid.uuid4().hex}"
    backup_directory = instance / "backups" / backup_name
    backup_directory.mkdir(parents=True, exist_ok=False)

    try:
        destination = backup_directory / "document.pdf"
        shutil.copyfile(source, destination)

        metadata = {
            field: record[field]
            for field in DOCUMENT_FIELDS
        }

        manifest = {
            "format": "alameda-document-backup-v1",
            "document": metadata,
            "sha256": file_hash(destination),
        }

        (backup_directory / "manifest.json").write_text(
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    except Exception:
        shutil.rmtree(backup_directory)
        raise

    return backup_name


def restore_document_backup(db, instance_path, backup_name):
    if not re.fullmatch(r"\d+-[a-f0-9]{32}", backup_name):
        raise BackupError("El identificador del respaldo no es válido.")

    instance = Path(instance_path)
    backup_directory = instance / "backups" / backup_name

    try:
        manifest = json.loads(
            (backup_directory / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, ValueError) as error:
        raise BackupError(
            "No se pudo leer el manifiesto del respaldo."
        ) from error

    if not isinstance(manifest, dict):
        raise BackupError("El manifiesto no tiene un formato válido.")

    if manifest.get("format") != "alameda-document-backup-v1":
        raise BackupError("El formato del respaldo no es compatible.")

    metadata = manifest.get("document")

    if (
        not isinstance(metadata, dict)
        or set(metadata) != set(DOCUMENT_FIELDS)
    ):
        raise BackupError("Los metadatos están incompletos.")

    expected_id = int(backup_name.split("-", 1)[0])

    if metadata["id"] != expected_id:
        raise BackupError("El respaldo no corresponde al documento.")

    source = backup_directory / "document.pdf"

    if not source.is_file():
        raise BackupError("Falta el PDF del respaldo.")

    if file_hash(source) != manifest.get("sha256"):
        raise BackupError(
            "El contenido del respaldo no coincide con su manifiesto."
        )

    if source.stat().st_size != metadata["size_bytes"]:
        raise BackupError("El tamaño del respaldo no coincide.")

    storage = instance / "documents"
    storage.mkdir(parents=True, exist_ok=True)

    storage_name = f"{uuid.uuid4().hex}.pdf"
    destination = storage / storage_name

    previous = db.execute(
        "SELECT storage_name FROM documents WHERE id = ?",
        (metadata["id"],),
    ).fetchone()

    try:
        shutil.copyfile(source, destination)

        db.execute(
            """
            INSERT INTO documents (
                id, title, subject_id, owner_id, audience,
                storage_name, original_name, size_bytes,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                subject_id = excluded.subject_id,
                owner_id = excluded.owner_id,
                audience = excluded.audience,
                storage_name = excluded.storage_name,
                original_name = excluded.original_name,
                size_bytes = excluded.size_bytes,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                metadata["id"],
                metadata["title"],
                metadata["subject_id"],
                metadata["owner_id"],
                metadata["audience"],
                storage_name,
                metadata["original_name"],
                metadata["size_bytes"],
                metadata["created_at"],
                metadata["updated_at"],
            ),
        )
        db.commit()

    except Exception:
        db.rollback()
        destination.unlink(missing_ok=True)
        raise

    # El documento restaurado ya está disponible.
    # Retiramos una versión activa anterior, si existía.
    cleanup_warning = False

    if previous:
        try:
            (
                storage / previous["storage_name"]
            ).unlink(missing_ok=True)
        except OSError:
            cleanup_warning = True

    return metadata["id"], cleanup_warning