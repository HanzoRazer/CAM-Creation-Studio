"""Import evidence infrastructure — loss fields, codes, and the summary view.

CS-008 remediation, PR 1. Covers the additive `GeometryDiagnostic` fields, the
fidelity code vocabulary, and `GeometryCollection.report()`.

This module tests the *mechanism* for reporting loss. Whether the importer
actually emits these findings is the subject of `test_geometry_characterization`
and of the two increments that follow.
"""

import pytest

from cam_creation_studio.enums import DiagnosticSeverity
from cam_creation_studio.geometry import diagnostics as diag
from cam_creation_studio.geometry.diagnostics import GeometryDiagnostic
from cam_creation_studio.geometry.models import (
    GeometryCollection,
    ImportMetadata,
    ImportReport,
)
from cam_creation_studio.shared.serialization import from_dict, to_dict


# --------------------------------------------------------------------------- #
# Additive fields
# --------------------------------------------------------------------------- #
def test_existing_diagnostics_are_unchanged_by_the_new_fields():
    # The additive fields must not disturb any existing construction site.
    d = diag.warning(diag.ZERO_RADIUS, "Arc has zero radius.", entity_type="ARC")
    assert d.recoverable is None
    assert d.metadata == {}
    assert d.severity is DiagnosticSeverity.WARNING


def test_loss_helper_requires_recoverability():
    with pytest.raises(TypeError):
        diag.loss(diag.LWPOLYLINE_ELEVATION_DROPPED, "…")  # no recoverable=


def test_loss_helper_records_structured_particulars():
    d = diag.loss(
        diag.RATIONAL_SPLINE_WEIGHTS_DROPPED,
        "Rational spline weights are not represented.",
        recoverable=False,
        metadata={"weight_count": 4, "degree": 3},
        entity_type="SPLINE", handle="2F",
    )
    assert d.recoverable is False
    assert d.metadata == {"weight_count": 4, "degree": 3}
    assert d.handle == "2F"
    assert d.severity is DiagnosticSeverity.WARNING


def test_loss_helper_copies_its_metadata():
    source = {"count": 1}
    d = diag.loss(diag.EMPTY_SPLINE_GEOMETRY, "…", recoverable=True, metadata=source)
    source["count"] = 99
    assert d.metadata == {"count": 1}


def test_loss_severity_can_be_raised():
    d = diag.loss(diag.UNSUPPORTED_ENTITY, "…", recoverable=False,
                  severity=DiagnosticSeverity.DANGER)
    assert d.severity is DiagnosticSeverity.DANGER


def test_as_dict_exposes_the_loss_fields():
    d = diag.loss(diag.POLYLINE_BULGE_IGNORED, "…", recoverable=True,
                  metadata={"segments": 2})
    payload = d.as_dict()
    assert payload["recoverable"] is True
    assert payload["metadata"] == {"segments": 2}
    assert set(payload) == {
        "severity", "code", "message", "entity_type", "handle", "layer",
        "recoverable", "metadata",
    }


def test_as_dict_metadata_is_a_copy():
    d = diag.loss(diag.POLYLINE_BULGE_IGNORED, "…", recoverable=True,
                  metadata={"segments": 2})
    d.as_dict()["metadata"]["segments"] = 99
    assert d.metadata == {"segments": 2}


def test_diagnostic_round_trips_through_the_shared_serializer():
    original = diag.loss(
        diag.FIT_POINT_SPLINE_UNREPRESENTED, "…",
        recoverable=True, metadata={"fit_points": 4, "degree": 3},
        entity_type="SPLINE", handle="30", layer="curves",
    )
    assert from_dict(GeometryDiagnostic, to_dict(original)) == original


# --------------------------------------------------------------------------- #
# Code vocabulary
# --------------------------------------------------------------------------- #
def test_fidelity_codes_are_registered():
    for code in (
        diag.FIT_POINT_SPLINE_UNREPRESENTED,
        diag.RATIONAL_SPLINE_WEIGHTS_DROPPED,
        diag.OCS_TRANSFORM_FAILED,
        diag.LWPOLYLINE_ELEVATION_DROPPED,
        diag.EMPTY_SPLINE_GEOMETRY,
    ):
        assert code in diag.CANONICAL_CODES


def test_codes_are_unique():
    assert len(set(diag.CANONICAL_CODES)) == len(diag.CANONICAL_CODES)


def test_loss_codes_are_a_subset_of_canonical_codes():
    assert diag.LOSS_CODES <= set(diag.CANONICAL_CODES)


def test_successful_ocs_normalization_has_no_code():
    # A transform that succeeds is correct behavior, not a defect. Coding it
    # would train readers to skim past the codes that do matter.
    assert not any("APPLIED" in c for c in diag.CANONICAL_CODES)
    assert diag.OCS_TRANSFORM_FAILED not in diag.LOSS_CODES


def test_is_loss_distinguishes_cost_from_observation():
    assert diag.is_loss(diag.LWPOLYLINE_ELEVATION_DROPPED)
    assert diag.is_loss(diag.UNSUPPORTED_ENTITY)
    assert not diag.is_loss(diag.ZERO_RADIUS)         # geometry arrived intact
    assert not diag.is_loss(diag.UNKNOWN_UNITS)       # an assumption, not a loss
    assert not diag.is_loss(diag.OCS_TRANSFORM_FAILED)  # failure, not fidelity cost


def test_is_loss_property_agrees_with_the_module_function():
    for code in diag.CANONICAL_CODES:
        assert diag.warning(code, "…").is_loss == diag.is_loss(code)


# --------------------------------------------------------------------------- #
# Import summary
# --------------------------------------------------------------------------- #
def _collection(*diagnostics):
    return GeometryCollection(
        entities=[],
        metadata=ImportMetadata(
            source_path="x.dxf", source_units="mm", unit_scale=1.0,
            entity_count=0, raw_entity_count=3, unsupported_entity_count=1),
        diagnostics=list(diagnostics),
    )


def test_report_summarizes_existing_objects():
    report = _collection(
        diag.warning(diag.ZERO_RADIUS, "…"),
        diag.loss(diag.UNSUPPORTED_ENTITY, "…", recoverable=False),
    ).report()
    assert isinstance(report, ImportReport)
    assert report.raw_entity_count == 3
    assert report.unsupported_entity_count == 1
    assert report.diagnostic_count == 2
    assert report.codes == sorted({diag.ZERO_RADIUS, diag.UNSUPPORTED_ENTITY})


def test_report_separates_recoverable_from_unrecoverable_loss():
    report = _collection(
        diag.loss(diag.POLYLINE_BULGE_IGNORED, "…", recoverable=True),
        diag.loss(diag.RATIONAL_SPLINE_WEIGHTS_DROPPED, "…", recoverable=False),
        diag.warning(diag.ZERO_RADIUS, "…"),      # not a loss at all
    ).report()
    assert report.loss_count == 2
    assert report.recoverable_loss_count == 1
    assert report.unrecoverable_loss_count == 1
    assert report.has_loss and report.has_unrecoverable_loss


def test_report_of_a_clean_import_shows_no_loss():
    report = GeometryCollection().report()
    assert report.loss_count == 0
    assert not report.has_loss and not report.has_unrecoverable_loss


def test_report_counts_severities():
    report = _collection(
        diag.info(diag.UNKNOWN_UNITS, "…"),
        diag.warning(diag.ZERO_RADIUS, "…"),
        diag.warning(diag.ZERO_LENGTH_LINE, "…"),
    ).report()
    assert report.counts_by_severity == {"info": 1, "warning": 2}


def test_report_carries_no_duration_or_timestamp():
    # Wall-clock would make two imports of one file compare unequal, for a
    # number that says nothing about fidelity.
    fields = set(to_dict(GeometryCollection().report()))
    assert not any(k in f for f in fields for k in ("duration", "time", "date", "elapsed"))


def test_report_is_recomputed_and_cannot_go_stale():
    collection = _collection(diag.warning(diag.ZERO_RADIUS, "…"))
    assert collection.report() == collection.report()


def test_losses_view_preserves_order():
    a = diag.loss(diag.UNSUPPORTED_ENTITY, "first", recoverable=False)
    b = diag.warning(diag.ZERO_RADIUS, "middle")
    c = diag.loss(diag.POLYLINE_BULGE_IGNORED, "last", recoverable=True)
    assert [d.message for d in _collection(a, b, c).losses] == ["first", "last"]


def test_report_serializes_through_the_shared_serializer():
    payload = _collection(diag.loss(diag.UNSUPPORTED_ENTITY, "…", recoverable=False)).report().as_dict()
    assert payload["loss_count"] == 1
    assert payload["unrecoverable_loss_count"] == 1


def test_collection_round_trip_preserves_loss_evidence():
    collection = _collection(
        diag.loss(diag.RATIONAL_SPLINE_WEIGHTS_DROPPED, "…",
                  recoverable=False, metadata={"weight_count": 4}))
    restored = GeometryCollection.from_dict(collection.to_dict())
    assert restored.diagnostics[0].recoverable is False
    assert restored.diagnostics[0].metadata == {"weight_count": 4}
    assert restored.report() == collection.report()
