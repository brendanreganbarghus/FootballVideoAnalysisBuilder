-- Consolidate the Innovation Day (BAC) and Live review workflows into the
-- single `football_review` workflow.
--
-- * Live rows win for segments present in both workflows; the Innovation
--   copies of those segments are removed.
-- * Innovation-only segments retired before consolidation are removed.
--   Both are preserved in the pre-migration pg_dump backup.
-- * Every remaining row is relabelled to `football_review`, and each segment
--   records the ball-coordinate source (`bac` or `live`) of its outputs.
-- * Engine output JSON is stored per segment revision in `segment_outputs`.
--
-- Append-only triggers and workflow foreign keys are suspended only inside
-- this migration transaction and restored before it commits.

INSERT INTO workflows (workflow_id, display_name, artifact_namespace)
VALUES ('football_review', 'Football review', '')
ON CONFLICT (workflow_id) DO NOTHING;

ALTER TABLE segments
    ADD COLUMN ball_source text
        CHECK (ball_source IS NULL OR ball_source IN ('bac', 'live'));

CREATE TEMPORARY TABLE consolidation_foreign_keys ON COMMIT DROP AS
SELECT
    constraint_row.conrelid::regclass AS table_name,
    constraint_row.conname AS constraint_name,
    pg_get_constraintdef(constraint_row.oid) AS definition
FROM pg_constraint AS constraint_row
JOIN pg_namespace AS namespace_row
    ON namespace_row.oid = constraint_row.connamespace
WHERE constraint_row.contype = 'f'
  AND namespace_row.nspname = current_schema()
  AND EXISTS (
      SELECT 1
      FROM unnest(constraint_row.conkey) AS key_column(attnum)
      JOIN pg_attribute AS attribute_row
        ON attribute_row.attrelid = constraint_row.conrelid
       AND attribute_row.attnum = key_column.attnum
      WHERE attribute_row.attname = 'workflow_id'
  );

CREATE TEMPORARY TABLE consolidation_tables ON COMMIT DROP AS
SELECT
    format('%I.%I', table_schema, table_name)::regclass AS table_name,
    bool_or(column_name = 'segment_id') AS has_segment
FROM information_schema.columns
WHERE table_schema = current_schema()
  AND table_name IN (
      SELECT table_name
      FROM information_schema.columns
      WHERE table_schema = current_schema()
        AND column_name = 'workflow_id'
  )
  AND table_name <> 'workflows'
GROUP BY table_schema, table_name;

CREATE TEMPORARY TABLE consolidation_removed_segments ON COMMIT DROP AS
SELECT innovation.segment_id
FROM segments AS innovation
WHERE innovation.workflow_id = 'innovation_day_bac'
  AND (
      EXISTS (
          SELECT 1
          FROM segments AS live
          WHERE live.workflow_id = 'live_iteration_25'
            AND live.segment_id = innovation.segment_id
      )
      OR innovation.segment_id IN (
          'segment-0060-020',
          'segment-0300-020',
          'segment-0575-020',
          'segment-0595-020',
          'segment-0615-020'
      )
  );

DO $$
DECLARE
    foreign_key record;
    target record;
BEGIN
    FOR target IN SELECT table_name FROM consolidation_tables LOOP
        EXECUTE format('ALTER TABLE %s DISABLE TRIGGER USER', target.table_name);
    END LOOP;

    FOR foreign_key IN SELECT * FROM consolidation_foreign_keys LOOP
        EXECUTE format(
            'ALTER TABLE %s DROP CONSTRAINT %I',
            foreign_key.table_name,
            foreign_key.constraint_name
        );
    END LOOP;

    FOR target IN SELECT * FROM consolidation_tables LOOP
        IF target.has_segment THEN
            EXECUTE format(
                'DELETE FROM %s WHERE workflow_id = %L AND segment_id IN '
                '(SELECT segment_id FROM consolidation_removed_segments)',
                target.table_name,
                'innovation_day_bac'
            );
        END IF;
    END LOOP;
    DELETE FROM segments
    WHERE workflow_id = 'innovation_day_bac'
      AND segment_id IN (SELECT segment_id FROM consolidation_removed_segments);

    UPDATE segments SET ball_source = 'bac'
    WHERE workflow_id = 'innovation_day_bac';
    UPDATE segments SET ball_source = 'live'
    WHERE workflow_id = 'live_iteration_25';

    FOR target IN SELECT table_name FROM consolidation_tables LOOP
        EXECUTE format(
            'UPDATE %s SET workflow_id = %L '
            'WHERE workflow_id IN (%L, %L)',
            target.table_name,
            'football_review',
            'innovation_day_bac',
            'live_iteration_25'
        );
    END LOOP;

    DELETE FROM workflows
    WHERE workflow_id IN ('innovation_day_bac', 'live_iteration_25');

    FOR foreign_key IN SELECT * FROM consolidation_foreign_keys LOOP
        EXECUTE format(
            'ALTER TABLE %s ADD CONSTRAINT %I %s',
            foreign_key.table_name,
            foreign_key.constraint_name,
            foreign_key.definition
        );
    END LOOP;

    FOR target IN SELECT table_name FROM consolidation_tables LOOP
        EXECUTE format('ALTER TABLE %s ENABLE TRIGGER USER', target.table_name);
    END LOOP;
END;
$$;

CREATE TABLE segment_outputs (
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    revision bigint NOT NULL CHECK (revision > 0),
    ball_source text NOT NULL CHECK (ball_source IN ('bac', 'live')),
    engine_sha256 char(64) NOT NULL
        CHECK (engine_sha256 ~ '^[0-9a-f]{64}$'),
    output_sha256 char(64) NOT NULL
        CHECK (output_sha256 ~ '^[0-9a-f]{64}$'),
    files jsonb NOT NULL CHECK (jsonb_typeof(files) = 'object'),
    created_by text NOT NULL REFERENCES developers(developer_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (workflow_id, segment_id, revision),
    CONSTRAINT segment_output_segment_fk
        FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE INDEX segment_outputs_latest_idx
    ON segment_outputs (workflow_id, segment_id, revision DESC);

CREATE TRIGGER segment_outputs_append_only
    BEFORE UPDATE OR DELETE ON segment_outputs
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
