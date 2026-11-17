from __future__ import annotations

import pytest

from app.services.annotation_schema import AnnotationRegion


@pytest.fixture
def v():
    return {"label": "defect", "x": 367, "y": 67, "width": 57, "height": 21,
           "area": 1197, "status": "scratch", "image_id": "real_pcb_v1_ref",
           "annotator_id": "annotator_01", "creation_timestamp": "2025-01-15T10:30:45Z"}


class Test:
    def test_v_passes(self, v):
        r = AnnotationRegion.from_dict(v)
        assert r.label == "defect" and r.x == 367 and r.y == 67

    def test_f_raises(self):
        data = {"label": "invalid", "x": 0, "y": 0, "width": 10, "height": 10,
                "area": 100, "status": "test", "image_id": "test_ref",
                "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"}
        import pytest as pt
        with pt.raises(Exception):
            AnnotationRegion.from_dict(data)

    def test_n_passes(self):
        r = AnnotationRegion.from_dict({"label": "normal", "x": 0, "y": 0, "width": 10, "height": 10, "area": 100, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})
        assert r.label == "normal"

    def test_c_passes(self):
        r = AnnotationRegion.from_dict({"label": "defect", "x": 0, "y": 0, "width": 10, "height": 10, "area": 100, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})
        assert r.label == "defect"

    def test_y_passes(self):
        r = AnnotationRegion.from_dict({"label": "uncertain", "x": 0, "y": 0, "width": 10, "height": 10, "area": 100, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})
        assert r.label == "uncertain"


class Test2:
    def test_nx_raises(self):
        with pytest.raises(Exception):
            AnnotationRegion.from_dict({"label": "normal", "x": -5, "y": 0, "width": 10, "height": 10, "area": 100, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})

    def test_ny_raises(self):
        with pytest.raises(Exception):
            AnnotationRegion.from_dict({"label": "normal", "x": 0, "y": -3, "width": 10, "height": 10, "area": 100, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})

    def test_x0_passes(self):
        r = AnnotationRegion.from_dict({"label": "normal", "x": 0, "y": 0, "width": 10, "height": 10, "area": 100, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})
        assert r.x == 0

    def test_y0_passes(self):
        r = AnnotationRegion.from_dict({"label": "normal", "x": 0, "y": 0, "width": 10, "height": 10, "area": 100, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})
        assert r.y == 0


class Test3:
    def test_w0_raises(self):
        with pytest.raises(Exception):
            AnnotationRegion.from_dict({"label": "normal", "x": 0, "y": 0, "width": 0, "height": 10, "area": 0, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})

    def test_h0_raises(self):
        with pytest.raises(Exception):
            AnnotationRegion.from_dict({"label": "normal", "x": 0, "y": 0, "width": 10, "height": 0, "area": 0, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})

    def test_w1_passes(self):
        r = AnnotationRegion.from_dict({"label": "normal", "x": 0, "y": 0, "width": 1, "height": 1, "area": 1, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})
        assert r.width == 1

    def test_h1_passes(self):
        r = AnnotationRegion.from_dict({"label": "normal", "x": 0, "y": 0, "width": 1, "height": 1, "area": 1, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})
        assert r.height == 1


class Test4:
    def test_am_raises(self):
        with pytest.raises(Exception):
            AnnotationRegion.from_dict({"label": "normal", "x": 0, "y": 0, "width": 10, "height": 10, "area": 99, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})

    def test_ac_passes(self):
        r = AnnotationRegion.from_dict({"label": "normal", "x": 2, "y": 3, "width": 7, "height": 5, "area": 35, "status": "test", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})
        assert r.area == 35


class Test5:
    def test_es_raises(self):
        with pytest.raises(Exception):
            AnnotationRegion.from_dict({"label": "normal", "x": 0, "y": 0, "width": 10, "height": 10, "area": 100, "status": "", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})

    def test_vs_passes(self):
        r = AnnotationRegion.from_dict({"label": "defect", "x": 0, "y": 0, "width": 10, "height": 10, "area": 100, "status": "scratch", "image_id": "test_ref", "annotator_id": "test_annotator", "creation_timestamp": "2025-01-15T10:30:45Z"})
        assert r.status == "scratch"


if __name__ == "__main__":
    import sys
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))