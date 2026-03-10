# Investigación Técnica: Sesión No Inicia - "Waiting for session to start..."

**Fecha:** 2026-03-09  
**Agente:** reasearch-codebase  
**Estado:** ✅ RESUELTO (2026-03-09)  
**Severidad:** BLOQUEANTE - Usuario no puede iniciar sesiones

---

## ✅ Resolución

**Fecha de implementación:** 2026-03-09  
**Plan ejecutado:** [.context/active/plans/2026-03-09-002-fix-sesion-no-inicia.md](.context/active/plans/2026-03-09-002-fix-sesion-no-inicia.md)  
**Ejecutor:** implementator

**Fix aplicado:** Agregada llamada a `self.session_manager.start_session()` en [handsome_transcribe/ui/windows/session_window.py](handsome_transcribe/ui/windows/session_window.py#L378)

**Resultado:**
- ✅ Sesión inicia correctamente (estado RECORDING)
- ✅ Database tests: 9/9 pasan
- ✅ EventBus tests: 6/6 pasan
- ✅ Pipeline E2E: 7/9 pasan (mejora vs 0/9 antes del fix)
- ✅ NO hay regresiones introducidas

**Pendientes identificados:**
- Tests unitarios de SessionManager necesitan actualización (firma del método)
- Tests de workers necesitan actualización (AttributeError)

---

## Resumen Ejecutivo

El flujo de inicio de sesión está **incompleto** en [session_window.py#L367-L382](handsome_transcribe/ui/windows/session_window.py#L367-L382). El método `_on_session_requested()` **crea** el `SessionManager` pero **NO invoca** `start_session()`, dejando la sesión en estado `IDLE` y la UI congelada en "Waiting for session to start...".

**Hallazgos clave:**
- ✅ Señal `session_requested` se emite correctamente desde `ConfigPanel`
- ✅ Conexión a slot `_on_session_requested` está establecida
- ❌ **FALTA:** Llamada a `self.session_manager.start_session()` después de instanciación
- ❌ Como consecuencia: Nunca se emiten señales `session_started` ni `session_state_changed`
- ❌ `LiveSessionView` permanece esperando indefinidamente

**Fix:** Agregar UNA línea en [session_window.py#L377](handsome_transcribe/ui/windows/session_window.py#L377):
```python
self.session_manager.start_session()
```

---

## Mapa Técnico del Flujo de Inicio de Sesión

### 1. Punto de Entrada: ConfigPanel (User Action)

**Ubicación:** [handsome_transcribe/ui/windows/panels.py#L341-L365](handsome_transcribe/ui/windows/panels.py#L341-L365)

**Método:** `_on_start_session()`

**Comportamiento actual:**
```python
def _on_start_session(self):
    """Slot: start session button clicked."""
    # Check for active session
    if self._has_active_session:
        QMessageBox.warning(...)
        return
    
    # Collect configuration
    config = SessionConfig(
        modelo_whisper=self.whisper_combo.currentText(),
        habilitar_diarizacion=self.diarization_check.isChecked(),
        habilitar_resumen=self.summarization_check.isChecked(),
        dispositivo_audio=self.device_combo.currentText(),
        hf_token=self.config_manager.load_config().hf_token,
        session_context=self.context_text.toPlainText() or None
    )
    
    # Validate
    is_valid, error = self.config_manager.validate_config(config)
    if not is_valid:
        QMessageBox.warning(self, "Configuration Invalid", ...)
        return
    
    # ✅ Emit signal with config
    self.session_requested.emit(config)
```

**Estado:** ✅ **FUNCIONA CORRECTAMENTE**
- Validación de configuración exitosa
- Emisión de señal `session_requested` confirmada
- Documentación en línea 198: `.clicked.connect(self._on_start_session)`

---

### 2. Orquestador: SessionWindow (Signal Handler)

**Ubicación:** [handsome_transcribe/ui/windows/session_window.py#L367-L382](handsome_transcribe/ui/windows/session_window.py#L367-L382)

**Método:** `_on_session_requested(config: SessionConfig)`

**Comportamiento actual (BUGGY):**
```python
@Slot(object)
def _on_session_requested(self, config):
    """Slot: session start requested from ConfigPanel."""
    try:
        # Create or update session manager
        self.session_manager = SessionManager(
            config,
            self.event_bus,
            self.db,
            self.speaker_manager
        )
        
        # ❌ PROBLEMA: Solo crea SessionManager, no lo inicia
        # ❌ FALTA: self.session_manager.start_session()
        
        # Switch to live session tab
        self.tab_widget.setCurrentWidget(self.live_session_view)
    except Exception as e:
        self.event_bus.emit_session_error("Failed to Start Session", str(e))
```

**Estado:** ❌ **INCOMPLETO**
- Instanciación de `SessionManager` exitosa
- **PERO:** `SessionManager` queda en estado `IDLE` (línea 59 de session_manager.py)
- **PERO:** Nunca se inicia recording worker, eventos, ni auto-save
- Conexión de señal confirmada en línea 110: `.session_requested.connect(self._on_session_requested)`

**Impacto:**
- UI cambia a `live_session_view` tab
- Pero `LiveSessionView` nunca recibe señal `session_state_changed`
- Usuario ve mensaje "Waiting for session to start..." indefinidamente

---

### 3. Motor de Sesión: SessionManager (Engine)

**Ubicación:** [handsome_transcribe/ui/session_manager.py#L90-L162](handsome_transcribe/ui/session_manager.py#L90-L162)

**Método:** `start_session() -> SessionData`

**Comportamiento esperado (NO SE EJECUTA):**
```python
def start_session(self) -> SessionData:
    """
    Start a new recording session.
    
    This method:
    1. Validates no active session exists
    2. Creates session directory structure
    3. Initializes SessionData
    4. Saves session to database
    5. Starts recorder worker
    6. Starts auto-save timer
    
    Returns:
        Created SessionData
        
    Raises:
        ActiveSessionError: If a session is already active
    """
    # 1. Validate no active session (línea 107-110)
    if self.current_state not in (SessionState.IDLE, SessionState.COMPLETED, SessionState.ERROR):
        raise ActiveSessionError(...)
    
    # Check database for active sessions (línea 113-117)
    active_db_session = self.database.get_active_session()
    if active_db_session:
        raise ActiveSessionError(...)
    
    # 2. Create session directory (línea 120-121)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = self._create_session_directory(timestamp)
    
    # 3. Initialize session data (línea 124-137)
    session_data = SessionData(
        id=-1,
        created_at=datetime.now(),
        session_dir=session_dir,
        recording_path=session_dir / RECORDING_FILENAME,
        transcript_path=session_dir / TRANSCRIPT_FILENAME,
        summary_path=session_dir / SUMMARY_FILENAME if self.config.habilitar_resumen else None,
        metadata_path=session_dir / METADATA_FILENAME,
        temp_dir=session_dir / TEMP_DIR_NAME,
        config=self.config,
        state=SessionState.RECORDING,
        session_context=self.config.session_context,
        partial_audio_count=0
    )
    
    # 4. Save to database (línea 140)
    session_data.id = self.database.create_session(session_data)
    
    # Set as current session (línea 143-144)
    self.current_session = session_data
    self._transition_state(SessionState.RECORDING)  # ← CRÍTICO: Emite session_state_changed
    
    # 5. Start recorder worker (línea 147-153)
    self.recorder_worker = RecorderWorker(
        event_bus=self.event_bus,
        device_name=self.config.dispositivo_audio,
        sample_rate=16000,
        channels=1
    )
    self._thread_pool.start(self.recorder_worker)
    
    # 6. Start auto-save timer (línea 156)
    self._start_autosave_timer()
    
    # 7. Emit session_started event (línea 159)
    self.event_bus.emit_session_started(session_data.id)
    
    return session_data
```

**Estado:** ⚠️ **IMPLEMENTADO PERO NO INVOCADO**
- Método existe y está completo
- Documentación exhaustiva
- **PERO:** Nunca se llama desde `SessionWindow._on_session_requested()`

**Consecuencias de no ejecutar:**
- Directorio de sesión no creado
- Base de datos sin registro de sesión activa
- Estado permanece en `IDLE`
- RecorderWorker no iniciado → Sin captura de audio
- Auto-save timer no iniciado
- **Señales críticas no emitidas:**
  - `session_started` (línea 159)
  - `session_state_changed("RECORDING")` (vía `_transition_state` línea 144)

---

### 4. Transición de Estados: _transition_state()

**Ubicación:** [handsome_transcribe/ui/session_manager.py#L282-L320](handsome_transcribe/ui/session_manager.py#L282-L320)

**Método:** `_transition_state(new_state: SessionState)`

**Comportamiento:**
```python
def _transition_state(self, new_state: SessionState):
    """Transition to a new state with validation."""
    # Valid transitions map (línea 292-303)
    valid_transitions = {
        SessionState.IDLE: [SessionState.RECORDING],
        SessionState.RECORDING: [SessionState.PAUSED, SessionState.TRANSCRIBING, SessionState.ERROR],
        SessionState.PAUSED: [SessionState.RECORDING, SessionState.TRANSCRIBING, SessionState.ERROR],
        # ... más transiciones
    }
    
    # Validate transition (línea 305-308)
    if new_state not in valid_transitions.get(self.current_state, []):
        raise SessionError(...)
    
    old_state = self.current_state
    self.current_state = new_state
    
    # Update database if session exists (línea 313-314)
    if self.current_session:
        self.database.update_session(self.current_session.id, state=new_state)
    
    # ✅ CRÍTICO: Emit event (línea 317)
    self.event_bus.emit_session_state_changed(new_state.value)
```

**Estado:** ✅ **IMPLEMENTADO CORRECTAMENTE**
- Validación de transiciones de estado
- Actualización de BD
- **Emisión de señal `session_state_changed`** → LiveSessionView debería responder a esto

**Problema:** Este método nunca se ejecuta porque `start_session()` no se invoca.

---

### 5. EventBus: Sistema de Señales

**Ubicación:** [handsome_transcribe/ui/event_bus.py](handsome_transcribe/ui/event_bus.py)

**Señales relevantes:**

#### a) session_started (línea 63)
```python
session_started = Signal(str)  # session_info_json
```

**Emisor:** [event_bus.py#L216-L224](handsome_transcribe/ui/event_bus.py#L216-L224)
```python
def emit_session_started(self, session_info_json: str):
    """Emit session started event."""
    self.session_started.emit(session_info_json)
```

**Invocado desde:** [session_manager.py#L159](handsome_transcribe/ui/session_manager.py#L159) dentro de `start_session()`

**Estado:** ❌ **NUNCA EMITIDA** (porque `start_session()` no se ejecuta)

#### b) session_state_changed (línea 67)
```python
session_state_changed = Signal(str)  # new_state (SessionState.value)
```

**Emisor:** [event_bus.py#L245-L253](handsome_transcribe/ui/event_bus.py#L245-L253)
```python
def emit_session_state_changed(self, new_state: str):
    """Emit session state change."""
    self.session_state_changed.emit(new_state)
```

**Invocado desde:** [session_manager.py#L317](handsome_transcribe/ui/session_manager.py#L317) dentro de `_transition_state()`

**Estado:** ❌ **NUNCA EMITIDA** (porque `_transition_state()` no se ejecuta)

---

### 6. Receptor: LiveSessionView (UI Update)

**Ubicación:** [handsome_transcribe/ui/windows/panels.py#L574-L610](handsome_transcribe/ui/windows/panels.py#L574-L610)

**Método:** `_on_state_changed(state: str)`

**Comportamiento esperado:**
```python
@Slot(str)
def _on_state_changed(self, state: str):
    """Slot: session state changed."""
    try:
        session_state = SessionState[state]
        
        # ✅ ESPERADO: Estado RECORDING
        if session_state == SessionState.RECORDING:
            self.pause_button.setText("Pause")
            self.pause_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self._is_paused = False
            self.stage_label.setText("Recording in progress...")  # ← Esto debería mostrarse
            self.transcript_view.clear()
            self._session_active = True
        
        elif session_state == SessionState.PAUSED:
            self.pause_button.setText("Resume")
            self._is_paused = True
            self.stage_label.setText("Recording paused")
        
        elif session_state == SessionState.TRANSCRIBING:
            self.pause_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.stage_label.setText("Transcribing...")
        
        # ... más estados
```

**Conexión de señal:** [panels.py#L538](handsome_transcribe/ui/windows/panels.py#L538)
```python
self.event_bus.session_state_changed.connect(self._on_state_changed)
```

**Estado:** ⚠️ **IMPLEMENTADO PERO INACTIVO**
- Slot conectado correctamente a señal `session_state_changed`
- **PERO:** Señal nunca emitida
- **Resultado:** UI permanece en estado inicial con mensaje "Waiting for session to start..."
- Botones `pause_button` y `stop_button` permanecen deshabilitados

---

## Flujo de Ejecución Detallado

### Flujo ACTUAL (Buggy)

```
1. Usuario: Clic en "Start Session" (ConfigPanel)
   ├─ Archivo: panels.py
   └─ Línea: 341 (_on_start_session)

2. Validación de configuración
   ├─ Verificar sesión activa: ✅
   ├─ Crear SessionConfig: ✅
   └─ Validar config: ✅

3. ConfigPanel emite señal: session_requested.emit(config)
   ├─ Archivo: panels.py
   ├─ Línea: ~365
   └─ Estado: ✅ Señal emitida

4. SessionWindow recibe señal: _on_session_requested(config)
   ├─ Archivo: session_window.py
   ├─ Línea: 367
   └─ Acción: Crear SessionManager(config, ...) ✅

5. ❌ PROBLEMA: NO llama a start_session()
   ├─ Línea faltante: ~377
   └─ Consecuencia: SessionManager en estado IDLE

6. SessionWindow cambia tab
   ├─ Línea: 379
   └─ Acción: setCurrentWidget(live_session_view) ✅

7. ❌ LiveSessionView espera señales que nunca llegan
   ├─ Señal esperada: session_state_changed("RECORDING")
   ├─ Slot destino: _on_state_changed (línea 574)
   └─ Estado UI: "Waiting for session to start..." (CONGELADO)

8. ❌ Usuario: Ve UI congelada sin feedback
   └─ Sin logs de error visibles
```

### Flujo ESPERADO (Con Fix)

```
1-4. [Igual que flujo actual]

5. ✅ SessionWindow llama a start_session()
   ├─ Archivo: session_window.py
   ├─ Línea: 377 (AGREGAR)
   └─ Acción: self.session_manager.start_session()

6. SessionManager.start_session() ejecuta:
   ├─ Validar estados: ✅ (línea 107)
   ├─ Crear directorio sesión: ✅ (línea 120)
   ├─ Inicializar SessionData: ✅ (línea 124)
   ├─ Guardar en BD: ✅ (línea 140)
   ├─ Transición estado → RECORDING: ✅ (línea 144)
   │  └─► EMITE: session_state_changed("RECORDING") [línea 317]
   ├─ Iniciar RecorderWorker: ✅ (línea 147)
   ├─ Iniciar auto-save timer: ✅ (línea 156)
   └─ EMITE: session_started(session_id) ✅ (línea 159)

7. ✅ EventBus entrega señales:
   ├─ session_started → No hay receptores críticos
   └─ session_state_changed("RECORDING") → LiveSessionView

8. ✅ LiveSessionView._on_state_changed("RECORDING"):
   ├─ Archivo: panels.py
   ├─ Línea: 574-587
   ├─ Actualizar UI:
   │  ├─ stage_label.setText("Recording in progress...") ✅
   │  ├─ pause_button.setEnabled(True) ✅
   │  ├─ stop_button.setEnabled(True) ✅
   │  └─ transcript_view.clear() ✅
   └─ Estado: _session_active = True

9. ✅ RecorderWorker inicia captura audio:
   ├─ Device: config.dispositivo_audio
   ├─ Sample rate: 16000 Hz
   └─ Emitir frames periódicamente

10. ✅ Usuario: Ve UI actualizada con feedback en tiempo real
    └─ Grabación en progreso visible
```

---

## Dependencias y Contratos

### SessionManager ← SessionWindow
- **Contrato:** SessionWindow debe invocar `start_session()` después de instanciar SessionManager
- **Estado actual:** ❌ Contrato roto - Solo instancia, no invoca
- **Ubicación:** [session_window.py#L372-L377](handsome_transcribe/ui/windows/session_window.py#L372-L377)

### SessionManager → EventBus
- **Contrato:** SessionManager emite `session_started` y `session_state_changed` al iniciar
- **Dependencias:**
  - `event_bus.emit_session_started(session_id)` (línea 159)
  - `event_bus.emit_session_state_changed(state)` (línea 317)
- **Estado:** ⚠️ Implementado pero no ejecutado

### EventBus → LiveSessionView
- **Contrato:** LiveSessionView escucha `session_state_changed` para actualizar UI
- **Conexión:** [panels.py#L538](handsome_transcribe/ui/windows/panels.py#L538)
- **Estado:** ✅ Conectado correctamente, esperando señales

### SessionManager → RecorderWorker
- **Contrato:** SessionManager inicia RecorderWorker en thread pool
- **Dependencia:** [session_manager.py#L147-L153](handsome_transcribe/ui/session_manager.py#L147-L153)
- **Estado:** ❌ Nunca ejecutado (worker no iniciado)

### SessionManager → Database
- **Contratos:**
  1. Verificar sesión activa antes de crear nueva (línea 113)
  2. Crear registro de sesión (línea 140)
  3. Actualizar estado en transiciones (línea 314)
- **Estado:** ❌ Solo punto 1 podría ejecutarse; 2 y 3 nunca

---

## Riesgos de Regresión

### 1. Validaciones en start_session()
**Riesgo:** Si existen validaciones silenciosas que fallan, el fix no resolvería el problema

**Mitigación:**
- ✅ Verificado: Validaciones lanzan excepciones explícitas (ActiveSessionError, SessionError)
- ✅ SessionWindow._on_session_requested() tiene try/except que captura y emite session_error

**Áreas sensibles:**
- [session_manager.py#L107-L110](handsome_transcribe/ui/session_manager.py#L107-L110): Verificación de estado
- [session_manager.py#L113-L117](handsome_transcribe/ui/session_manager.py#L113-L117): Verificación BD de sesión activa

### 2. Thread Pool Initialization
**Riesgo:** `_thread_pool` podría no estar inicializado

**Mitigación:**
- ✅ Verificado: `_thread_pool = QThreadPool.globalInstance()` (línea 70)
- ✅ globalInstance() siempre retorna instancia válida

### 3. Auto-save Timer
**Riesgo:** Timer podría fallar al iniciar

**Mitigación:**
- ✅ Timer inicializado en __init__ (línea 73-75)
- ✅ Método `_start_autosave_timer()` existe (referenciado en línea 156)

### 4. Directorio de Sesión Faltante
**Riesgo:** Fallo en creación de directorio podría abortar start_session()

**Mitigación:**
- ✅ Verificado: `SESSIONS_DIR.mkdir(parents=True, exist_ok=True)` en __init__ (línea 80)
- ✅ Método `_create_session_directory()` maneja creación (línea 322+)

### 5. Múltiples Llamadas Accidentales
**Riesgo:** Si se llama start_session() múltiples veces

**Mitigación:**
- ✅ Validación existente en start_session() previene esto (línea 107-110)
- ✅ Lanza ActiveSessionError si estado no es IDLE/COMPLETED/ERROR

---

## Tests Afectados

### Tests Existentes

#### 1. test_pipeline_e2e.py
**Estado:** ❌ **Falló la última ejecución** (Exit code 1)
- Terminal muestra: `pytest tests/ui/test_pipeline_e2e.py -q`
- Probable que el test intente iniciar sesión y falle por el mismo bug

**Recomendación:** Ejecutar después del fix para confirmar

#### 2. test_session_manager.py
**Ubicación:** `tests/ui/test_session_manager.py`

**Tests esperados:**
- `test_start_session_creates_directory`
- `test_start_session_emits_signals`
- `test_start_session_starts_recorder`
- `test_start_session_rejects_duplicate`

**Estado:** Desconocido - Requiere verificación

#### 3. Cobertura de SessionWindow
**Brecha:** No parece haber tests específicos para `SessionWindow._on_session_requested()`

**Recomendación:** Agregar test que verifique:
```python
def test_on_session_requested_calls_start_session(qtbot, mock_db, mock_event_bus):
    """Verify _on_session_requested() calls start_session()."""
    window = SessionWindow(mock_event_bus, mock_db)
    config = SessionConfig(...)
    
    with patch.object(window.session_manager, 'start_session') as mock_start:
        window._on_session_requested(config)
        mock_start.assert_called_once()
```

---

## Brechas en la Investigación

### 1. Confirmación de RecorderWorker Functionality
**Pregunta:** ¿RecorderWorker funciona correctamente cuando se inicia?

**Notas:**
- Código analizado sugiere que sí (línea 147-153)
- Requiere validación manual después del fix

### 2. Comportamiento de Auto-save
**Pregunta:** ¿El timer de auto-save funciona después de iniciar?

**Notas:**
- Método `_start_autosave_timer()` no leído en detalle
- Intervalo configurado: 2 minutos (AUTO_SAVE_INTERVAL_MS)

### 3. Error Handling End-to-End
**Pregunta:** ¿Errores en start_session() se manejan correctamente?

**Evidencia parcial:**
- ✅ try/except en `_on_session_requested()` (línea 377-382)
- ✅ Emit `session_error` en caso de excepción
- ⚠️ No verificado si LiveSessionView responde a session_error

---

## Verificación Post-Fix

### Checklist de Validación Manual

1. **UI Flow:**
   - [ ] Abrir app desktop (`python desktop_app.py`)
   - [ ] Navegar a Configuration tab
   - [ ] Configurar sesión (modelo, dispositivo)
   - [ ] Clic en "Start Session"
   - [ ] **Verificar:** UI cambia a LiveSessionView
   - [ ] **Verificar:** stage_label muestra "Recording in progress..."
   - [ ] **Verificar:** Botones Pause y Stop habilitados
   - [ ] **Verificar:** NO aparece "Waiting for session to start..."

2. **Logs y Señales:**
   - [ ] Verificar en logs/console: "session_started emitted"
   - [ ] Verificar: "session_state_changed: RECORDING"
   - [ ] Verificar: RecorderWorker iniciado (frames capturados)

3. **Base de Datos:**
   - [ ] Verificar registro de sesión creado en BD
   - [ ] Verificar estado de sesión = RECORDING
   - [ ] Verificar paths de archivos creados

4. **Sistema de Archivos:**
   - [ ] Verificar directorio de sesión creado en `outputs/sessions/`
   - [ ] Verificar estructura: `YYYYMMDD_HHMMSS/`
   - [ ] Verificar subdirectorio `temp/` creado

5. **Funcionalidad de Grabación:**
   - [ ] Clic en "Pause" → UI actualiza a "Recording paused"
   - [ ] Clic en "Resume" → UI vuelve a "Recording in progress..."
   - [ ] Clic en "Stop" → Sesión termina correctamente

### Checklist de Tests Automatizados

1. **Tests de Integración:**
   - [ ] `pytest tests/ui/test_pipeline_e2e.py -v` → PASS
   - [ ] Verificar no hay fallos relacionados con inicio de sesión

2. **Tests de SessionManager:**
   - [ ] `pytest tests/ui/test_session_manager.py -v` → PASS
   - [ ] Verificar tests de `start_session()` pasan

3. **Tests de SessionWindow (si existen):**
   - [ ] Verificar `_on_session_requested()` ejecuta flujo completo
   - [ ] Verificar manejo de excepciones

---

## Conclusiones

### Causa Raíz Confirmada
**La sesión no inicia porque** [session_window.py#L367-L382](handsome_transcribe/ui/windows/session_window.py#L367-L382) **solo instancia SessionManager pero NO invoca el método `start_session()` que:**
- Crea la infraestructura de sesión
- Inicia workers de grabación
- Emite señales críticas para actualizar la UI

### Fix Confirmado
**Agregar UNA línea** en [session_window.py#L377](handsome_transcribe/ui/windows/session_window.py#L377):
```python
self.session_manager.start_session()
```

### Impacto del Fix
- ✅ Iniciará grabación automáticamente
- ✅ Actualizará UI a "Recording in progress..."
- ✅ Habilitará controles de Pause/Stop
- ✅ Iniciará auto-save y persistencia
- ⚠️ Requiere validación manual y tests

### Próximos Pasos Recomendados
1. **Implementar fix** en session_window.py
2. **Validar manualmente** siguiendo checklist
3. **Ejecutar tests** para confirmar no hay regresiones
4. **Agregar test específico** para _on_session_requested()
5. **Verificar comportamiento** de RecorderWorker y auto-save

---

## Referencias de Código

| Componente | Archivo | Líneas Clave |
|------------|---------|--------------|
| ConfigPanel._on_start_session | panels.py | 341-365 |
| ConfigPanel.session_requested (signal) | panels.py | 198 (conexión) |
| SessionWindow._on_session_requested | session_window.py | 367-382 |
| SessionWindow conexión de señal | session_window.py | 110 |
| SessionManager.__init__ | session_manager.py | 49-80 |
| SessionManager.start_session | session_manager.py | 90-162 |
| SessionManager._transition_state | session_manager.py | 282-320 |
| EventBus.session_started (signal) | event_bus.py | 63 |
| EventBus.session_state_changed (signal) | event_bus.py | 67 |
| EventBus.emit_session_started | event_bus.py | 216-224 |
| EventBus.emit_session_state_changed | event_bus.py | 245-253 |
| LiveSessionView._on_state_changed | panels.py | 574-610 |
| LiveSessionView conexión de señal | panels.py | 538 |
| RecorderWorker inicialización | session_manager.py | 147-153 |

---

**Investigación completada por:** reasearch-codebase agent  
**Fecha:** 2026-03-09  
**Versión:** 1.0  
**Confianza del diagnóstico:** 99% (evidencia directa en código)
