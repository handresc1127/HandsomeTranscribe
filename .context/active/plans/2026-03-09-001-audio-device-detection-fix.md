# Plan: Fix deteccion de microfonos en UI

## Ejecucion

**Iniciada**: 2026-03-09 10:00
**Completada**: 2026-03-09 11:15
**Tiempo total**: 01:15
**Estado**: COMPLETADO_CON_PENDIENTES

## Resumen

Corregir la carga de dispositivos de audio en el panel de configuracion para que el combo box muestre nombres legibles y evitar fallos de tipo. Agregar logging minimo para diagnostico y reforzar el manejo defensivo de datos de dispositivos en configuracion. Opcionalmente, alinear el worker de grabacion con la misma fuente de dispositivos.

## Estado Actual (con evidencia)
- ConfigPanel agrega una lista de dicts a QComboBox, lo que impide que se muestren los dispositivos correctamente: [handsome_transcribe/ui/windows/panels.py](handsome_transcribe/ui/windows/panels.py#L206-L215).
- ConfigManager retorna List[Dict] de dispositivos de entrada sin logging diagnostico: [handsome_transcribe/ui/config_manager.py](handsome_transcribe/ui/config_manager.py#L87-L119).
- RecorderWorker vuelve a consultar dispositivos sin logging ni manejo centralizado: [handsome_transcribe/ui/workers.py](handsome_transcribe/ui/workers.py#L78-L90).
- La verificacion confirma que sounddevice detecta 22 dispositivos y el error principal es el tipo incorrecto en el combo: [.context/active/research/verified-research.md](.context/active/research/verified-research.md).

## Estado Deseado
- El combo de dispositivos muestra una lista de nombres (strings) y permite seleccionar microfonos.
- Se registra logging minimo para diagnostico cuando se carga la lista.
- ConfigManager maneja claves faltantes de manera defensiva sin romper el flujo.
- (Opcional) RecorderWorker usa la misma fuente de datos que el UI para resolver el device index.

## Fuera de Alcance
- Hot-reload de dispositivos.
- Seleccion de output devices.
- Cambios en CLI o nuevas opciones de linea de comandos.

## Fases

- [x] Fase 1: Fix critico en UI
- [x] Fase 2: Logging minimo y manejo defensivo en ConfigManager
- [x] Fase 3 (Opcional): Unificar resolucion de dispositivo en RecorderWorker

### Fase 1: Fix critico en UI

Cambios
- Modificar `ConfigPanel._load_audio_devices()` para convertir List[Dict] en List[str] antes de `addItems()`.
- Limpiar el combo box antes de cargar items.
- Guardar el mapeo de dispositivos en un atributo local para uso posterior si es necesario.

Riesgos
- Bajo: solo afecta el panel de configuracion.

Verificacion automatizada
- N/A (no hay tests de UI existentes que cubran este flujo).

Verificacion manual
- Ejecutar la app y abrir el panel de configuracion; verificar que el combo muestra los microfonos detectados.

### Fase 2: Logging minimo y manejo defensivo en ConfigManager

Cambios
- Agregar logging en `get_audio_devices()` para numero de dispositivos encontrados y numero de inputs.
- Usar `.get()` con defaults para claves opcionales como `default_samplerate`.

Riesgos
- Bajo: solo agrega logging y fallback defensivo.

Verificacion automatizada
- Ejecutar tests existentes relacionados con audio si aplican (`pytest tests/test_recorder.py -v`).

Verificacion manual
- Revisar el log `logs/handsome_transcribe_YYYYMMDD.log` para confirmar entradas de deteccion.

### Fase 3 (Opcional): Unificar resolucion de dispositivo en RecorderWorker

Cambios
- Reutilizar `ConfigManager.get_audio_devices()` para resolver `device_idx` por nombre.
- Agregar logging al flujo de resolucion y apertura de `InputStream`.

Riesgos
- Medio: cambios en flujo de grabacion pueden impactar si el nombre de dispositivo no coincide exactamente.

Verificacion automatizada
- `pytest tests/test_recorder.py -v`

Verificacion manual
- Iniciar grabacion y verificar que se abre el dispositivo correcto.

## Resumen de cambios

- **Archivos modificados**: 3
- **Tests ejecutados**: 1
- **Tests pasados**: 1
- **Tests fallidos**: 0

### Cambios por archivo
- `handsome_transcribe/ui/windows/panels.py`: el combo de dispositivos ahora recibe nombres (strings), se limpia antes de cargar, se guarda el mapeo de dispositivos, se registra el listado en logs y se prioriza la seleccion de dispositivo Microsoft Array AMD cuando esta disponible.
- `handsome_transcribe/ui/config_manager.py`: logging minimo de deteccion y acceso defensivo a claves opcionales.
- `handsome_transcribe/ui/workers.py`: resolucion del dispositivo unificada con ConfigManager y logging de seleccion.

## Verificacion ejecutada

### Automatizada
- `python.exe -m pytest tests/test_recorder.py -v`: PASS

### Manual sugerida
- [ ] `python desktop_app.py` y abrir el panel de configuracion para confirmar que el combo muestra microfonos.
- [ ] Revisar `logs/handsome_transcribe_YYYYMMDD.log` para validar entradas de deteccion.

## Riesgos identificados

- [MENOR] Verificacion manual y tests aun pendientes.

## Pendientes

- [ ] Ejecutar verificacion manual en UI.

## Estrategia de Pruebas

- Priorizar verificacion manual en UI (config panel).
- Ejecutar pruebas existentes de audio y workers si estan disponibles.
- Evitar imprimir logs con emojis en Python (restriccion de UTF-8 en Windows).

## Rollback

- Revertir los cambios en `ConfigPanel._load_audio_devices()` y `ConfigManager.get_audio_devices()` si el combo deja de funcionar o si el logging introduce ruido.
- Mantener el codigo previo guardado por git para rollback rapido.

## Criterios de Cierre

- El combo box muestra los microfonos en Windows.
- No hay errores de tipo en la carga del combo.
- El log registra la cantidad de dispositivos detectados.
- Se puede iniciar grabacion usando un dispositivo seleccionado.
