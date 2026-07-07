"""Download CV models. Run once: python download_models.py"""
import ssl
import urllib.request
from pathlib import Path

try:  # macOS python.org installs often lack system certs; use certifi's bundle
    import certifi
    CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    CTX = ssl.create_default_context()

MODELS = {
    # YuNet face detector (~230 KB, fast enough for Pi CPU)
    "yunet.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    # FER+ emotion classifier (~34 MB): 64x64 grayscale -> 8 emotion logits
    "emotion-ferplus-8.onnx": "https://media.githubusercontent.com/media/onnx/models/main/validated/vision/body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx",
    # SFace face recognition (~37 MB): 112x112 aligned crop -> 128-d embedding
    "sface.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}

def main():
    out = Path(__file__).parent / "models"
    out.mkdir(exist_ok=True)
    for name, url in MODELS.items():
        dest = out / name
        if dest.exists() and dest.stat().st_size > 10_000:
            print(f"[skip] {name} already present")
            continue
        print(f"[get ] {name} ...")
        with urllib.request.urlopen(url, context=CTX) as r, open(dest, "wb") as f:
            f.write(r.read())
        size = dest.stat().st_size
        assert size > 10_000, f"{name} looks like an LFS pointer ({size} B) — download manually"
        print(f"[ ok ] {name} ({size/1e6:.1f} MB)")

if __name__ == "__main__":
    main()
