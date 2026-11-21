"""One-shot digitizer for Fan et al. Fig 4A model curves (dashed lines)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

IMG = Path(
    r"C:\Users\alexi\.cursor\projects\c-Users-alexi-MEGADocuments-Projets-RIMAG"
    r"\assets\image-00c7fd58-1c4a-437c-ae7d-598b7b4ed299.png"
)

# Plot frame in image pixels (estimated from axes box).
# Image is 1024 x 886; y grows downward.
X0, X1 = 118, 980  # 900 → 1600 °C
Y0, Y1 = 70, 780  # 50% → 5%


def temp_of(x: float) -> float:
    return 900 + (x - X0) / (X1 - X0) * 700


def eff_of(y: float) -> float:
    return 50 - (y - Y0) / (Y1 - Y0) * 45


def main() -> None:
    arr = np.asarray(Image.open(IMG).convert("RGB"), dtype=np.float32)
    h, w, _ = arr.shape
    print("size", w, h)

    # Color masks for dashed model strokes (not solid markers).
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    orange = (r > 180) & (g > 80) & (g < 170) & (b < 100) & (r > g + 40)
    purple = (r > 100) & (b > 140) & (g < 140) & (b > g + 20) & (r > 80)
    green = (g > 140) & (r < 140) & (b < 140) & (g > r + 30) & (g > b + 20)

    temps = np.arange(900, 1601, 25)
    for name, mask in (("0.90eV", orange), ("0.74eV", purple), ("1.1eV", green)):
        pts = []
        for T in temps:
            x = int(round(X0 + (T - 900) / 700 * (X1 - X0)))
            col = mask[:, x] if 0 <= x < w else None
            if col is None or not col.any():
                # search nearby columns
                found = False
                for dx in range(1, 8):
                    for xx in (x - dx, x + dx):
                        if 0 <= xx < w and mask[:, xx].any():
                            col = mask[:, xx]
                            x = xx
                            found = True
                            break
                    if found:
                        break
                if not found:
                    continue
            ys = np.where(col)[0]
            ys = ys[(ys >= Y0) & (ys <= Y1)]
            if len(ys) == 0:
                continue
            # Prefer the densest cluster (dashed stroke), take median y.
            y = float(np.median(ys))
            pts.append((T, round(eff_of(y), 2)))
        print(name, pts)


if __name__ == "__main__":
    main()
