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

Abre `http://127.0.0.1:8000`. El script hereda `OPENAI_API_KEY` de la terminal; opcionalmente el backend puede leer `.env.local` en la raíz, excluido de Git. La clave nunca debe colocarse en variables `VITE_*` ni en código del navegador. `OPENAI_MODEL` permite cambiar el modelo (default: `gpt-5.4-mini`).

Para desarrollo simultáneo:

```sh
# Terminal 1
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
# Terminal 2
cd frontend && npm run dev
```

El backend guarda los datos en `data/finanzas.sqlite`, excluido de Git. `FINANZAS_DB` permite indicar una base separada para pruebas. `/health` informa si ese proceso tiene clave, sin revelar su valor.

## Estado y alcance

Implementados: dashboard, movimientos y filtros, importación específica de Balance XLSX, vista previa, confirmación, duplicados, registro manual, procedencia, exportación CSV, agentes acotados e interfaz de consulta con respaldo.

El modo real empieza vacío: hay que subir el Excel y confirmar. El importador admite las hojas `Movimientos Efectivo`, `Movimientos Banco` y `Movimientos Tarjeta BBVA`, con encabezados en la fila 3. Usa el catálogo del libro y los saldos iniciales de sus hojas de balance. Otros formatos requieren su adaptador.

Importado/confirmado **no** significa conciliado con el banco. No es un sistema fiscal ni una contabilidad completa de doble partida. Telegram, PDF bancario, audio, facturación y cálculo de nómina quedan fuera del MVP. Una sola empresa, un usuario y MXN; servidor limitado a loopback para la demo local.

Los agentes no tienen herramientas para confirmar ni para ejecutar SQL arbitrario. El analista consulta funciones permitidas y las cifras de la respuesta se construyen desde los totales calculados en el backend. Captura produce una propuesta revisable. Sin clave el registro manual y la importación siguen disponibles, pero el chat real devuelve un error de conexión claro.

## Equipo

1. UI/UX: frontend y accesibilidad.
2. Backend: libro, API y cálculos.
3. Agentes: interpretación y consulta con respaldo.
4. Importación: adaptador Excel, pruebas e integración.

Desarrollo desde cero; no contiene código de Cuadra. No subir estados de cuenta, libros reales, bases locales ni secretos a este repositorio.
