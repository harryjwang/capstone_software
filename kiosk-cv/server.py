"""
Kiosk CV backend. Run: uvicorn server:app --host 0.0.0.0 --port 8000

Order of operations per customer session:
  POST /session/reset      -> clear stored ID data
  POST /scan/id/barcode    -> read PDF417 on ID back, parse DOB, age-check
  POST /scan/id/portrait   -> capture the portrait on ID front, store embedding
  POST /scan/face          -> live face: match vs ID portrait + emotion
Dev helpers:
  POST /scan/face/upload   -> run analysis on an uploaded image
  GET  /health
"""
import time

import cv2
import numpy as np
from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from camera import open_camera
from cv_service import FaceAnalyzer, analyze_over_frames
from id_service import scan_id_barcode

CAMERA_INDEX = None  # None = auto-detect; pin to an int (e.g. 1 on Mac) if needed
N_FRAMES = 8
FRAME_SKIP = 2
BARCODE_TIMEOUT_S = 8   # keep trying frames until a barcode decodes
PORTRAIT_TIMEOUT_S = 6

app = FastAPI(title="kiosk-cv")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the kiosk origin for the real build
    allow_methods=["*"],
    allow_headers=["*"],
)

analyzer = FaceAnalyzer()

# Single-kiosk session state (one customer at a time)
SESSION = {"id_info": None, "id_embedding": None}


def _camera():
    try:
        return open_camera(preferred=CAMERA_INDEX)
    except SystemExit:
        return None


def grab_frames(n=N_FRAMES, skip=FRAME_SKIP):
    cap = _camera()
    if cap is None:
        return []
    frames, i = [], 0
    while len(frames) < n:
        ok, frame = cap.read()
        if not ok:
            break
        if i % skip == 0:
            frames.append(frame)
        i += 1
        if i > n * skip * 3:
            break
    cap.release()
    return frames


@app.post("/session/reset")
def session_reset():
    SESSION["id_info"] = None
    SESSION["id_embedding"] = None
    return {"ok": True}


@app.post("/scan/id/barcode")
def scan_barcode():
    """Keep reading frames until the PDF417 on the ID back decodes (or timeout)."""
    cap = _camera()
    if cap is None:
        return {"found": False, "error": "camera unavailable"}
    deadline = time.time() + BARCODE_TIMEOUT_S
    info = None
    while time.time() < deadline:
        ok, frame = cap.read()
        if not ok:
            continue
        info = scan_id_barcode(frame)
        if info:
            break
    cap.release()
    if not info:
        return {"found": False, "error": "no readable barcode — hold the back of the ID steady, fill the frame"}
    SESSION["id_info"] = info
    return {"found": True, **info}


@app.post("/scan/id/portrait")
def scan_portrait():
    """Capture the portrait photo on the ID front, store its face embedding."""
    if analyzer.recognizer is None:
        return {"found": False, "error": "sface.onnx missing — run download_models.py"}
    cap = _camera()
    if cap is None:
        return {"found": False, "error": "camera unavailable"}
    deadline = time.time() + PORTRAIT_TIMEOUT_S
    emb = None
    while time.time() < deadline:
        ok, frame = cap.read()
        if not ok:
            continue
        emb = analyzer.get_embedding(frame)
        if emb is not None:
            break
    cap.release()
    if emb is None:
        return {"found": False, "error": "no face found on ID — hold the front closer to the camera"}
    SESSION["id_embedding"] = emb
    return {"found": True}


@app.post("/scan/face")
def scan_face():
    """Live face: emotion (majority vote) + identity match vs stored ID portrait."""
    frames = grab_frames()
    if not frames:
        return {"face_found": False, "error": "camera unavailable"}
    result = analyze_over_frames(analyzer, frames)
    if not result.get("face_found"):
        return result

    # identity match against the ID portrait, if we have one
    if SESSION["id_embedding"] is not None and analyzer.recognizer is not None:
        for f in frames:
            live_emb = analyzer.get_embedding(f)
            if live_emb is not None:
                result.update(analyzer.match_embeddings(
                    SESSION["id_embedding"], live_emb))
                break
        else:
            result.update({"match": None, "error_match": "could not embed live face"})
    else:
        result["match"] = None  # no ID portrait stored — UI falls back to simulated match
    return result


@app.post("/scan/face/upload")
async def scan_face_upload(file: UploadFile):
    data = np.frombuffer(await file.read(), np.uint8)
    frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if frame is None:
        return {"face_found": False, "error": "could not decode image"}
    return analyzer.analyze(frame)


@app.get("/health")
def health():
    return {
        "ok": True,
        "detector": analyzer.backend,
        "emotion_model": analyzer.emotion_net is not None,
        "recognizer": analyzer.recognizer is not None,
        "id_scanned": SESSION["id_info"] is not None,
        "portrait_stored": SESSION["id_embedding"] is not None,
    }
