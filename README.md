# Folio · Finanzas con agentes de IA

Base del hackathon: React + TypeScript + Vite en frontend; FastAPI + SQLite en backend. Dos agentes: consulta financiera y preparación de movimientos. Toda incorporación al libro requiere confirmación explícita.

## Para quien hará UI/UX: empezar aquí

Solo necesitas Node 20+; no necesitas Python, una API key ni datos financieros reales.

```sh
cd frontend
npm ci
npm run dev:demo
```

Abre la URL que imprime Vite. Este modo usa **datos ficticios** y respuestas de chat simuladas en memoria. Recargar reinicia el ejemplo. No conecta con OpenAI ni importa el archivo que selecciones: muestra una vista previa ficticia para diseñar el flujo.

Lee [UI_UX_BRIEF.md](UI_UX_BRIEF.md) para las pantallas, estados y límites del diseño; [API_CONTRACT.md](API_CONTRACT.md) para conectar el frontend al backend.

### Archivos a trabajar

- `frontend/src/App.tsx`: pantallas y componentes iniciales.
- `frontend/src/style.css`: diseño adaptable a escritorio y móvil.
- `frontend/src/types.ts`: tipos compartidos con la API.
- `frontend/src/demo.ts`: datos exclusivamente ficticios para UI/UX.
- `frontend/src/api.ts`: cliente HTTP; conecta demo cuando `VITE_DEMO=true`.

Validación: `npm run build` (real) o `npm run build:demo` (diseño).

## App completa en local

Requiere Python 3.10+ y Node 20+.

```sh
# Si python3 es antiguo: PYTHON_BIN=python3.12 ./scripts/setup.sh
./scripts/setup.sh
./start.sh
```

Abre `http://127.0.0.1:8000`. **Por defecto la app completa utiliza exclusivamente datos ficticios**, guardados en `data/demo.sqlite`. La empresa se llama Empresa Demo. Se precargan 18 registros de ejemplo; “Cargar movimientos ficticios” prepara otros 6 y detecta los 18 ya presentes. No hay acceso automático a archivos personales: este modo rechaza cargas reales de Excel, PDF, imágenes y audio. Los ejemplos de documento y dictado se identifican como simulados.

El script hereda `OPENAI_API_KEY` de la terminal; opcionalmente el backend puede leer `.env.local` en la raíz, excluido de Git. La clave nunca debe colocarse en variables `VITE_*` ni en código del navegador. `OPENAI_MODEL` permite cambiar el modelo (default: `gpt-5.4-mini`). En la app completa los agentes, cuando están conectados, consultan el dataset ficticio mediante el backend; el modo de diseño del frontend mantiene respuestas simuladas.

Para desarrollo simultáneo:

```sh
# Terminal 1
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
# Terminal 2
cd frontend && npm run dev
```

El backend guarda la demostración en `data/demo.sqlite`, excluido de Git. `FINANZAS_DB` permite indicar una base separada para pruebas. `/health` informa el modo de datos y si ese proceso tiene clave, sin revelar su valor. El uso posterior de archivos propios requiere activar explícitamente `FOLIO_DEMO=0`; utiliza `data/finanzas.sqlite`, separada de la demostración, y exige seleccionar el archivo manualmente.

Desde la misma terminal donde configuraste la clave, puedes abrir el modo real en otro puerto conservando la demo:

```sh
FOLIO_DEMO=0 PORT=8001 ./start.sh
```

Abre `http://127.0.0.1:8001`. Los datos que incorpores a esta base serán los de tus archivos; la app no los anonimiza automáticamente.

## Captura de documentos y voz

La app permite preparar movimientos desde PDF, capturas de pantalla y dictado. Todos pasan por revisión: subir un documento o transcribir un audio **no cambia los saldos**.

- **PDF o imagen:** selecciona la cuenta y carga el documento. El backend solicita una extracción estructurada a OpenAI, valida sus campos y muestra una propuesta con la procedencia. Las filas incompletas o ambiguas bloquean la confirmación hasta corregirse con un motivo. También puedes editar los registros extraídos sin error antes de confirmar. Revisa fechas, importes, moneda y tipo de movimiento; la extracción puede equivocarse u omitir registros.
- **Dictado:** graba con el micrófono o selecciona un archivo de audio. Revisa y edita la transcripción antes de enviarla al agente de captura. El agente prepara una propuesta o pide datos faltantes. Después confirmas el movimiento en una acción separada.
- **Wispr Flow:** puedes usar su dictado externo dentro del campo de texto, como en cualquier otra aplicación. Folio no incorpora un plugin nativo de Wispr Flow; su botón de micrófono usa la API de transcripción de OpenAI.

Límites: PDF sin contraseña de hasta 10 MB y 10 páginas; imágenes PNG, JPEG o WebP de hasta 10 MB y 20 megapíxeles; audio MP3, MP4, M4A, WAV o WebM de hasta 10 MB. La grabación del navegador se detiene a los 60 segundos. Se requiere permiso del micrófono y un contexto seguro (`localhost` o HTTPS). La carga de audio se limita por tamaño, no por duración.

En modo real, PDF, imágenes y audio se envían a OpenAI desde el backend. La app no conserva los archivos originales tras la petición; el framework puede usar archivos temporales durante la recepción. Los campos extraídos y su procedencia sí permanecen en SQLite como propuesta. Las peticiones de extracción usan `store=False`; esto no equivale a prometer retención cero por parte del proveedor. La transcripción no utiliza ese parámetro.

La extracción utiliza `OPENAI_DOCUMENT_MODEL`, o `OPENAI_MODEL` si no se define el primero. `OPENAI_TRANSCRIBE_MODEL` permite elegir el modelo de transcripción; por defecto es `gpt-transcribe`. El flujo sigue la [guía oficial de transcripción de OpenAI](https://developers.openai.com/api/docs/guides/speech-to-text). La clave se mantiene exclusivamente en el backend.

La detección de duplicados compara fecha, cuenta, tipo, descripción, importe, referencia y folio, conservando la multiplicidad de registros iguales dentro de una importación. Diferencias de lectura o de descripción entre un PDF y un Excel pueden impedir la coincidencia. No detecta automáticamente equivalencias con registros manuales o capturados por chat; revisa posibles duplicados antes de confirmar.

## Estado y alcance

Implementados: dashboard, movimientos y filtros, importación específica de Balance XLSX, extracción de PDF e imágenes, transcripción y dictado editable, vista previa, confirmación, duplicados, registro manual, procedencia, exportación CSV, agentes acotados e interfaz de consulta con respaldo.

La demostración usa `fixtures/movimientos-demo.json` y ejemplos creados de cero con importes, clientes, proveedores y folios inventados. El modo real optativo empieza vacío: cada incorporación requiere preparar una propuesta y confirmar. El importador Excel admite las hojas `Movimientos Efectivo`, `Movimientos Banco` y `Movimientos Tarjeta BBVA`, con encabezados en la fila 3. Usa el catálogo del libro y los saldos iniciales de sus hojas de balance. Otros formatos de Excel requieren su adaptador. Las filas con error bloquean la confirmación; pueden corregirse en la propuesta con un motivo registrado, sin alterar el original.

Importado/confirmado **no** significa conciliado con el banco. No es un sistema fiscal ni una contabilidad completa de doble partida. Telegram, facturación y cálculo de nómina quedan fuera del MVP. Una sola empresa, un usuario y MXN; servidor limitado a loopback para la demo local. Los documentos no establecen automáticamente saldos iniciales ni acreditan que se hayan extraído todos los movimientos.

Los agentes no tienen herramientas para confirmar ni para ejecutar SQL arbitrario. El analista consulta funciones permitidas y las cifras de la respuesta se construyen desde los totales calculados en el backend. Captura produce una propuesta revisable. Sin clave el registro manual, la importación Excel y los ejemplos ficticios siguen disponibles; el chat, la extracción de documentos y la transcripción reales requieren una conexión configurada.

Las pruebas usan archivos sintéticos y respuestas controladas de OpenAI. No sustituyen una comprobación con una clave activa: la conexión real de extracción, transcripción y agentes todavía debe verificarse en el entorno donde se configure la clave.

## Equipo

1. UI/UX: frontend y accesibilidad.
2. Backend: libro, API y cálculos.
3. Agentes: interpretación y consulta con respaldo.
4. Importación: adaptador Excel, pruebas e integración.

Desarrollo desde cero; no contiene código de Cuadra. No subir estados de cuenta, libros reales, bases locales ni secretos a este repositorio.
