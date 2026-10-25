READ_ACTIONS = {"view", "download"}
MANAGE_ACTIONS = {"replace", "delete"}


def can_access_document(user, document, subject_ids, action):
    """
    Decide si un usuario puede realizar una operación sobre un documento.

    subject_ids debe obtenerse de la base de datos, no del formulario
    ni de parámetros enviados por el navegador.
    """
    if user is None or document is None:
        return False

    if document["subject_id"] not in subject_ids:
        return False

    role = user["role"]

    if action in READ_ACTIONS:
        if role == "teacher":
            return True

        return (
            role == "student"
            and document["audience"] == "students"
        )

    if action in MANAGE_ACTIONS:
        return role == "teacher"

    # Una operación desconocida no recibe permiso por defecto.
    return False


def can_upload_document(user, subject_id, subject_ids):
    """Un docente solo puede publicar en sus asignaturas."""
    return (
        user is not None
        and user["role"] == "teacher"
        and subject_id in subject_ids
    )