import pytest

from app import create_app


@pytest.fixture
def make_client(tmp_path):
    def factory(mode):
        app = create_app({
            "TESTING": True,
            "SECRET_KEY": "clave-ficticia-para-pruebas",
            "LAB_MODE": mode,
            "DATABASE": str(tmp_path / f"{mode}.sqlite"),
        })
        return app.test_client()

    return factory


def login(client, username):
    return client.post(
        "/login",
        data={
            "username": username,
            "password": "Laboratorio123!",
        },
    )


@pytest.mark.parametrize("mode", ["vulnerable", "protected"])
def test_requires_login(make_client, mode):
    client = make_client(mode)

    response = client.get("/estudiante/1001")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    assert b"Ana Torres" not in response.data


def test_vulnerable_mode_exposes_another_record(make_client):
    client = make_client("vulnerable")
    login(client, "ana")

    response = client.get("/estudiante/1002")

    assert response.status_code == 200
    assert b"Luis Mendoza" in response.data
    assert b"9.5" in response.data

    # Consultar otro expediente no cambia la identidad de la sesión.
    with client.session_transaction() as current_session:
        assert current_session["student_id"] == 1001


@pytest.mark.parametrize(
    "username, other_id, other_name",
    [
        ("ana", 1002, b"Luis Mendoza"),
        ("luis", 1001, b"Ana Torres"),
    ],
)
def test_protected_mode_blocks_another_record(
    make_client, username, other_id, other_name
):
    client = make_client("protected")
    login(client, username)

    response = client.get(f"/estudiante/{other_id}")

    assert response.status_code == 403
    assert other_name not in response.data
    assert b"Calificaciones" not in response.data


@pytest.mark.parametrize("mode", ["vulnerable", "protected"])
@pytest.mark.parametrize(
    "username, own_id, own_name",
    [
        ("ana", 1001, b"Ana Torres"),
        ("luis", 1002, b"Luis Mendoza"),
    ],
)
def test_own_record_remains_accessible(
    make_client, mode, username, own_id, own_name
):
    client = make_client(mode)

    login_response = login(client, username)
    assert login_response.status_code == 302
    assert login_response.headers["Location"].endswith(
        f"/estudiante/{own_id}"
    )

    response = client.get(f"/estudiante/{own_id}")

    assert response.status_code == 200
    assert own_name in response.data
    assert b"Calificaciones" in response.data