# Alameda · Portal documental

Aplicación académica para demostrar confidencialidad, integridad,
disponibilidad y su relación con el Hexad de Parker mediante
un incidente de autorización sobre documentos.

La práctica utiliza una institución, usuarios y datos ficticios.
Se ejecuta únicamente en el equipo local.

## Requisitos

- Git.
- Docker Engine y Docker Compose.
- Navegador.
- curl y Python 3 para preparar las solicitudes desde Ubuntu.
- Puerto 8001 disponible.

## Versiones del escenario

- `video-02/autorizacion-ausente`: omite la comprobación de permisos
  sobre documentos solicitados directamente.
- `video-02/correccion-verificada`: aplica autorización por
  asignatura, audiencia y operación.
- `alameda-autorizacion-correcta-v1`: referencia de la implementación
  correcta y sus pruebas.

La interfaz no cambia entre escenarios.
El listado permanece filtrado en ambas versiones.

## Arranque inicial

Desde la raíz del repositorio:

```bash
cd labs/video-02-portal-documental
docker compose up --build -d
docker compose exec web flask --app app seed-documents
```

Abrir http://localhost:8001.

El comando de preparación crea los documentos iniciales ausentes.
No debe utilizarse como recuperación durante la demostración:
para eso se utiliza el respaldo del documento original.

## Cuentas de práctica

Contraseña para las cuatro cuentas: `Alameda2026!`.

| Usuario | Rol | Asignatura |
|---|---|---|
| ana | Estudiante | Matemáticas |
| luis | Estudiante | Ciencias Naturales |
| elena | Docente | Matemáticas |
| marco | Docente | Ciencias Naturales |

Las credenciales y la clave configurada en Compose son de desarrollo.
No deben utilizarse en un despliegue público.

## Documentos

| ID | Archivo | Audiencia |
|---|---|---|
| 101 | Guía de Matemáticas | Estudiantes y docente de Matemáticas |
| 102 | Acta de Matemáticas | Solo docente de Matemáticas |
| 201 | Guía de Ciencias Naturales | Estudiantes y docente de Ciencias |
| 202 | Acta de Ciencias Naturales | Solo docente de Ciencias |

Los PDF están fuera de la carpeta pública.
El acceso se realiza mediante rutas de la aplicación.

## Incidente demostrado

Con una sesión real de Ana y su token CSRF válido:

1. Descargar el acta 102 sin autorización.
2. Sustituir su contenido mediante una solicitud POST.
3. Eliminarla mediante una solicitud POST.

No se utilizan cookies docentes para atribuir acciones al estudiante.

Consecuencias:

- Lectura indebida: confidencialidad.
- Sustitución indebida: integridad.
- Documento inaccesible tras eliminarlo: disponibilidad del documento.

No se afirma que todo el portal haya sido derribado.

## Corrección

La función `authorized_document` utiliza la política definida en
`permissions.py` antes de permitir operaciones sobre un documento.

Se consideran usuario autenticado, asignatura, audiencia y operación.
Tener el rol docente no concede acceso a otras asignaturas.

Al repetir las tres solicitudes como Ana, todas deben devolver HTTP 403.
Elena conserva sus operaciones legítimas y Marco no accede al acta 102.

La protección CSRF se conserva en ambos escenarios.
Un token válido no concede permisos sobre un documento.

## Respaldo y recuperación

Antes del incidente, con el acta original:

```bash
docker compose exec web flask --app app backup-document 102
```

Guardar el identificador devuelto.

Para recuperar el PDF y sus metadatos:

```bash
docker compose exec web flask --app app restore-document IDENTIFICADOR
```

Sustituir `IDENTIFICADOR` por el valor real.

Comprobar contenido, audiencia y acceso legítimo después de restaurar.

Los respaldos comparten el volumen local con la aplicación:
permiten recuperar una eliminación de esta práctica, pero no protegen
frente a perder todo el volumen.

## Relación con el Hexad de Parker

- Posesión/control: bloquear nuevas descargas no recupera el control
  de una copia que otra persona ya obtuvo.
- Autenticidad: nombre y apariencia no acreditan quién emitió un acta.
  Este laboratorio no implementa firma digital ni acredita su emisor.
- Utilidad: el respaldo debe restaurarse y producir un documento legible
  y adecuado para su propósito.

SHA-256 permite comparar contenido con el manifiesto del respaldo.
No constituye por sí solo una prueba de autenticidad.

## Pruebas de la versión correcta

```bash
docker compose build web
docker compose run --rm --no-deps web python -m pytest -v
```

Resultado esperado: `52 passed`.

Las pruebas utilizan archivos y bases temporales.
En la versión vulnerable fallarán los casos que exigen autorización;
eso documenta el fallo deliberado y no debe ocultarse modificando
sus resultados esperados.

## Cambiar entre escenarios

Con los cambios locales guardados, desde la raíz del repositorio:

```bash
git switch video-02/autorizacion-ausente
```

O:

```bash
git switch video-02/correccion-verificada
```

Después, desde la carpeta de la aplicación:

```bash
docker compose up --build -d
```

Cambiar de rama no restaura los datos.
Recuperar el acta desde su respaldo antes de repetir la grabación.

No ejecutar `docker compose down -v` para alternar escenarios:
eliminaría también los datos y respaldos del volumen.

## Evidencia de entrega

Antes de grabar cada versión:

```bash
git status --short
git rev-parse HEAD
```

Anotar el commit y mantener el árbol de trabajo limpio.
El índice de entrega incluirá participantes, tema, duración,
enlace del video y commits mostrados.

## Fuentes y apoyo de IA

- Material docente 1.1.2: Tríada CIA y Hexad de Parker.
- Flask: https://flask.palletsprojects.com/
- OWASP, autorización:
  https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- SQLite: https://www.sqlite.org/docs.html
- Docker Compose: https://docs.docker.com/compose/

Se utilizó ChatGPT/Codex para apoyar la preparación del código,
las pruebas y la documentación. Los integrantes ejecutaron las
comprobaciones y deben comprender las decisiones presentadas.

La aplicación cubre el escenario educativo descrito.
Las pruebas aprobadas no representan una certificación de seguridad
ni preparación completa para producción.