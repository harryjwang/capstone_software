"""Shared camera helper: opens the first camera that produces real (non-black) frames.

On macOS, Continuity Camera (iPhone) often occupies index 0 and returns black
frames when the phone isn't active, while the built-in webcam sits at index 1.
"""
import time
import cv2

BACKEND = cv2.CAP_AVFOUNDATION if hasattr(cv2, "CAP_AVFOUNDATION") else cv2.CAP_ANY


def open_camera(preferred=None, indices=(0, 1, 2), warmup_s=0.5, min_brightness=5.0):
    order = [preferred] + [i for i in indices if i != preferred] if preferred is not None else list(indices)
    for idx in order:
        cap = cv2.VideoCapture(idx, BACKEND)
        if not cap.isOpened():
            cap.release()
            continue
        time.sleep(warmup_s)
        frame = None
        for _ in range(10):
            ok, frame = cap.read()
            time.sleep(0.03)
        if frame is not None and frame.mean() > min_brightness:
            print(f"[camera] using index {idx} (brightness {frame.mean():.0f})")
            return cap
        cap.release()
    raise SystemExit("No working camera found — check macOS camera permissions for your terminal app")
