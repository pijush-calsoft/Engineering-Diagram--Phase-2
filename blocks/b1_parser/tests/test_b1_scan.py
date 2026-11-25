"""Scan path with a fake model backend: no network, no key, no cost."""

import io
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pypdfium2 as pdfium
import pytest

from edp_b1_parser import DrawingParser, scan
from edp_contracts import BlockRequest
from edp_fabric import FabricStore
from edp_gateway import Gateway, GatewayConfig
from edp_gateway.backend import Reply

W, H = 1000, 600


def page_image(angle: float = 0.0) -> np.ndarray:
    img = np.full((H, W), 255, np.uint8)
    cv2.rectangle(img, (50, 50), (950, 550), 0, 3)
    cv2.line(img, (100, 300), (900, 300), 0, 2)
    rot = cv2.getRotationMatrix2D((W / 2, H / 2), angle, 1.0)
    return cv2.warpAffine(img, rot, (W, H), borderValue=255)


def field(value: str | None, box: list[float] | None = None, confidence: float = 0.9) -> dict[str, Any]:
    return {
        "value": value,
        "box": dict(zip(("x0", "y0", "x1", "y1"), box, strict=True)) if box else None,
        "confidence": confidence,
    }


READING = {
    "title_block": {
        "part_number": field("EDP-1", [0.7, 0.9, 0.8, 0.95]),
        "revision": field("B", [0.85, 0.9, 0.9, 0.95]),
        "material": field("S355", [0.7, 0.85, 0.8, 0.88]),
        "scale": field("1:1", [0.7, 0.8, 0.75, 0.83]),
        "units": field("mm", [0.8, 0.8, 0.85, 0.83]),
        "tolerances": field(None),
    },
    "dimensions": [
        {
            "text": "120",
            "value": 120,
            "kind": "linear",
            "box": {"x0": 0.4, "y0": 0.1, "x1": 0.5, "y1": 0.15},
            "confidence": 0.95,
        },
        {
            "text": "Ø6.5",
            "value": 65,
            "kind": "diameter",
            "box": {"x0": 0.2, "y0": 0.4, "x1": 0.25, "y1": 0.45},
            "confidence": 0.6,
        },
        {
            "text": "R10",
            "value": 10,
            "kind": "radius",
            "box": {"x0": 0.6, "y0": 0.5, "x1": 0.5, "y1": 0.55},
            "confidence": 0.8,
        },
    ],
    "notes": [
        {"text": "BREAK ALL EDGES", "box": {"x0": 0.1, "y0": 0.8, "x1": 0.3, "y1": 0.85}, "confidence": 0.9}
    ],
    "units": "mm",
}


class FakeVision:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete(self, model: str, messages: list[dict[str, Any]], **options: Any) -> Reply:
        self.calls.append({"model": model, "messages": messages})
        return Reply(json.dumps(READING), model, 4000, 1500, 0.07, "test")

    def embed(self, model: str, texts: list[str], **options: Any) -> Any:
        raise NotImplementedError


def gateway(tmp_path: Path) -> tuple[Gateway, FakeVision]:
    fake = FakeVision()
    cfg = GatewayConfig(
        api_key="k",
        provider="openai",
        models={"vision": "vision-model"},
        embedding_model=None,
        budget_usd=None,
        redact_terms=(),
        timeout_s=None,
        max_retries=None,
        data_dir=tmp_path,
    )
    return Gateway(cfg, backend=fake), fake


def png(img: np.ndarray) -> bytes:
    return cv2.imencode(".png", img)[1].tobytes()


def test_skew_angle_finds_the_rotation():
    assert scan.skew_angle(page_image(0)) == pytest.approx(0, abs=0.1)
    assert scan.skew_angle(page_image(2.0)) == pytest.approx(2.0, abs=0.2)
    assert scan.skew_angle(page_image(-1.5)) == pytest.approx(-1.5, abs=0.2)


def test_scan_reading_becomes_geometry_with_locators(tmp_path):
    gw, fake = gateway(tmp_path)
    geo, flags, metrics = scan.parse(png(page_image()), "image", "f1", "v1", gw, "synthetic", "r1")
    assert fake.calls[0]["model"] == "openai/vision-model"
    image_part = fake.calls[0]["messages"][1]["content"][0]
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")
    assert geo.units == "mm" and geo.scale == "1:1" and geo.views == ["page-1"]
    assert geo.title_block and geo.title_block.part_number.value == "EDP-1"
    assert geo.title_block.tolerances is None  # not shown: left empty, never guessed
    dims = [e for e in geo.entities if e.kind == "dimension"]
    assert [d.locator.handle for d in dims] == ["p1/dim-1", "p1/dim-2", "p1/dim-3"]
    # Box (fractions, top-left origin) -> pixels, bottom-left origin: 0.4..0.5 x, 0.1..0.15 y.
    assert dims[0].locator.bbox == pytest.approx((400, H - 90, 500, H - 60), abs=1e-6)
    assert dims[0].data["text_at"] == pytest.approx([450, H - 75]) and dims[0].data["value"] == 120
    codes = [(f.code, f.target.handle if f.target else None) for f in flags]
    assert ("DIM_TEXT_MISMATCH", "p1/dim-2") in codes  # 65 is not a number in "Ø6.5"
    assert ("LOW_CONFIDENCE", "p1/dim-3") in codes  # x1 < x0: no valid position
    assert dims[2].locator.bbox is None
    assert ("UNCALIBRATED_CONFIDENCE", None) in codes
    assert [e.data["text"] for e in geo.entities if e.kind == "text"] == ["BREAK ALL EDGES"]
    assert metrics["cost_usd"] == 0.07 and metrics["pages"][0]["size_px"] == [W, H]


def test_deskewed_boxes_map_back_to_the_original_image(tmp_path):
    gw, _ = gateway(tmp_path)
    geo, flags, _ = scan.parse(png(page_image(2.0)), "image", "f1", "v1", gw, "synthetic")
    assert any(f.code == "SCAN_DESKEWED" for f in flags)
    b = geo.entities[0].locator.bbox
    assert b is not None and (b[2] - b[0]) > 100  # the rotated box still covers the text area


def scanned_pdf(img: np.ndarray) -> bytes:
    doc = pdfium.PdfDocument.new()
    page = doc.new_page(W * 72 / 150, H * 72 / 150)
    image = pdfium.PdfImage.new(doc)
    image.load_jpeg(io.BytesIO(cv2.imencode(".jpg", img)[1].tobytes()), pages=[page])
    image.set_matrix(pdfium.PdfMatrix().scale(page.get_width(), page.get_height()))
    page.insert_obj(image)
    page.gen_content()
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_scanned_pdf_pages_are_read_at_their_own_resolution(tmp_path):
    imgs = scan.pages(scanned_pdf(page_image()), "pdf")
    assert len(imgs) == 1 and imgs[0].shape == (H, W)


def run_block(tmp_path: Path, data: bytes, filename: str, data_class: str):
    fabric = FabricStore(tmp_path / "fabric")
    up = fabric.ingest(filename, data, uploader="t")
    gw, fake = gateway(tmp_path)
    parser = DrawingParser(store=fabric, gateway=gw)
    res = parser.run(BlockRequest(run_id="r1", inputs=[up.as_artifact()], params={"data_class": data_class}))
    return res, fake


def test_block_reads_synthetic_scans_and_refuses_client_scans(tmp_path):
    res, fake = run_block(tmp_path, png(page_image()), "sheet.png", "synthetic")
    assert res.outputs and res.outputs[0].kind == "geometry" and len(fake.calls) == 1
    res, fake = run_block(tmp_path / "client", png(page_image()), "sheet.png", "client")
    assert res.status == "failed" and not res.outputs and fake.calls == []
    (flag,) = [f for f in res.flags if f.code == "SCAN_NOT_READ"]
    assert flag.severity == "block" and "masking" in flag.message


def test_block_sends_scanned_pdfs_to_the_scan_path(tmp_path):
    res, fake = run_block(tmp_path, scanned_pdf(page_image()), "scan.pdf", "synthetic")
    assert res.outputs and len(fake.calls) == 1
    assert not any(f.code == "SCANNED_PDF" for f in res.flags)
