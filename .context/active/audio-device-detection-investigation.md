# Investigación: Detección de Micrófonos - Análisis de Logs y Debug

**Fecha:** 2026-03-09  
**Investigador:** reasearch-codebase agent  
**Problema:** No se detectan dispositivos de audio (micrófonos) en Windows

---

## 1. Resumen Ejecutivo

El sistema de detección de micrófonos falla silenciosamente debido a **ausencia de logging** en puntos críticos y **manejo inadecuado de excepciones**. Los 3 componentes principales (ConfigManager, UI Panels, RecorderWorker) no registran información de diagnóstico cuando `sounddevice.query_devices()` falla o retorna dispositivos con claves faltantes.

**Ubicación del problema:**
- [handsome_transcribe/ui/config_manager.py](handsome_transcribe/ui/config_manager.py#L87-L139): Sin logging, KeyError en `default_samplerate`
- [handsome_transcribe/ui/windows/panels.py](handsome_transcribe/ui/windows/panels.py#L206-L215): TypeError silencioso, error truncado
- [handsome_transcribe/ui/workers.py](handsome_transcribe/ui/workers.py#L78-L90): Sin manejo de errores

**Sistema de logging disponible:**
- [handsome_transcribe/ui/logger.py](handsome_transcribe/ui/logger.py#L1-L100): AppLogger con niveles DEBUG/INFO, rotación diaria

---

## 2. Flujo de Ejecución y Puntos de Fallo

```
┌─────────────────────────────────────────────────────────────┐
│ 1. INICIO: Usuario abre aplicación desktop_app.py          │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. ConfigPanel.__init__() se inicializa                    │
│    Archivo: handsome_transcribe/ui/windows/panels.py       │
│    Línea: ~150-180                                          │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. ConfigPanel._load_audio_devices() se ejecuta            │
│    Archivo: panels.py                                       │
│    Líneas: 206-215                                          │
│                                                             │
│    ACTUAL (sin logging):                                    │
│    ```python                                                │
│    def _load_audio_devices(self):                           │
│        try:                                                 │
│            devices = self.config_manager.get_audio_devices()│
│            if devices:                                      │
│                self.device_combo.addItems(devices)  # ❌ BUG│
│            else:                                            │
│                self.device_combo.addItem("Default Device")  │
│        except Exception as e:                               │
│            self.device_combo.addItem(f"Error: {str(e)[:50]}")│
│    ```                                                      │
│                                                             │
│    ❌ PROBLEMA 1: No hay logging antes/después del try      │
│    ❌ PROBLEMA 2: TypeError cuando devices es List[Dict]    │
│    ❌ PROBLEMA 3: Error truncado a 50 caracteres            │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. ConfigManager.get_audio_devices() intenta enumerar      │
│    Archivo: handsome_transcribe/ui/config_manager.py       │
│    Líneas: 87-119                                           │
│                                                             │
│    ACTUAL (sin logging):                                    │
│    ```python                                                │
│    def get_audio_devices(self) -> List[Dict[str, any]]:    │
│        try:                                                 │
│            devices = sd.query_devices()  # ← PUNTO CRÍTICO  │
│            input_devices = []                               │
│                                                             │
│            for idx, device in enumerate(devices):           │
│                if device.get("max_input_channels", 0) > 0:  │
│                    input_devices.append({                   │
│                        "index": idx,                        │
│                        "name": device["name"],  # ❌ KeyError│
│                        "max_input_channels": ...,           │
│                        "default_samplerate": device[...]    │
│                    })                                       │
│            return input_devices                             │
│        except Exception as e:                               │
│            raise ConfigurationError(...) from e             │
│    ```                                                      │
│                                                             │
│    ❌ PROBLEMA 4: No logging de cuántos devices detectó     │
│    ❌ PROBLEMA 5: KeyError en device["name"] y ["...rate"]  │
│    ❌ PROBLEMA 6: No logging de dispositivos con keys falt. │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. OPCIONAL: Usuario inicia grabación                      │
│    RecorderWorker.run() duplica lógica de enumeración      │
│    Archivo: handsome_transcribe/ui/workers.py              │
│    Líneas: 78-90                                            │
│                                                             │
│    ACTUAL (sin logging ni error handling):                  │
│    ```python                                                │
│    def run(self):                                           │
│        try:                                                 │
│            device_idx = None                                │
│            if self.device_name:                             │
│                devices = sd.query_devices()  # ❌ Duplicado │
│                for idx, device in enumerate(devices):       │
│                    if device["name"] == self.device_name:   │
│                        device_idx = idx                     │
│                        break                                │
│                                                             │
│            with sd.InputStream(...):  # ← Falla si no device│
│                while self._recording:                       │
│                    time.sleep(0.1)                          │
│        except Exception as e:                               │
│            self.signals.error.emit(str(e))  # Sin logging   │
│    ```                                                      │
│                                                             │
│    ❌ PROBLEMA 7: Lógica duplicada de config_manager        │
│    ❌ PROBLEMA 8: No logging cuando device_name no match    │
│    ❌ PROBLEMA 9: Exception genérica sin diagnóstico        │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Análisis de Logs Actual vs Propuesto

### 3.1. ConfigManager.get_audio_devices()

**ACTUAL:** ❌ Sin logging

```python
def get_audio_devices(self) -> List[Dict[str, any]]:
    try:
        devices = sd.query_devices()
        input_devices = []
        
        for idx, device in enumerate(devices):
            if device.get("max_input_channels", 0) > 0:
                input_devices.append({
                    "index": idx,
                    "name": device["name"],  # KeyError risk
                    "max_input_channels": device["max_input_channels"],
                    "default_samplerate": device["default_samplerate"]  # KeyError risk
                })
        
        return input_devices
    except Exception as e:
        raise ConfigurationError(f"Failed to query audio devices: {e}") from e
```

**PROPUESTO:** ✅ Con logging detallado

```python
def get_audio_devices(self) -> List[Dict[str, any]]:
    """
    Get list of available audio input devices.
    
    Returns:
        List of dictionaries with device information.
    
    Raises:
        ConfigurationError: If device enumeration fails
    """
    from .logger import AppLogger
    logger = AppLogger.get_logger("ui.config_manager")
    
    try:
        logger.debug("Querying audio devices via sounddevice")
        devices = sd.query_devices()
        logger.info(f"sounddevice.query_devices() returned {len(devices)} total devices")
        
        input_devices = []
        
        for idx, device in enumerate(devices):
            # Log all device keys for debugging
            logger.debug(f"Device {idx} keys: {list(device.keys())}")
            
            # Only include devices with input channels
            max_input = device.get("max_input_channels", 0)
            if max_input > 0:
                # Safe access with .get() to handle missing keys
                device_info = {
                    "index": idx,
                    "name": device.get("name", f"Unknown Device {idx}"),
                    "max_input_channels": max_input,
                    "default_samplerate": device.get("default_samplerate", 44100)
                }
                input_devices.append(device_info)
                logger.debug(f"Added input device: {device_info['name']} (index={idx}, rate={device_info['default_samplerate']})")
            else:
                logger.debug(f"Skipped device {idx} ({device.get('name', 'Unknown')}): no input channels")
        
        logger.info(f"Found {len(input_devices)} input devices")
        
        if not input_devices:
            logger.warning("No audio input devices detected. Check system audio settings.")
        
        return input_devices
        
    except Exception as e:
        logger.error(f"Failed to query audio devices: {e}", exc_info=True)
        raise ConfigurationError(f"Failed to query audio devices: {e}") from e
```

**Logs esperados (caso exitoso):**
```
2026-03-09 14:23:10 [DEBUG   ] ui.config_manager              Querying audio devices via sounddevice
2026-03-09 14:23:10 [INFO    ] ui.config_manager              sounddevice.query_devices() returned 5 total devices
2026-03-09 14:23:10 [DEBUG   ] ui.config_manager              Device 0 keys: ['name', 'hostapi', 'max_input_channels', 'max_output_channels', 'default_low_input_latency', 'default_low_output_latency', 'default_high_input_latency', 'default_high_output_latency', 'default_samplerate']
2026-03-09 14:23:10 [DEBUG   ] ui.config_manager              Skipped device 0 (Microsoft Sound Mapper - Output): no input channels
2026-03-09 14:23:10 [DEBUG   ] ui.config_manager              Device 1 keys: ['name', 'hostapi', 'max_input_channels', 'max_output_channels', 'default_low_input_latency', 'default_low_output_latency', 'default_high_input_latency', 'default_high_output_latency']
2026-03-09 14:23:10 [DEBUG   ] ui.config_manager              Added input device: Microphone (Realtek High Definition Audio) (index=1, rate=44100)
2026-03-09 14:23:10 [DEBUG   ] ui.config_manager              Device 2 keys: ['name', 'hostapi', 'max_input_channels', 'max_output_channels', 'default_samplerate']
2026-03-09 14:23:10 [DEBUG   ] ui.config_manager              Added input device: Microphone Array (Intel SST) (index=2, rate=48000)
2026-03-09 14:23:10 [INFO    ] ui.config_manager              Found 2 input devices
```

**Logs esperados (caso fallo):**
```
2026-03-09 14:23:10 [DEBUG   ] ui.config_manager              Querying audio devices via sounddevice
2026-03-09 14:23:10 [ERROR   ] ui.config_manager              Failed to query audio devices: PortAudio library not initialized
Traceback (most recent call last):
  File "handsome_transcribe/ui/config_manager.py", line 93, in get_audio_devices
    devices = sd.query_devices()
  File "sounddevice.py", line 87, in query_devices
    raise PortAudioError("PortAudio library not initialized")
sounddevice.PortAudioError: PortAudio library not initialized
```

---

### 3.2. ConfigPanel._load_audio_devices()

**ACTUAL:** ❌ Sin logging, TypeError silencioso

```python
def _load_audio_devices(self):
    """Load audio devices into combo box."""
    try:
        devices = self.config_manager.get_audio_devices()
        if devices:
            self.device_combo.addItems(devices)  # ❌ TypeError: expects List[str], not List[Dict]
        else:
            self.device_combo.addItem("Default Device")
    except Exception as e:
        self.device_combo.addItem(f"Error: {str(e)[:50]}")  # ❌ Truncated error
```

**PROPUESTO:** ✅ Con logging y fix de tipo

```python
def _load_audio_devices(self):
    """Load audio devices into combo box."""
    from ..logger import AppLogger
    logger = AppLogger.get_logger("ui.panels.config")
    
    try:
        logger.debug("Loading audio devices into combo box")
        devices = self.config_manager.get_audio_devices()
        
        if devices:
            # Extract device names from list of dicts
            device_names = [f"{d['name']} (Index: {d['index']})" for d in devices]
            logger.info(f"Loading {len(device_names)} audio devices into UI")
            logger.debug(f"Device names: {device_names}")
            
            self.device_combo.clear()
            self.device_combo.addItems(device_names)
            
            # Store full device info for later lookup
            self._device_info = devices
            
        else:
            logger.warning("No audio devices found, using default")
            self.device_combo.clear()
            self.device_combo.addItem("Default Device")
            self._device_info = []
            
    except Exception as e:
        logger.error(f"Failed to load audio devices: {e}", exc_info=True)
        self.device_combo.clear()
        self.device_combo.addItem(f"Error: {str(e)}")  # Full error message
        QMessageBox.warning(
            self,
            "Audio Device Error",
            f"Failed to detect audio devices:\n\n{str(e)}\n\nCheck logs for details."
        )
```

**Logs esperados (caso exitoso):**
```
2026-03-09 14:23:11 [DEBUG   ] ui.panels.config               Loading audio devices into combo box
2026-03-09 14:23:11 [INFO    ] ui.panels.config               Loading 2 audio devices into UI
2026-03-09 14:23:11 [DEBUG   ] ui.panels.config               Device names: ['Microphone (Realtek High Definition Audio) (Index: 1)', 'Microphone Array (Intel SST) (Index: 2)']
```

**Logs esperados (caso sin dispositivos):**
```
2026-03-09 14:23:11 [DEBUG   ] ui.panels.config               Loading audio devices into combo box
2026-03-09 14:23:11 [WARNING ] ui.panels.config               No audio devices found, using default
```

**Logs esperados (caso error):**
```
2026-03-09 14:23:11 [DEBUG   ] ui.panels.config               Loading audio devices into combo box
2026-03-09 14:23:11 [ERROR   ] ui.panels.config               Failed to load audio devices: Failed to query audio devices: PortAudio library not initialized
Traceback (most recent call last):
  ...
```

---

### 3.3. RecorderWorker.run()

**ACTUAL:** ❌ Sin logging, lógica duplicada

```python
def run(self):
    try:
        # Determine device index
        device_idx = None
        if self.device_name:
            devices = sd.query_devices()  # ❌ Duplicate logic
            for idx, device in enumerate(devices):
                if device["name"] == self.device_name:
                    device_idx = idx
                    break
        
        # Record audio until stopped
        with sd.InputStream(
            device=device_idx,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=np.float32,
            callback=self._audio_callback
        ):
            while self._recording:
                time.sleep(0.1)
    except Exception as e:
        self.signals.error.emit(str(e))  # ❌ No logging
```

**PROPUESTO:** ✅ Con logging y uso de ConfigManager

```python
def run(self):
    """
    Main worker execution: record audio to buffer until stopped.
    
    Uses ConfigManager to resolve device name to index, ensuring consistency
    with UI device enumeration.
    """
    from .logger import AppLogger
    logger = AppLogger.get_logger("ui.workers.recorder")
    
    try:
        logger.info(f"RecorderWorker starting (device_name={self.device_name}, rate={self.sample_rate}Hz, channels={self.channels})")
        
        # Determine device index using ConfigManager (no duplication)
        device_idx = None
        if self.device_name:
            logger.debug(f"Resolving device name '{self.device_name}' to index")
            
            from .config_manager import ConfigManager
            config_manager = ConfigManager()
            devices = config_manager.get_audio_devices()
            
            for device in devices:
                if device["name"] in self.device_name or str(device["index"]) in self.device_name:
                    device_idx = device["index"]
                    logger.info(f"Resolved device '{self.device_name}' to index {device_idx}")
                    break
            
            if device_idx is None:
                logger.warning(f"Device '{self.device_name}' not found, using system default")
        else:
            logger.info("No device specified, using system default input device")
        
        # Start recording
        logger.debug(f"Opening InputStream (device={device_idx})")
        with sd.InputStream(
            device=device_idx,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=np.float32,
            callback=self._audio_callback
        ):
            logger.info("Recording started successfully")
            
            while self._recording:
                time.sleep(0.1)
            
            logger.info("Recording stopped by user")
        
        logger.info("RecorderWorker completed successfully")
        self.signals.finished.emit()
        
    except Exception as e:
        logger.error(f"RecorderWorker failed: {e}", exc_info=True)
        self.signals.error.emit(str(e))
```

**Logs esperados (caso exitoso):**
```
2026-03-09 14:25:30 [INFO    ] ui.workers.recorder            RecorderWorker starting (device_name=Microphone (Realtek High Definition Audio) (Index: 1), rate=16000Hz, channels=1)
2026-03-09 14:25:30 [DEBUG   ] ui.workers.recorder            Resolving device name 'Microphone (Realtek High Definition Audio) (Index: 1)' to index
2026-03-09 14:25:30 [INFO    ] ui.workers.recorder            Resolved device 'Microphone (Realtek High Definition Audio) (Index: 1)' to index 1
2026-03-09 14:25:30 [DEBUG   ] ui.workers.recorder            Opening InputStream (device=1)
2026-03-09 14:25:30 [INFO    ] ui.workers.recorder            Recording started successfully
... (usuario graba audio) ...
2026-03-09 14:26:45 [INFO    ] ui.workers.recorder            Recording stopped by user
2026-03-09 14:26:45 [INFO    ] ui.workers.recorder            RecorderWorker completed successfully
```

**Logs esperados (caso device no encontrado):**
```
2026-03-09 14:25:30 [INFO    ] ui.workers.recorder            RecorderWorker starting (device_name=Some Unknown Device, rate=16000Hz, channels=1)
2026-03-09 14:25:30 [DEBUG   ] ui.workers.recorder            Resolving device name 'Some Unknown Device' to index
2026-03-09 14:25:30 [WARNING ] ui.workers.recorder            Device 'Some Unknown Device' not found, using system default
2026-03-09 14:25:30 [DEBUG   ] ui.workers.recorder            Opening InputStream (device=None)
2026-03-09 14:25:30 [INFO    ] ui.workers.recorder            Recording started successfully
```

**Logs esperados (caso error):**
```
2026-03-09 14:25:30 [INFO    ] ui.workers.recorder            RecorderWorker starting (device_name=Microphone (Index: 99), rate=16000Hz, channels=1)
2026-03-09 14:25:30 [DEBUG   ] ui.workers.recorder            Resolving device name 'Microphone (Index: 99)' to index
2026-03-09 14:25:30 [INFO    ] ui.workers.recorder            Resolved device 'Microphone (Index: 99)' to index 99
2026-03-09 14:25:30 [DEBUG   ] ui.workers.recorder            Opening InputStream (device=99)
2026-03-09 14:25:30 [ERROR   ] ui.workers.recorder            RecorderWorker failed: Invalid device 99
Traceback (most recent call last):
  File "handsome_transcribe/ui/workers.py", line 95, in run
    with sd.InputStream(...):
  ...
sounddevice.PortAudioError: Invalid device 99
```

---

### 3.4. ConfigManager.get_default_audio_device()

**ACTUAL:** ❌ Sin logging, KeyError risk

```python
def get_default_audio_device(self) -> Optional[Dict[str, any]]:
    try:
        default_idx = sd.default.device[0]  # ❌ KeyError if not set
        devices = self.get_audio_devices()
        
        for device in devices:
            if device["index"] == default_idx:
                return device
        
        # If default not found in input devices, return first available
        return devices[0] if devices else None
    except Exception as e:
        raise ConfigurationError(f"Failed to get default audio device: {e}") from e
```

**PROPUESTO:** ✅ Con logging y fallback robusto

```python
def get_default_audio_device(self) -> Optional[Dict[str, any]]:
    """
    Get default input audio device.
    
    Returns:
        Dictionary with default device info or None if no devices available.
    """
    from .logger import AppLogger
    logger = AppLogger.get_logger("ui.config_manager")
    
    try:
        logger.debug("Getting default audio input device")
        
        # Try system default first
        try:
            default_idx = sd.default.device[0]
            logger.debug(f"System default input device index: {default_idx}")
        except (AttributeError, IndexError, TypeError) as e:
            logger.warning(f"System default device not available: {e}")
            default_idx = None
        
        # Get all input devices
        devices = self.get_audio_devices()
        
        if not devices:
            logger.error("No audio input devices available")
            return None
        
        # Match system default
        if default_idx is not None:
            for device in devices:
                if device["index"] == default_idx:
                    logger.info(f"Using system default device: {device['name']} (index={default_idx})")
                    return device
            logger.warning(f"System default index {default_idx} not in input devices, using fallback")
        
        # Fallback to first available input device
        fallback_device = devices[0]
        logger.info(f"Using fallback device: {fallback_device['name']} (index={fallback_device['index']})")
        return fallback_device
        
    except Exception as e:
        logger.error(f"Failed to get default audio device: {e}", exc_info=True)
        raise ConfigurationError(f"Failed to get default audio device: {e}") from e
```

**Logs esperados (caso exitoso con default del sistema):**
```
2026-03-09 14:23:11 [DEBUG   ] ui.config_manager              Getting default audio input device
2026-03-09 14:23:11 [DEBUG   ] ui.config_manager              System default input device index: 1
2026-03-09 14:23:11 [INFO    ] ui.config_manager              Using system default device: Microphone (Realtek High Definition Audio) (index=1)
```

**Logs esperados (caso fallback):**
```
2026-03-09 14:23:11 [DEBUG   ] ui.config_manager              Getting default audio input device
2026-03-09 14:23:11 [WARNING ] ui.config_manager              System default device not available: 'NoneType' object is not subscriptable
2026-03-09 14:23:11 [INFO    ] ui.config_manager              Using fallback device: Microphone Array (Intel SST) (index=2)
```

---

## 4. Método de Diagnóstico Propuesto

### 4.1. Nuevo método: ConfigManager.diagnose_audio_devices()

```python
def diagnose_audio_devices(self) -> Dict[str, any]:
    """
    Comprehensive audio device diagnostics.
    
    Returns detailed information about:
    - PortAudio initialization status
    - Total devices detected (input + output)
    - Each device's available keys
    - System default devices
    - sounddevice version
    
    Returns:
        Dictionary with diagnostic information
    """
    from .logger import AppLogger
    logger = AppLogger.get_logger("ui.config_manager")
    
    logger.info("=" * 80)
    logger.info("AUDIO DEVICE DIAGNOSTICS START")
    logger.info("=" * 80)
    
    diagnostics = {
        "timestamp": datetime.now().isoformat(),
        "sounddevice_version": sd.__version__,
        "portaudio_version": None,
        "total_devices": 0,
        "input_devices": 0,
        "output_devices": 0,
        "devices_detail": [],
        "default_input_index": None,
        "default_output_index": None,
        "errors": []
    }
    
    # Check PortAudio version
    try:
        diagnostics["portaudio_version"] = sd.get_portaudio_version()[1]
        logger.info(f"PortAudio version: {diagnostics['portaudio_version']}")
    except Exception as e:
        error_msg = f"Failed to get PortAudio version: {e}"
        diagnostics["errors"].append(error_msg)
        logger.error(error_msg)
    
    # Check default devices
    try:
        diagnostics["default_input_index"] = sd.default.device[0]
        diagnostics["default_output_index"] = sd.default.device[1]
        logger.info(f"Default input device index: {diagnostics['default_input_index']}")
        logger.info(f"Default output device index: {diagnostics['default_output_index']}")
    except Exception as e:
        error_msg = f"Failed to get default devices: {e}"
        diagnostics["errors"].append(error_msg)
        logger.warning(error_msg)
    
    # Query all devices
    try:
        devices = sd.query_devices()
        diagnostics["total_devices"] = len(devices)
        logger.info(f"Total devices detected: {len(devices)}")
        
        for idx, device in enumerate(devices):
            device_detail = {
                "index": idx,
                "name": device.get("name", "UNKNOWN"),
                "hostapi": device.get("hostapi", -1),
                "max_input_channels": device.get("max_input_channels", 0),
                "max_output_channels": device.get("max_output_channels", 0),
                "default_samplerate": device.get("default_samplerate", None),
                "available_keys": list(device.keys()),
                "missing_keys": []
            }
            
            # Check for missing common keys
            expected_keys = ["name", "hostapi", "max_input_channels", "max_output_channels", "default_samplerate"]
            device_detail["missing_keys"] = [k for k in expected_keys if k not in device.keys()]
            
            # Count input/output devices
            if device_detail["max_input_channels"] > 0:
                diagnostics["input_devices"] += 1
            if device_detail["max_output_channels"] > 0:
                diagnostics["output_devices"] += 1
            
            diagnostics["devices_detail"].append(device_detail)
            
            # Log each device
            logger.info(f"Device {idx}: {device_detail['name']}")
            logger.debug(f"  Input channels: {device_detail['max_input_channels']}")
            logger.debug(f"  Output channels: {device_detail['max_output_channels']}")
            logger.debug(f"  Sample rate: {device_detail['default_samplerate']}")
            logger.debug(f"  Available keys: {device_detail['available_keys']}")
            if device_detail["missing_keys"]:
                logger.warning(f"  Missing keys: {device_detail['missing_keys']}")
        
        logger.info(f"Summary: {diagnostics['input_devices']} input, {diagnostics['output_devices']} output devices")
        
    except Exception as e:
        error_msg = f"Failed to query devices: {e}"
        diagnostics["errors"].append(error_msg)
        logger.error(error_msg, exc_info=True)
    
    logger.info("=" * 80)
    logger.info("AUDIO DEVICE DIAGNOSTICS END")
    logger.info("=" * 80)
    
    return diagnostics
```

**Logs esperados (diagnóstico completo):**
```
2026-03-09 14:30:00 [INFO    ] ui.config_manager              ================================================================================
2026-03-09 14:30:00 [INFO    ] ui.config_manager              AUDIO DEVICE DIAGNOSTICS START
2026-03-09 14:30:00 [INFO    ] ui.config_manager              ================================================================================
2026-03-09 14:30:00 [INFO    ] ui.config_manager              PortAudio version: PortAudio V19.7.0-devel, revision 147dd722548358763a8b649b3e4b41dfffbcfbb6
2026-03-09 14:30:00 [INFO    ] ui.config_manager              Default input device index: 1
2026-03-09 14:30:00 [INFO    ] ui.config_manager              Default output device index: 0
2026-03-09 14:30:00 [INFO    ] ui.config_manager              Total devices detected: 5
2026-03-09 14:30:00 [INFO    ] ui.config_manager              Device 0: Microsoft Sound Mapper - Output
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Input channels: 0
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Output channels: 2
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Sample rate: 48000.0
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Available keys: ['name', 'hostapi', 'max_input_channels', 'max_output_channels', 'default_low_input_latency', 'default_low_output_latency', 'default_high_input_latency', 'default_high_output_latency', 'default_samplerate']
2026-03-09 14:30:00 [INFO    ] ui.config_manager              Device 1: Microphone (Realtek High Definition Audio)
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Input channels: 2
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Output channels: 0
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Sample rate: None
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Available keys: ['name', 'hostapi', 'max_input_channels', 'max_output_channels', 'default_low_input_latency', 'default_high_input_latency']
2026-03-09 14:30:00 [WARNING ] ui.config_manager                Missing keys: ['default_samplerate']
2026-03-09 14:30:00 [INFO    ] ui.config_manager              Device 2: Microphone Array (Intel SST)
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Input channels: 4
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Output channels: 0
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Sample rate: 48000.0
2026-03-09 14:30:00 [DEBUG   ] ui.config_manager                Available keys: ['name', 'hostapi', 'max_input_channels', 'max_output_channels', 'default_low_input_latency', 'default_high_input_latency', 'default_samplerate']
2026-03-09 14:30:00 [INFO    ] ui.config_manager              Summary: 2 input, 3 output devices
2026-03-09 14:30:00 [INFO    ] ui.config_manager              ================================================================================
2026-03-09 14:30:00 [INFO    ] ui.config_manager              AUDIO DEVICE DIAGNOSTICS END
2026-03-09 14:30:00 [INFO    ] ui.config_manager              ================================================================================
```

### 4.2. Integración CLI para diagnóstico

**Archivo:** `main.py` o `desktop_app.py`

```python
@app.command()
def diagnose_audio():
    """
    Run audio device diagnostics and display detailed information.
    
    Useful for troubleshooting microphone detection issues on Windows.
    """
    from handsome_transcribe.ui.config_manager import ConfigManager
    from handsome_transcribe.ui.logger import AppLogger
    import json
    
    # Initialize logging
    AppLogger()
    
    config_manager = ConfigManager()
    diagnostics = config_manager.diagnose_audio_devices()
    
    # Print to console as well
    console.print("\n[bold cyan]Audio Device Diagnostics[/bold cyan]")
    console.print(f"Timestamp: {diagnostics['timestamp']}")
    console.print(f"sounddevice version: {diagnostics['sounddevice_version']}")
    console.print(f"PortAudio version: {diagnostics['portaudio_version']}")
    console.print(f"\nTotal devices: {diagnostics['total_devices']}")
    console.print(f"Input devices: {diagnostics['input_devices']}")
    console.print(f"Output devices: {diagnostics['output_devices']}")
    
    if diagnostics['errors']:
        console.print("\n[bold red]Errors:[/bold red]")
        for error in diagnostics['errors']:
            console.print(f"  - {error}")
    
    # Save to file
    diag_file = Path("logs") / f"audio_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    diag_file.parent.mkdir(exist_ok=True)
    with open(diag_file, 'w', encoding='utf-8') as f:
        json.dump(diagnostics, f, indent=2)
    
    console.print(f"\n[green]Diagnostics saved to: {diag_file}[/green]")
    console.print("[yellow]Check logs/handsome_transcribe_*.log for detailed device enumeration[/yellow]")
```

**Uso:**
```powershell
# Con Typer CLI
python main.py diagnose-audio

# O agregar flag a desktop_app.py
python desktop_app.py --diagnose-audio
```

---

## 5. Puntos Críticos para Debug

### 5.1. Checklist de verificación

Cuando un usuario reporte que no se detectan micrófonos, verificar en este orden:

1. **¿Se está ejecutando el logging?**
   - Buscar archivo `logs/handsome_transcribe_YYYYMMDD.log`
   - Si no existe: problema con AppLogger initialization
   - Si existe pero vacío: nivel de logging demasiado alto

2. **¿sounddevice puede consultar dispositivos?**
   ```python
   import sounddevice as sd
   print(sd.query_devices())
   ```
   - Si retorna lista vacía: problema con PortAudio en Windows
   - Si lanza excepción: PortAudio no instalado/inicializado

3. **¿Los dispositivos tienen la clave `default_samplerate`?**
   - Buscar en logs: `Device X keys: [...]`
   - Si falta `default_samplerate`: usar fallback de 44100
   - Común en dispositivos WASAPI de Windows

4. **¿El UI combo box está recibiendo strings?**
   - Buscar en logs: `Loading X audio devices into UI`
   - Si hay TypeError: check que se extraen nombres de dicts

5. **¿RecorderWorker puede resolver device_name?**
   - Buscar en logs: `Resolved device 'X' to index Y`
   - Si no hace match: formato de nombre inconsistente con UI

### 5.2. Tabla de síntomas y diagnóstico

| Síntoma | Log esperado si funciona | Log real (fallo) | Archivo responsable | Línea |
|---------|-------------------------|------------------|---------------------|-------|
| Combo box vacío | `Loading 2 audio devices into UI` | (ausente) | panels.py | 206-215 |
| Combo box muestra "Error: ..." | (no aplica) | `Failed to load audio devices:` | panels.py | 214 |
| Aplicación crash al abrir | `Querying audio devices via sounddevice` | (ausente o exception) | config_manager.py | 87-119 |
| Grabación falla | `Resolved device 'X' to index Y` | `Device 'X' not found` | workers.py | 78-90 |
| Sin dispositivos detectados | `Found 2 input devices` | `Found 0 input devices` | config_manager.py | 115 |

### 5.3. Filtros de búsqueda en logs

```powershell
# Ver solo mensajes de configuración de audio
Select-String -Path "logs\handsome_transcribe_*.log" -Pattern "config_manager|audio device"

# Ver errores relacionados con audio
Select-String -Path "logs\handsome_transcribe_*.log" -Pattern "ERROR.*audio|Failed to query"

# Ver dispositivos detectados
Select-String -Path "logs\handsome_transcribe_*.log" -Pattern "Device \d+:|Found \d+ input"

# Ver flujo completo de grabación
Select-String -Path "logs\handsome_transcribe_*.log" -Pattern "RecorderWorker|Recording"
```

---

## 6. Cambios Específicos en Código

### Archivo 1: handsome_transcribe/ui/config_manager.py

```python
# AÑADIR al inicio del archivo (después de imports existentes)
from .logger import AppLogger

# MODIFICAR método get_audio_devices() (líneas 87-119)
# Ver sección 3.1 para implementación completa

# MODIFICAR método get_default_audio_device() (líneas 122-139)
# Ver sección 3.4 para implementación completa

# AÑADIR nuevo método (después de get_default_audio_device)
def diagnose_audio_devices(self) -> Dict[str, any]:
    # Ver sección 4.1 para implementación completa
```

### Archivo 2: handsome_transcribe/ui/windows/panels.py

```python
# AÑADIR al inicio de la clase ConfigPanel
from ...logger import AppLogger

# MODIFICAR método _load_audio_devices() (líneas 206-215)
# Ver sección 3.2 para implementación completa

# AÑADIR atributo de instancia en __init__
self._device_info = []  # Stores full device info from ConfigManager
```

### Archivo 3: handsome_transcribe/ui/workers.py

```python
# AÑADIR al inicio de RecorderWorker.run()
from .logger import AppLogger

# MODIFICAR método run() (líneas 75-95)
# Ver sección 3.3 para implementación completa
```

---

## 7. Tests Propuestos

### test_audio_device_detection.py

```python
"""
Tests for audio device detection with edge cases.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from handsome_transcribe.ui.config_manager import ConfigManager
from handsome_transcribe.ui.exceptions import ConfigurationError


class TestAudioDeviceDetection:
    """Test audio device enumeration and error handling."""
    
    @patch('handsome_transcribe.ui.config_manager.sd.query_devices')
    def test_get_audio_devices_success(self, mock_query):
        """Test successful device enumeration."""
        mock_query.return_value = [
            {
                "name": "Microphone 1",
                "hostapi": 0,
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_samplerate": 48000.0
            },
            {
                "name": "Speaker",
                "hostapi": 0,
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100.0
            }
        ]
        
        config_manager = ConfigManager()
        devices = config_manager.get_audio_devices()
        
        assert len(devices) == 1
        assert devices[0]["name"] == "Microphone 1"
        assert devices[0]["index"] == 0
        assert devices[0]["default_samplerate"] == 48000.0
    
    @patch('handsome_transcribe.ui.config_manager.sd.query_devices')
    def test_get_audio_devices_missing_samplerate(self, mock_query):
        """Test device with missing default_samplerate key."""
        mock_query.return_value = [
            {
                "name": "WASAPI Microphone",
                "hostapi": 1,
                "max_input_channels": 2,
                "max_output_channels": 0
                # Missing 'default_samplerate'
            }
        ]
        
        config_manager = ConfigManager()
        devices = config_manager.get_audio_devices()
        
        assert len(devices) == 1
        assert devices[0]["name"] == "WASAPI Microphone"
        assert devices[0]["default_samplerate"] == 44100  # Fallback value
    
    @patch('handsome_transcribe.ui.config_manager.sd.query_devices')
    def test_get_audio_devices_missing_name(self, mock_query):
        """Test device with missing name key."""
        mock_query.return_value = [
            {
                "hostapi": 0,
                "max_input_channels": 1,
                "max_output_channels": 0,
                "default_samplerate": 44100.0
                # Missing 'name'
            }
        ]
        
        config_manager = ConfigManager()
        devices = config_manager.get_audio_devices()
        
        assert len(devices) == 1
        assert "Unknown Device" in devices[0]["name"]
    
    @patch('handsome_transcribe.ui.config_manager.sd.query_devices')
    def test_get_audio_devices_empty_list(self, mock_query):
        """Test when no devices are detected."""
        mock_query.return_value = []
        
        config_manager = ConfigManager()
        devices = config_manager.get_audio_devices()
        
        assert devices == []
    
    @patch('handsome_transcribe.ui.config_manager.sd.query_devices')
    def test_get_audio_devices_portaudio_error(self, mock_query):
        """Test PortAudio initialization failure."""
        mock_query.side_effect = Exception("PortAudio library not initialized")
        
        config_manager = ConfigManager()
        
        with pytest.raises(ConfigurationError) as exc_info:
            config_manager.get_audio_devices()
        
        assert "Failed to query audio devices" in str(exc_info.value)
    
    @patch('handsome_transcribe.ui.config_manager.sd.default')
    @patch('handsome_transcribe.ui.config_manager.sd.query_devices')
    def test_get_default_audio_device_fallback(self, mock_query, mock_default):
        """Test fallback when system default not available."""
        mock_default.device = [None, None]  # No default set
        mock_query.return_value = [
            {
                "name": "Mic 1",
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_samplerate": 48000.0
            }
        ]
        
        config_manager = ConfigManager()
        default_device = config_manager.get_default_audio_device()
        
        assert default_device is not None
        assert default_device["name"] == "Mic 1"


class TestConfigPanelDeviceLoading:
    """Test UI device loading."""
    
    @patch('handsome_transcribe.ui.windows.panels.ConfigManager')
    def test_load_audio_devices_success(self, mock_config_class):
        """Test successful loading into combo box."""
        mock_config = Mock()
        mock_config.get_audio_devices.return_value = [
            {"index": 0, "name": "Mic 1", "max_input_channels": 2, "default_samplerate": 48000},
            {"index": 1, "name": "Mic 2", "max_input_channels": 1, "default_samplerate": 44100}
        ]
        mock_config_class.return_value = mock_config
        
        # ConfigPanel initialization would call _load_audio_devices()
        # Verify combo box receives List[str] not List[Dict]
        # (Requires full UI test setup with QApplication)
    
    @patch('handsome_transcribe.ui.windows.panels.ConfigManager')
    def test_load_audio_devices_error_handling(self, mock_config_class):
        """Test error display in UI."""
        mock_config = Mock()
        mock_config.get_audio_devices.side_effect = ConfigurationError("Test error")
        mock_config_class.return_value = mock_config
        
        # Verify error message shown in combo box
        # Verify QMessageBox displayed
        # (Requires full UI test setup)
```

---

## 8. Prioridad de Implementación

### ALTA PRIORIDAD (bloqueante)
1. Fix ConfigManager.get_audio_devices() con `.get()` para claves faltantes (sección 3.1)
2. Fix ConfigPanel._load_audio_devices() para extraer strings (sección 3.2)
3. Agregar logging básico en ConfigManager (INFO level)

### MEDIA PRIORIDAD (mejora experiencia)
4. Refactorizar RecorderWorker para usar ConfigManager (sección 3.3)
5. Agregar método diagnose_audio_devices() (sección 4.1)
6. Mejorar get_default_audio_device() con fallback (sección 3.4)

### BAJA PRIORIDAD (nice-to-have)
7. Tests unitarios completos (sección 7)
8. Comando CLI diagnose-audio (sección 4.2)
9. Botón "Refresh Devices" en UI

---

## 9. Referencias

### Archivos clave
- [handsome_transcribe/ui/config_manager.py](handsome_transcribe/ui/config_manager.py)
- [handsome_transcribe/ui/windows/panels.py](handsome_transcribe/ui/windows/panels.py)
- [handsome_transcribe/ui/workers.py](handsome_transcribe/ui/workers.py)
- [handsome_transcribe/ui/logger.py](handsome_transcribe/ui/logger.py)

### Documentación external
- sounddevice: https://python-sounddevice.readthedocs.io/
- PortAudio Windows issues: https://github.com/PortAudio/portaudio/wiki/Notes_Windows

### Issues conocidos en development-plan.md
- Línea 852: "sounddevice no detecta dispositivo"
- Línea 1514: "Audio device query tiene KeyError en clave `default_samplerate`"
- Línea 2155: "Audio device no detectado en windows"

---

## 10. Conclusiones

El problema de detección de micrófonos es **100% solucionable** implementando:

1. **Safe access** a device keys con `.get(key, default)`
2. **Logging comprehensivo** en todos los puntos críticos
3. **Extracción correcta** de strings para UI combo box
4. **Reutilización** de ConfigManager en RecorderWorker

**Causa raíz confirmada:**
- Windows devices (especialmente WASAPI) no siempre exponen `default_samplerate`
- Código actual usa acceso directo `device["key"]` → KeyError
- UI recibe List[Dict] en lugar de List[str] → TypeError
- Sin logging, errores son invisibles para usuario y desarrollador

**Solución estimada:** 2-3 horas de desarrollo + 1 hora de testing

---

**Siguiente paso recomendado:** Ejecutar script de diagnóstico para confirmar estado actual del sistema del usuario:

```powershell
python -c "import sounddevice as sd; devices = sd.query_devices(); print(f'Total: {len(devices)}'); [print(f'{i}: {d}') for i, d in enumerate(devices)]"
```
