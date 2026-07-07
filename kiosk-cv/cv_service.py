"""
Face detection + emotion recognition for the drink kiosk.

Pipeline:  frame -> YuNet face detect (Haar fallback) -> crop -> FER+ emotion
Output shape matches what the kiosk UI expects from /scan/face.
"""
from pathlib import Path
import cv2
import numpy as np

MODELS_DIR = Path(__file__).parent / "models"

# FER+ output order (fixed by the model)
FERPLUS_LABELS = [
    "neutral", "happiness", "surprise", "sadness",
    "anger", "disgust", "fear", "contempt",
]

# FER+ emotion -> kiosk mood (keep in sync with EMOTION_MAP in the UI)
MOOD_MAP = {
    "happiness": "happy",
    "surprise": "excited",
    "neutral": "neutral",
    "sadness": "tired",
    "anger": "stressed",
    "disgust": "stressed",
    "fear": "stressed",
    "contempt": "neutral",
}


class FaceAnalyzer:
    def __init__(self, det_size=(320, 320), score_thresh=0.7):
        self.det_size = det_size
        yunet_path = MODELS_DIR / "yunet.onnx"
        if yunet_path.exists() and yunet_path.stat().st_size > 10_000:
            self.detector = cv2.FaceDetectorYN.create(
                str(yunet_path), "", det_size, score_thresh, 0.3, 5000
            )
            self.backend = "yunet"
        else:
            # Fallback: Haar cascade ships inside opencv-python, no download
            self.detector = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            self.backend = "haar"

        emo_path = MODELS_DIR / "emotion-ferplus-8.onnx"
        self.emotion_net = (
            cv2.dnn.readNetFromONNX(str(emo_path)) if emo_path.exists() else None
        )

    # ── detection ────────────────────────────────────────────────
    def detect_faces(self, frame_bgr):
        """Returns list of (x, y, w, h, det_conf), largest face first."""
        if self.backend == "yunet":
            h, w = frame_bgr.shape[:2]
            self.detector.setInputSize((w, h))
            _, faces = self.detector.detect(frame_bgr)
            if faces is None:
                return []
            out = [
                (int(f[0]), int(f[1]), int(f[2]), int(f[3]), float(f[14]))
                for f in faces
            ]
        else:
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            rects = self.detector.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
            out = [(int(x), int(y), int(w), int(h), 1.0) for (x, y, w, h) in rects]
        return sorted(out, key=lambda f: f[2] * f[3], reverse=True)

    # ── emotion ──────────────────────────────────────────────────
    def classify_emotion(self, frame_bgr, box):
        """FER+ on a face crop. Returns (mood, raw_emotion, confidence, probs)."""
        if self.emotion_net is None:
            raise RuntimeError("emotion-ferplus-8.onnx missing — run download_models.py")
        x, y, w, h = box[:4]
        # pad crop slightly; FER+ was trained on loose crops
        pad = int(0.1 * max(w, h))
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1 = min(frame_bgr.shape[1], x + w + pad)
        y1 = min(frame_bgr.shape[0], y + h + pad)
        crop = frame_bgr[y0:y1, x0:x1]

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (64, 64))
        blob = gray.astype(np.float32).reshape(1, 1, 64, 64)  # raw 0-255, per FER+ spec

        self.emotion_net.setInput(blob)
        logits = self.emotion_net.forward().flatten()
        probs = np.exp(logits - logits.max())
        probs /= probs.sum()

        idx = int(np.argmax(probs))
        raw = FERPLUS_LABELS[idx]
        return MOOD_MAP[raw], raw, float(probs[idx]), {
            l: round(float(p), 3) for l, p in zip(FERPLUS_LABELS, probs)
        }

    # ── one-shot analysis (what the API endpoint calls) ──────────
    def analyze(self, frame_bgr):
        faces = self.detect_faces(frame_bgr)
        if not faces:
            return {"face_found": False}
        box = faces[0]
        if self.emotion_net is None:
            return {
                "face_found": True, "n_faces": len(faces),
                "box": {"x": box[0], "y": box[1], "w": box[2], "h": box[3]},
                "det_confidence": round(box[4], 3),
                "emotion": None, "error": "emotion model missing — run download_models.py",
                "detector": self.backend,
            }
        mood, raw, conf, probs = self.classify_emotion(frame_bgr, box)
        return {
            "face_found": True,
            "n_faces": len(faces),
            "box": {"x": box[0], "y": box[1], "w": box[2], "h": box[3]},
            "det_confidence": round(box[4], 3),
            "emotion": mood,               # kiosk mood category
            "emotion_raw": raw,            # FER+ label
            "confidence": round(conf, 3),
            "probs": probs,
            "detector": self.backend,
        }


def analyze_over_frames(analyzer, frames):
    """Majority-vote emotion over several frames — much more stable than one shot."""
    votes, results = {}, []
    for f in frames:
        r = analyzer.analyze(f)
        if r.get("face_found"):
            results.append(r)
            votes[r["emotion"]] = votes.get(r["emotion"], 0) + r["confidence"]
    if not results:
        return {"face_found": False}
    winner = max(votes, key=votes.get)
    best = max(
        (r for r in results if r["emotion"] == winner),
        key=lambda r: r["confidence"],
    )
    best["frames_used"] = len(results)
    return best
