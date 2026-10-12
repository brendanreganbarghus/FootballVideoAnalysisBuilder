"""A run of in-flight labels longer than any real flight is not a flight."""

from football_poc.chrono_engine import ChronoSettings, _credible_flights


def _track(seconds):
    return [(i, t, 100.0, 100.0) for i, t in enumerate(seconds)]


def test_long_aerial_run_is_dropped_20261012T061113314Z():
    track = _track([i * 0.2 for i in range(40)])
    lofted = set(range(2, 37))  # 6.8 s "in the air"
    assert _credible_flights(track, lofted, ChronoSettings().max_flight_seconds) == set()


def test_real_flight_is_kept_20261012T061113314Z():
    track = _track([i * 0.2 for i in range(40)])
    flight = set(range(5, 18))  # 2.4 s
    late = set(range(25, 40))  # 2.8 s, separate run
    kept = _credible_flights(track, flight | late, ChronoSettings().max_flight_seconds)
    assert kept == flight | late
