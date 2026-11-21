import pytest
from app.splits import SplitError, split_equal, split_exact, split_percent


def test_equal_100_among_3():  # AC3.1
    assert split_equal(10000, [1, 2, 3]) == {1: 3334, 2: 3333, 3: 3333}


def test_equal_one_cent_among_3():  # AC3.2
    assert split_equal(1, [1, 2, 3]) == {1: 1, 2: 0, 3: 0}


def test_equal_leftover_goes_to_lowest_ids():
    assert split_equal(10, [3, 1, 2]) == {1: 4, 2: 3, 3: 3}


@pytest.mark.parametrize("amount", [0, -1, 100_000_001, 12.5, "100", None, True])
def test_equal_invalid_amount(amount):  # AC3.3
    with pytest.raises(SplitError):
        split_equal(amount, [1, 2])


def test_max_amount_allowed():
    assert sum(split_equal(100_000_000, [1, 2, 3]).values()) == 100_000_000


def test_equal_no_participants():  # AC3.8
    with pytest.raises(SplitError):
        split_equal(100, [])


def test_equal_duplicate_participants():
    with pytest.raises(SplitError):
        split_equal(100, [1, 1])


def test_exact_ok():
    assert split_exact(6000, {1: 4000, 2: 2000}) == {1: 4000, 2: 2000}


def test_exact_wrong_sum():  # AC3.4
    with pytest.raises(SplitError):
        split_exact(6000, {1: 4000, 2: 1999})


def test_exact_negative_share():
    with pytest.raises(SplitError):
        split_exact(6000, {1: 7000, 2: -1000})


def test_percent_33_33_34():  # AC3.6
    shares = split_percent(10000, {1: "33.33", 2: "33.33", 3: "33.34"})
    assert shares == {1: 3333, 2: 3333, 3: 3334}
    assert sum(shares.values()) == 10000


def test_percent_largest_remainder_sums_exactly():
    shares = split_percent(100, {1: 33.33, 2: 33.33, 3: 33.34})
    assert sum(shares.values()) == 100


def test_percent_not_100():  # AC3.5
    with pytest.raises(SplitError):
        split_percent(10000, {1: 50, 2: 49.99})


def test_percent_three_decimals_rejected():
    with pytest.raises(SplitError):
        split_percent(10000, {1: "50.001", 2: "49.999"})


def test_percent_negative_rejected():
    with pytest.raises(SplitError):
        split_percent(10000, {1: 120, 2: -20})


def test_percent_non_numeric_rejected():
    with pytest.raises(SplitError):
        split_percent(10000, {1: "abc", 2: 50})
