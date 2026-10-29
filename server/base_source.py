from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

class BaseVideoSource(ABC):
    """
    Abstract Base Class for video capture sources in the PHF streaming pipeline on Raspberry Pi.
    """

    @abstractmethod
    def list_devices(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Enumerates available video input devices (CSI Ribbon cameras and USB webcams).
        """
        pass

    @abstractmethod
    def start(self, device_id: Any, width: int = 640, height: int = 480, fps: int = 30) -> Tuple[bool, Optional[str]]:
        """
        Starts capture on the given device ID with the requested parameters.
        Returns (success: bool, warning_or_error: Optional[str]).
        """
        pass

    @abstractmethod
    def read_frame(self) -> Optional[Tuple[float, np.ndarray]]:
        """
        Reads the latest captured frame.
        Returns (timestamp_seconds, rgb_uint8_array_HxWx3), or None if no frame is available.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
        Stops the capture source and releases all hardware resources.
        """
        pass

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        """
        Returns runtime status information about the active stream.
        """
        pass
