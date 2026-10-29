import queue
import threading
from typing import List, Dict, Any, Optional

try:
    import sounddevice as sd
    import numpy as np
    HAVE_SOUNDDEVICE = True
except ImportError:
    HAVE_SOUNDDEVICE = False

DEFAULT_SAMPLE_RATE = 44100
DEFAULT_CHANNELS = 1
BLOCK_SIZE = 1024

class AudioSource:
    def __init__(self):
        self._stream = None
        self._enabled = False
        self._device_id: Optional[int] = None
        self._queue = queue.Queue(maxsize=50)
        self._lock = threading.Lock()

    def list_devices(self) -> List[Dict[str, Any]]:
        if not HAVE_SOUNDDEVICE:
            return []
        devs = []
        try:
            default_api = sd.default.hostapi
            host_info = sd.query_hostapis(default_api)
            for dev_idx in host_info['devices']:
                d = sd.query_devices(dev_idx)
                if d.get('max_input_channels', 0) > 0:
                    raw_name = d.get('name', f"Microphone {dev_idx}")
                    devs.append({
                        "id": dev_idx,
                        "name": raw_name,
                        "channels": d.get('max_input_channels', 1),
                        "samplerate": DEFAULT_SAMPLE_RATE
                    })
        except Exception as e:
            print(f"[AudioSource] Notice: could not enumerate audio devices: {e}")
        return devs

    def start(self, device_id: Optional[int] = None) -> bool:
        if not HAVE_SOUNDDEVICE:
            return False
        self.stop()
        try:
            self._device_id = device_id
            self._stream = sd.InputStream(
                device=device_id,
                channels=DEFAULT_CHANNELS,
                samplerate=DEFAULT_SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                dtype='int16',
                callback=self._audio_callback
            )
            self._stream.start()
            self._enabled = True
            print(f"[AudioSource] Microfone iniciado no dispositivo #{device_id}")
            return True
        except Exception as e:
            print(f"[AudioSource] Falha ao abrir microfone: {e}")
            self._enabled = False
            return False

    def _audio_callback(self, indata, frames, time_info, status):
        if self._enabled:
            data_bytes = indata.tobytes()
            try:
                self._queue.put_nowait(data_bytes)
            except queue.Full:
                try:
                    self._queue.get_nowait()
                    self._queue.put_nowait(data_bytes)
                except queue.Empty:
                    pass

    def get_chunk(self) -> Optional[bytes]:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self):
        self._enabled = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def is_enabled(self) -> bool:
        return self._enabled

    @property
    def device_id(self) -> Optional[int]:
        return self._device_id
