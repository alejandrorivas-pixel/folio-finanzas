# Contrato mínimo de integración

Base URL relativa: `/api`. Vite dirige `/api` a `http://127.0.0.1:8000`. JSON salvo las cargas de archivos, que usan `multipart/form-data`. Los tipos de frontend están en `frontend/src/types.ts`.

## Movimiento

`id`, `date` (AAAA-MM-DD), `account` (`efectivo`, `banco`, `tarjeta_bbva`), `kind`, `category`, `description`, `amount_minor` (entero con signo), `currency` (`MXN`), `reference`, `property`, `treatment`, `source_file`, `source_sheet`, `source_row`.

Negativo reduce efectivo/posición neta; positivo lo aumenta. Un cargo de tarjeta es negativo y un pago de tarjeta positivo. En el formulario el usuario da importe positivo y el backend aplica el signo. `treatment` es `operational`, `transfer`, `card_payment`, `custody`, `financing` o `por_revisar`.

## Endpoints

| Método y ruta | Uso |
|---|---|
| `GET /health` | `{application:"folio", status, ai_configured, model, demo_mode}` sin secretos |
| `GET /api/meta` | Cuentas, categorías, meses, conteo confirmado y pendiente |
| `GET /api/summary?month=2026-10&account=banco` | Totales, saldos por cuenta, series diarias, categorías y últimos registros |
| `GET /api/movements` | Filtros opcionales `month`, `account`, `category`, `search`, `ids` (separados por coma), `page`, `size` (máx. 100). Devuelve `{items,total,page,size,totals}` |
| `GET /api/movements/{id}` | Detalle y procedencia |
| `POST /api/imports/preview` | Multipart con campo `file` XLSX. Devuelve propuesta pendiente |
| `POST /api/imports/local-preview` | Vista previa del dataset ficticio; no abre archivos personales y solo está disponible en modo demo |
| `POST /api/imports/document-preview` | Multipart con `file` (PDF, PNG, JPEG o WebP) y `account`. Extrae y valida datos; devuelve propuesta pendiente de tipo `import` |
| `POST /api/imports/document-demo` | `{format: "pdf" \| "image", account}`. Genera una propuesta ficticia; solo en modo demo |
| `POST /api/audio/transcribe` | Multipart con `file` (MP3, MP4, M4A, WAV o WebM). Devuelve `{text,model,language:"es"}`; no crea propuestas ni registra movimientos |
| `GET /api/proposals` | Propuestas pendientes |
| `GET /api/proposals/{id}` | Estado y contenido actualizado de una propuesta |
| `POST /api/proposals/manual` | Prepara un movimiento; nunca lo confirma |
| `POST /api/agent/proposals/manual` | Prepara un movimiento para un cliente agente; requiere `request_id` y devuelve la propuesta completa. Repetir una solicitud idéntica reutiliza la propuesta; reutilizar su identificador con otros datos devuelve 409 |
| `POST /api/proposals/{id}/confirm` | Body `{ "confirm": true }`. Devuelve `{inserted,duplicates,already_confirmed}` |
| `POST /api/proposals/{id}/corrections` | `{sheet,row,movement,reason}`; corrige filas inválidas y permite revisar registros válidos de PDF/imágenes, solo en propuestas pendientes y con trazabilidad |
| `POST /api/proposals/{id}/reject` | Body `{ "confirm": true }` |
| `POST /api/chat` | `{message, mode: "analyst" | "capture", month, account, history}` |
| `GET /api/export?month=2026-10` | CSV de los movimientos confirmados del filtro |

### Propuesta manual

```json
{"date":"2026-10-28","account":"efectivo","kind":"egreso","category":"Nómina y sueldos","description":"Pago de nómina","amount_minor":150000,"reference":null,"property":null}
```

### Propuesta de un agente externo

`POST /api/agent/proposals/manual` recibe los mismos campos que la propuesta manual y añade `request_id` obligatorio: de 8 a 100 caracteres, empezando por una letra o número, y utilizando letras ASCII, números, `_`, `.`, `:`, `-`. `amount_minor` es un entero positivo en centavos de MXN; el backend determina su signo según el tipo. El agente debe obtener primero las cuentas y categorías permitidas de `GET /api/meta`.

```json
{"request_id":"demo-papeleria-20261028-001","date":"2026-10-28","account":"efectivo","kind":"egreso","category":"Por revisar","description":"Compra ficticia de papelería","amount_minor":12550,"reference":null,"property":null}
```

Respuesta: `{id,kind,status,created_at,payload}`. El cliente conserva `request_id` al reintentar la misma operación, incluso si no recibió la primera respuesta. Una solicitud idéntica devuelve el mismo `id` y el estado actual de la propuesta; no genera otro movimiento. Si cambian los datos con el mismo `request_id`, el servidor responde `409`. Una intención nueva necesita otro identificador. Esta garantía cubre los reintentos del cliente; dos identificadores distintos no prueban que sean dos gastos diferentes.

La operación solamente prepara una propuesta. Su confirmación se realiza en la web, en **Por confirmar**. El puente MCP llama a esta ruta para preparar movimientos; sus herramientas no incluyen los endpoints HTTP de confirmación o rechazo.

### Transporte MCP

`start-mcp.sh` inicia `backend.mcp_server` por stdio. `FOLIO_API_URL` selecciona el backend local; por defecto `http://127.0.0.1:8000`. Solo admite `http://127.0.0.1:PUERTO` o `http://localhost:PUERTO`, con puerto explícito entre 1024 y 65535, sin credenciales ni rutas adicionales. El MCP usa este contrato HTTP y no abre SQLite directamente. Herramientas disponibles: `folio_status`, `folio_catalog`, `folio_summary`, `folio_movements`, `folio_movement`, `folio_propose_movement`, `folio_pending_proposals` y `folio_proposal`. El recurso `folio://guide` contiene las reglas de uso.

No hay herramientas para SQL, rutas HTTP arbitrarias, archivos locales o confirmación de movimientos. Los textos financieros devueltos son datos externos, no instrucciones para el agente. La API sigue siendo local y de un solo usuario, sin autenticación: limitar herramientas MCP no restringe a un agente que ya tenga acceso independiente a la terminal o a toda la API. Configuración y recorrido de uso en [MCP_GUIDE.md](MCP_GUIDE.md).

### Propuesta de importación

`{id,kind,status,created_at,payload}`. `payload` incluye `movements`, `stats` (`total,new,duplicates,errors,review,accounts`), `errors`, `notes`, `openings`, `filename`. Hay que impedir confirmar si hay errores. Si el usuario cierra el modal, la propuesta sigue pendiente.

### PDF e imágenes

`POST /api/imports/document-preview` requiere una cuenta explícita: `efectivo`, `banco` o `tarjeta_bbva`. Acepta un PDF sin cifrar de 1 a 10 páginas, o una imagen estática PNG/JPEG/WebP de hasta 20 megapíxeles. El tamaño máximo es 10 MB y la extracción admite hasta 200 movimientos. Se valida el contenido además de la extensión antes de enviarlo al proveedor. No establece saldos iniciales.

La respuesta usa el mismo contrato de propuesta de importación que Excel. Añade `payload.document` con tipo MIME, número de páginas, cuenta, modelo, advertencias y campos extraídos para revisión. En PDF e imágenes, `source_sheet` identifica la página y `source_row` es un identificador del registro extraído, no el número de línea impreso en el documento. Conserva `source_file` y el hash del archivo como procedencia; el original no se conserva para abrirlo después.

Una fecha, importe, moneda o estado de pago sin evidencia suficiente genera un error de fila con `draft`; no se completa con el día actual, cero o una cifra inferida. Las advertencias también bloquean la confirmación. El flujo de corrección existente recibe `{sheet,row,movement,reason}` y registra la intervención humana. También admite corregir registros válidos de documentos para revisar errores de lectura que el modelo no detectó. Esta versión admite exclusivamente MXN; un documento con moneda extranjera explícita se rechaza y no se convierte.

Al cargar de nuevo los mismos bytes y cuenta, se reutiliza la propuesta pendiente o la extracción previamente confirmada; no se solicita otra interpretación al modelo. Los duplicados se comparan contra registros importados confirmados mediante coincidencia exacta de campos y ocurrencia. Una versión diferente del mismo documento o un movimiento registrado manualmente puede no identificarse como duplicado. La vista previa no prueba conciliación ni cobertura completa del documento.

En modo demo, `document-preview` rechaza archivos reales. `document-demo` devuelve datos inventados y no llama a OpenAI. En modo real requiere `OPENAI_API_KEY` en el backend; el modelo es `OPENAI_DOCUMENT_MODEL`, o `OPENAI_MODEL` si no se define el primero.

### Audio y dictado

`POST /api/audio/transcribe` recibe un único archivo de hasta 10 MB: MP3, MP4, M4A, WAV o WebM. La respuesta es texto editable de hasta 3,000 caracteres, no una propuesta financiera. El frontend coloca `text` en el campo de captura; el usuario lo revisa y envía mediante `POST /api/chat` con `mode:"capture"`. La confirmación del movimiento sigue siendo una llamada posterior e independiente.

El endpoint rechaza audio real en modo demo; el botón de ejemplo del frontend inserta texto ficticio, sin grabar ni llamar al proveedor. En modo real utiliza `OPENAI_TRANSCRIBE_MODEL` (por defecto `gpt-transcribe`). `language:"es"` indica el idioma solicitado, no una verificación lingüística del contenido.

La UI limita su grabación a 60 segundos y permite cancelar. El backend limita bytes; no promete comprobar la duración de todos los formatos. El permiso de micrófono corresponde al navegador. La transcripción no guarda el audio ni altera los saldos.

Las cargas reales se envían a OpenAI desde el backend. El framework puede crear archivos temporales al recibirlas; la app no conserva los originales tras la petición. Los datos estructurados de documentos sí quedan guardados como propuestas. `store=False` en extracción no es una promesa de retención cero del proveedor; las transcripciones no usan ese parámetro.

### Respuesta del agente

`{agent,message,evidence?,proposal?,draft?}`. Una evidencia contiene `filters`, `totals` y `movement_ids`. El analista no modifica datos. Captura puede pedir datos faltantes o devolver propuesta pendiente. Confirmar sigue siendo una acción HTTP independiente iniciada por el usuario.

### Errores

`{detail: "mensaje"}` con estado no 2xx. Mostrar el mensaje y conservar la vista. Errores de validación de FastAPI pueden devolver `detail` como array; el cliente muestra un mensaje genérico legible. No mostrar tokens ni objetos internos de OpenAI.
