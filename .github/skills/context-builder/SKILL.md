# Skill: context-builder

## Proposito
Crear y mantener archivos de contexto en `.context/` usando como fuente principal lo indicado por el usuario.

## Cuando usar
- Cuando el usuario pide documentar lo que esta trabajando.
- Cuando se necesita insumo para planificacion o implementacion.
- Actualizacion de arquitectura, convenciones o constraints.
- Limpieza de contenido heredado o desactualizado.

## Prioridad de fuentes
1. Input del usuario (principal).
2. Evidencia del codebase.
3. Contexto existente en `.context/project/`.

## Salida esperada
- Documento de contexto util para otros agentes (feature, sesion o contexto actual).
- Rutas sugeridas:
	- `.context/active/{feature}/feature-context.md`
	- `.context/sessions/session-{YYYY-MM-DD}.md`
	- `.context/active/current-context.md`
