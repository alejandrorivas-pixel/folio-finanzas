# Contrato mínimo de integración

Base URL relativa: `/api`. Vite dirige `/api` a `http://127.0.0.1:8000`. JSON salvo la carga de XLSX. Los tipos de frontend están en `frontend/src/types.ts`.

## Movimiento

`id`, `date` (AAAA-MM-DD), `account` (`efectivo`, `banco`, `tarjeta_bbva`), `kind`, `category`, `description`, `amount_minor` (entero con signo), `currency` (`MXN`), `reference`, `property`, `treatment`, `source_file`, `source_sheet`, `source_row`.

Negativo reduce efectivo/posición neta; positivo lo aumenta. Un cargo de tarjeta es negativo y un pago de tarjeta positivo. En el formulario el usuario da importe positivo y el backend aplica el signo. `treatment` es `operational`, `transfer`, `card_payment`, `custody`, `financing` o `por_revisar`.

## Endpoints

| Método y ruta | Uso |
|---|---|
| `GET /health` | `{status, ai_configured, model, demo_mode}` sin secretos |
| `GET /api/meta` | Cuentas, categorías, meses, conteo confirmado y pendiente |
| `GET /api/summary?month=2026-10&account=banco` | Totales, saldos por cuenta, series diarias, categorías y últimos registros |
| `GET /api/movements` | Filtros opcionales `month`, `account`, `category`, `search`, `ids` (separados por coma), `page`, `size` (máx. 100). Devuelve `{items,total,page,size,totals}` |
| `GET /api/movements/{id}` | Detalle y procedencia |
| `POST /api/imports/preview` | Multipart con campo `file` XLSX. Devuelve propuesta pendiente |
| `POST /api/imports/local-preview` | Vista previa del dataset ficticio; no abre archivos personales y solo está disponible en modo demo |
| `GET /api/proposals` | Propuestas pendientes |
| `GET /api/proposals/{id}` | Estado y contenido actualizado de una propuesta |
| `POST /api/proposals/manual` | Prepara un movimiento; nunca lo confirma |
| `POST /api/proposals/{id}/confirm` | Body `{ "confirm": true }`. Devuelve `{inserted,duplicates,already_confirmed}` |
| `POST /api/proposals/{id}/corrections` | `{sheet,row,movement,reason}`; corrige una fila inválida solo en la propuesta pendiente y conserva la trazabilidad |
| `POST /api/proposals/{id}/reject` | Body `{ "confirm": true }` |
| `POST /api/chat` | `{message, mode: "analyst" | "capture", month, account, history}` |
| `GET /api/export?month=2026-10` | CSV de los movimientos confirmados del filtro |

### Propuesta manual

```json
{"date":"2026-10-28","account":"efectivo","kind":"egreso","category":"Nómina y sueldos","description":"Pago de nómina","amount_minor":150000,"reference":null,"property":null}
```

### Propuesta de importación

`{id,kind,status,created_at,payload}`. `payload` incluye `movements`, `stats` (`total,new,duplicates,errors,review,accounts`), `errors`, `notes`, `openings`, `filename`. Hay que impedir confirmar si hay errores. Si el usuario cierra el modal, la propuesta sigue pendiente.

### Respuesta del agente

`{agent,message,evidence?,proposal?,draft?}`. Una evidencia contiene `filters`, `totals` y `movement_ids`. El analista no modifica datos. Captura puede pedir datos faltantes o devolver propuesta pendiente. Confirmar sigue siendo una acción HTTP independiente iniciada por el usuario.

### Errores

`{detail: "mensaje"}` con estado no 2xx. Mostrar el mensaje y conservar la vista. Errores de validación de FastAPI pueden devolver `detail` como array; el cliente muestra un mensaje genérico legible. No mostrar tokens ni objetos internos de OpenAI.
