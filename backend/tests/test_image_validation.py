from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.image_validation import (
    ImageValidationError,
    MAX_IMAGE_BYTES,
    decode_uploaded_image,
)


def _encoded_png() -> bytes:
    success, encoded = cv2.imencode(
        ".png", np.zeros((16, 16, 3), dtype=np.uint8)
    )
    assert success
    return encoded.tobytes()


def test_decodes_supported_png_and_detects_extension() -> None:
    result = decode_uploaded_image(_encoded_png())
    assert result.extension == ".png"
    assert result.image.shape == (16, 16, 3)


@pytest.mark.parametrize("content", [b"", b"not an image", b"\xff\xd8\xffbroken"])
def test_rejects_empty_unsupported_or_corrupt_images(content: bytes) -> None:
    with pytest.raises(ImageValidationError):
        decode_uploaded_image(content)


def test_rejects_image_above_documented_maximum() -> None:
    with pytest.raises(ImageValidationError, match="10 MiB"):
        decode_uploaded_image(b"\x89PNG\r\n\x1a\n" + b"x" * MAX_IMAGE_BYTES)
