import numpy as np

from football_poc.team_colors import assign_color_group, dominant_jersey_color


def test_dominant_jersey_color_uses_largest_kmeans_cluster() -> None:
    crop = np.zeros((10, 10, 3), dtype=np.uint8)
    crop[:, :8] = (10, 20, 220)
    crop[:, 8:] = (20, 180, 20)

    color = dominant_jersey_color(crop, clusters=2)

    assert color[2] > 200
    assert assign_color_group(
        color,
        {"team_a": (10, 20, 220), "team_b": (220, 220, 220)},
    ) == "team_a"
