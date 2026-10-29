# Brief para UI/UX

## Producto

Folio permite a un dueño de negocio revisar movimientos de efectivo, banco y tarjeta, importar Excel o documentos y hablar con dos agentes de IA. Queremos claridad y confianza: cada número se puede rastrear, los cambios pendientes se distinguen de los confirmados.

## Recorrido prioritario

Importar Excel → vista previa (cuentas, registros nuevos, duplicados, errores) → confirmar → dashboard → preguntar por nómina → abrir movimientos de respaldo → ver archivo, hoja y fila de origen.

Segundo recorrido: nuevo movimiento manual o mensaje al agente de captura → revisar propuesta → confirmar o descartar.

Documentos: “Importar movimientos” → “Añade movimientos” → pestaña PDF o Captura / foto → seleccionar cuenta → cargar → revisar datos y procedencia → corregir errores con motivo → confirmar. Una lectura asistida puede contener errores; no presentar “extracción terminada” como comprobación bancaria.

Dictado: agente de captura → “Dictar” → permiso del micrófono → “Terminar” → transcripción en el campo de texto → editar → enviar al agente → revisar propuesta → confirmar. “Cancelar” detiene la grabación sin transcribir. También se puede seleccionar un archivo de audio. La transcripción nunca se envía automáticamente al agente.

## Pantallas

1. **Resumen:** ingresos y gastos operativos, flujo, posición neta, gráfica, categorías principales, cuentas y movimientos recientes.
2. **Movimientos:** filtros de mes/cuenta/categoría, búsqueda, tabla paginada, exportación y detalle de origen.
3. **Por confirmar:** propuestas pendientes de importación o captura. No afectan las cifras hasta confirmación.
4. **Agentes IA:** analista (lectura) y captura (propuestas). Chat lateral en escritorio y accesible en móvil.
5. **Modales:** importar (Excel, PDF, Captura / foto), revisar propuesta, corregir fila, registro manual, detalle de movimiento y estado de conexión.

## Estados obligatorios

- Libro vacío, carga y errores de red.
- Archivo incompatible, filas con error y duplicados.
- Lectura del documento en curso, formato/tamaño/páginas rechazados, campos ambiguos y moneda sin confirmar.
- Micrófono no disponible o denegado, grabación con contador, cancelación, transcripción en curso, texto editable y error del proveedor.
- Propuesta pendiente, confirmada y descartada.
- Sin resultados y sin datos suficientes.
- OpenAI conectado, pendiente y error/cuota.
- Saldo desconocido se muestra como “Sin determinar”, nunca como cero.
- Datos ficticios se identifican siempre. “Modo diseño” corresponde al frontend independiente; la app completa usa “Demostración · todos los datos son ficticios”.

## Reglas que debe respetar la UI

- No confirmar automáticamente. El usuario pulsa un botón explícito.
- Mostrar MXN y hasta dos decimales; el contrato transporta centavos enteros.
- Distinguir ingreso operativo de transferencias, pagos de tarjeta, financiamiento y dinero en custodia.
- Una tarjeta muestra deuda registrada; no es efectivo disponible.
- Evitar llamar “conciliado” a un registro importado. No tenemos conciliación bancaria implementada en este MVP.
- Respuestas de IA con respaldo abren los registros citados, incluso si no hay coincidencias.
- En modo diseño los resultados son simulados; en modo real, mostrar errores sin inventar respuestas.
- Los ejemplos “Probar PDF ficticio”, “Probar captura ficticia” y “Probar dictado” son simulados. No activar un selector de archivo ni pedir permiso de micrófono al usarlos.
- Antes de una carga real, explicar que el documento o audio se envía a OpenAI para su procesamiento. Mantener las claves fuera de la interfaz.
- Mostrar cuenta, fecha, tipo, importe MXN, categoría y procedencia antes de confirmar un documento. Ofrecer edición con motivo también en registros sin error. Los errores impiden la confirmación; no ocultarlos bajo un estado de éxito general.
- Para documentos, “Página” indica la página física y “registro” identifica la extracción. No llamar “fila del documento” al identificador interno ni ofrecer abrir un original que no se almacena.
- La cuenta se elige antes de cargar documentos. Los importes pendientes y sin moneda confirmada no afectan los saldos.
- Mantener editable el texto dictado y ofrecer carga de audio si el micrófono no funciona. Comunicar el máximo de 60 segundos de grabación y 10 MB por archivo.
- Wispr Flow puede escribir en el campo mediante su dictado externo. No presentarlo como un plugin integrado en Folio.

## Libertad de diseño

Puedes cambiar colores, tipografía, componentes y estructura del frontend. Conserva los tipos y el contrato HTTP; propone cambios coordinados si necesitas otro endpoint. La identidad inicial (Folio, verde y fondos claros) es editable.

Responsive: escritorio 1440 px y móvil desde 375 px. Navegación por teclado, labels de formularios, contraste y estados de foco visibles. Si divides App.tsx, crea componentes en `src/components/` y pantallas en `src/pages/`.

## Entrega esperada

Una rama con la interfaz terminada, `npm run build` pasando y los recorridos de importación, consulta, captura y dictado comprobados en `npm run dev:demo`. No requiere secretos ni datos reales. Los ejemplos verifican interacción; no demuestran extracción o transcripción reales.
