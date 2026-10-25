# Alameda · Portal documental

## Propósito del producto

Permitir que estudiantes y docentes de Instituto Alameda consulten
y gestionen documentos de sus asignaturas según sus permisos.

La aplicación representa un servicio institucional de gestión documental.
El contenido educativo sobre seguridad estará en el video y en la
documentación, fuera de las pantallas habituales del producto.

## Alcance

La aplicación incluirá:

- Inicio y cierre de sesión.
- Listado de documentos autorizados.
- Búsqueda por título.
- Filtro por asignatura.
- Detalle y descarga de documentos.
- Carga, sustitución y eliminación de documentos por docentes autorizados.
- Confirmación antes de eliminar.
- Mensajes de éxito, acceso denegado y recurso no encontrado.

No incluirá matrículas, pagos, mensajería, edición de calificaciones
ni un sistema completo de administración escolar.

## Identidad visual

Institución: Instituto Alameda.
Nombre del servicio: Portal documental.
Idioma de la interfaz: español.

Dirección visual:

- Navegación e identidad: azul marino #17324D.
- Acciones principales: azul #2457A7.
- Fondo: gris claro #F4F6F9.
- Superficies: blanco.
- Texto: gris oscuro #243247.
- Estados: texto e iconos acompañados de color.

El contraste se verificará durante el diseño.

Las pantallas no mostrarán conceptos como CIA, Parker, integridad
o confidencialidad, ni indicadores de modo vulnerable/protegido.
Las credenciales de práctica estarán en la documentación.

## Usuarios y asignaturas

| Usuario | Nombre | Rol | Asignatura |
|---|---|---|---|
| ana | Ana Torres | Estudiante | Matemáticas |
| luis | Luis Mendoza | Estudiante | Ciencias Naturales |
| elena | Elena Vargas | Docente | Matemáticas |
| marco | Marco Salazar | Docente | Ciencias Naturales |

Cada docente administra únicamente su asignatura.
Cada estudiante está matriculado únicamente en la asignatura indicada.

Estas asignaciones simplifican el escenario y permiten comprobar
que los permisos no se conceden solo por tener el rol docente.

## Documentos iniciales

| ID | Documento | Asignatura | Audiencia |
|---|---|---|---|
| 101 | Guía de ejercicios — Unidad 1 | Matemáticas | Estudiantes y docente de Matemáticas |
| 102 | Acta de evaluación — Matemáticas | Matemáticas | Solo docente de Matemáticas |
| 201 | Guía de observación — Unidad 1 | Ciencias Naturales | Estudiantes y docente de Ciencias Naturales |
| 202 | Acta de evaluación — Ciencias Naturales | Ciencias Naturales | Solo docente de Ciencias Naturales |

Los archivos serán PDF con contenido académico ficticio.

Las actas son documentos internos de trabajo del docente.
No se publican como documentos de consulta estudiantil.

## Política de permisos

Una persona sin sesión no puede consultar ni descargar documentos.

Un estudiante:

- Puede listar, consultar y descargar documentos dirigidos a estudiantes
  de sus asignaturas.
- No puede acceder a actas internas del docente.
- No puede cargar, sustituir ni eliminar documentos.

Un docente:

- Puede listar, consultar y descargar todos los documentos de sus asignaturas.
- Puede cargar, sustituir y eliminar documentos de sus asignaturas.
- No puede acceder ni gestionar documentos de otras asignaturas.

El propietario individual se registra como metadato.
La autorización se determina por asignatura, audiencia y operación.

## Matriz de ejemplos

| Acción | Ana | Luis | Elena | Marco |
|---|---|---|---|---|
| Descargar guía de Matemáticas 101 | Permitido | Denegado | Permitido | Denegado |
| Descargar acta de Matemáticas 102 | Denegado | Denegado | Permitido | Denegado |
| Sustituir o eliminar acta 102 | Denegado | Denegado | Permitido | Denegado |
| Descargar guía de Ciencias 201 | Denegado | Permitido | Denegado | Permitido |
| Descargar acta de Ciencias 202 | Denegado | Denegado | Denegado | Permitido |
| Sustituir o eliminar acta 202 | Denegado | Denegado | Denegado | Permitido |

Ocultar una acción en la interfaz no sustituye la autorización
de la solicitud en el servidor.

## Pantallas

### Inicio de sesión

Identidad institucional, usuario, contraseña y acceso al portal.
Sin cuentas de demostración publicadas en la pantalla.

### Mis documentos

Navegación, identidad de la sesión, búsqueda y filtro por asignatura.
Listado con título, asignatura, tipo de documento y fecha de actualización.

Solo se muestran los documentos permitidos para la persona autenticada.

### Detalle del documento

Título, asignatura, propietario, audiencia, fecha y descarga.

El docente autorizado dispone además de sustituir y eliminar.
El estudiante no ve esas acciones.

### Carga y sustitución

Formulario para docentes autorizados.
Permite indicar título y audiencia y seleccionar un PDF.
La asignatura debe pertenecer al docente.

La sustitución conserva el identificador del documento y actualiza
su archivo y fecha.

### Confirmación de eliminación

Identifica el documento y permite confirmar o cancelar.
La eliminación retira el documento del servicio activo.
La recuperación se realiza desde un respaldo independiente.

## Caso del video

Situación inicial:

Elena utiliza el portal para gestionar documentos de Matemáticas.
Ana puede descargar la guía 101, pero no debe acceder al acta 102.

Investigación:

1. Observar una descarga legítima y su solicitud.
2. Intentar descargar el documento 102 con la sesión de Ana.
3. Reproducir una solicitud de sustitución usando la sesión de Ana.
4. Reproducir una solicitud de eliminación usando la sesión de Ana.

Las solicitudes se analizarán desde herramientas externas a la interfaz.
La obtención de las solicitudes docentes se mostrará como inspección
del entorno autorizado, sin afirmar que Ana robó una sesión docente.

Nunca se reutilizará la cookie de Elena para atribuir una acción a Ana.

Problema deliberado de la versión vulnerable:

Las operaciones sobre un documento exigen iniciar sesión, pero omiten
la comprobación de permisos sobre ese documento y esa operación.

El listado de documentos continúa filtrado.
El fallo se encuentra en el servidor que atiende las solicitudes directas.

Consecuencias:

- Descargar el acta: pérdida de confidencialidad.
- Sustituirla por una versión alterada: pérdida de integridad.
- Eliminarla: pérdida de disponibilidad de ese documento.

La eliminación no representa una caída completa del portal.

## Corrección

Centralizar la comprobación de permisos y aplicarla antes de leer,
sustituir o eliminar un documento.

La decisión debe considerar:

- Usuario autenticado.
- Asignatura asignada.
- Audiencia del documento.
- Operación solicitada.

Repetir los intentos con la sesión de Ana y comprobar que se bloquean.
Verificar además que Elena conserva sus operaciones legítimas
y que Marco no obtiene permisos sobre Matemáticas.

Conservar versiones de Git identificadas para el antes y el después.
No añadir un selector de vulnerabilidad en la interfaz.

## Recuperación y Hexad de Parker

Preparar un respaldo del acta original antes del incidente.

Después de demostrar el daño y corregir el acceso:

- Restaurar el documento y sus metadatos.
- Verificar que Elena puede descargarlo.
- Comparar su contenido con la copia original conocida.

Relación con las propiedades adicionales:

Posesión/control:
Bloquear descargas futuras no recupera el control de una copia
que otra persona ya obtuvo.

Autenticidad:
El nombre y la apariencia de un acta no prueban quién la emitió.
La comparación con un respaldo ayuda a comprobar contenido,
pero no sustituye una firma vinculada a un emisor de confianza.
Este video no implementará una demostración separada de firmas.

Utilidad:
Un respaldo debe poder restaurarse y producir un documento legible
y apto para su propósito. Se comprobará la descarga y apertura del PDF.

## Criterios para considerar lista la práctica

- Funciones normales y coherentes para cada usuario.
- Pantallas sin botones educativos ni explicaciones de seguridad.
- Documentos privados fuera de la carpeta pública.
- Fallo reproducible usando realmente la sesión del estudiante.
- Corrección aplicada en todas las operaciones afectadas.
- Pruebas de accesos bloqueados y funciones legítimas.
- Recuperación comprobada.
- Instrucciones para reconstruir el escenario.
- Código y resultados legibles para grabación.
- Documentación con fuentes y declaración del apoyo de IA.

## Alcance del video

Duración prevista: entre 5 minutos y 30 segundos y 6 minutos.

Primera parte: Jeancarlo.
Funcionamiento normal, investigación y consecuencias sobre CIA.

Segunda parte: Danny.
Código relevante, corrección, pruebas y recuperación.
Relación del mismo incidente con el Hexad de Parker.

El guion definitivo se redactará después de verificar la práctica.