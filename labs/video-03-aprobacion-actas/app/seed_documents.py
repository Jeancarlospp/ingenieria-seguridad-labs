import uuid
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#2457A7")
MUTED = colors.HexColor("#526174")
BORDER = colors.HexColor("#DCE3EB")


def generate_pdf(path, title, subject, teacher, internal):
    styles = {
        "institution": ParagraphStyle(
            "Institution",
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=NAVY,
            spaceAfter=5 * mm,
        ),
        "title": ParagraphStyle(
            "DocumentTitle",
            fontName="Helvetica-Bold",
            fontSize=21,
            leading=26,
            textColor=NAVY,
            spaceAfter=5 * mm,
        ),
        "body": ParagraphStyle(
            "DocumentBody",
            fontName="Helvetica",
            fontSize=11,
            leading=17,
            textColor=colors.HexColor("#243247"),
            spaceAfter=4 * mm,
            alignment=TA_LEFT,
        ),
        "metadata": ParagraphStyle(
            "Metadata",
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            textColor=MUTED,
            spaceAfter=5 * mm,
        ),
    }

    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=24 * mm,
        title=title,
        author=teacher,
    )

    story = [
        Paragraph("INSTITUTO ALAMEDA", styles["institution"]),
        Paragraph(title, styles["title"]),
        Paragraph(
            f"{subject} · Período académico 2026<br/>"
            f"Docente responsable: {teacher}",
            styles["metadata"],
        ),
    ]

    if internal:
        story.extend([
            Paragraph(
                "Acta interna de evaluación",
                styles["body"],
            ),
            Paragraph(
                "Registro de resultados del primer período. "
                "Documento reservado al personal docente autorizado.",
                styles["body"],
            ),
            Spacer(1, 5 * mm),
        ])

        if subject == "Matemáticas":
            rows = [
                ["Código", "Estudiante", "Calificación / 10"],
                ["MAT-001", "Ana Torres", "8.5"],
                ["MAT-002", "Sofía Ríos", "9.0"],
                ["MAT-003", "Diego Vega", "7.5"],
            ]
        else:
            rows = [
                ["Código", "Estudiante", "Calificación / 10"],
                ["CIE-001", "Luis Mendoza", "8.0"],
                ["CIE-002", "Valeria Paz", "9.5"],
                ["CIE-003", "Andrés Mora", "7.0"],
            ]

        table = Table(
            rows,
            colWidths=[32 * mm, 77 * mm, 57 * mm],
            repeatRows=1,
        )

        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("LINEBELOW", (0, 0), (-1, 0), 1, NAVY),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, BORDER),
            ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ]))

        story.extend([
            table,
            Spacer(1, 8 * mm),
            Paragraph(
                "Estado: consolidado para revisión docente.",
                styles["body"],
            ),
        ])

    else:
        story.append(Paragraph(
            "Objetivo de aprendizaje",
            styles["body"],
        ))

        if subject == "Matemáticas":
            sections = [
                (
                    "Aplicar operaciones algebraicas y explicar "
                    "el procedimiento empleado."
                ),
                "1. Resuelve la ecuación: 3x + 6 = 24.",
                "2. Simplifica la expresión: 2(a + 3) - a.",
                (
                    "3. Un artículo cuesta 40 dólares y recibe un "
                    "descuento del 15 %. Calcula su precio final."
                ),
            ]
        else:
            sections = [
                (
                    "Registrar observaciones y distinguir evidencias "
                    "de interpretaciones."
                ),
                (
                    "1. Observa una planta y describe sus hojas, "
                    "tallo y condiciones del entorno."
                ),
                (
                    "2. Registra los cambios observados durante "
                    "cinco días."
                ),
                (
                    "3. Formula una explicación y señala qué "
                    "observaciones la respaldan."
                ),
            ]

        for text in sections:
            story.append(Paragraph(text, styles["body"]))

        story.extend([
            Spacer(1, 6 * mm),
            Paragraph(
                "Entrega: presenta tus respuestas con un "
                "procedimiento claro y ordenado.",
                styles["body"],
            ),
        ])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(BORDER)
        canvas.line(22 * mm, 20 * mm, 188 * mm, 20 * mm)
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(MUTED)
        canvas.drawString(
            22 * mm,
            14 * mm,
            "Instituto Alameda | Gestión académica",
        )
        canvas.drawRightString(
            188 * mm,
            14 * mm,
            f"Página {doc.page}",
        )
        canvas.restoreState()

    document.build(
        story,
        onFirstPage=footer,
        onLaterPages=footer,
    )


def seed_documents(db, storage_directory):
    storage = Path(storage_directory)
    storage.mkdir(parents=True, exist_ok=True)

    definitions = [
        (
            101, "Guía de ejercicios - Unidad 1",
            1, 3, "students", "guia-matematicas.pdf",
            "Matemáticas", "Elena Vargas",
        ),
        (
            102, "Acta de evaluación - Matemáticas",
            1, 3, "teachers", "acta-matematicas.pdf",
            "Matemáticas", "Elena Vargas",
        ),
        (
            201, "Guía de observación - Unidad 1",
            2, 4, "students", "guia-ciencias.pdf",
            "Ciencias Naturales", "Marco Salazar",
        ),
        (
            202, "Acta de evaluación - Ciencias Naturales",
            2, 4, "teachers", "acta-ciencias.pdf",
            "Ciencias Naturales", "Marco Salazar",
        ),
    ]

    created = 0

    for definition in definitions:
        (
            document_id, title, subject_id, owner_id,
            audience, original_name, subject, teacher,
        ) = definition

        existing = db.execute(
            "SELECT id FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()

        if existing is not None:
            continue

        storage_name = f"{uuid.uuid4().hex}.pdf"
        destination = storage / storage_name

        try:
            generate_pdf(
                destination,
                title,
                subject,
                teacher,
                internal=audience == "teachers",
            )

            timestamp = datetime.now(timezone.utc).isoformat(
                timespec="seconds"
            )

            db.execute(
                """
                INSERT INTO documents (
                    id, title, subject_id, owner_id, audience,
                    storage_name, original_name, size_bytes,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document_id, title, subject_id, owner_id,
                    audience, storage_name, original_name,
                    destination.stat().st_size,
                    timestamp, timestamp,
                ),
            )
            db.commit()

        except Exception:
            db.rollback()
            destination.unlink(missing_ok=True)
            raise

        created += 1

    return created