import math

import pytest

from common_lib.geometry_utils import circle_intersection_area


def test_non_overlapping_circles():
    """Test when circles are too far apart to overlap."""
    assert circle_intersection_area(5, 3, 10) == 0
    assert circle_intersection_area(2, 2, 5) == 0
    assert circle_intersection_area(1, 3, 4.01) == 0


def test_tangent_circles():
    """Test when circles are exactly touching (tangent)."""
    # For tangent circles, overlap should be effectively zero
    assert circle_intersection_area(3, 2, 5) < 1e-10
    assert circle_intersection_area(1, 1, 2) < 1e-10


def test_one_circle_inside_another():
    """Test when one circle is completely inside the other."""
    # Smaller circle should be the area of overlap
    assert math.isclose(circle_intersection_area(5, 3, 1), math.pi * 3**2)
    assert math.isclose(circle_intersection_area(3, 5, 1), math.pi * 3**2)
    assert math.isclose(circle_intersection_area(10, 2, 7), math.pi * 2**2)


def test_concentric_circles():
    """Test when circles have the same center."""
    # For concentric circles, overlap is area of smaller circle
    assert math.isclose(circle_intersection_area(5, 3, 0), math.pi * 3**2)
    assert math.isclose(circle_intersection_area(2, 7, 0), math.pi * 2**2)


def test_partial_overlap():
    """Test when circles partially overlap."""
    # These values were calculated independently to verify algorithm
    assert math.isclose(circle_intersection_area(5, 3, 4), 18.2247, abs_tol=1e-4)
    assert math.isclose(circle_intersection_area(2, 2, 2), 4.9135, abs_tol=1e-4)
    assert math.isclose(
        circle_intersection_area(10, 5, 8), 54.91062185967077, abs_tol=1e-4
    )


def test_edge_cases():
    """Test edge cases and special inputs."""
    # Zero radius
    assert circle_intersection_area(0, 5, 3) == 0
    assert circle_intersection_area(5, 0, 3) == 0

    # Negative radius should raise ValueError
    with pytest.raises(ValueError):
        circle_intersection_area(-1, 5, 3)

    # Negative distance should raise ValueError
    with pytest.raises(ValueError):
        circle_intersection_area(5, 3, -2)
