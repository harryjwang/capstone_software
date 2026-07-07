"""Live webcam demo: draws face box + emotion overlay. Run: python live_test.py (q to quit)"""
import sys
import time

import cv2
from cv_service import FaceAnalyzer

analyzer = FaceAnalyzer()
print(f"detector backend: {analyzer.backend}")

from camera import open_camera
# usage: python live_test.py [camera_index]  e.g. `python live_test.py 1`
idx = int(sys.argv[1]) if len(sys.argv) > 1 else None
cap = open_camera(preferred=idx)

fails = 0
while True:
    ok, frame = cap.read()
    if not ok:
        fails += 1
        if fails > 30:
            raise SystemExit("Camera opened but no frames arrived — check macOS camera permission")
        time.sleep(0.1)
        continue
    fails = 0
    r = analyzer.analyze(frame)
    if r.get("face_found"):
        b = r["box"]
        cv2.rectangle(frame, (b["x"], b["y"]), (b["x"] + b["w"], b["y"] + b["h"]),
                      (61, 163, 232), 2)
        label = f'{r["emotion"]} ({r["emotion_raw"]} {r["confidence"]:.2f})'
        cv2.putText(frame, label, (b["x"], b["y"] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (61, 163, 232), 2)
        top3 = sorted(r["probs"].items(), key=lambda kv: -kv[1])[:3]
        for j, (name, p) in enumerate(top3):
            cv2.putText(frame, f"{name}: {p:.2f}", (10, 30 + j * 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120, 220, 120), 2)
    cv2.imshow("kiosk-cv live", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cap.release()
cv2.destroyAllWindows()
