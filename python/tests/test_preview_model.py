from cam_creation_studio.preview.toolpath_model import (
    model_from_moves,
    model_from_etch_paths,
    bounds,
    TRAVEL,
    CUT,
    BURN,
)


def test_g0_is_travel():  # Test 14a
    segs = model_from_moves([{"type": "G0", "x": "10", "y": "0"}])
    assert segs[0].type == TRAVEL


def test_g1_negative_z_is_cut():  # Test 14b
    segs = model_from_moves([{"type": "G1", "x": "10", "z": "-0.5", "f": "300"}])
    assert segs[0].type == CUT
    assert segs[0].to.z == -0.5
    assert segs[0].feed == 300


def test_laser_mode_is_burn():  # Test 14c
    segs = model_from_moves([{"type": "G1", "x": "10", "f": "600"}], laser=True)
    assert segs[0].type == BURN


def test_modal_feed_carries_forward():
    segs = model_from_moves([
        {"type": "G1", "x": "10", "f": "800"},
        {"type": "G1", "x": "20"},
    ])
    assert segs[0].feed == 800 and segs[1].feed == 800


def test_arc_is_flattened():
    segs = model_from_moves([{"type": "G2", "x": "0", "y": "0", "i": "5", "j": "0"}])
    assert len(segs) > 1
    assert all(s.type == CUT for s in segs)


def test_etch_paths_travel_between_burns():
    paths = [
        {"poly": [{"x": 0, "y": 0}, {"x": 10, "y": 0}]},
        {"poly": [{"x": 0, "y": 5}, {"x": 10, "y": 5}]},
    ]
    segs = model_from_etch_paths(paths, control="power", feed=600)
    types = [s.type for s in segs]
    assert BURN in types and TRAVEL in types


def test_bounds():
    segs = model_from_moves([{"type": "G0", "x": "10", "y": "20"}])
    assert bounds(segs) == (0.0, 0.0, 10.0, 20.0)
