"""Rule: one ball cannot be released by two different same-team senders to the
same receiver within half a second; the two passes are competing readings of
one pass and only the stronger is counted. Releases further apart are kept."""

from football_poc.engine.common import PredictedEvent
from football_poc.engine.pass_cleanup import collapse_simultaneous_releases_to_same_receiver


def test_near_simultaneous_releases_count_once_20261004T201514367Z():
    weak = PredictedEvent("pass_candidate", 51.6, "black", 800, 821, 0.43, "", 52.8)
    strong = PredictedEvent("pass_candidate", 51.8, "black", 815, 821, 0.79, "", 52.4)
    assert collapse_simultaneous_releases_to_same_receiver([weak, strong]) == [strong]


def test_separate_releases_to_same_receiver_are_kept_20261004T201514383Z():
    first = PredictedEvent("pass_candidate", 22.6, "black", 418, 43, 0.6, "", 25.4)
    second = PredictedEvent("pass_candidate", 24.4, "black", 11, 43, 0.7, "", 25.0)
    assert collapse_simultaneous_releases_to_same_receiver([first, second]) == [first, second]
