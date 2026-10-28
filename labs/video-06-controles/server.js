// Laboratorio 1.3.1 — Tipos de controles
// Portal de notas con controles preventivo, detectivo y correctivo.
// Sin dependencias: ejecutar con `node server.js` y abrir http://localhost:8006

const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const PORT = Number(process.env.PORT) || 8006;
const LIMITE_INTENTOS = 5; // control preventivo
const UMBRAL_ALERTA = 5; // control detectivo (en la teoría se usa 50; aquí 5 para la demostración)
const BLOQUEO_MS = 5 * 60 * 1000;

const NOTAS_ANA = [
  { materia: 'Ingeniería de Seguridad de Software', nota: 8.5 },
  { materia: 'Bases de Datos', nota: 9.0 },
  { materia: 'Redes de Computadoras', nota: 7.8 },
];

const ARCHIVOS = {
  '/': ['index.html', 'text/html; charset=utf-8'],
  '/app.js': ['app.js', 'text/javascript; charset=utf-8'],
  '/styles.css': ['styles.css', 'text/css; charset=utf-8'],
};

let estado = estadoInicial();

function estadoInicial() {
  return {
    controles: { preventivo: false, detectivo: false },
    usuarios: {
      ana: { nombre: 'Ana Torres', contrasena: 'ana2024', fallos: 0, bloqueadoHasta: 0 },
    },
    sesiones: new Map(),
    fallosPorOrigen: {},
    logs: [],
    alertas: [],
  };
}

function hora() {
  return new Date().toLocaleTimeString('es-EC', { hour12: false });
}

function registrar(nivel, mensaje, origen) {
  // Sin control detectivo no queda ningún registro del evento.
  if (!estado.controles.detectivo) return;
  const entrada = { hora: hora(), nivel, mensaje, origen };
  estado.logs.unshift(entrada);
  console.log(`[${entrada.hora}] ${nivel.padEnd(11)} ${mensaje} — origen: ${origen}`);
}

function alertar(mensaje, origen) {
  if (!estado.controles.detectivo) return;
  estado.alertas.unshift({ hora: hora(), mensaje, origen });
  registrar('ALERTA', mensaje, origen);
}

function iniciarSesion(datos) {
  const nombreUsuario = String(datos.usuario || '');
  const origen = String(datos.origen || 'desconocido').slice(0, 60);
  const usuario = estado.usuarios[nombreUsuario];

  if (!usuario) {
    registrar('ADVERTENCIA', `Intento con usuario inexistente "${nombreUsuario.slice(0, 30)}"`, origen);
    return [401, { error: 'Credenciales incorrectas' }];
  }

  // Control preventivo: con la cuenta bloqueada ni siquiera se compara la contraseña.
  if (estado.controles.preventivo && usuario.bloqueadoHasta > Date.now()) {
    registrar('ADVERTENCIA', `Intento sobre la cuenta bloqueada "${nombreUsuario}"`, origen);
    return [423, { error: 'Cuenta bloqueada temporalmente por demasiados intentos fallidos' }];
  }

  if (datos.contrasena !== usuario.contrasena) {
    usuario.fallos += 1;
    estado.fallosPorOrigen[origen] = (estado.fallosPorOrigen[origen] || 0) + 1;
    registrar('ADVERTENCIA', `Contraseña incorrecta para "${nombreUsuario}" (fallo ${usuario.fallos})`, origen);

    if (estado.fallosPorOrigen[origen] === UMBRAL_ALERTA) {
      alertar(`${UMBRAL_ALERTA} intentos fallidos seguidos desde el mismo origen contra "${nombreUsuario}"`, origen);
    }
    if (estado.controles.preventivo && usuario.fallos >= LIMITE_INTENTOS) {
      usuario.bloqueadoHasta = Date.now() + BLOQUEO_MS;
      registrar('ADVERTENCIA', `Cuenta "${nombreUsuario}" bloqueada durante 5 minutos`, origen);
    }
    return [401, { error: 'Credenciales incorrectas' }];
  }

  const fallosPrevios = estado.fallosPorOrigen[origen] || 0;
  usuario.fallos = 0;
  estado.fallosPorOrigen[origen] = 0;

  const token = crypto.randomBytes(16).toString('hex');
  estado.sesiones.set(token, { usuario: nombreUsuario, origen, creada: hora() });
  registrar('INFO', `Inicio de sesión exitoso de "${nombreUsuario}"`, origen);
  if (fallosPrevios >= UMBRAL_ALERTA) {
    alertar(`Acceso exitoso después de ${fallosPrevios} fallos: posible toma de cuenta`, origen);
  }
  return [200, { token, nombre: usuario.nombre }];
}

function consultarNotas(req) {
  const token = String(req.headers.authorization || '').replace(/^Bearer /, '');
  const sesion = estado.sesiones.get(token);
  if (!sesion) return [401, { error: 'Sesión inválida o revocada' }];
  registrar('INFO', `Consulta de notas de "${sesion.usuario}"`, sesion.origen);
  return [200, { usuario: sesion.usuario, notas: NOTAS_ANA }];
}

function cambiarControles(datos) {
  for (const control of ['preventivo', 'detectivo']) {
    if (typeof datos[control] !== 'boolean' || datos[control] === estado.controles[control]) continue;
    estado.controles[control] = datos[control];
    // Al cambiar la configuración se empieza a contar desde cero.
    for (const usuario of Object.values(estado.usuarios)) {
      usuario.fallos = 0;
      usuario.bloqueadoHasta = 0;
    }
    estado.fallosPorOrigen = {};
    console.log(`[${hora()}] Control ${control} ${datos[control] ? 'ACTIVADO' : 'desactivado'}`);
    registrar('INFO', `Control ${control} activado`, 'Administrador');
  }
  return [200, estado.controles];
}

function aplicarCorrectivo(datos) {
  const usuario = estado.usuarios.ana;
  const nueva = String(datos.nuevaContrasena || '');
  if (nueva.length < 8 || nueva === usuario.contrasena) {
    return [400, { error: 'La nueva contraseña debe tener al menos 8 caracteres y ser distinta de la anterior' }];
  }

  let revocadas = 0;
  for (const [token, sesion] of estado.sesiones) {
    if (sesion.usuario === 'ana') {
      estado.sesiones.delete(token);
      revocadas += 1;
    }
  }
  usuario.contrasena = nueva;
  usuario.fallos = 0;
  usuario.bloqueadoHasta = 0;
  console.log(`[${hora()}] Correctivo: ${revocadas} sesiones revocadas y contraseña cambiada`);
  registrar('INFO', `Correctivo: ${revocadas} sesiones revocadas y contraseña de "ana" cambiada`, 'Administrador');
  return [200, { revocadas }];
}

function obtenerEstado() {
  const ana = estado.usuarios.ana;
  return [200, {
    controles: estado.controles,
    cuenta: {
      fallos: ana.fallos,
      bloqueada: estado.controles.preventivo && ana.bloqueadoHasta > Date.now(),
    },
    sesiones: [...estado.sesiones].map(([token, s]) => ({ id: token.slice(0, 6), ...s })),
    logs: estado.logs.slice(0, 60),
    alertas: estado.alertas.slice(0, 5),
  }];
}

function enviarJson(res, codigo, datos) {
  res.writeHead(codigo, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(JSON.stringify(datos));
}

function leerJson(req) {
  return new Promise((resolve, reject) => {
    let cuerpo = '';
    req.on('data', (trozo) => {
      cuerpo += trozo;
      if (cuerpo.length > 10000) {
        reject(new Error('Cuerpo demasiado grande'));
        req.destroy();
      }
    });
    req.on('end', () => {
      try {
        resolve(cuerpo ? JSON.parse(cuerpo) : {});
      } catch {
        reject(new Error('JSON inválido'));
      }
    });
  });
}

const RUTAS_POST = {
  '/api/login': iniciarSesion,
  '/api/controles': cambiarControles,
  '/api/correctivo': aplicarCorrectivo,
  '/api/reiniciar': () => {
    estado = estadoInicial();
    console.log(`[${hora()}] Laboratorio reiniciado`);
    return [200, { ok: true }];
  },
};

const servidor = http.createServer(async (req, res) => {
  const ruta = new URL(req.url, 'http://localhost').pathname;

  try {
    if (req.method === 'GET' && ARCHIVOS[ruta]) {
      const [archivo, tipo] = ARCHIVOS[ruta];
      res.writeHead(200, { 'Content-Type': tipo, 'Cache-Control': 'no-store' });
      return fs.createReadStream(path.join(__dirname, 'public', archivo)).pipe(res);
    }
    if (req.method === 'GET' && ruta === '/api/estado') return enviarJson(res, ...obtenerEstado());
    if (req.method === 'GET' && ruta === '/api/notas') return enviarJson(res, ...consultarNotas(req));
    if (req.method === 'POST' && RUTAS_POST[ruta]) {
      const datos = await leerJson(req);
      return enviarJson(res, ...RUTAS_POST[ruta](datos));
    }
    enviarJson(res, 404, { error: 'No encontrado' });
  } catch (error) {
    enviarJson(res, 400, { error: error.message });
  }
});

servidor.listen(PORT, () => {
  console.log(`Portal de notas en http://localhost:${PORT}`);
  console.log('Los eventos del control detectivo aparecerán aquí.\n');
});
