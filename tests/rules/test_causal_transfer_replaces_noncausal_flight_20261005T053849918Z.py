"""Rule: when the flight inference dates a pass with its completion before its
release (non-causal) and the possession-segment inference has the same pass
(same team, type, sender and receiver, release or completion within the
deduplication window) in causal order, the causal version is kept; otherwise
the later non-causal cleanup would delete a real pass."""

from football_poc.engine.common import PredictedEvent
from football_poc.engine.completed_pass import merge_transfer_events


def _pass(release, completion, sender=854, receiver=343):
    return PredictedEvent(
        "pass_candidate", release, "red", sender, receiver, 0.8, "pass",
        completion,
    )


def test_causal_fallback_replaces_noncausal_primary_20261005T053849918Z():
    merged = merge_transfer_events(
        [_pass(58.0, 57.4)], [_pass(56.8, 57.4)], deduplication_seconds=0.8
    )
    assert [(e.clip_seconds, e.completion_seconds) for e in merged] == [
        (56.8, 57.4)
    ]


def test_different_receiver_does_not_replace_20261005T053849919Z():
    merged = merge_transfer_events(
        [_pass(58.0, 57.4)],
        [_pass(56.8, 57.4, receiver=999)],
        deduplication_seconds=0.8,
    )
    assert (58.0, 57.4) in [(e.clip_seconds, e.completion_seconds) for e in merged]
