"""Single camera owner: a background thread keeps the latest frame available
so multiple consumers (scan endpoints + the MJPEG preview stream) can read
concurrently without reopening the device."""
import threading
import time

from camera import open_camera


class CameraManager:
    def __init__(self, preferred=None):
        self.preferred = preferred
        self._cap = None
        self._latest = None
        self._lock = threading.Lock()
        self._thread = None

    def _ensure_running(self):
        if self._thread and self._thread.is_alive():
            return True
        try:
            self._cap = open_camera(preferred=self.preferred)
        except SystemExit:
            return False
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def _loop(self):
        while True:
            ok, frame = self._cap.read()
            if ok:
                with self._lock:
                    self._latest = frame
            else:
                time.sleep(0.05)

    def get_frame(self, timeout=2.0):
        """Latest frame (copy), or None if the camera is unavailable."""
        if not self._ensure_running():
            return None
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                if self._latest is not None:
                    return self._latest.copy()
            time.sleep(0.02)
        return None
