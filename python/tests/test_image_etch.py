from cam_creation_studio.image.field import DarknessField, fit_rect
from cam_creation_studio.image.raster_etch import raster_etch
from cam_creation_studio.image.outline_etch import outline_etch


def solid(value, w=12, h=12):
    return DarknessField.from_rows([[value] * w for _ in range(h)])


def gradient(w=20, h=20):
    # Darkness increases left -> right from 0 to ~1.
    return DarknessField.from_rows([[x / (w - 1) for x in range(w)] for _ in range(h)])


def test_white_image_no_segments():  # Test 11
    assert raster_etch(solid(0.0), 100, 100, line_spacing=2, threshold=0.55) == []


def test_black_image_produces_segments():  # Test 12
    segs = raster_etch(solid(1.0), 100, 100, line_spacing=5, threshold=0.55)
    assert len(segs) > 0
    assert all("poly" in s and len(s["poly"]) == 2 for s in segs)


def test_higher_threshold_reduces_paths():  # Test 13
    field = gradient()
    low = raster_etch(field, 100, 100, line_spacing=5, threshold=0.3)
    high = raster_etch(field, 100, 100, line_spacing=5, threshold=0.8)
    total_low = sum(abs(s["poly"][1]["x"] - s["poly"][0]["x"]) for s in low)
    total_high = sum(abs(s["poly"][1]["x"] - s["poly"][0]["x"]) for s in high)
    assert total_high < total_low


def test_outline_finds_contours_on_block():
    rows = [[0.0] * 12 for _ in range(12)]
    for y in range(3, 9):
        for x in range(3, 9):
            rows[y][x] = 1.0
    field = DarknessField.from_rows(rows)
    polys = outline_etch(field, 100, 100, threshold=0.5)
    assert len(polys) >= 1
    assert all(len(p["poly"]) >= 2 for p in polys)


def test_outline_empty_on_blank():
    assert outline_etch(solid(0.0), 100, 100, threshold=0.5) == []


def test_fit_rect_centers_square_in_square():
    fr = fit_rect(solid(1.0, 10, 10), 100, 100)
    assert fr.draw_w == 100 and fr.draw_h == 100
    assert fr.off_x == 0 and fr.off_y == 0
