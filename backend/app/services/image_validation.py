from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


MAX_IMAGE_BYTES = 10 * 1024 * 1024


class ImageValidationError(ValueError):
    """Raised when an uploaded image is unsupported or cannot be decoded."""


@dataclass(frozen=True)
class ValidatedImage:
    image: np.ndarray
    extension: str


def decode_uploaded_image(content: bytes) -> ValidatedImage:
    if not content:
        raise ImageValidationError("Uploaded image is empty.")
    if len(content) > MAX_IMAGE_BYTES:
        raise ImageValidationError(
            f"Image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MiB limit."
        )

    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        extension = ".png"
    elif content.startswith(b"\xff\xd8\xff"):
        extension = ".jpg"
    else:
        raise ImageValidationError("Only JPEG and PNG images are supported.")

    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        raise ImageValidationError("Uploaded file is not a decodable image.")
    return ValidatedImage(image=image, extension=extension)
