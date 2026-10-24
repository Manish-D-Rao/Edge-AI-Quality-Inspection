
import argparse
import json
import time
from pathlib import Path

import cv2


def load_image(path: str):
    """Load an image and raise a helpful error if it cannot be read."""
    image = cv2.imread(path)

    if image is None:
        raise ValueError(
            f"Could not read image: {path}. "
            "Check that the path exists and the file is a valid image."
        )

    return image


def preprocess(image, target_size=None):
    """
    Resize to the reference dimensions when required.
    Convert to grayscale, normalize local contrast, and blur noise.
    """
    if target_size is not None:
        width, height = target_size
        image = cv2.resize(
            image, (width, height), interpolation=cv2.INTER_AREA
        )

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )
    gray = clahe.apply(gray)

    return cv2.GaussianBlur(gray, (5, 5), 0)


def inspect_images(
    reference_path: str,
    test_path: str,
    output_dir: str = "outputs",
    min_area: int = 80,
    threshold: int = 25,
):
    started = time.perf_counter()

    reference = load_image(reference_path)
    test = load_image(test_path)

    # Keep coordinates consistent with the reference image.
    height, width = reference.shape[:2]
    if test.shape[:2] != reference.shape[:2]:
        test = cv2.resize(
            test, (width, height), interpolation=cv2.INTER_AREA
        )

    reference_gray = preprocess(reference)
    test_gray = preprocess(test)

    # Pixel-level differences provide candidate regions, not
    # verified defects.
    difference = cv2.absdiff(reference_gray, test_gray)

    _, mask = cv2.threshold(
        difference, threshold, 255, cv2.THRESH_BINARY
    )

    # Merge nearby difference pixels and remove tiny noise.
    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (3, 3)
    )
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_OPEN, kernel
    )
    mask = cv2.morphologyEx(
        mask, cv2.MORPH_CLOSE, kernel, iterations=2
    )

    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    annotated = test.copy()
    regions = []

    for contour in contours:
        area = int(cv2.contourArea(contour))

        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)

        regions.append({
            "x": int(x),
            "y": int(y),
            "width": int(w),
            "height": int(h),
            "area": area,
            "status": "suspicious_difference",
        })

        cv2.rectangle(
            annotated,
            (x, y),
            (x + w, y + h),
            (0, 0, 255),
            2,
        )

        cv2.putText(
            annotated,
            "Candidate",
            (x, max(y - 8, 20)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            1,
            cv2.LINE_AA,
        )

    elapsed_ms = round(
        (time.perf_counter() - started) * 1000, 2
    )

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    cv2.imwrite(str(output_path / "annotated.jpg"), annotated)
    cv2.imwrite(str(output_path / "difference.jpg"), difference)
    cv2.imwrite(str(output_path / "mask.jpg"), mask)

    result = {
        "method": "opencv_reference_difference",
        "reference_image": str(reference_path),
        "test_image": str(test_path),
        "image_width": width,
        "image_height": height,
        "candidate_count": len(regions),
        "processing_time_ms": elapsed_ms,
        "parameters": {
            "threshold": threshold,
            "min_area": min_area,
        },
        "regions": regions,
        "warning": (
            "Candidates indicate image differences, not confirmed defects."
        ),
    }

    with open(output_path / "result.json", "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Lightweight PCB inspection baseline"
    )
    parser.add_argument("--reference", required=True)
    parser.add_argument("--test", required=True)
    parser.add_argument("--output", default="outputs")
    parser.add_argument("--min-area", type=int, default=80)
    parser.add_argument("--threshold", type=int, default=25)

    args = parser.parse_args()

    if args.min_area < 1:
        parser.error("--min-area must be at least 1")

    if not 0 <= args.threshold <= 255:
        parser.error("--threshold must be between 0 and 255")

    try:
        result = inspect_images(
            reference_path=args.reference,
            test_path=args.test,
            output_dir=args.output,
            min_area=args.min_area,
            threshold=args.threshold,
        )
        print(json.dumps(result, indent=2))
        print(f"\nSaved results to: {args.output}")

    except (ValueError, cv2.error, OSError) as error:
        parser.exit(1, f"Inspection failed: {error}\n")


if __name__ == "__main__":
    main()
