CREATE TABLE historical_review_imports (
    workflow_id text NOT NULL REFERENCES workflows(workflow_id),
    provider_id text NOT NULL REFERENCES artifact_providers(provider_id),
    logical_key text NOT NULL,
    source_sha256 char(64) NOT NULL
        CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    segment_id text,
    source_size bigint NOT NULL CHECK (source_size >= 0),
    state_sha256 char(64) NOT NULL
        CHECK (state_sha256 ~ '^[0-9a-f]{64}$'),
    status text NOT NULL
        CHECK (status IN ('inserted', 'unchanged', 'conflicting', 'rejected')),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    imported_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (workflow_id, provider_id, logical_key, source_sha256)
);

CREATE INDEX historical_import_segment_idx
    ON historical_review_imports
    (workflow_id, segment_id, imported_at DESC);

CREATE TRIGGER historical_review_imports_append_only
    BEFORE DELETE ON historical_review_imports
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
