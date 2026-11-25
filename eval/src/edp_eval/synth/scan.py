"""Scan copies of a synthetic vector-PDF set, for the scan path of the parser (plan Phase 2).

Each PDF page is rendered to a grey image at ``dpi`` and degraded like a scan: rotated by a
random angle within ``max_skew_deg``, blurred, and given grain noise. These are test-data
choices, not plan values. The labels are copied unchanged; a ``.scanmap.json`` sidecar gives,
per truth dimension handle, where its text ends up in the image: ``[x, y, text height]`` in
pixels with the origin at the bottom-left (the parser's scan locator convention).
"""

import json
import random
import shutil
from pathlib import Path

import cv2
import numpy as np
import pypdfium2 as pdfium

from edp_eval.synth.labels import SyntheticLabel

BLUR_KERNEL = 3
NOISE_SIGMA = 6.0


def write_scan_set(src: Path, out: Path, dpi: float, max_skew_deg: float, seed: int) -> list[str]:
    """Write ``<id>.png``, ``<id>.labels.json`` and ``<id>.scanmap.json`` for every PDF in ``src``."""
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    done = []
    for label_path in sorted(src.glob("*.labels.json")):
        label = SyntheticLabel.model_validate_json(label_path.read_text(encoding="utf-8"))
        pdf_path = src / f"{label.id}.pdf"
        mapping = json.loads(pdf_path.with_suffix(".pdfmap.json").read_text(encoding="utf-8"))
        s = dpi / 72
        doc = pdfium.PdfDocument(pdf_path.read_bytes())
        try:
            page = doc[0]
            h_pt = page.get_height()
            gray = page.render(scale=s, grayscale=True).to_numpy()
        finally:
            doc.close()
        gray = gray if gray.ndim == 2 else gray[..., 0]
        h, w = gray.shape
        angle = rng.uniform(-max_skew_deg, max_skew_deg)
        rot = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        img = cv2.warpAffine(gray, rot, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)
        img = cv2.GaussianBlur(img, (BLUR_KERNEL, BLUR_KERNEL), 0)
        noise = np.random.default_rng(rng.randrange(2**32)).normal(0, NOISE_SIGMA, img.shape)
        img = np.clip(img.astype(np.float64) + noise, 0, 255).astype(np.uint8)
        cv2.imwrite(str(out / f"{label.id}.png"), img)

        ppu = mapping["pt_per_unit"]
        ox, oy = mapping["offset_pt"]
        placed = {}
        for handle, (x, y, th) in mapping["dimension_text"].items():
            px, py_down = (x * ppu + ox) * s, (h_pt - (y * ppu + oy)) * s
            rx, ry = rot @ np.array([px, py_down, 1.0])
            placed[handle] = [float(rx), float(h - ry), th * ppu * s]
        (out / f"{label.id}.scanmap.json").write_text(
            json.dumps(
                {"dpi": dpi, "skew_deg": angle, "size_px": [w, h], "dimension_text": placed}, indent=1
            ),
            encoding="utf-8",
        )
        shutil.copyfile(label_path, out / label_path.name)
        done.append(label.id)
    return done
