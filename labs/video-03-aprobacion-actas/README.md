# Laboratorio 03 — Aprobación de actas

Tema 1.1.3: autenticidad, trazabilidad, responsabilidad y no repudio.

## Estado actual

Base independiente copiada del portal corregido del video 02. Incluye
sesiones, permisos por asignatura, documentos PDF, respaldo, recuperación
y las pruebas originales del portal. Todavía no implementa aprobación,
auditoría de aprobaciones ni firmas. No presentar esas funciones como listas.

Origen: `labs/video-02-portal-documental`, versión corregida `f3aa2a1`.
Rama de trabajo inicial: `video-03/base-aprobacion-actas`, creada desde
`origin/main` en `5f9563e`, que integra las dos ramas del video 02.

## Independencia del video 02

- Carpeta: `labs/video-03-aprobacion-actas`.
- Proyecto Compose: `alameda-aprobaciones`.
- Puerto: `127.0.0.1:8002`.
- Volumen: `alameda-aprobaciones_approval_data` con el nombre predeterminado.
- Base de datos: `aprobaciones.sqlite` dentro del volumen propio.
- Cookie: `alameda_aprobaciones_session`.
- Clave de sesión de desarrollo distinta.

No se copiaron bases, sesiones, respaldos, claves privadas ni archivos
persistentes del video 02. Ambos portales pueden ejecutarse a la vez.
Las cookies tienen nombres distintos porque los puertos por sí solos
no aíslan las cookies de un mismo host.

## Arranque de la base

Desde la raíz del repositorio:

```bash
cd labs/video-03-aprobacion-actas
docker compose up --build -d
docker compose exec web flask --app app seed-documents
```

Abrir http://localhost:8002.

Cuentas ficticias: `ana`, `luis`, `elena`, `marco`.
Contraseña local: `Alameda2026!`.
Elena es docente de Matemáticas y Marco de Ciencias Naturales.
El acta de Matemáticas tiene identificador 102.

El arranque no importa datos del laboratorio anterior: crea datos nuevos.
Las credenciales son exclusivas de la práctica educativa local.

## Verificar la base reutilizada

```bash
docker compose build web
docker compose run --rm --no-deps web python -m pytest -v
```

Se conservan los 52 casos del portal corregido como regresión de la base.
No prueban todavía los objetivos nuevos del tema 1.1.3.

## Detener

```bash
docker compose down
```

No usar `down -v` para alternar versiones: elimina los datos del laboratorio.

## Siguiente implementación

1. Una operación de aprobación del acta 102, reservada a su docente.
2. Evento con hora UTC, identidad, origen, operación, recurso, resultado
   e identificador de correlación, sin contraseñas ni tokens.
3. Claves de demostración individuales: la privada fuera del servidor;
   la pública asociada previamente al aprobador.
4. Comprobante firmado de acción, identidad y versión/hash del documento.
5. Verificación externa del comprobante y detección de cambios en PDF
   y comprobante. Documentar los límites de identidad, custodia y tiempo.
6. Pruebas de aprobación legítima, rechazo y alteración de evidencias.

El video tendrá 5:30, repartidos en 2:45 para Jeancarlo y 2:45 para Danny.

## Fuentes y apoyo

Base: código y documentación del laboratorio 02; material docente 1.1.3.
Se utilizó ChatGPT/Codex para preparar esta base independiente.
