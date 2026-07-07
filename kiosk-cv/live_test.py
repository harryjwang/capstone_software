"""Live webcam demo: draws face box + emotion overlay. Run: python live_test.py (q to quit)"""
import cv2
from cv_service import FaceAnalyzer

analyzer = FaceAnalyzer()
print(f"detector backend: {analyzer.backend}")

cap = cv2.VideoCapture(0)
while True:
    ok, frame = cap.read()
    if not ok:
        break
    r = analyzer.analyze(frame)
    if r.get("face_found"):
        b = r["box"]
        cv2.rectangle(frame, (b["x"], b["y"]), (b["x"] + b["w"], b["y"] + b["h"]),
                      (61, 163, 232), 2)
        label = f'{r["emotion"]} ({r["emotion_raw"]} {r["confidence"]:.2f})'
        cv2.putText(frame, label, (b["x"], b["y"] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (61, 163, 232), 2)
    cv2.imshow("kiosk-cv live", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break
cap.release()
cv2.destroyAllWindows()
