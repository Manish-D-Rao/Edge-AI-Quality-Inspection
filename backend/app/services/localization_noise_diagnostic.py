from __future__ import annotations

import math
from collections import Counter
from typing import Any

import cv2
import numpy as np


def _area_bucket(area: int) -> str:
    if area <= 500:
        return "small_le_500"
    if area <= 10_000:
        return "medium_501_10000"
    return "large_gt_10000"


def _bbox_bucket(area: int) -> str:
    if area <= 500:
        return "small_le_500"
    if area <= 10_000:
        return "medium_501_10000"
    return "large_gt_10000"


def _aspect_bucket(ratio: float) -> str:
    if ratio < 0.5:
        return "portrait_lt_0_5"
    if ratio <= 2.0:
        return "balanced_0_5_to_2"
    return "landscape_gt_2"


def _count_distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "median": None,
            "p90": None,
            "max": None,
        }
    array = np.asarray(values, dtype=np.float64)
    return {
        "count": int(array.size),
        "min": float(np.min(array)),
        "median": float(np.median(array)),
        "p90": float(np.percentile(array, 90)),
        "max": float(np.max(array)),
    }


def _count_buckets(values: list[str], keys: tuple[str, ...]) -> dict[str, int]:
    counts = Counter(values)
    return {key: int(counts.get(key, 0)) for key in keys}


def _box_gap(
    first: dict[str, Any], second: dict[str, Any]
) -> tuple[int, int, int]:
    first_x2 = first["x"] + first["width"]
    first_y2 = first["y"] + first["height"]
    second_x2 = second["x"] + second["width"]
    second_y2 = second["y"] + second["height"]
    gap_x = max(0, second["x"] - first_x2, first["x"] - second_x2)
    gap_y = max(0, second["y"] - first_y2, first["y"] - second_y2)
    overlap_width = max(
        0, min(first_x2, second_x2) - max(first["x"], second["x"])
    )
    overlap_height = max(
        0, min(first_y2, second_y2) - max(first["y"], second["y"])
    )
    overlap_area = overlap_width * overlap_height
    return gap_x, gap_y, overlap_area


def _nearby_box_statistics(
    regions: list[dict[str, Any]], distance_limit: int
) -> dict[str, Any]:
    parent = list(range(len(regions)))
    rank = [0] * len(regions)

    def find(item: int) -> int:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(first: int, second: int) -> None:
        root_first = find(first)
        root_second = find(second)
        if root_first == root_second:
            return
        if rank[root_first] < rank[root_second]:
            root_first, root_second = root_second, root_first
        parent[root_second] = root_first
        if rank[root_first] == rank[root_second]:
            rank[root_first] += 1

    ordered = sorted(
        enumerate(regions), key=lambda item: item[1]["x"]
    )
    active: list[tuple[int, dict[str, Any]]] = []
    near_pairs = 0
    overlapping_pairs = 0
    gaps: list[float] = []
    for index, region in ordered:
        left = region["x"]
        active = [
            (other_index, other)
            for other_index, other in active
            if other["x"] + other["width"] + distance_limit >= left
        ]
        for other_index, other in active:
            gap_x, gap_y, overlap_area = _box_gap(other, region)
            if overlap_area:
                overlapping_pairs += 1
            separation = max(gap_x, gap_y)
            if separation <= distance_limit:
                near_pairs += 1
                gaps.append(float(separation))
                union(index, other_index)
        active.append((index, region))

    groups: Counter[int] = Counter(find(index) for index in range(len(regions)))
    group_sizes = list(groups.values())
    multi_groups = [size for size in group_sizes if size > 1]
    return {
        "definition": (
            "Two boxes are neighbors when their maximum horizontal/vertical "
            f"edge-to-edge gap is at most {distance_limit} pixels. Connected "
            "groups are transitive and indicate proximity, not proven common "
            "physical changes."
        ),
        "distance_limit_pixels": distance_limit,
        "nearby_box_pair_count": near_pairs,
        "overlapping_box_pair_count": overlapping_pairs,
        "nearby_pair_separation_pixels": _count_distribution(gaps),
        "connected_group_count_including_singletons": len(group_sizes),
        "multi_box_group_count": len(multi_groups),
        "candidates_in_multi_box_groups": int(sum(multi_groups)),
        "largest_group_size": max(group_sizes, default=0),
        "multi_box_group_size_distribution": _count_distribution(
            [float(size) for size in multi_groups]
        ),
    }


def analyze_localization(
    reference: np.ndarray,
    regions: list[dict[str, Any]],
    *,
    grid_rows: int = 4,
    grid_columns: int = 4,
    image_border_fraction: float = 0.02,
    nearby_distance_pixels: int = 10,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    if reference is None or reference.size == 0:
        raise ValueError("Reference image must be non-empty.")
    if grid_rows < 1 or grid_columns < 1:
        raise ValueError("Grid dimensions must be positive.")
    if image_border_fraction < 0 or image_border_fraction >= 0.5:
        raise ValueError("Image-border fraction must be in [0, 0.5).")
    height, width = reference.shape[:2]
    area_keys = (
        "small_le_500",
        "medium_501_10000",
        "large_gt_10000",
    )
    bbox_keys = area_keys
    aspect_keys = (
        "portrait_lt_0_5",
        "balanced_0_5_to_2",
        "landscape_gt_2",
    )
    enriched: list[dict[str, Any]] = []
    centers_x: list[float] = []
    centers_y: list[float] = []
    contour_areas: list[float] = []
    bbox_areas: list[float] = []
    aspect_ratios: list[float] = []
    area_labels: list[str] = []
    bbox_labels: list[str] = []
    aspect_labels: list[str] = []
    grid = [[0 for _ in range(grid_columns)] for _ in range(grid_rows)]
    border_x = width * image_border_fraction
    border_y = height * image_border_fraction
    image_border_count = 0
    for index, region in enumerate(regions):
        x, y = int(region["x"]), int(region["y"])
        box_width, box_height = int(region["width"]), int(region["height"])
        area = int(region["area"])
        bbox_area = box_width * box_height
        ratio = box_width / box_height if box_height else math.inf
        center_x = x + box_width / 2
        center_y = y + box_height / 2
        column = min(grid_columns - 1, int(center_x / width * grid_columns))
        row = min(grid_rows - 1, int(center_y / height * grid_rows))
        grid[row][column] += 1
        touches_image_border = (
            x <= border_x
            or y <= border_y
            or x + box_width >= width - border_x
            or y + box_height >= height - border_y
        )
        image_border_count += int(touches_image_border)
        area_label = _area_bucket(area)
        bbox_label = _bbox_bucket(bbox_area)
        aspect_label = _aspect_bucket(ratio)
        enriched_region = {
            **region,
            "index": index,
            "bbox_area": bbox_area,
            "aspect_ratio": round(ratio, 4),
            "area_bucket": area_label,
            "bbox_area_bucket": bbox_label,
            "aspect_ratio_bucket": aspect_label,
            "grid_row": row,
            "grid_column": column,
            "touches_image_border_2_percent": touches_image_border,
        }
        enriched.append(enriched_region)
        centers_x.append(center_x)
        centers_y.append(center_y)
        contour_areas.append(float(area))
        bbox_areas.append(float(bbox_area))
        aspect_ratios.append(float(ratio))
        area_labels.append(area_label)
        bbox_labels.append(bbox_label)
        aspect_labels.append(aspect_label)

    heatmap = np.zeros((height, width), dtype=np.uint8)
    for region in enriched:
        cx = min(width - 1, int(region["x"] + region["width"] / 2))
        cy = min(height - 1, int(region["y"] + region["height"] / 2))
        cv2.circle(heatmap, (cx, cy), 12, 255, -1)
    density = cv2.GaussianBlur(heatmap, (0, 0), sigmaX=18, sigmaY=18)
    density_color = cv2.applyColorMap(density, cv2.COLORMAP_TURBO)
    density_overlay = cv2.addWeighted(reference, 0.62, density_color, 0.38, 0)

    box_overlay = reference.copy()
    colors = {
        "small_le_500": (0, 180, 255),
        "medium_501_10000": (0, 0, 255),
        "large_gt_10000": (255, 0, 255),
    }
    for region in enriched:
        x, y = region["x"], region["y"]
        x2, y2 = x + region["width"], y + region["height"]
        cv2.rectangle(
            box_overlay,
            (x, y),
            (x2, y2),
            colors[region["area_bucket"]],
            2 if region["area_bucket"] == "large_gt_10000" else 1,
        )

    result = {
        "image_dimensions": {"width": width, "height": height},
        "coordinate_system": "reference image pixel coordinates",
        "candidate_count": len(enriched),
        "bin_definitions": {
            "contour_area_pixels_squared": {
                "small_le_500": "contour area <= 500 px^2",
                "medium_501_10000": "500 < contour area <= 10000 px^2",
                "large_gt_10000": "contour area > 10000 px^2",
            },
            "bounding_box_area_pixels_squared": {
                "small_le_500": "width * height <= 500 px^2",
                "medium_501_10000": "500 < width * height <= 10000 px^2",
                "large_gt_10000": "width * height > 10000 px^2",
            },
            "aspect_ratio": {
                "portrait_lt_0_5": "width / height < 0.5",
                "balanced_0_5_to_2": "0.5 <= width / height <= 2.0",
                "landscape_gt_2": "width / height > 2.0",
            },
        },
        "distributions": {
            "contour_area_px2": _count_distribution(contour_areas),
            "bounding_box_area_px2": _count_distribution(bbox_areas),
            "aspect_ratio_width_over_height": _count_distribution(aspect_ratios),
            "contour_area_buckets": _count_buckets(area_labels, area_keys),
            "bounding_box_area_buckets": _count_buckets(bbox_labels, bbox_keys),
            "aspect_ratio_buckets": _count_buckets(aspect_labels, aspect_keys),
        },
        "spatial_distribution": {
            "grid_rows": grid_rows,
            "grid_columns": grid_columns,
            "counts_by_row": grid,
            "center_x_pixels": _count_distribution(centers_x),
            "center_y_pixels": _count_distribution(centers_y),
            "image_border_definition": (
                f"Candidate box intersects the outer {image_border_fraction:.0%} "
                "of image width or height."
            ),
            "image_border_fraction": image_border_fraction,
            "candidate_boxes_touching_image_border": image_border_count,
        },
        "nearby_boxes": {
            "within_10_pixels": _nearby_box_statistics(
                enriched, nearby_distance_pixels
            ),
            "within_25_pixels": _nearby_box_statistics(enriched, 25),
        },
        "regions": enriched,
    }
    return result, {
        "candidate_area_overlay.jpg": box_overlay,
        "candidate_density_overlay.jpg": density_overlay,
    }
