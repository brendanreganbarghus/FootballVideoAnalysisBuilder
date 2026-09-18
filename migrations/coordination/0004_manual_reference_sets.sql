CREATE TABLE manual_reference_set_revisions (
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    revision bigint NOT NULL CHECK (revision > 0),
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'approved')),
    based_on_revision bigint,
    created_by text NOT NULL REFERENCES developers(developer_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    approved_by text REFERENCES developers(developer_id),
    approved_at timestamptz,
    PRIMARY KEY (workflow_id, segment_id, revision),
    CONSTRAINT manual_reference_set_segment_fk
        FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id),
    CONSTRAINT manual_reference_set_base_fk
        FOREIGN KEY (workflow_id, segment_id, based_on_revision)
        REFERENCES manual_reference_set_revisions(
            workflow_id, segment_id, revision
        ),
    CONSTRAINT manual_reference_set_approval_check CHECK (
        (status = 'draft' AND approved_by IS NULL AND approved_at IS NULL)
        OR
        (status = 'approved' AND approved_by IS NOT NULL AND approved_at IS NOT NULL)
    )
);

ALTER TABLE event_revisions
    ADD CONSTRAINT manual_event_position_check CHECK (
        stream <> 'M'
        OR (
            jsonb_typeof(payload -> 'timestamp_ms') = 'number'
            AND (payload ->> 'timestamp_ms') ~ '^[0-9]+$'
            AND (payload ->> 'timestamp_ms')::bigint BETWEEN 0 AND 60000
            AND jsonb_typeof(payload -> 'source_frame') = 'number'
            AND (payload ->> 'source_frame') ~ '^[0-9]+$'
            AND (payload ->> 'source_frame')::bigint >= 0
        )
    ) NOT VALID;

CREATE TABLE manual_reference_memberships (
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    set_revision bigint NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    stream char(1) NOT NULL DEFAULT 'M' CHECK (stream = 'M'),
    event_key text NOT NULL,
    event_revision bigint NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (workflow_id, segment_id, set_revision, ordinal),
    UNIQUE (workflow_id, segment_id, set_revision, event_key),
    CONSTRAINT manual_reference_membership_set_fk
        FOREIGN KEY (workflow_id, segment_id, set_revision)
        REFERENCES manual_reference_set_revisions(
            workflow_id, segment_id, revision
        ),
    CONSTRAINT manual_reference_membership_event_fk
        FOREIGN KEY (
            workflow_id, segment_id, stream, event_key, event_revision
        )
        REFERENCES event_revisions(
            workflow_id, segment_id, stream, event_key, revision
        )
);

CREATE TABLE manual_event_mappings (
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    set_revision bigint NOT NULL,
    manual_event_key text NOT NULL,
    engine_event_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (
        workflow_id, segment_id, set_revision, manual_event_key
    ),
    UNIQUE (
        workflow_id, segment_id, set_revision, engine_event_key
    ),
    CONSTRAINT manual_event_mapping_member_fk
        FOREIGN KEY (
            workflow_id, segment_id, set_revision, manual_event_key
        )
        REFERENCES manual_reference_memberships(
            workflow_id, segment_id, set_revision, event_key
        )
);

CREATE INDEX manual_reference_sets_latest_idx
    ON manual_reference_set_revisions (
        workflow_id, segment_id, revision DESC
    );
CREATE INDEX manual_reference_members_order_idx
    ON manual_reference_memberships (
        workflow_id, segment_id, set_revision, ordinal
    );

CREATE FUNCTION coordination_guard_manual_reference_set() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status = 'approved' THEN
        RAISE EXCEPTION 'approved manual reference set revisions are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    IF NEW.workflow_id <> OLD.workflow_id
       OR NEW.segment_id <> OLD.segment_id
       OR NEW.revision <> OLD.revision
       OR NEW.based_on_revision IS DISTINCT FROM OLD.based_on_revision
       OR NEW.created_by <> OLD.created_by
       OR NEW.created_at <> OLD.created_at
       OR NEW.status <> 'approved'
       OR NEW.approved_by IS NULL
       OR NEW.approved_at IS NULL THEN
        RAISE EXCEPTION 'manual reference set may only transition draft to approved';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION coordination_guard_manual_reference_child() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP <> 'INSERT' AND EXISTS (
        SELECT 1 FROM manual_reference_set_revisions
        WHERE workflow_id = OLD.workflow_id
          AND segment_id = OLD.segment_id
          AND revision = OLD.set_revision
          AND status = 'approved'
    ) THEN
        RAISE EXCEPTION 'approved manual reference set revisions are immutable';
    END IF;
    IF TG_OP <> 'DELETE' AND EXISTS (
        SELECT 1 FROM manual_reference_set_revisions
        WHERE workflow_id = NEW.workflow_id
          AND segment_id = NEW.segment_id
          AND revision = NEW.set_revision
          AND status = 'approved'
    ) THEN
        RAISE EXCEPTION 'approved manual reference set revisions are immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER manual_reference_set_immutable
    BEFORE UPDATE OR DELETE ON manual_reference_set_revisions
    FOR EACH ROW EXECUTE FUNCTION coordination_guard_manual_reference_set();
CREATE TRIGGER manual_reference_membership_immutable
    BEFORE INSERT OR UPDATE OR DELETE ON manual_reference_memberships
    FOR EACH ROW EXECUTE FUNCTION coordination_guard_manual_reference_child();
CREATE TRIGGER manual_event_mapping_immutable
    BEFORE INSERT OR UPDATE OR DELETE ON manual_event_mappings
    FOR EACH ROW EXECUTE FUNCTION coordination_guard_manual_reference_child();
