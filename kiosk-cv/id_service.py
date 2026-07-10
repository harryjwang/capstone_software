"""
ID scanning: decode the PDF417 barcode on the back of a driver's license
and parse the AAMVA fields (DOB, name) for the age check.

Ontario licenses (and all AAMVA-compliant North American IDs) carry a PDF417
barcode. Canadian DOB format is CCYYMMDD; US is MMDDCCYY — both handled.
"""
import re
from datetime import date

import cv2
import zxingcpp

LEGAL_AGE = 19  # Ontario


def decode_pdf417(frame_bgr):
    """Returns raw AAMVA text if a PDF417 barcode is found, else None.

    Tries the raw frame, then grayscale, then 2x upscale — webcam frames of
    dense PDF417 codes are often right at the edge of readability.
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    candidates = [
        frame_bgr,
        gray,
        cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC),
    ]
    for img in candidates:
        results = zxingcpp.read_barcodes(
            img,
            formats=zxingcpp.BarcodeFormat.PDF417,
            try_rotate=True,
            try_downscale=True,
        )
        for r in results:
            if r.text:
                return r.text
    return None


def _parse_dob(raw):
    """AAMVA DBB field: CCYYMMDD (Canada) or MMDDCCYY (US)."""
    if raw[:2] in ("19", "20"):
        y, m, d = int(raw[0:4]), int(raw[4:6]), int(raw[6:8])
    else:
        m, d, y = int(raw[0:2]), int(raw[2:4]), int(raw[4:8])
    return date(y, m, d)


def parse_aamva(text):
    """Lenient AAMVA parse: regex the fields we need out of the raw text."""
    fields = {}
    for code, key in [("DBB", "dob_raw"), ("DCS", "last_name"),
                      ("DAC", "first_name"), ("DAQ", "license_no"),
                      ("DAJ", "region"), ("DCG", "country")]:
        m = re.search(code + r"([^\n\r<]+)", text)
        if m:
            fields[key] = m.group(1).strip()

    if "dob_raw" not in fields or not re.fullmatch(r"\d{8}", fields["dob_raw"]):
        return None

    dob = _parse_dob(fields["dob_raw"])
    today = date.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    first = fields.get("first_name", "")
    last = fields.get("last_name", "")
    return {
        "dob": dob.isoformat(),
        "age": age,
        "of_age": age >= LEGAL_AGE,
        # initials only — no need to hold full PII in the kiosk session
        "name": f"{first[:1]}. {last[:1].upper()}{last[1:].lower()}" if last else "",
        "region": fields.get("region"),
    }


def scan_id_barcode(frame_bgr):
    """One-shot: frame -> parsed ID info, or None if no readable barcode."""
    text = decode_pdf417(frame_bgr)
    if not text:
        return None
    return parse_aamva(text)
