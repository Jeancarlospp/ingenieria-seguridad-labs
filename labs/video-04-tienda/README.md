# FORMA — Tienda y pedidos

Tema 1.1.4: activo, amenaza, vulnerabilidad, ataque, impacto, riesgo,
control y verificación. La interfaz es una tienda, sin explicaciones
académicas ni selectores de vulnerabilidad.

## Arranque

Requisitos: Docker con Compose, Git y Firefox. No se necesita instalar Python.
Desde la raíz del repositorio, con los cambios guardados:

```bash
git switch video-04/precio-cliente
cd labs/video-04-tienda
docker compose up --build -d --wait
```

Abrir http://localhost:8003 en Firefox. No hay registro ni contraseñas:
los pedidos se asocian a una sesión de comprador en ese navegador.
Usar nombre `Ana Torres` y correo `ana@example.test`.
No se cobra dinero: se registran pedidos pendientes de pago al retirar.

Proyecto `forma-tienda`, puerto local 8003, volumen `forma-tienda_store_data`,
base `forma.sqlite` y cookie `forma_store_session`, independientes de los
videos anteriores. No iniciar, detener ni reconstruir los otros laboratorios.

## Recorrido antes de la corrección

1. Abrir Auriculares A1, precio $50, y añadir al carrito una unidad.
2. Continuar al pedido. Completar nombre y correo.
3. Antes de confirmar, pulsar F12 y abrir **Red / Network**.
4. Activar **Persistir registros / Persist Logs** desde los ajustes de Red
   (para conservar la solicitud cuando el navegador abre la confirmación).
5. Confirmar el pedido. Debe aparecer un pedido por $50.
6. En Red, filtrar por `api/pedidos` y seleccionar el POST de la compra.
7. Clic derecho en esa solicitud: **Editar y reenviar / Edit and Resend**.
8. En el cuerpo de la solicitud cambiar únicamente `"unit_price":50` por
   `"unit_price":1`. Si aparece como `50.0`, también se sustituye por `1`.
   Conservar producto, cantidad, datos y cabecera `X-CSRF-Token`.
9. Pulsar **Enviar / Send**. La respuesta será HTTP 201 y mostrará `total: "1.00"`.
10. Cerrar F12 y pulsar **Mis pedidos** (o recargar `/pedidos`). El nuevo
    pedido debe mostrar $1. No basta con editar el texto de la página:
    ese importe está guardado en SQLite y persiste al recargar.

El reenvío crea OTRO pedido; no modifica el primer pedido de $50.
El navegador no abre automáticamente el pedido reenviado: consultar Mis pedidos.

## Aplicar la corrección

Desde la misma carpeta, sin borrar datos:

```bash
git switch video-04/precio-verificado
docker compose up --build -d --wait
```

En el mismo navegador, volver a hacer una compra y reenviar la solicitud
con `unit_price: 1`. Esta vez el servidor registra **$50**, tomado de su
catálogo. Verificar además la compra normal por $50.

No se necesita una variable LAB_MODE ni selector de modo. Las ramas
cambian únicamente la regla de origen del precio en `app/pricing.py`.
El puerto, la interfaz, los controles CSRF y el volumen se conservan.

## Código de Jeancarlo y Danny

`app/static/store.js`: el navegador envía producto, cantidad y precio mostrado.
Es un mensaje normal de checkout; el cliente puede modificarlo.

`app/pricing.py`, rama `precio-cliente`: convierte a centavos el precio
recibido. Validar que sea numérico y positivo NO demuestra que sea el correcto.

`app/pricing.py`, rama `precio-verificado`: obtiene `product["price_cents"]`
del catálogo del servidor. El comprador elige producto y cantidad; no precio.

`app/__init__.py`, `create_order`: valida cantidad y datos, consulta el
producto y persiste el pedido y su importe calculado.

## Relación con el tema

- Activo: ingresos esperados y exactitud de los pedidos.
- Amenaza: un comprador dispuesto a manipular la compra.
- Vulnerabilidad: confiar en el precio recibido del navegador.
- Ataque: enviar la solicitud con un precio distinto.
- Impacto observado: pedido por $1 en lugar de $50.
- Pérdida potencial: diferencia de $49 por unidad si se despachara y cobrara
  ese pedido; NO afirmar que ya hubo una pérdida monetaria o pago real.
- Riesgo: posibilidad de explotación y consecuencias sobre ventas. Se analiza
  antes del ataque; una prueba no calcula la probabilidad de ocurrencia.
- Control: calcular importes a partir del catálogo del servidor.
- Verificación: repetir la manipulación y conservar compras legítimas.

## Pruebas

En la rama corregida:

```bash
docker compose run --rm --no-deps web python -m pytest -q
```

La suite exige precios del catálogo: en la rama vulnerable fallan
intencionalmente los casos contra manipulación. No alterar las expectativas
para ocultar el fallo. Las pruebas usan bases temporales.

## Límites

Compra directa de una referencia por carrito, entre una y cinco unidades.
Elegir otro producto sustituye la selección del carrito. No hay pagos,
stock, impuestos, cupones, envío ni cuentas de usuario de producción.
El precio es un campo manipulable para reproducir un fallo de confianza
en el cliente; el control se aplica exclusivamente en el servidor.
La versión corregida conserva el campo recibido para repetir exactamente
el intento, pero no lo utiliza como fuente de precio.
Cada reenvío puede generar otro pedido: no hay idempotencia de checkout.
La clave de sesión configurada es pública para desarrollo local.
Datos, marca y productos son ficticios. El servicio se publica solo en localhost.
Las pruebas no certifican preparación para producción.

## Detener y reanudar

```bash
docker compose stop
docker compose start
```

No usar `down -v`: elimina los pedidos y el catálogo del volumen.
Antes de grabar, anotar `git rev-parse HEAD` y comprobar `git status --short`.

## Fuentes y apoyo

Material docente 1.1.4; Flask y SQLite; OWASP Web Security Testing Guide,
Business Logic Testing; Firefox Source Docs, Network request details:
https://firefox-source-docs.mozilla.org/devtools-user/network_monitor/request_details/

ChatGPT/Codex apoyó implementación, documentación y pruebas. Los participantes
deben comprender y verificar el flujo presentado.
