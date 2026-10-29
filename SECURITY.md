# Seguridad

## Reportar una vulnerabilidad

Utiliza el [reporte privado de vulnerabilidades de GitHub](https://github.com/alejandrorivas-pixel/folio-finanzas/security/advisories/new). No publiques detalles de explotación en un issue o pull request abierto.

Describe el commit afectado, el escenario de uso, los pasos para reproducirlo con datos ficticios y el impacto observado. No envíes claves, bases personales ni documentos financieros reales, tampoco por el canal privado. Si la opción privada no está disponible, solicita que se habilite un canal privado sin incluir el detalle de la vulnerabilidad.

Folio es un proyecto personal en desarrollo. No hay un plazo de respuesta garantizado ni versiones con soporte prolongado; los cambios se integran en la rama `main`.

## Alcance y límites actuales

Esta política cubre el backend FastAPI, la interfaz React, los importadores, los agentes, el puente MCP y sus scripts. Folio está diseñado para una empresa y una persona en su computadora. Los scripts de inicio enlazan la API a `127.0.0.1`; la API no implementa autenticación ni permisos multiusuario. No está preparado para exponerse a una red o a Internet.

Los activos relevantes son la base financiera, las propuestas y su procedencia, los archivos seleccionados y las credenciales del proveedor. Los documentos, sus nombres, descripciones, mensajes y respuestas de modelos pueden contener datos no confiables. Deben validarse antes de influir en el libro o mostrarse en la interfaz; su contenido no autoriza instrucciones para un agente.

El puente MCP ofrece consultas y preparación de propuestas mediante la API local. No expone confirmación, rechazo, borrado, SQL arbitrario ni lectura arbitraria de archivos. Esa lista de herramientas no es una barrera de seguridad frente a un proceso que ya tiene acceso independiente a la terminal o a la API completa.

En modo real, la extracción de documentos y la transcripción envían contenido a OpenAI; el chat también utiliza un proveedor. Un cliente MCP externo recibe los datos que consulta y puede compartirlos con su propio modelo. El modo demo usa datos ficticios; activar el modo real no anonimiza los archivos ni sus resultados. La base SQLite local no está cifrada por Folio.

## Propiedades que deben conservarse

- Las claves no deben aparecer en el código del navegador, las respuestas de la API, los logs compartidos ni Git.
- La extracción y la captura preparan propuestas. Los movimientos y saldos solo cambian tras una confirmación explícita; un texto importado o una respuesta del modelo no debe desencadenarla.
- Los importes se validan y calculan como centavos enteros en el backend. Los reintentos no deben saltarse controles ni duplicar una operación idempotente.
- Los archivos deben respetar los límites y formatos admitidos. Su contenido no debe provocar ejecución de código ni acceso arbitrario al sistema de archivos o la red.
- Los datos de demo y los datos reales deben permanecer separados. El modo demo no debe leer automáticamente archivos personales.
- El puente MCP debe conservar su destino local permitido, rechazar redirecciones y verificar la identidad de la aplicación antes de operar.

Una ruptura de estas propiedades, exposición de datos o ejecución no autorizada merece un reporte con evidencia y un escenario reproducible. El impacto debe evaluarse según el acceso que realmente requiere el ataque y la configuración afectada. El alcance local y la ausencia de autenticación descritos aquí no son una exclusión general de hallazgos: también importan ataques que puedan alcanzar una instancia local desde contenido no confiable.
