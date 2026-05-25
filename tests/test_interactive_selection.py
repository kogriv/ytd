from __future__ import annotations

import pytest

from ytd.interactive import _parse_selection_mask


@pytest.mark.parametrize(
    ("mask", "total", "expected"),
    [
        ("3-7", 10, [3, 4, 5, 6, 7]),
        ("5-", 10, list(range(5, 11))),
        ("-4", 10, [1, 2, 3, 4]),
        ("all", 5, [1, 2, 3, 4, 5]),
        ("все", 3, [1, 2, 3]),
        ("1,3,5", 6, [1, 3, 5]),
    ],
)
def test_parse_selection_mask_valid(mask: str, total: int, expected: list[int]) -> None:
    assert _parse_selection_mask(mask, total) == expected


@pytest.mark.parametrize(
    ("mask", "total"),
    [
        ("", 5),
        ("   ", 5),
        ("99", 5),
        ("5-2", 10),
        ("0", 5),
    ],
)
def test_parse_selection_mask_invalid(mask: str, total: int) -> None:
    with pytest.raises(ValueError):
        _parse_selection_mask(mask, total)
