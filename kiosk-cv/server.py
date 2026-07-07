"""
Kiosk CV backend. Run: uvicorn server:app --host 0.0.0.0 --port 8000

Endpoints:
  POST /scan/face          -> grabs frames from the camera, returns mood result
  POST /scan/face/upload   -> same but on an uploaded image (dev/testing)
"""
import time

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from cv_service import FaceAnalyzer, analyze_over_frames

CAMERA_INDEX = 1  # None = auto-detect first working camera; set an int to pin it
N_FRAMES = 8          # frames to majority-vote over
FRAME_SKIP = 2        # sample every Nth frame

app = FastAPI(title="kiosk-cv")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the kiosk origin for the real build
    allow_methods=["*"],
    allow_headers=["*"],
)

analyzer = FaceAnalyzer()


def grab_frames(n=N_FRAMES, skip=FRAME_SKIP):
    from camera import open_camera
    try:
        cap = open_camera(preferred=CAMERA_INDEX)
    except SystemExit:
        return []
    frames, i = [], 0
    while len(frames) < n:
        ok, frame = cap.read()
        if not ok:
            break
        if i % skip == 0:
            frames.append(frame)
        i += 1
        if i > n * skip * 3:  # safety bail
            break
    cap.release()
    return frames


@app.post("/scan/face")
def scan_face():
    frames = grab_frames()
    if not frames:
        return {"face_found": False, "error": "camera unavailable"}
    return analyze_over_frames(analyzer, frames)


@app.post("/scan/face/upload")
async def scan_face_upload(file: UploadFile):
    data = np.frombuffer(await file.read(), np.uint8)
    frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if frame is None:
        return {"face_found": False, "error": "could not decode image"}
    return analyzer.analyze(frame)


@app.get("/health")
def health():
    return {"ok": True, "detector": analyzer.backend,
            "emotion_model": analyzer.emotion_net is not None}