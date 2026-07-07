"""Live barcode scan debugger: shows the camera feed and decode attempts.

Usage: python barcode_test.py [camera_index]
Green banner = decoded. Watch the preview to judge focus/size/glare. q to quit.
"""
import sys
import time

import cv2
from camera import open_camera
from id_service import decode_pdf417, parse_aamva

idx = int(sys.argv[1]) if len(sys.argv) > 1 else None
cap = open_camera(preferred=idx)

last_hit, last_info = 0, None
while True:
    ok, frame = cap.read()
    if not ok:
        time.sleep(0.05)
        continue
    text = decode_pdf417(frame)
    if text:
        last_hit = time.time()
        last_info = parse_aamva(text)
        print("DECODED:", last_info if last_info else text[:80])
    if time.time() - last_hit < 2 and last_info:
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 46), (60, 170, 60), -1)
        cv2.putText(frame, f"DECODED age={last_info['age']} of_age={last_info['of_age']}",
                    (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    else:
        cv2.putText(frame, "searching for PDF417...", (12, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 60, 230), 2)
    cv2.imshow("barcode debug", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cap.release()
cv2.destroyAllWindows()