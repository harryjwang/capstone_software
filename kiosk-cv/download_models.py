"""Download CV models. Run once: python download_models.py"""
import urllib.request
from pathlib import Path

MODELS = {
    # YuNet face detector (~230 KB, fast enough for Pi CPU)
    "yunet.onnx": "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    # FER+ emotion classifier (~34 MB): 64x64 grayscale -> 8 emotion logits
    "emotion-ferplus-8.onnx": "https://media.githubusercontent.com/media/onnx/models/main/validated/vision/body_analysis/emotion_ferplus/model/emotion-ferplus-8.onnx",
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
        urllib.request.urlretrieve(url, dest)
        size = dest.stat().st_size
        assert size > 10_000, f"{name} looks like an LFS pointer ({size} B) — download manually"
        print(f"[ ok ] {name} ({size/1e6:.1f} MB)")

if __name__ == "__main__":
    main()
