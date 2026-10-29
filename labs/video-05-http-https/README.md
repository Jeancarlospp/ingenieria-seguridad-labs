# Video 5 — HTTP y HTTPS con Wireshark

## Qué vamos a demostrar

La misma solicitud académica viaja desde el navegador al mismo portal. Con HTTP, su contenido puede leerse en una captura de red. Con HTTPS, TLS cifra el contenido durante ese trayecto. La recepción funciona en ambos casos; cambia lo que puede observar alguien que captura la comunicación.

La captura no demuestra un robo de información ni la identidad de un atacante: reproduce la condición de exposición del contenido. No todos los ataques modifican datos. Wireshark también sirve para diagnóstico autorizado.

## Arranque

Requisitos: Python 3.10 o posterior, OpenSSL, navegador y Wireshark. No necesita Docker, pip, cuentas ni variables de terminal. En VS Code abre esta carpeta y ejecuta:

```bash
python3 app.py
```

Mantén abierta esa terminal. Ctrl+C detiene los dos servicios.

- HTTP: http://localhost:8080
- HTTPS: https://localhost:8443

El servidor solo escucha en tu computadora. No envía correos; confirma la recepción local y no guarda las solicitudes en disco. El certificado y su clave se generan automáticamente en `.local/`, excluida de Git. Conserva esa carpeta mientras ensayas para mantener la misma excepción del navegador. El certificado dura 30 días.

## Preparación antes de grabar

1. Abre las dos direcciones en pestañas separadas.
2. En HTTPS aparecerá inicialmente una advertencia: este certificado lo creó la aplicación local y el navegador no tiene una autoridad que lo avale. En Firefox, comprueba que la dirección es exactamente `https://localhost:8443`, abre **Avanzado** y acepta la excepción para este portal local. Hazlo tú, fuera de la grabación. No desactives la validación global del navegador ni instales una autoridad nueva.
3. Deja abiertas ambas pestañas en el formulario. Los campos ya contienen los mismos datos en ambas. El texto `ALAMEDA-2026` facilita encontrar el mensaje.
4. En Wireshark selecciona **Loopback: lo**. En el campo **Enter a capture filter**, junto a **using this filter**, escribe:

```text
tcp port 8080 or tcp port 8443
```

Este campo es el filtro de captura de la pantalla inicial, no la barra superior **Apply a display filter**.

## Primer ensayo

1. Haz doble clic en **Loopback: lo** para iniciar la captura. Si aparece un error de permisos, detente y comparte el error: ver interfaces no confirma por sí solo que puedas capturar.
2. En la pestaña HTTP presiona **Enviar solicitud**. Debe aparecer **Solicitud registrada**.
3. En la pestaña HTTPS presiona **Enviar solicitud**. Debe aparecer la misma confirmación.
4. En Wireshark detén la captura con el cuadrado rojo.
5. En la barra superior **Apply a display filter** escribe y pulsa Enter:

```text
http.request.method == "POST" && tcp.port == 8080
```

6. Selecciona la solicitud que contiene `POST /solicitudes`. Clic derecho → **Follow** → **TCP Stream** (Seguir → Flujo TCP). Allí se ven `nombre`, `correo`, `asunto` y `mensaje`. Busca `ALAMEDA-2026`. Los espacios pueden aparecer como `+` y las tildes como códigos; es codificación del formulario, no cifrado.
7. Cierra la ventana de seguimiento. Sustituye todo el filtro superior por:

```text
tcp.port == 8443
```

8. Selecciona un paquete TLS con **Application Data**. Su contenido de aplicación viaja cifrado. **Follow → TCP Stream** muestra los bytes transportados, no los campos legibles de la solicitud. La versión concreta de TLS dependerá del navegador.
9. Si el protocolo aparece solo como TCP, o no encuentras los paquetes, comparte una captura antes de cambiar ajustes. No uses **Follow TLS Stream** para esta comparación: queremos observar el tráfico transportado, sin claves de descifrado.

## Qué decir sobre el resultado

- HTTP permite leer estos campos en esta captura; el ejemplo representa el riesgo cuando un observador tiene acceso al tráfico.
- HTTPS protege el contenido entre navegador y servidor. El servidor y el navegador siguen pudiendo leerlo: son los extremos de la comunicación.
- HTTPS no vuelve invisible toda la conexión: siguen observándose direcciones, tamaños y tiempos. Tampoco garantiza que una página sea honesta.
- El certificado local permite demostrar cifrado, pero su excepción manual no representa la validación de identidad pública de un sitio comercial.
- La vista de F12 muestra datos en el propio navegador y no demuestra si viajan cifrados; por eso aquí usamos una captura de red.

## Tiempo del video

Las diapositivas ocupan aproximadamente 4:00. Reservamos 2:30 para la práctica y 0:30 de margen. La instalación, el arranque, la excepción del certificado y la preparación de ventanas quedan fuera del video. El tiempo final debe comprobarse con un ensayo.

## Código relevante

En `app.py`, la función `main` crea los servidores HTTP y HTTPS usando el mismo manejador `Portal`. `SSLContext` y `wrap_socket` habilitan TLS para el segundo. `do_POST` recibe los mismos campos en ambos casos. No hace falta editar código durante la demostración.
