-- Rename the non-BAC ball source from 'live' to 'detected'.
--
-- The value only says where ball coordinates come from: 'bac' uses the frozen
-- Alfheim BAC coordinates and 'detected' uses the project's own raw-video ball
-- detector and tracker. The rules engine is the same for both.
-- The append-only trigger on segment_outputs is suspended only for this
-- relabel inside the migration transaction.

ALTER TABLE segments DROP CONSTRAINT segments_ball_source_check;
ALTER TABLE segment_outputs DROP CONSTRAINT segment_outputs_ball_source_check;

UPDATE segments SET ball_source = 'detected' WHERE ball_source = 'live';

ALTER TABLE segment_outputs DISABLE TRIGGER USER;
UPDATE segment_outputs SET ball_source = 'detected' WHERE ball_source = 'live';
ALTER TABLE segment_outputs ENABLE TRIGGER USER;

ALTER TABLE segments ADD CONSTRAINT segments_ball_source_check
    CHECK (ball_source IS NULL OR ball_source IN ('bac', 'detected'));
ALTER TABLE segment_outputs ADD CONSTRAINT segment_outputs_ball_source_check
    CHECK (ball_source IN ('bac', 'detected'));
