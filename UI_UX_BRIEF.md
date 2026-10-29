# Brief para UI/UX

## Producto

Folio permite a un dueño de negocio revisar movimientos de efectivo, banco y tarjeta, importar su Excel y hablar con dos agentes de IA. Queremos claridad y confianza: cada número se puede rastrear, los cambios pendientes se distinguen de los confirmados.

## Recorrido prioritario

Importar Excel → vista previa (cuentas, registros nuevos, duplicados, errores) → confirmar → dashboard → preguntar por nómina → abrir movimientos de respaldo → ver archivo, hoja y fila de origen.

Segundo recorrido: nuevo movimiento manual o mensaje al agente de captura → revisar propuesta → confirmar o descartar.

## Pantallas

1. **Resumen:** ingresos y gastos operativos, flujo, posición neta, gráfica, categorías principales, cuentas y movimientos recientes.
2. **Movimientos:** filtros de mes/cuenta/categoría, búsqueda, tabla paginada, exportación y detalle de origen.
3. **Por confirmar:** propuestas pendientes de importación o captura. No afectan las cifras hasta confirmación.
4. **Agentes IA:** analista (lectura) y captura (propuestas). Chat lateral en escritorio y accesible en móvil.
5. **Modales:** importar, revisar propuesta, registro manual, detalle de movimiento, estado de conexión.

## Estados obligatorios

- Libro vacío, carga y errores de red.
- Archivo incompatible, filas con error y duplicados.
- Propuesta pendiente, confirmada y descartada.
- Sin resultados y sin datos suficientes.
- OpenAI conectado, pendiente y error/cuota.
- Saldo desconocido se muestra como “Sin determinar”, nunca como cero.
- Datos ficticios se identifican siempre como “Modo diseño”.

## Reglas que debe respetar la UI

- No confirmar automáticamente. El usuario pulsa un botón explícito.
- Mostrar MXN y hasta dos decimales; el contrato transporta centavos enteros.
- Distinguir ingreso operativo de transferencias, pagos de tarjeta, financiamiento y dinero en custodia.
- Una tarjeta muestra deuda registrada; no es efectivo disponible.
- Evitar llamar “conciliado” a un registro importado. No tenemos conciliación bancaria implementada en este MVP.
- Respuestas de IA con respaldo abren los registros citados, incluso si no hay coincidencias.
- En modo diseño los resultados son simulados; en modo real, mostrar errores sin inventar respuestas.

## Libertad de diseño

Puedes cambiar colores, tipografía, componentes y estructura del frontend. Conserva los tipos y el contrato HTTP; propone cambios coordinados si necesitas otro endpoint. La identidad inicial (Folio, verde y fondos claros) es editable.

Responsive: escritorio 1440 px y móvil desde 375 px. Navegación por teclado, labels de formularios, contraste y estados de foco visibles. Si divides App.tsx, crea componentes en `src/components/` y pantallas en `src/pages/`.

## Entrega esperada

Una rama con la interfaz terminada, `npm run build` pasando y ambos recorridos comprobados en `npm run dev:demo`. No requiere secretos ni datos reales.
