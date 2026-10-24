from __future__ import annotations

from collections import Counter
from typing import Any


def _box_geometry(
    first: dict[str, Any], second: dict[str, Any]
) -> tuple[int, int, int]:
    first_x2 = int(first["x"]) + int(first["width"])
    first_y2 = int(first["y"]) + int(first["height"])
    second_x2 = int(second["x"]) + int(second["width"])
    second_y2 = int(second["y"]) + int(second["height"])
    gap_x = max(
        0,
        int(second["x"]) - first_x2,
        int(first["x"]) - second_x2,
    )
    gap_y = max(
        0,
        int(second["y"]) - first_y2,
        int(first["y"]) - second_y2,
    )
    overlap_width = max(
        0,
        min(first_x2, second_x2) - max(int(first["x"]), int(second["x"])),
    )
    overlap_height = max(
        0,
        min(first_y2, second_y2) - max(int(first["y"]), int(second["y"])),
    )
    return gap_x, gap_y, overlap_width * overlap_height


def _connected_groups(
    regions: list[dict[str, Any]],
    *,
    distance_threshold: float,
    require_positive_overlap: bool,
) -> list[list[int]]:
    parent = list(range(len(regions)))
    rank = [0] * len(regions)

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

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
        enumerate(regions), key=lambda item: int(item[1]["x"])
    )
    active: list[tuple[int, dict[str, Any]]] = []
    for index, region in ordered:
        left = int(region["x"])
        active = [
            (other_index, other)
            for other_index, other in active
            if int(other["x"]) + int(other["width"]) + distance_threshold >= left
        ]
        for other_index, other in active:
            gap_x, gap_y, overlap_area = _box_geometry(other, region)
            if require_positive_overlap:
                connected = overlap_area > 0
            else:
                connected = max(gap_x, gap_y) <= distance_threshold
            if connected:
                union(index, other_index)
        active.append((index, region))

    groups: dict[int, list[int]] = {}
    for index in range(len(regions)):
        groups.setdefault(find(index), []).append(index)
    return list(groups.values())


def merge_candidate_boxes(
    regions: list[dict[str, Any]],
    *,
    strategy: str,
    distance_threshold: float = 0,
) -> list[dict[str, Any]]:
    """Merge candidate boxes transitively; preserve original member indices."""
    if strategy not in {"overlap", "nearby"}:
        raise ValueError(f"Unknown candidate-merging strategy: {strategy}")
    if distance_threshold < 0:
        raise ValueError("Distance threshold cannot be negative.")
    groups = _connected_groups(
        regions,
        distance_threshold=distance_threshold,
        require_positive_overlap=(strategy == "overlap"),
    )
    merged = []
    for indexes in groups:
        members = [regions[index] for index in indexes]
        x1 = min(int(region["x"]) for region in members)
        y1 = min(int(region["y"]) for region in members)
        x2 = max(
            int(region["x"]) + int(region["width"]) for region in members
        )
        y2 = max(
            int(region["y"]) + int(region["height"]) for region in members
        )
        merged.append({
            "x": x1,
            "y": y1,
            "width": x2 - x1,
            "height": y2 - y1,
            "bbox_area": (x2 - x1) * (y2 - y1),
            "group_size": len(indexes),
            "candidate_indexes": sorted(indexes),
        })
    merged.sort(key=lambda region: (region["y"], region["x"]))
    return merged


def summarize_boxes(regions: list[dict[str, Any]]) -> dict[str, Any]:
    widths = [int(region["width"]) for region in regions]
    heights = [int(region["height"]) for region in regions]
    areas = [
        int(region["width"]) * int(region["height"]) for region in regions
    ]
    group_sizes = [int(region.get("group_size", 1)) for region in regions]

    def summary(values: list[int]) -> dict[str, int | float | None]:
        if not values:
            return {"min": None, "median": None, "max": None}
        ordered = sorted(values)
        middle = len(ordered) // 2
        median = (
            ordered[middle]
            if len(ordered) % 2
            else (ordered[middle - 1] + ordered[middle]) / 2
        )
        return {
            "min": min(ordered),
            "median": median,
            "max": max(ordered),
        }

    return {
        "candidate_count": len(regions),
        "box_width_pixels": summary(widths),
        "box_height_pixels": summary(heights),
        "box_area_pixels_squared": summary(areas),
        "merge_group_sizes": {
            str(size): count
            for size, count in sorted(Counter(group_sizes).items())
        },
        "largest_merge_group_size": max(group_sizes, default=0),
    }
