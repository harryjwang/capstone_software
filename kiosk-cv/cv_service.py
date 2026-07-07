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

# Class weights: FER+ over-predicts neutral/happiness (dominant in its training
# data), which drowns out sadness/anger/fear. Downweight them so negative
# emotions can win ties. Tune with live_test.py's on-screen prob readout.
CLASS_WEIGHTS = {
    "neutral": 0.12,   # squashed hard — only wins when nothing else registers at all
    "happiness": 1.6,
    "surprise": 1.8,
    "sadness": 2.4,
    "anger": 2.2,
    "disgust": 2.2,
    "fear": 2.2,
    "contempt": 1.6,
}

# Using FER+ labels directly as kiosk moods (keep EMOTION_MAP in the UI in sync)
MOOD_MAP = {l: l for l in FERPLUS_LABELS}


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

        # SFace recognizer for ID<->live face matching (requires yunet backend
        # because alignCrop needs the 5 facial landmarks yunet provides)
        sface_path = MODELS_DIR / "sface.onnx"
        self.recognizer = (
            cv2.FaceRecognizerSF.create(str(sface_path), "")
            if sface_path.exists() and self.backend == "yunet" else None
        )
        # OpenCV's validated cosine-similarity threshold for SFace
        self.match_threshold = 0.363

    # ── detection ────────────────────────────────────────────────
    def detect_faces_raw(self, frame_bgr):
        """YuNet raw detection rows (needed for SFace alignment). Largest first."""
        if self.backend != "yunet":
            return []
        h, w = frame_bgr.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame_bgr)
        if faces is None:
            return []
        return sorted(faces, key=lambda f: f[2] * f[3], reverse=True)

    def get_embedding(self, frame_bgr):
        """Largest face in frame -> 128-d SFace embedding, or None."""
        if self.recognizer is None:
            return None
        rows = self.detect_faces_raw(frame_bgr)
        if not len(rows):
            return None
        aligned = self.recognizer.alignCrop(frame_bgr, rows[0])
        return self.recognizer.feature(aligned)

    def match_embeddings(self, feat_a, feat_b):
        """Cosine similarity + pass/fail against OpenCV's SFace threshold."""
        score = float(self.recognizer.match(
            feat_a, feat_b, cv2.FaceRecognizerSF_FR_COSINE))
        return {"match": score >= self.match_threshold,
                "match_score": round(score, 3),
                "threshold": self.match_threshold}

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

        # apply class weights, renormalize
        w = np.array([CLASS_WEIGHTS[l] for l in FERPLUS_LABELS])
        probs = probs * w
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
