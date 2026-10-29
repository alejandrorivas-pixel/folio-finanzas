# Contribuir a Folio

Folio nació como un proyecto personal. Las contribuciones pequeñas, los reportes reproducibles y las mejoras de documentación son bienvenidos. No hay un calendario de entregas ni un plazo garantizado de revisión.

Antes de un cambio grande, abre una propuesta para acordar su alcance. Para un arreglo concreto, puedes enviar directamente un pull request que explique el problema, el cambio y cómo lo comprobaste.

## Preparar el entorno

Necesitas Python 3.11+ y Node 20+. Desde la raíz de tu clon:

```sh
./scripts/setup.sh
./start.sh
```

La app abre en `http://127.0.0.1:8000` con datos ficticios. Si tu `python3` es anterior a 3.11, indica uno compatible: `PYTHON_BIN=python3.12 ./scripts/setup.sh`.

Para trabajar únicamente en la interfaz, sin Python ni una clave de IA:

```sh
cd frontend
npm ci
npm run dev:demo
```

Este modo usa ejemplos y respuestas simuladas en memoria. Los contratos reales están en [API_CONTRACT.md](API_CONTRACT.md); la conexión de agentes, en [MCP_GUIDE.md](MCP_GUIDE.md).

## Comprobar un cambio

Desde la raíz, ejecuta las pruebas del backend:

```sh
.venv/bin/python -m pytest
```

Para comprobar tipos y compilar la interfaz:

```sh
cd frontend
npm run build
```

Las pruebas usan bases temporales, documentos sintéticos y respuestas controladas del proveedor. No necesitan una clave de OpenAI; las de MCP requieren poder iniciar procesos y escuchar en un puerto local. Una prueba con respuestas simuladas no demuestra que una integración con un proveedor esté funcionando: indica por separado qué verificaste realmente.

Si cambias una regla del libro, un importador o una operación de escritura, añade una prueba del comportamiento relevante. Para cambios visuales, incluye una captura con datos ficticios y comprueba escritorio y móvil. Mantén los cambios de formato ajenos al objetivo fuera del PR.

## Reglas que debemos conservar

- Dinero en centavos enteros; los cálculos y signos los determina el backend.
- Una propuesta pendiente no cambia el libro ni los saldos. Los agentes preparan; la persona revisa y confirma en una acción separada.
- Las consultas financieras deben permitir identificar los movimientos que respaldan sus resultados. No inventar importes ni convertir un saldo desconocido en cero.
- Conservar la procedencia de importaciones y las correcciones humanas. Confirmar no equivale a conciliar con el banco.
- Distinguir ingresos y gastos operativos de transferencias propias, pagos de tarjeta, depósitos en garantía y financiación.
- Comprobar los reintentos y duplicados al modificar una importación o la API de propuestas para agentes.
- Tratar documentos, descripciones y respuestas de modelos como datos no confiables. Mantener las claves exclusivamente en el backend.

## Datos y reportes

Crea los ejemplos desde cero. No adjuntes estados de cuenta, hojas reales, bases SQLite personales, audios privados, capturas con información financiera ni secretos a issues, commits o PRs. Cambiar nombres en un documento real no garantiza que deje de contener datos sensibles.

Para reproducir un fallo, incluye pasos, comportamiento esperado y observado, versión o commit, y un ejemplo mínimo ficticio. Revisa también los logs antes de compartirlos. Los posibles problemas de seguridad se reportan por el canal de [SECURITY.md](SECURITY.md), no en un issue público.
