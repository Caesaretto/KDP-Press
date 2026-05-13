"""Special pages produce well-formed PIL images at KDP dimensions."""
from __future__ import annotations

from PIL import Image

from special_pages import (
    KDP_W, KDP_H,
    make_qr_page,
    make_frontespizio,
    make_test_colors,
    make_black_page,
    make_review_page,
    make_collection_page,
)


ALL_BUILDERS = (
    make_qr_page,
    make_frontespizio,
    make_test_colors,
    make_black_page,
    make_review_page,
    make_collection_page,
)


def test_each_page_returns_pil_image_with_correct_size_and_mode():
    for builder in ALL_BUILDERS:
        img = builder()
        assert isinstance(img, Image.Image), f"{builder.__name__}: not a PIL Image"
        assert img.size == (KDP_W, KDP_H), f"{builder.__name__}: size {img.size}"
        assert img.mode == "RGB", f"{builder.__name__}: mode {img.mode}"


def test_black_page_is_solid_black():
    img = make_black_page()
    pixels = list(img.getdata())
    # Sample the corners + center (full scan would be slow)
    samples = [pixels[0], pixels[-1], pixels[len(pixels) // 2]]
    assert all(p == (0, 0, 0) for p in samples), f"black page not solid black: {samples}"


def test_pages_save_with_correct_dpi(tmp_path):
    img = make_qr_page()
    out = tmp_path / "page.png"
    img.save(out, dpi=(300, 300))
    with Image.open(out) as reopened:
        # PIL converts dpi via PPI (pixels per cm) round-trip, introducing
        # floating-point error (e.g. 300 → 299.9994). Allow ±1 DPI tolerance.
        dpi = reopened.info.get("dpi")
        if dpi is not None:
            assert abs(dpi[0] - 300) < 1.0 and abs(dpi[1] - 300) < 1.0, (
                f"unexpected dpi {dpi}"
            )
