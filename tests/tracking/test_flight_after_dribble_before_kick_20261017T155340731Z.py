"""Rule: when no flight leaves the last seen ball, a player may have
dribbled it slowly for up to a second before the kick; a flight whose line
starts within that rolled distance, and is seen soon after the kick, is
followed."""

from __future__ import annotations

import football_poc.ball.aerial as aerial


def _flight(kick_frame, kick_x, kick_y, vx, vy, frames):
    return {
        t: [(kick_x + vx * (t - kick_frame), kick_y + vy * (t - kick_frame))]
        for t in range(kick_frame + 1, kick_frame + 1 + frames)
    }


def test_flight_after_dribble_before_kick_20261017T155340731Z() -> None:
    """The ball is last seen at frame 100, rolls about 40 px, and is kicked
    at frame 118. The flight is found from the dribble. A trail whose line
    meets the dribble at frame 106 but is first seen at 121, 15 unseen
    frames later, is not a kick.
    """
    anchor = (100, 1066.0, 624.0)
    blobs = _flight(118, 1026.0, 632.0, -10.0, -3.0, 40)
    track = aerial._aerial_one_sided_track(anchor, blobs, 25.0)
    assert track is not None
    assert track[0][0] == 119 and track[-1][0] == 158

    early_kick = _flight(106, 1056.0, 626.0, -10.0, -3.0, 30)
    late = {t: c for t, c in early_kick.items() if t >= 121}
    assert not aerial._aerial_rolled_kick_seeds(anchor, late)
