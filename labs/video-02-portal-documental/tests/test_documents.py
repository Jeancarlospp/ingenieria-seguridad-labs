import re
from io import BytesIO

import pytest


@pytest.mark.parametrize(
    "username, expected_ids",
    [
        ("ana", {101}),
        ("luis", {201}),
        ("elena", {101, 102}),
        ("marco", {201, 202}),
    ],
)
def test_list_only_contains_authorized_documents(
    client, login, username, expected_ids
):
    login(username)

    response = client.get("/documentos")
    html = response.get_data(as_text=True)

    visible_ids = {
        int(value)
        for value in re.findall(
            r'href="/documentos/(\d+)"',
            html,
        )
    }

    assert response.status_code == 200
    assert visible_ids == expected_ids


@pytest.mark.parametrize("suffix", ["", "/archivo"])
@pytest.mark.parametrize(
    "username, document_id, expected_status",
    [
        ("ana", 101, 200),
        ("ana", 102, 403),
        ("ana", 201, 403),
        ("elena", 102, 200),
        ("marco", 102, 403),
        ("luis", 201, 200),
        ("luis", 202, 403),
        ("marco", 202, 200),
    ],
)
def test_detail_and_file_check_permissions(
    client,
    login,
    username,
    document_id,
    expected_status,
    suffix,
):
    login(username)

    response = client.get(
        f"/documentos/{document_id}{suffix}"
    )

    assert response.status_code == expected_status

    if expected_status == 403:
        assert not response.data.startswith(b"%PDF-")
        assert "Publicado por" not in response.get_data(as_text=True)

    elif suffix == "/archivo":
        assert response.mimetype == "application/pdf"
        assert response.data.startswith(b"%PDF-")


@pytest.mark.parametrize(
    "path",
    [
        "/documentos/102",
        "/documentos/102/archivo",
        "/documentos/102/sustituir",
        "/documentos/102/eliminar",
        "/documentos/nuevo",
    ],
)
def test_anonymous_user_is_redirected(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/ingresar")


@pytest.mark.parametrize("username", ["ana", "marco"])
@pytest.mark.parametrize("operation", ["sustituir", "eliminar"])
def test_forbidden_operations_do_not_change_document(
    client,
    login,
    csrf_token,
    document_snapshot,
    username,
    operation,
):
    login(username)
    before = document_snapshot(102)

    response = client.post(
        f"/documentos/102/{operation}",
        data={
            "csrf_token": csrf_token(),
            "file": (
                BytesIO(before["content"]),
                "intento.pdf",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 403
    assert document_snapshot(102) == before


def test_teacher_can_replace_document(
    client, login, csrf_token, document_snapshot
):
    login("elena")

    original = document_snapshot(102)
    replacement = document_snapshot(101)["content"]

    response = client.post(
        "/documentos/102/sustituir",
        data={
            "csrf_token": csrf_token(),
            "file": (
                BytesIO(replacement),
                "acta-revisada.pdf",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 302

    updated = document_snapshot(102)

    assert updated["content"] == replacement
    assert updated["metadata"]["id"] == 102
    assert updated["metadata"]["title"] == original["metadata"]["title"]
    assert updated["metadata"]["audience"] == "teachers"
    assert updated["metadata"]["original_name"] == "acta-revisada.pdf"
    assert updated["path"] != original["path"]
    assert not original["path"].exists()


def test_teacher_can_delete_document(
    client, login, csrf_token, document_snapshot
):
    login("elena")
    before = document_snapshot(102)

    response = client.post(
        "/documentos/102/eliminar",
        data={"csrf_token": csrf_token()},
    )

    assert response.status_code == 302
    assert document_snapshot(102) is None
    assert not before["path"].exists()
    assert client.get("/documentos/102").status_code == 404
    assert client.get("/documentos/102/archivo").status_code == 404


def test_opening_delete_confirmation_does_not_delete(
    client, login, document_snapshot
):
    login("elena")
    before = document_snapshot(102)

    response = client.get("/documentos/102/eliminar")

    assert response.status_code == 200
    assert document_snapshot(102) == before


def test_delete_requires_csrf_token(
    client, login, document_snapshot
):
    login("elena")
    before = document_snapshot(102)

    response = client.post("/documentos/102/eliminar")

    assert response.status_code == 400
    assert document_snapshot(102) == before


@pytest.mark.parametrize("username", ["ana", "luis"])
def test_students_cannot_open_upload_form(
    client, login, username
):
    login(username)

    assert client.get("/documentos/nuevo").status_code == 403


@pytest.mark.parametrize(
    "audience, visible_to_ana",
    [
        ("students", True),
        ("teachers", False),
    ],
)
def test_teacher_upload_respects_audience(
    client,
    login,
    csrf_token,
    document_snapshot,
    audience,
    visible_to_ana,
):
    login("elena")
    content = document_snapshot(101)["content"]

    response = client.post(
        "/documentos/nuevo",
        data={
            "csrf_token": csrf_token(),
            "title": "Material complementario",
            "subject_id": "1",
            "audience": audience,
            "file": (
                BytesIO(content),
                "material.pdf",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 302
    location = response.headers["Location"]

    client.post(
        "/salir",
        data={"csrf_token": csrf_token()},
    )
    login("ana")

    response = client.get(location)

    assert response.status_code == (
        200 if visible_to_ana else 403
    )


def test_teacher_cannot_upload_to_another_subject(
    client, login, csrf_token, document_snapshot
):
    login("marco")
    content = document_snapshot(201)["content"]

    response = client.post(
        "/documentos/nuevo",
        data={
            "csrf_token": csrf_token(),
            "title": "Documento fuera de asignatura",
            "subject_id": "1",
            "audience": "students",
            "file": (
                BytesIO(content),
                "documento.pdf",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "filename, content",
    [
        ("archivo.txt", b"Esto no es un PDF"),
        ("archivo.pdf", b"Esto tampoco es un PDF"),
        ("vacio.pdf", b""),
    ],
)
def test_invalid_replacement_preserves_original(
    client,
    login,
    csrf_token,
    document_snapshot,
    filename,
    content,
):
    login("elena")
    before = document_snapshot(102)

    response = client.post(
        "/documentos/102/sustituir",
        data={
            "csrf_token": csrf_token(),
            "file": (
                BytesIO(content),
                filename,
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert document_snapshot(102) == before


def test_search_does_not_expose_private_documents(
    client, login
):
    login("ana")

    response = client.get("/documentos?q=Acta")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href="/documentos/102"' not in html
    assert "No encontramos coincidencias" in html


def test_subject_filter_does_not_grant_access(
    client, login
):
    login("elena")

    response = client.get("/documentos?subject=2")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'href="/documentos/201"' not in html
    assert 'href="/documentos/202"' not in html