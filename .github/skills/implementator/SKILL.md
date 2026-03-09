# Skill: implementator

## Proposito
Ejecutar planes tecnicos aprobados fase por fase, actualizando el plan en tiempo real con avance, hallazgos y pendientes.

## Entrada esperada
- Ruta de plan en `.context/active/plans/`.

## Flujo minimo
1. Leer plan completo y archivos objetivo.
2. Actualizar plan con metadatos de inicio (fecha, estado: en-progreso).
3. Para cada fase:
   - Marcar como [IN PROGRESS] en el plan.
   - Ejecutar cambios acotados.
   - Ejecutar verificacion automatizada.
   - Actualizar plan con resultados (checkboxes, hallazgos, cambios).
   - Si pasa: marcar como [DONE].
   - Si falla: agregar a seccion "Hallazgos" y pedir aclaracion.
4. Verificacion final y actualizar plan con seccion "Ejecucion" completa.
5. Marcar plan como [COMPLETADO] o [COMPLETADO_CON_PENDIENTES].

## Actualizacion del plan
- El plan es la fuente de verdad unica. NO crear reportes separados.
- Agregar seccion "Ejecucion" con metadatos: inicio, fin, estado.
- Agregar seccion "Hallazgos" con problemas encontrados (CRITICO/MAYOR/MENOR).
- Agregar seccion "Resumen de cambios" con archivos y comandos ejecutados.
- Agregar seccion "Pendientes" con verificacion manual o tareas pendientes.

## Reglas
- No romper comandos CLI existentes sin actualizar tests y README.
- Preferir `pathlib.Path` para portabilidad.
- Reportar resultados de pruebas o limitaciones de ejecucion en el plan.
- Evitar refactors no relacionados con la fase en curso.
- Usar tools (replace_string_in_file, etc) para editar el plan mientras se ejecuta.
- Siempre actualizar el plan despues de cada fase importante o hallazgo.
