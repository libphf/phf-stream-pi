import os
import sys
import time
import threading
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from base_source import BaseVideoSource

KNOWN_RESOLUTIONS = [
    {"width": 320,  "height": 240,  "tier": "smooth",           "label": "320x240 (Ultra Rápida / Baixa Latência)"},
    {"width": 640,  "height": 480,  "tier": "smooth",           "label": "640x480 (VGA - Padrão Recomendado)"},
    {"width": 800,  "height": 600,  "tier": "moderate",         "label": "800x600 (SVGA)"},
    {"width": 1280, "height": 720,  "tier": "hardware_limited", "label": "1280x720 (720p HD)"},
    {"width": 1920, "height": 1080, "tier": "hardware_limited", "label": "1920x1080 (1080p FHD - Alerta: Alto Uso CPU)"}
]

class PiCameraSource(BaseVideoSource):
    """
    Video capture source for Raspberry Pi.
    Detects and captures from:
      1. CSI Ribbon Cable Cameras (Picamera2 / libcamera) e.g. OV5647, IMX219, IMX477, IMX708
      2. USB Webcams (via Picamera2 UVC or V4L2/OpenCV)
    """

    def __init__(self):
        self._picam2 = None
        self._cap = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._latest_frame: Optional[np.ndarray] = None
        self._latest_ts: float = 0.0
        self._frame_count: int = 0

        self._device_id: Any = 0
        self._device_type: str = "csi"  # "csi" or "usb"
        self._width: int = 640
        self._height: int = 480
        self._fps: int = 30
        self._actual_fps: float = 0.0
        self._cached_devices: Optional[List[Dict[str, Any]]] = None

    def list_devices(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Enumerates all cameras on the Raspberry Pi:
        Checks CSI Ribbon cameras and USB Webcams.
        """
        if self._cached_devices is not None and not force_refresh:
            return self._cached_devices

        devices = []

        # 1. Probe via Picamera2 (Official Raspberry Pi Camera interface)
        try:
            from picamera2 import Picamera2
            picam_info = Picamera2.global_camera_info()
            for cam in picam_info:
                cam_num = cam.get("Num", 0)
                model = cam.get("Model", f"Camera {cam_num}")
                cam_id = cam.get("Id", "")

                # Detect if camera is connected via CSI ribbon cable or USB
                is_csi = any(x in cam_id.lower() for x in ["soc", "csi", "i2c", "unicam"])
                cam_type = "csi" if is_csi else "usb"
                type_prefix = "[CSI Fita]" if is_csi else "[USB]"

                label = f"{type_prefix} {model} (Dispositivo #{cam_num})"

                devices.append({
                    "id": f"picam:{cam_num}",
                    "raw_num": cam_num,
                    "name": label,
                    "model": model,
                    "type": cam_type,
                    "sensor_id": cam_id,
                    "default_resolution": [640, 480],
                    "resolutions": KNOWN_RESOLUTIONS
                })
        except Exception as e:
            print(f"[PiCameraSource] Picamera2 enumeration notice: {e}")

        # 2. Fallback / supplementary probe via V4L2 / OpenCV for USB webcams
        if not devices:
            try:
                import cv2
                for idx in range(4):
                    cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                    if cap.isOpened():
                        devices.append({
                            "id": f"v4l2:{idx}",
                            "raw_num": idx,
                            "name": f"[V4L2/USB] Câmera USB #{idx}",
                            "model": f"Video {idx}",
                            "type": "usb",
                            "default_resolution": [640, 480],
                            "resolutions": KNOWN_RESOLUTIONS
                        })
                        cap.release()
            except Exception as e:
                print(f"[PiCameraSource] OpenCV enumeration notice: {e}")

        if not devices:
            # Add fallback entry if no device discovered yet
            devices.append({
                "id": "picam:0",
                "raw_num": 0,
                "name": "[CSI Fita] Câmera Padrão Raspberry Pi (#0)",
                "model": "Raspberry Pi Camera",
                "type": "csi",
                "default_resolution": [640, 480],
                "resolutions": KNOWN_RESOLUTIONS
            })

        self._cached_devices = devices
        return devices

    def start(self, device_id: Any, width: int = 640, height: int = 480, fps: int = 30) -> Tuple[bool, Optional[str]]:
        self.stop()
        time.sleep(0.3)  # Allow hardware / sensor cleanup

        self._device_id = device_id
        self._width = width
        self._height = height
        self._fps = fps

        dev_str = str(device_id)
        if dev_str.startswith("picam:"):
            cam_num = int(dev_str.split(":")[1])
            use_picam = True
        elif dev_str.startswith("v4l2:"):
            cam_num = int(dev_str.split(":")[1])
            use_picam = False
        else:
            try:
                cam_num = int(device_id)
            except (ValueError, TypeError):
                cam_num = 0
            use_picam = True

        if use_picam:
            success, warning = self._start_picamera2(cam_num, width, height, fps)
            if success:
                return True, warning
            print("[PiCameraSource] Picamera2 falhou para a câmera, tentando V4L2 fallback...")

        return self._start_v4l2(cam_num, width, height, fps)

    def _start_picamera2(self, cam_num: int, width: int, height: int, fps: int) -> Tuple[bool, Optional[str]]:
        try:
            from picamera2 import Picamera2

            # Only apply OV5647 NoIR tuning to the CSI ribbon camera (cam 0)
            tuning = None
            if cam_num == 0:
                for candidate in [
                    "/usr/share/libcamera/ipa/rpi/vc4/ov5647_noir.json",
                    "/usr/share/libcamera/ipa/rpi/vc4/ov5647.json"
                ]:
                    if os.path.exists(candidate):
                        tuning = candidate
                        break

            if tuning:
                self._picam2 = Picamera2(camera_num=cam_num, tuning=tuning)
            else:
                self._picam2 = Picamera2(camera_num=cam_num)

            # Note: For CSI ribbon cameras, BGR888 in memory maps to R-G-B buffer layout.
            # For USB webcams, omit format restriction so libcamera configures standard UVC MJPEG/RGB.
            if cam_num == 0:
                video_config = self._picam2.create_video_configuration(
                    main={"size": (width, height), "format": "BGR888"}
                )
            else:
                video_config = self._picam2.create_video_configuration(
                    main={"size": (width, height)}
                )

            self._picam2.configure(video_config)
            self._picam2.start()

            self._running = True
            self._frame_count = 0
            self._thread = threading.Thread(target=self._picam2_capture_loop, daemon=True)
            self._thread.start()

            warning = None
            if width > 1280:
                warning = f"Aviso: {width}x{height} exige alto consumo de CPU no Raspberry Pi 4. Recomendamos 640x480 para streaming a 30 fps contínuo."

            print(f"[PiCameraSource] Picamera2 iniciada: câmera #{cam_num} ({width}x{height} @ {fps}fps)")
            return True, warning
        except Exception as e:
            print(f"[PiCameraSource] Falha ao iniciar Picamera2: {e}")
            if self._picam2:
                try:
                    self._picam2.close()
                except Exception:
                    pass
                self._picam2 = None
            return False, str(e)

    def _start_v4l2(self, dev_idx: int, width: int, height: int, fps: int) -> Tuple[bool, Optional[str]]:
        try:
            import cv2
            cap = cv2.VideoCapture(dev_idx, cv2.CAP_V4L2)
            if not cap.isOpened():
                return False, f"Falha ao abrir dispositivo V4L2 #{dev_idx}"

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            cap.set(cv2.CAP_PROP_FPS, fps)

            self._cap = cap
            self._running = True
            self._frame_count = 0
            self._thread = threading.Thread(target=self._v4l2_capture_loop, daemon=True)
            self._thread.start()

            print(f"[PiCameraSource] V4L2 iniciado: câmera #{dev_idx} ({width}x{height} @ {fps}fps)")
            return True, None
        except Exception as e:
            print(f"[PiCameraSource] Falha ao iniciar V4L2: {e}")
            return False, str(e)

    def _picam2_capture_loop(self):
        last_calc_time = time.perf_counter()
        calc_frames = 0

        while self._running and self._picam2:
            try:
                frame = self._picam2.capture_array("main")
                if frame is not None and frame.size > 0:
                    # Wall-clock Unix timestamp for browser latency calculation
                    now = time.time()
                    with self._lock:
                        self._latest_frame = frame
                        self._latest_ts = now
                        self._frame_count += 1
                        calc_frames += 1

                    perf_now = time.perf_counter()
                    if perf_now - last_calc_time >= 1.0:
                        self._actual_fps = calc_frames / (perf_now - last_calc_time)
                        calc_frames = 0
                        last_calc_time = perf_now
            except Exception as e:
                if self._running:
                    print(f"[PiCameraSource] Erro no loop de captura Picamera2: {e}")
                time.sleep(0.01)

    def _v4l2_capture_loop(self):
        import cv2
        last_calc_time = time.perf_counter()
        calc_frames = 0

        while self._running and self._cap:
            ret, frame = self._cap.read()
            if ret and frame is not None:
                # Convert BGR (OpenCV) to RGB for PHF
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Wall-clock Unix timestamp for browser latency calculation
                now = time.time()
                with self._lock:
                    self._latest_frame = rgb
                    self._latest_ts = now
                    self._frame_count += 1
                    calc_frames += 1

                perf_now = time.perf_counter()
                if perf_now - last_calc_time >= 1.0:
                    self._actual_fps = calc_frames / (perf_now - last_calc_time)
                    calc_frames = 0
                    last_calc_time = perf_now
            else:
                time.sleep(0.005)

    def read_frame(self) -> Optional[Tuple[float, np.ndarray]]:
        with self._lock:
            if self._latest_frame is None:
                return None
            return (self._latest_ts, self._latest_frame)

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

        if self._picam2:
            try:
                self._picam2.stop()
                self._picam2.close()
            except Exception:
                pass
            self._picam2 = None

        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        with self._lock:
            self._latest_frame = None
            self._latest_ts = 0.0

    def get_info(self) -> Dict[str, Any]:
        return {
            "device_id": self._device_id,
            "width": self._width,
            "height": self._height,
            "fps_target": self._fps,
            "actual_fps": round(self._actual_fps, 1),
            "frame_count": self._frame_count,
            "running": self._running
        }
