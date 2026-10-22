# Laboratorio 01 — ¿Una aplicación funcional puede ser insegura?

Este laboratorio reproduce un fallo de autorización en un portal académico
local. Un estudiante inicia sesión correctamente, pero puede consultar
el expediente de otro estudiante modificando un identificador en la URL.

Después se activa una comprobación de permisos en el servidor y se repite
la prueba para verificar que el acceso ajeno queda bloqueado y el propio
continúa funcionando.

Todos los nombres, cuentas y calificaciones son ficticios. La aplicación
contiene una vulnerabilidad intencional para fines educativos y se publica
únicamente en la dirección local del equipo.

## 1. Objetivo

Distinguir funcionalidad y seguridad mediante una demostración reproducible,
relacionando el comportamiento observado con los conceptos básicos de
Ingeniería de la Seguridad.

## 2. Requisitos

- Git.
- Docker Engine en funcionamiento y Docker Compose.
- Navegador web.
- Conexión a Internet para descargar inicialmente las imágenes y dependencias.
- Puerto local 8000 disponible.

Comprobar Docker:

```bash
docker info
docker compose version
```

El primer comando debe mostrar la sección `Server` sin errores de conexión
o permisos.

Los comandos de este documento están preparados para una terminal de
Ubuntu. No se necesita instalar Python ni las dependencias en el equipo:
se ejecutan dentro del contenedor.

## 3. Descargar el proyecto

Si todavía no tienes el repositorio:

```bash
git clone https://github.com/Jeancarlospp/ingenieria-seguridad-labs.git
cd ingenieria-seguridad-labs
```

Si ya lo tienes descargado, abre una terminal en la raíz del repositorio.

Después entra en el laboratorio:

```bash
cd labs/video-01-conceptos-basicos
```

Todos los comandos siguientes se ejecutan desde esta carpeta.

## 4. Arquitectura

Navegador → aplicación Flask → base de datos SQLite.

- Flask gestiona el inicio de sesión y la consulta de expedientes.
- SQLite almacena estudiantes y calificaciones ficticias.
- Gunicorn ejecuta la aplicación.
- Docker Compose configura el servicio.
- Un volumen de Docker conserva la base de datos al recrear el contenedor.

La dirección publicada es:

http://localhost:8000

La configuración enlaza el puerto con `127.0.0.1`, por lo que el laboratorio
no se publica en las interfaces de red del equipo.

## 5. Cuentas de demostración

| Usuario | Contraseña ficticia | Expediente |
|---|---|---|
| ana | Laboratorio123! | 1001 — Ana Torres |
| luis | Laboratorio123! | 1002 — Luis Mendoza |

Las contraseñas se almacenan como hashes en la base de datos.
Estas credenciales son públicas y exclusivas del laboratorio.

## 6. Demostración antes del control

Arrancar explícitamente en modo vulnerable:

```bash
LAB_MODE=vulnerable docker compose up --build -d
```

La primera construcción puede tardar mientras se descargan las dependencias.

1. Abrir http://localhost:8000.
2. Iniciar sesión con `ana`.
3. Comprobar que se muestra el expediente de Ana en `/estudiante/1001`.
4. Cambiar manualmente la dirección a:
   http://localhost:8000/estudiante/1002.
5. Observar el nombre del expediente y la identidad de la sesión.

Resultado esperado:

- El portal indica `Modo vulnerable`.
- La sesión sigue perteneciendo a Ana Torres.
- Se muestran el expediente y las calificaciones de Luis Mendoza.
- La respuesta de esa consulta tiene estado HTTP 200.

El acceso ajeno se produce por una comprobación de autorización ausente.
No es necesario conocer la contraseña de Luis.

Para observar el estado HTTP en Firefox, abrir las herramientas de desarrollo
con F12, seleccionar la pestaña Red y recargar la página. Seleccionar
la solicitud correspondiente al expediente.

## 7. Código relevante y control

Archivo: `app/__init__.py`.

La función `login_required` exige que exista una sesión iniciada.
Sin embargo, estar autenticado no autoriza a consultar cualquier expediente.

El control se encuentra en la función `student`:

```python
if app.config["LAB_MODE"] == "protected":
    if student_id != session["student_id"]:
        app.logger.warning(
            "Acceso bloqueado: usuario=%s expediente=%s",
            session["student_id"],
            student_id,
        )
        abort(403)
```

En modo protegido, el servidor compara el identificador solicitado con
el del estudiante autenticado antes de consultar y devolver el expediente.

En modo vulnerable, esa comprobación se omite intencionalmente.

Ambos comportamientos están incluidos en el mismo código para facilitar
la comparación. Cambiar de modo activa o desactiva el control; no modifica
el archivo fuente.

## 8. Demostración posterior al control

Activar explícitamente el modo protegido:

```bash
LAB_MODE=protected docker compose up -d
```

1. Recargar http://localhost:8000/estudiante/1002 manteniendo la sesión de Ana.
2. Si no hay sesión, iniciar sesión como Ana y repetir la dirección.
3. Comprobar que aparece `Modo protegido`.
4. Comprobar la respuesta `403 — Acceso denegado`.
5. Pulsar `Volver a mi expediente`.
6. Verificar que Ana puede consultar sus propias calificaciones.

Repetir, si se desea, iniciando sesión como Luis e intentando acceder
al expediente 1001.

Resultados esperados:

| Situación | Modo vulnerable | Modo protegido |
|---|---|---|
| Usuario sin sesión solicita un expediente | Redirección al inicio de sesión | Redirección al inicio de sesión |
| Estudiante consulta su expediente | HTTP 200 | HTTP 200 |
| Estudiante consulta un expediente ajeno existente | HTTP 200: expone información | HTTP 403: bloquea el acceso |

Consultar el registro del bloqueo:

```bash
docker compose logs --tail=30 portal
```

Ejemplo:

```text
Acceso bloqueado: usuario=1001 expediente=1002
```

Ese registro es evidencia de la decisión del servidor. Por sí solo no
constituye una prueba de no repudio.

### Importante sobre los modos

Indicar siempre `LAB_MODE` al arrancar el portal.

La elección queda aplicada al contenedor creado, pero no se guarda como
preferencia para futuros comandos de Compose. En la configuración actual,
ejecutar `docker compose up -d` sin indicar un modo utiliza `vulnerable`
como valor predeterminado, salvo que exista otra configuración de entorno.

El indicador visible del portal permite comprobar el modo activo.

## 9. Pruebas automatizadas

Construir la imagen para incluir los archivos actuales:

```bash
docker compose build portal
```

Ejecutar las pruebas:

```bash
docker compose run --rm --no-deps portal python -m pytest -v
```

Resultado esperado:

```text
9 passed
```

Las pruebas comprueban:

- La exigencia de iniciar sesión en ambos modos.
- La exposición del expediente ajeno en modo vulnerable.
- El bloqueo del acceso ajeno para ambos estudiantes en modo protegido.
- El acceso legítimo de ambos estudiantes en ambos modos.

La prueba del modo vulnerable pasa cuando reproduce el fallo intencional.
Por tanto, que todas las pruebas pasen no significa que ambos modos sean seguros.

Las pruebas usan bases de datos temporales y no modifican los datos del portal.

## 10. Relación con los conceptos del tema

| Concepto | Ejemplo en el laboratorio |
|---|---|
| Dato | La calificación `8.5` |
| Información | La calificación asociada a una persona y asignatura |
| Activo | Los expedientes y los datos académicos |
| Recurso | El servidor, la aplicación y la base de datos |
| Sistema | El conjunto de usuarios, aplicación, datos y procesos |
| Servicio | La consulta de calificaciones |
| Usuario | Ana o Luis |
| Control | La comprobación de autorización en el servidor |
| Incidente | El acceso exitoso al expediente ajeno sin permiso |

Estas categorías pueden coincidir: una base de datos puede ser un recurso
para prestar el servicio y también un activo que debe protegerse.

### Ámbitos de seguridad

- Seguridad de la información: protege la información independientemente
  de su soporte, incluido un expediente impreso.
- Seguridad informática: protege los sistemas computacionales que procesan
  y almacenan la información.
- Ciberseguridad: aborda la protección de sistemas y servicios en su
  interacción mediante redes digitales.
- Seguridad de software: incorpora seguridad al diseño, desarrollo,
  pruebas y mantenimiento de la aplicación.

Estos ámbitos se superponen y aportan perspectivas complementarias.

## 11. Decisiones y limitaciones

- La comprobación se realiza en el servidor porque el cliente puede
  modificar la dirección y las solicitudes.
- Las consultas SQL están parametrizadas en ambos modos. El fallo
  demostrado corresponde a autorización, no a inyección SQL.
- La regla permite a cada estudiante consultar únicamente su expediente.
  No implementa permisos para docentes ni administradores.
- La prueba posterior comprueba tanto el bloqueo como el acceso legítimo.
- Se demuestra una ruta de consulta; no una auditoría completa del sistema.
- Es un laboratorio educativo, no una aplicación preparada para producción.
- Incluye credenciales y una clave de sesión públicas de demostración.
- No incorpora todas las protecciones de una aplicación real, como HTTPS,
  protección CSRF en formularios o limitación de intentos de inicio de sesión.
- El modo vulnerable está presente intencionalmente y no debe desplegarse
  como un servicio público.

## 12. Detener y reiniciar

Detener el laboratorio conservando la base de datos:

```bash
docker compose down
```

Arrancar de nuevo indicando el modo deseado:

```bash
LAB_MODE=protected docker compose up -d
```

Para borrar los datos locales del laboratorio y volver a crear los
estudiantes iniciales:

```bash
docker compose down -v
LAB_MODE=vulnerable docker compose up -d
```

Atención: `down -v` elimina el volumen y los datos persistidos de este
proyecto de Compose. No es necesario hacerlo para cambiar de modo.

## 13. Problemas frecuentes

### El navegador no conecta

Comprobar el estado y los registros:

```bash
docker compose ps
docker compose logs --tail=50 portal
```

### El puerto 8000 ya está ocupado

Detener el otro servicio que lo utiliza o cambiar en `compose.yaml`:

```yaml
ports:
  - "127.0.0.1:8001:8000"
```

Después recrear el servicio indicando el modo y abrir
http://localhost:8001.

### Los cambios del código no aparecen

El código se copia al construir la imagen. Reconstruir y recrear:

```bash
LAB_MODE=protected docker compose up --build -d
```

### No se puede descargar el repositorio

Si el repositorio es privado, se necesita acceso como colaborador y
autenticación en GitHub.

## 14. Identificar la versión mostrada

Desde el repositorio:

```bash
git rev-parse HEAD
git status --short
```

El primer comando muestra el commit que se debe anotar en el índice de
entrega. El segundo debe quedar sin salida para confirmar que no hay
cambios locales pendientes que alteren esa versión.

## 15. Herramientas y fuentes

- Flask: https://flask.palletsprojects.com/
- Werkzeug: https://werkzeug.palletsprojects.com/
- SQLite: https://www.sqlite.org/docs.html
- Docker Compose: https://docs.docker.com/compose/
- pytest: https://docs.pytest.org/
- OWASP, prevención de IDOR:
  https://cheatsheetseries.owasp.org/cheatsheets/Insecure_Direct_Object_Reference_Prevention_Cheat_Sheet.html
- Material docente del tema 1.1.1 — Conceptos básicos.

### Declaración de apoyo de IA

Se utilizó ChatGPT/Codex como apoyo para proponer la estructura del
laboratorio, generar una base de código y pruebas, y redactar documentación.
La implementación fue ejecutada y verificada por los integrantes.
Cada participante debe comprender y poder explicar el código presentado.