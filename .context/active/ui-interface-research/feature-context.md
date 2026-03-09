# Context: Investigacion de interfaz de usuario (Desktop vs Web)

Date: 2026-03-09
Status: ACTIVE
Source Priority: USER_INPUT > CODEBASE > PROJECT_CONTEXT

## Resumen
Se abre investigacion para definir la interfaz principal de HandsomeTranscribe.
El usuario necesita captura con microfono, visualizacion en vivo de conversacion e interlocutores, y reproduccion de audios/textos/reportes al finalizar.
Actualmente el repositorio opera como pipeline CLI por etapas (batch), sin interfaz grafica ni streaming en tiempo real.
La decision de interfaz debe balancear UX, acceso a perifericos, costo bajo y esfuerzo de implementacion incremental.

## Input del Usuario (fuente principal)
- Se desea una UI para la aplicacion.
- Puede ser aplicacion de escritorio en Python o aplicacion web.
- El uso del microfono es critico; si es web debe pedir permisos.
- Si corre local, puede facilitar uso de perifericos (microfono o varios microfonos).
- Aun no esta definida la interfaz final; se requiere investigacion para decidir.
- La UI debe incluir configuraciones de API y modelos de IA.
- Si no hay APIs/modelos pagos, se debe soportar modo gratuito con herramientas disponibles.
- Se requiere visualizacion en vivo de la conversacion/meeting.
- Se deben mostrar interlocutores en vivo.
- Al finalizar sesion, se deben reproducir audios, textos y reportes de la sesion.

## Componentes Implicados
- `main.py`: orquestador CLI actual por comandos (`record`, `transcribe`, `diarize`, `summarize`, `generate-report`).
- `handsome_transcribe/audio/recorder.py`: captura de microfono local con `sounddevice` y guardado WAV.
- `handsome_transcribe/transcription/whisper_transcriber.py`: transcripcion Whisper local y salida JSON.
- `handsome_transcribe/diarization/speaker_identifier.py`: diarizacion pyannote y etiquetado de hablantes.
- `handsome_transcribe/summarization/meeting_summarizer.py`: resumen y extraccion de temas/acciones.
- `handsome_transcribe/reporting/report_generator.py`: salida Markdown/JSON/PDF.
- `outputs/audio/`, `outputs/transcripts/`, `outputs/reports/`: artefactos finales consumibles por UI.
- `README.md`: politica actual local-only y costo bajo (sin proveedores cloud activos en runtime).

## Flujo Actual
1. Captura de audio local a archivo WAV.
2. Transcripcion batch a JSON.
3. Diarizacion batch y asignacion de speaker labels.
4. Resumen batch (transformers opcional, fallback extractivo).
5. Generacion batch de reportes (md/json/pdf).

## Flujo Objetivo de UI (alto nivel)
1. Seleccionar modo de sesion y configuracion (modelo STT, diarizacion, resumen, modo gratuito/pago).
2. Iniciar sesion con captura de microfono(s) y estado visible en UI.
3. Ver timeline en vivo con texto parcial y speaker estimado.
4. Finalizar sesion y disparar consolidacion de resultados.
5. Revisar/reproducir audio, transcript, resumen y reportes desde la UI.

## Dependencias
- Internas: modulos del pipeline actual (audio/transcription/diarization/summarization/reporting).
- Externas actuales: `sounddevice`, `whisper`, `pyannote.audio`, `transformers` (opcional), `reportlab`, `ffmpeg`.
- Posibles para UI desktop: `customtkinter`, `PySide6` o `textual`.
- Posibles para UI web: `FastAPI` + frontend (`React/Vite` o HTMX), WebSocket para actualizaciones en vivo.

## Criterios de Decision de Interfaz
- Acceso robusto a microfono y manejo de multiples dispositivos.
- Facilidad para mostrar transcripcion/interlocutores en vivo.
- Complejidad de empaquetado y distribucion en Windows.
- Curva de desarrollo con stack actual Python.
- Costo operativo (mantener local-only como default).
- Mantenibilidad y escalado futuro (integrar proveedores cloud opcionales).

## Analisis Inicial Desktop vs Web
- Desktop (Python):
  - Pros: acceso directo a perifericos, menor friccion de permisos, reutilizacion directa de modulos Python existentes.
  - Contras: empaquetado/distribucion mas compleja, UI moderna requiere libreria adicional.
- Web local (backend Python + navegador):
  - Pros: UX moderna, facil iteracion visual, extensible para acceso remoto futuro.
  - Contras: permisos de microfono dependen del navegador/contexto, integrar captura multi-mic puede requerir mas trabajo en frontend.

## Discrepancias Detectadas
- Requisito de visualizacion en vivo de conversacion e interlocutores vs implementacion actual batch sin streaming incremental.
- Requisito de reproducir resultados desde UI vs sistema actual orientado a archivos en disco y uso por CLI.

## Reglas y Restricciones
- Mantener prioridad de costo bajo y modo gratuito por defecto.
- No activar proveedores pagos como ruta obligatoria del runtime.
- Respetar convenciones del proyecto (Python 3.10+, `pathlib.Path`, errores claros por etapa).
- No romper comandos CLI existentes; si se integra UI, conservar CLI como interfaz estable.

## Riesgos de Regresion
- Acoplar UI directamente a logica interna puede romper comandos CLI o tests existentes.
- Introducir dependencias UI pesadas sin limites puede aumentar complejidad de instalacion.
- Intentar tiempo real completo en un solo paso puede degradar estabilidad del pipeline.

## Validacion Recomendada
- Automatizada:
  - Mantener tests actuales de modulos (`tests/test_*.py`) pasando.
  - Agregar pruebas de capa de orquestacion para eventos de sesion (inicio/parcial/fin).
- Manual:
  - Prueba de permisos de microfono y seleccion de dispositivo.
  - Prueba de sesion completa con visualizacion en vivo y revision de artefactos finales.

## Preguntas Abiertas
- El target principal de UI es solo Windows local o multiplataforma desde el inicio.
- Se requiere soporte real de multiples microfonos simultaneos o seleccion de uno por sesion.
- Nivel de tiempo real esperado: parcial cada N segundos o palabra a palabra.
- Prioridad de decision: velocidad de entrega inicial vs calidad visual avanzada.

## Recomendacion de investigacion siguiente
- Prototipo A (desktop Python): pantalla de sesion + eventos en vivo simulados sobre pipeline actual.
- Prototipo B (web local): backend Python con WebSocket + permisos de microfono en navegador.
- Comparar ambos con una matriz corta: latencia percibida, esfuerzo, estabilidad de audio, mantenibilidad.
