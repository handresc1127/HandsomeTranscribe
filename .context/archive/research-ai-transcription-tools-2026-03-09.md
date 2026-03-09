# Investigacion: Transcripcion Local (Whisper) y Roadmap de Integraciones

Date: 2026-03-09
Project: HandsomeTranscribe
Scope: Definir el enfoque oficial del proyecto para transcripcion local y registrar integraciones futuras como roadmap desactivado.

## 1. Resumen Ejecutivo

El proyecto adopta una politica local-first:

1. Transcripcion activa: Whisper local (sin APIs pagas).
2. Reportes y resumen: procesamiento local en Python.
3. Integraciones cloud (OpenAI API, Google, Azure, AWS): solo roadmap futuro, no habilitadas en runtime.

Decision oficial:

- No usar herramientas pagas de otros proveedores en la operacion actual del proyecto.
- Mantener costos de API en 0 USD en la configuracion por defecto.

## 2. Tecnologia activa (hoy)

### 2.1 Transcripcion

- Motor activo: Whisper local (open-source).
- Ejecucion: local en CPU/GPU del usuario.
- Dependencia clave: ffmpeg.

### 2.2 Diarizacion

- pyannote.audio permanece opcional.
- Si no hay token HF, el flujo puede operar sin diarizacion.

### 2.3 Resumen y reportes

- Resumen por reglas disponible con --no-transformers.
- Exportacion local en markdown/json/pdf.

## 3. Estado de proveedores pagos

Estado actual en el proyecto:

- OpenAI API: DESACTIVADO
- Google Speech-to-Text: DESACTIVADO
- Azure Speech: DESACTIVADO
- AWS Transcribe: DESACTIVADO

Nota:

Estas opciones pueden evaluarse en una fase futura, pero no forman parte del runtime actual.

## 4. Implicaciones para licencias de usuario

- ChatGPT Plus: no habilita API runtime para el proyecto.
- GitHub Copilot: ayuda al desarrollo, no sustituye un backend STT para usuarios finales.

## 5. Configuracion y seguridad

Para el estado actual local-only:

- No se requieren claves de proveedores cloud para transcribir.
- Evitar agregar variables de entorno de proveedores pagos en configuracion base.

Variable opcional vigente:

- HF_TOKEN (solo para diarizacion opcional con pyannote).

## 6. Recomendacion operativa oficial

1. Mantener Whisper local como motor unico activo.
2. Mantener Modo Gratis como default del CLI.
3. Posponer integraciones cloud hasta decision formal de presupuesto y roadmap.

## 7. Roadmap (futuro, no implementado)

Si en el futuro se habilita cloud:

1. Debe ser opt-in (nunca default).
2. Debe documentarse costo por minuto y presupuesto mensual.
3. Debe conservarse fallback local para evitar bloqueo por costo.

## 8. Fuentes tecnicas base

- Whisper repository: https://github.com/openai/whisper
- faster-whisper repository: https://github.com/SYSTRAN/faster-whisper
- Vosk: https://alphacephei.com/vosk/

## 9. Vigencia

Esta investigacion reemplaza el enfoque previo orientado a comparativa de proveedores pagos como opcion activa.
El estado oficial del proyecto pasa a local-only hasta nuevo aviso.
