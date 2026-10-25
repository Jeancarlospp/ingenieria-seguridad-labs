import uuid
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from werkzeug.utils import secure_filename


MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PDF_PAGES = 100


class InvalidDocument(ValueError):
    pass


def save_pdf(upload, directory):
    if upload is None or not upload.filename:
        raise InvalidDocument("Selecciona un archivo PDF.")

    original_name = secure_filename(upload.filename)

    if not original_name.lower().endswith(".pdf"):
        raise InvalidDocument("El archivo debe tener extensión PDF.")

    content = upload.stream.read(MAX_PDF_BYTES + 1)

    if not content:
        raise InvalidDocument("El archivo está vacío.")

    if len(content) > MAX_PDF_BYTES:
        raise InvalidDocument("El PDF no puede superar los 8 MB.")

    if not content.startswith(b"%PDF-"):
        raise InvalidDocument("El archivo no tiene un formato PDF válido.")

    try:
        reader = PdfReader(BytesIO(content), strict=True)

        if reader.is_encrypted:
            raise InvalidDocument(
                "El PDF no debe estar protegido con contraseña."
            )

        pages = len(reader.pages)

        if not 1 <= pages <= MAX_PDF_PAGES:
            raise InvalidDocument(
                "El PDF debe tener entre 1 y 100 páginas."
            )

    except InvalidDocument:
        raise
    except Exception as error:
        raise InvalidDocument(
            "No se pudo leer el PDF. Comprueba el archivo."
        ) from error

    storage = Path(directory)
    storage.mkdir(parents=True, exist_ok=True)

    storage_name = f"{uuid.uuid4().hex}.pdf"
    destination = storage / storage_name

    try:
        with destination.open("xb") as file:
            file.write(content)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return {
        "storage_name": storage_name,
        "original_name": original_name,
        "size_bytes": len(content),
    }