"""Generate a test AAMVA PDF417 barcode PNG. Display it on your phone or print it
to test /scan/id/barcode without using a real license.

Usage: python make_test_id.py [age]      (default 23; try 17 to test the underage path)
"""
import sys
from datetime import date

import cv2
import numpy as np
import zxingcpp

age = int(sys.argv[1]) if len(sys.argv) > 1 else 23
today = date.today()
dob = date(today.year - age, today.month, max(1, today.day - 1))

payload = (
    "@\n\x1e\rANSI 636012080002DL00410278ZO03190024DL"
    "DAQT1234-56789-01234\n"
    "DCSTESTER\nDACKIOSK\n"
    f"DBB{dob.strftime('%Y%m%d')}\n"
    "DBC1\nDCGCAN\nDAJON\n"
)

img = np.array(zxingcpp.write_barcode(zxingcpp.BarcodeFormat.PDF417, payload, width=1000, height=320))
img = cv2.copyMakeBorder(img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
cv2.imwrite("test_id_barcode.png", img)
print(f"wrote test_id_barcode.png (DOB {dob}, age {age}, of_age={age >= 19})")
