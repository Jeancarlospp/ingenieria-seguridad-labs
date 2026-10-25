# Alameda — Aprobación de documentos

Práctica del tema 1.1.3: autenticidad, trazabilidad, responsabilidad y no repudio.
El portal mantiene la interfaz institucional. Los conceptos y las instrucciones
educativas se explican en el video, fuera de las pantallas del producto.

## Alcance implementado

- Acceso y permisos por asignatura heredados de la versión corregida del video 02.
- Revisión y aprobación de documentos por docentes de su asignatura.
- Solicitudes vinculadas al PDF, la cuenta y una clave pública registrada.
- Firma Ed25519 con confirmación explícita y clave privada externa al portal.
- Comprobante descargable y verificación independiente del servidor.
- Historial con hora UTC, cuenta, origen, operación, documento, resultado y correlación.
- Rechazo de evidencias alteradas, caducadas y reutilizadas.
- Estado que exige nueva aprobación si cambia el contenido del PDF.

## Separación y Git

Trabajar en `video-03/base-aprobacion-actas`. Base inicial: `135cb92`.
Los laboratorios 01 y 02 no se modifican. No se requiere fusionar las ramas
anteriores ni volver a main para ejecutar esta carpeta.

Puerto 8002, proyecto Docker `alameda-aprobaciones`, volumen
`alameda-aprobaciones_approval_data`, base `aprobaciones.sqlite` y cookie
`alameda_aprobaciones_session`. Las claves y documentos de trabajo locales
están en `keys/`, excluida de Git y de la imagen del portal.

## Preparación automática

Desde la raíz del repositorio:

```bash
cd labs/video-03-aprobacion-actas
bash tools/preparar.sh
```

Este comando construye y arranca únicamente este portal, crea los cuatro
PDF iniciales ausentes, genera una clave local para Elena si no existe y
registra su clave pública. Se puede repetir: no sobrescribe claves ni
restaura documentos modificados. Si la cuenta tiene otra clave, se detiene
sin reemplazarla. No borrar claves para intentar resolver ese caso.

Abrir http://localhost:8002.
Cuentas ficticias: `ana`, `luis`, `elena`, `marco`.
Contraseña: `Alameda2026!`. Elena gestiona Matemáticas; Marco, Ciencias.

Antes de los ensayos, crear un respaldo del acta original:

```bash
docker compose exec web flask --app app backup-document 102
```

Anotar el identificador real. Para recuperarla después:

```bash
docker compose exec web flask --app app restore-document IDENTIFICADOR
```

## Aprobar el acta de Matemáticas

1. Iniciar sesión como Elena.
2. Abrir `http://localhost:8002/documentos/102`, revisar el acta y descargar
   el PDF. Guardarlo como `keys/acta-102.pdf`.
3. Pulsar **Revisar y aprobar**.
4. Pulsar **Descargar solicitud de aprobación**. Guardar el JSON como
   `keys/solicitud-102.json`. La solicitud caduca en 15 minutos.
5. Desde esta carpeta ejecutar:

```bash
bash tools/firma-local.sh firmar \
  solicitud-102.json acta-102.pdf elena-private.pem firmado-102.json
```

La herramienta muestra cuenta, documento y hash; escribir `APROBAR` para
confirmar. Si el PDF no coincide o la clave no corresponde, rechaza la firma.
No sobrescribe un archivo firmado existente: usar otro nombre al repetir.

6. Volver al portal, seleccionar `keys/firmado-102.json` en **Solicitud
   firmada** y pulsar **Registrar aprobación**.
7. Comprobar el estado **Aprobada** y el historial de actividad.
8. Descargar el comprobante y guardarlo como `keys/comprobante-102.json`.

La herramienta de firma ejecuta un contenedor temporal sin red, bajo el
usuario local. Solo monta `keys/`; no monta el volumen del portal. La clave
privada no se sube, no se incorpora a la imagen ni se entrega al servidor.
El contenedor web recibe únicamente la clave pública.

## Verificación independiente

```bash
bash tools/firma-local.sh verificar \
  comprobante-102.json acta-102.pdf elena-public.pem --usuario elena
```

Resultado esperado: firma válida, PDF coincidente y aprobador Elena.
El verificador utiliza la clave pública conservada durante el registro;
no confía en una clave enviada dentro del comprobante.

El comprobante firmado prueba una declaración de aprobación. La aceptación
en el portal se confirma en su historial. Una solicitud firmada aún no
presentada no demuestra que el servidor haya registrado la operación.

## Demostrar las alteraciones

Crear dos copias de trabajo sin modificar los originales:

```bash
cp keys/acta-102.pdf keys/acta-alterada.pdf
printf '\ncontenido modificado\n' >> keys/acta-alterada.pdf
bash tools/firma-local.sh verificar \
  comprobante-102.json acta-alterada.pdf elena-public.pem --usuario elena
```

Resultado esperado: la firma del comprobante es válida pero el PDF no
coincide. La herramienta termina con código 1: es el rechazo esperado.

Para modificar el comprobante sin editar manualmente el original:

```bash
docker run --rm --network none \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/keys:/signing" -w /signing \
  alameda-aprobaciones-web python -c 'import json; from pathlib import Path; p=json.loads(Path("comprobante-102.json").read_text()); p["payload"]["username"]="marco"; Path("comprobante-alterado.json").write_text(json.dumps(p))'

bash tools/firma-local.sh verificar \
  comprobante-alterado.json acta-102.pdf elena-public.pem --usuario elena
```

Resultado esperado: rechazo de la firma. No afirmar que cambió la firma
original: se cambió el contenido cubierto por ella.

También se puede sustituir el PDF desde la cuenta de Elena y volver a
**Revisar y aprobar**. El estado indica que requiere nueva aprobación.
La aprobación anterior sigue probando únicamente los bytes anteriores.

## Permisos y controles

Ana no ve la acción de aprobación. Al solicitar directamente
`/documentos/102/aprobacion`, Ana y Marco reciben HTTP 403.
Ocultar el botón no es el control: el servidor comprueba los permisos.
Todos los formularios POST conservan CSRF.

Las solicitudes guardan el hash, cuenta, clave, acción, nonce aleatorio y
caducidad. Al recibirlas se valida la firma y la coincidencia exacta con
la solicitud emitida. La aceptación consume la solicitud una sola vez.
La aprobación y su evento de auditoría se guardan en una misma transacción.

## Código para explicar

- `app/approvals.py`: emisión de solicitud, validación, transacción,
  auditoría, descarga del comprobante y registro administrativo de claves.
- `app/signatures.py`: serialización estable, huella de clave y verificación.
- `tools/firma.py`: clave privada local, revisión/confirmación y firma.
- `app/permissions.py`: política por asignatura y operación reutilizada.
- `app/schema.sql`: claves públicas, solicitudes, aprobaciones y eventos.

No es necesario explicar todo el portal en el video. Mostrar una operación
completa, un evento, la verificación y dos rechazos.

## Pruebas

```bash
docker compose run --rm --no-deps web python -m pytest -q
```

Se incluyen 52 casos heredados y 17 casos de aprobación/verificación:
69 en total. Prueban éxito, permisos, clave incorrecta, alteración,
caducidad, reutilización, cambio del documento, CSRF y registro de claves.
Los datos de prueba son temporales, independientes del volumen activo.

## Límites que deben explicarse

- Una firma demuestra el uso de una clave; atribuirla a una persona depende
  de comprobar su identidad y de custodiar esa clave. Las claves de esta
  práctica son locales, sin autoridad certificadora ni segundo factor.
- La clave privada se guarda sin contraseña, con permisos 0600, para la
  práctica local. No representa un dispositivo criptográfico de producción.
- No hay sello de tiempo de confianza: se utiliza el reloj del servidor.
- El historial SQLite ayuda a reconstruir acciones, pero un administrador
  del almacenamiento puede alterarlo. No es un registro inmutable.
- El origen corresponde al cliente observado por el servidor. Con Docker
  o proxy puede ser una dirección de intermediario, no una persona.
- No existe evidencia legal absoluta ni certificación de no repudio.
- El comprobante no incluye una contrafirma del servidor: verificarlo
  externamente no prueba por sí solo la aceptación en el portal.
- La condición actual se compara por contenido; restaurar exactamente los
  mismos bytes vuelve a coincidir con una aprobación de ese contenido.
- Los respaldos comparten el volumen. No protegen contra perderlo entero.

## Detener y reconstruir

```bash
docker compose down
docker compose up --build -d
```

No ejecutar `down -v`: eliminaría documentos, aprobaciones y claves públicas
registradas del volumen. Las claves privadas locales no están en ese volumen.

## Fuentes y apoyo

Material docente 1.1.3; documentación de Flask; documentación de Ed25519
de cryptography; OWASP Logging Cheat Sheet y Authorization Cheat Sheet.
Se utilizó ChatGPT/Codex para implementar código, pruebas y documentación.
Los participantes deben ejecutar y comprender lo presentado.
