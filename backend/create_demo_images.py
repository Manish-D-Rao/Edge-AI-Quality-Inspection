## NOT NEEDED NOW
from pathlib import Path

import cv2
import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPOSITORY_ROOT / "datasets" / "synthetic"
REFERENCE_PATH = OUTPUT / "reference.jpg"
TEST_PATH = OUTPUT / "test.jpg"

if REFERENCE_PATH.exists() or TEST_PATH.exists():
    raise FileExistsError(
        f"Refusing to overwrite existing synthetic images in {OUTPUT}"
    )

OUTPUT.mkdir(parents=True, exist_ok=True)

height, width = 480, 640

# Create a simple synthetic PCB.
board = np.full((height, width, 3), (45, 90, 45), dtype=np.uint8)

# Board outline and traces.
cv2.rectangle(board, (30, 30), (610, 450), (65, 120, 65), 3)

for y in (100, 180, 260, 340):
    cv2.line(board, (70, y), (570, y), (45, 150, 170), 3)

# Component bodies.
for x, y in ((150, 100), (320, 180), (470, 260), (220, 340)):
    cv2.rectangle(board, (x - 35, y - 22), (x + 35, y + 22),
                  (35, 35, 35), -1)
    cv2.rectangle(board, (x - 35, y - 22), (x + 35, y + 22),
                  (180, 180, 180), 2)

# Gold-colored pads.
for x in range(90, 570, 40):
    cv2.rectangle(board, (x, 400), (x + 12, 415),
                  (20, 190, 220), -1)

reference = board.copy()
test = board.copy()

# Artificial visible difference: a bright scratch-like mark.
cv2.line(test, (370, 70), (420, 82), (235, 235, 235), 5)

# Artificial visible difference: a small metallic-looking mark.
cv2.circle(test, (520, 150), 9, (220, 220, 220), -1)

if not cv2.imwrite(str(REFERENCE_PATH), reference):
    raise OSError(f"Could not write synthetic reference image: {REFERENCE_PATH}")
if not cv2.imwrite(str(TEST_PATH), test):
    raise OSError(f"Could not write synthetic test image: {TEST_PATH}")

print(f"Created demo images in: {OUTPUT}")
