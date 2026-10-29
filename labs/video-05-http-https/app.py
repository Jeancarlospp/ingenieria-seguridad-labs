"""Portal local para comparar HTTP y HTTPS. Python estándar, sin dependencias."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs
import html
import secrets
import signal
import ssl
import subprocess
import threading

ROOT = Path(__file__).resolve().parent


def preparar_certificado():
    carpeta = ROOT / '.local'
    carpeta.mkdir(mode=0o700, exist_ok=True)
    certificado, clave = carpeta / 'localhost.crt', carpeta / 'localhost.key'
    if not certificado.exists() or not clave.exists():
        subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-sha256',
            '-nodes', '-days', '30', '-keyout', str(clave), '-out', str(certificado),
            '-subj', '/CN=localhost',
            '-addext', 'subjectAltName=DNS:localhost,IP:127.0.0.1',
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clave.chmod(0o600)
    return certificado, clave


class Portal(BaseHTTPRequestHandler):
    server_version = 'Alameda'

    def responder(self, contenido, estado=200):
        datos = contenido.encode('utf-8')
        self.send_response(estado)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(datos)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        if self.path not in ('/', '/favicon.ico'):
            self.send_error(404)
            return
        if self.path == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        self.responder((ROOT / 'index.html').read_text(encoding='utf-8'))

    def do_POST(self):
        if self.path != '/solicitudes':
            self.send_error(404)
            return
        try:
            largo = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            self.send_error(400)
            return
        if not 0 < largo <= 8192:
            self.send_error(413)
            return
        if self.headers.get_content_type() != 'application/x-www-form-urlencoded':
            self.send_error(415)
            return
        try:
            datos = parse_qs(self.rfile.read(largo).decode('utf-8'), max_num_fields=8)
        except (UnicodeDecodeError, ValueError):
            self.send_error(400)
            return
        if any(not datos.get(campo, [''])[0].strip() for campo in ('nombre', 'correo', 'asunto', 'mensaje')):
            self.send_error(400, 'Completa todos los campos')
            return
        # El contenido llega igual con ambos protocolos. TLS protege el trayecto.
        referencia = secrets.token_hex(3).upper()
        pagina = (ROOT / 'index.html').read_text(encoding='utf-8')
        inicio, fin = pagina.index('<!-- FORMULARIO -->'), pagina.index('<!-- FIN FORMULARIO -->')
        confirmacion = f'''<section class="success"><div class="check">✓</div><p class="eyebrow">SOLICITUD REGISTRADA</p><h2>Nos encargamos<br>del siguiente paso.</h2><p>Tu solicitud ha sido recibida por Secretaría Académica.</p><div class="ticket">Referencia <strong>AL-{html.escape(referencia)}</strong></div><a class="button" href="/">Nueva solicitud <span>→</span></a></section>'''
        self.responder(pagina[:inicio] + confirmacion + pagina[fin:])

    def log_message(self, formato, *args):
        print(f'[{self.server.etiqueta}] {formato % args}', flush=True)


def main():
    certificado, clave = preparar_certificado()
    servidores = []
    try:
        for puerto, etiqueta in ((8080, 'HTTP'), (8443, 'HTTPS')):
            servidor = ThreadingHTTPServer(('127.0.0.1', puerto), Portal)
            servidores.append(servidor)
            servidor.etiqueta = etiqueta
            if etiqueta == 'HTTPS':
                contexto = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                contexto.minimum_version = ssl.TLSVersion.TLSv1_2
                contexto.load_cert_chain(certificado, clave)
                servidor.socket = contexto.wrap_socket(servidor.socket, server_side=True)
        for servidor in servidores:
            threading.Thread(target=servidor.serve_forever, daemon=True).start()
        print('\nPortal disponible:\n  HTTP:  http://localhost:8080\n  HTTPS: https://localhost:8443\n\nDetener: Ctrl+C\n', flush=True)
        signal.pause()
    except KeyboardInterrupt:
        print('\nPortal detenido.', flush=True)
    finally:
        for servidor in servidores:
            servidor.server_close()


if __name__ == '__main__':
    main()
