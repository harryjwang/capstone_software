# PourDecisions — AI Drink Kiosk (Capstone MVP)

Two parts:

- `kiosk-ui/` — React touchscreen kiosk (Vite). Full order flow: ID scan → face verify + mood → drink → amount/strength → confirm → dispense simulation.
- `kiosk-cv/` — Python CV backend (FastAPI + OpenCV). Real face detection (YuNet) + emotion recognition (FER+), exposed at `POST /scan/face`.

The UI calls the backend at `http://localhost:8000` for face scans and **falls back to
simulation automatically** if the backend isn't running — so you can develop either half
independently. ID scanning and face↔ID identity matching are still simulated (next phase).

## Prerequisites

- Python 3.10+ and Node 18+
- A webcam

## 1. Backend setup (one time)

```bash
cd kiosk-cv
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python download_models.py     # fetches yunet.onnx (~230 KB) + emotion-ferplus-8.onnx (~34 MB)
```

## 2. Test CV standalone (do this first)

```bash
python live_test.py
```

A window opens with your webcam. You should see a box around your face and a live
emotion label like `happy (happiness 0.87)`. Make faces at it — smile, frown, look
surprised — and confirm the labels react. Press `q` to quit (this releases the camera).

If detection is flaky: improve lighting, face the camera directly. If the label says the
detector backend is `haar` instead of `yunet`, the model download failed — rerun
`download_models.py`.

## 3. Run the backend server

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Sanity checks:
- `curl http://localhost:8000/health` → `{"ok": true, "detector": "yunet", "emotion_model": true}`
- `curl -X POST http://localhost:8000/scan/face` (look at the camera) → JSON with your emotion

## 4. Run the kiosk UI (one time setup, then dev server)

```bash
cd kiosk-ui
npm install
npm run dev
```

Open http://localhost:5173.

## 5. End-to-end test

1. Tap to Start → Start ID Scan (simulated, always passes as 23yo)
2. **Start Face Scan → look at your webcam.** Result card should say
   "● Live camera result" with your actual detected mood.
   ("○ Simulated result" means the UI couldn't reach the backend.)
3. Pick a drink → pick amount → try "🎭 Match my mood" (uses your real detected emotion)
4. Confirm screen: expand "Dev: MQTT payload" to see exactly what will be sent to the
   dispenser ESP32 (`abv_percent`, `volume_ml`, `abv_source`, etc.)
5. Pour It → watch the simulated dispense + MQTT log

## Gotchas

- **Camera contention**: `live_test.py` and the server can't use the webcam at the same
  time. Quit one before starting the other.
- **CORS**: backend allows all origins for dev; lock it down to the kiosk origin later.
- **Emotion mapping**: FER+ outputs 8 raw emotions; `MOOD_MAP` in `cv_service.py` folds
  them into the 5 kiosk moods, and `EMOTION_MAP` in `kiosk-ui/src/App.jsx` maps moods to
  strength. Keep those two in sync when tuning.

## Next phases

1. ID scanning: PDF417 barcode decode (zxing-cpp) → AAMVA DOB parse
2. Face↔ID matching: SFace embeddings (opencv_zoo) + cosine similarity vs the ID portrait
3. Comms: replace the dispense simulation with a real MQTT publish (paho-mqtt on the Pi,
   PubSubClient on the ESP32); payload schema is already final in the confirm screen
