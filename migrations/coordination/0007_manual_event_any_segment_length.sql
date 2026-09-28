-- Allow M# events on segments of any length.
--
-- 0004 limited M# timestamps to 0-60000 ms, which only fits 60-second
-- segments. The Canvas already checks each timestamp against the selected
-- segment's own duration, so the database only requires a non-negative
-- integer position.

ALTER TABLE event_revisions DROP CONSTRAINT manual_event_position_check;

ALTER TABLE event_revisions
    ADD CONSTRAINT manual_event_position_check CHECK (
        stream <> 'M'
        OR (
            jsonb_typeof(payload -> 'timestamp_ms') = 'number'
            AND (payload ->> 'timestamp_ms') ~ '^[0-9]+$'
            AND jsonb_typeof(payload -> 'source_frame') = 'number'
            AND (payload ->> 'source_frame') ~ '^[0-9]+$'
        )
    ) NOT VALID;
