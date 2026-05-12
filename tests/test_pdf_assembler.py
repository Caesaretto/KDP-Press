"""pdf_assembler.assemble_pdf produces a multi-page PDF with correct dimensions."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from pdf_assembler import KDP_W, KDP_H, OUTPUT_DPI, assemble_pdf, qc_report, TARGET_PAGES


def _synthetic_page(tmp: Path, idx: int, color: tuple = (255, 255, 255)) -> Path:
    """Write a 2550×3300 RGB PNG and return its path."""
    img = Image.new("RGB", (KDP_W, KDP_H), color)
    p = tmp / f"page_{idx:03d}.png"
    img.save(p, dpi=(OUTPUT_DPI, OUTPUT_DPI))
    return p


def test_assemble_pdf_yields_correct_page_count(tmp_path):
    pages = [_synthetic_page(tmp_path, i) for i in range(5)]
    out = tmp_path / "out.pdf"
    assemble_pdf(pages, out)
    assert out.exists()
    with Image.open(out) as pdf_img:
        # PIL's PDF reader exposes n_frames for multi-page PDFs
        assert getattr(pdf_img, "n_frames", 1) == 5
        assert pdf_img.size == (KDP_W, KDP_H)


def test_qc_report_flags_page_count_mismatch(tmp_path):
    pages = [_synthetic_page(tmp_path, i) for i in range(3)]
    report = qc_report(pages, target=5)
    assert report["actual"] == 3
    assert report["target"] == 5
    assert report["ok"] is False


def test_qc_report_passes_at_target(tmp_path):
    pages = [_synthetic_page(tmp_path, i) for i in range(2)]
    report = qc_report(pages, target=2)
    assert report["ok"] is True
    assert report["issues"] == []


def test_target_pages_is_65():
    """Masterplan §0 invariant: 3 front + 30×2 + 2 back = 65."""
    assert TARGET_PAGES == 65


def test_qc_flags_wrong_size_pages(tmp_path):
    bad = tmp_path / "bad.png"
    Image.new("RGB", (1000, 1000), (255, 255, 255)).save(bad)
    report = qc_report([bad], target=1)
    assert any("size" in issue for issue in report["issues"])
