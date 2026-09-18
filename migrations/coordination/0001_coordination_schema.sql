CREATE TABLE coordination_environments (
    deployment_id text PRIMARY KEY,
    authority_id text NOT NULL,
    authority_epoch bigint NOT NULL CHECK (authority_epoch > 0),
    retired boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE developers (
    developer_id text PRIMARY KEY,
    domain_name text NOT NULL,
    username text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_seen_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE machines (
    machine_id uuid PRIMARY KEY,
    developer_id text NOT NULL REFERENCES developers(developer_id),
    hostname text NOT NULL,
    ip_address inet,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    last_seen_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE workflows (
    workflow_id text PRIMARY KEY,
    display_name text NOT NULL,
    artifact_namespace text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE segments (
    workflow_id text NOT NULL REFERENCES workflows(workflow_id),
    segment_id text NOT NULL,
    logical_key text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (workflow_id, segment_id),
    UNIQUE (workflow_id, logical_key)
);

CREATE TABLE artifact_providers (
    provider_id text PRIMARY KEY,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE artifacts (
    artifact_id uuid PRIMARY KEY,
    provider_id text NOT NULL REFERENCES artifact_providers(provider_id),
    logical_key text NOT NULL,
    content_hash text NOT NULL CHECK (content_hash <> ''),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (provider_id, logical_key, content_hash)
);

CREATE TABLE segment_artifacts (
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    artifact_id uuid NOT NULL REFERENCES artifacts(artifact_id),
    relation text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (workflow_id, segment_id, artifact_id, relation),
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE TABLE assignments (
    assignment_id uuid PRIMARY KEY,
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    developer_id text NOT NULL REFERENCES developers(developer_id),
    status text NOT NULL,
    assigned_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE TABLE editing_leases (
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    owner_id text NOT NULL REFERENCES developers(developer_id),
    machine_id uuid NOT NULL,
    stage text NOT NULL,
    lease_token uuid NOT NULL UNIQUE,
    acquired_at timestamptz NOT NULL,
    heartbeat_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    PRIMARY KEY (workflow_id, segment_id),
    CONSTRAINT editing_lease_segment_fk
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id),
    CONSTRAINT editing_lease_machine_fk
        FOREIGN KEY (machine_id) REFERENCES machines(machine_id),
    CONSTRAINT editing_lease_stage_nonempty CHECK (btrim(stage) <> ''),
    CHECK (expires_at > heartbeat_at)
);

CREATE TABLE review_sessions (
    review_session_id uuid PRIMARY KEY,
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    developer_id text NOT NULL REFERENCES developers(developer_id),
    machine_id uuid NOT NULL REFERENCES machines(machine_id),
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    ended_at timestamptz,
    UNIQUE (workflow_id, segment_id, review_session_id),
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE TABLE state_snapshots (
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    version bigint NOT NULL CHECK (version > 0),
    state jsonb NOT NULL,
    author_id text NOT NULL REFERENCES developers(developer_id),
    review_session_id uuid,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (workflow_id, segment_id, version),
    CONSTRAINT state_snapshot_segment_fk
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id),
    FOREIGN KEY (workflow_id, segment_id, review_session_id)
        REFERENCES review_sessions(workflow_id, segment_id, review_session_id)
);

CREATE TABLE event_revisions (
    event_revision_id bigserial PRIMARY KEY,
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    stream char(1) NOT NULL CHECK (stream IN ('C', 'E', 'M')),
    event_key text NOT NULL,
    revision bigint NOT NULL CHECK (revision > 0),
    payload jsonb NOT NULL,
    actor_id text NOT NULL REFERENCES developers(developer_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (workflow_id, segment_id, stream, event_key, revision),
    CONSTRAINT event_revision_segment_fk
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE TABLE review_activity (
    activity_id bigserial PRIMARY KEY,
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    activity_type text NOT NULL,
    payload jsonb NOT NULL,
    actor_id text NOT NULL REFERENCES developers(developer_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE TABLE review_decisions (
    decision_id bigserial PRIMARY KEY,
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    proposal_key text NOT NULL,
    decision text NOT NULL,
    payload jsonb NOT NULL,
    actor_id text NOT NULL REFERENCES developers(developer_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE TABLE engine_verdicts (
    verdict_id bigserial PRIMARY KEY,
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    event_key text NOT NULL,
    verdict text NOT NULL,
    payload jsonb NOT NULL,
    actor_id text NOT NULL REFERENCES developers(developer_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE TABLE engine_confirmations (
    confirmation_id bigserial PRIMARY KEY,
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    event_key text NOT NULL,
    engine_source_hash text NOT NULL,
    cached_output_hash text NOT NULL,
    reason text NOT NULL,
    actor_id text NOT NULL REFERENCES developers(developer_id),
    confirmed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE TABLE output_fingerprints (
    fingerprint_id bigserial PRIMARY KEY,
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    fingerprint_type text NOT NULL,
    content_hash text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE TABLE jobs (
    job_id uuid PRIMARY KEY,
    workflow_id text NOT NULL REFERENCES workflows(workflow_id),
    segment_id text,
    job_type text NOT NULL,
    payload jsonb NOT NULL,
    priority integer NOT NULL DEFAULT 0,
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (workflow_id, job_id),
    CONSTRAINT job_segment_fk
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE TABLE job_attempts (
    attempt_id uuid PRIMARY KEY,
    workflow_id text NOT NULL REFERENCES workflows(workflow_id),
    job_id uuid NOT NULL,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    worker_id text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    status text NOT NULL DEFAULT 'running',
    error jsonb,
    UNIQUE (workflow_id, attempt_id),
    UNIQUE (job_id, attempt_number),
    CONSTRAINT job_attempt_job_fk
    FOREIGN KEY (workflow_id, job_id)
        REFERENCES jobs(workflow_id, job_id)
);

CREATE TABLE worker_leases (
    attempt_id uuid PRIMARY KEY,
    workflow_id text NOT NULL REFERENCES workflows(workflow_id),
    worker_id text NOT NULL,
    lease_token uuid NOT NULL UNIQUE,
    heartbeat_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    CHECK (expires_at > heartbeat_at),
    CONSTRAINT worker_lease_attempt_fk
    FOREIGN KEY (workflow_id, attempt_id)
        REFERENCES job_attempts(workflow_id, attempt_id)
);

CREATE TABLE job_stages (
    stage_id bigserial PRIMARY KEY,
    workflow_id text NOT NULL REFERENCES workflows(workflow_id),
    attempt_id uuid NOT NULL,
    stage_name text NOT NULL,
    status text NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT job_stage_attempt_fk
    FOREIGN KEY (workflow_id, attempt_id)
        REFERENCES job_attempts(workflow_id, attempt_id)
);

CREATE TABLE job_results (
    result_id bigserial PRIMARY KEY,
    workflow_id text NOT NULL REFERENCES workflows(workflow_id),
    attempt_id uuid NOT NULL,
    result_type text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT job_result_attempt_fk
    FOREIGN KEY (workflow_id, attempt_id)
        REFERENCES job_attempts(workflow_id, attempt_id)
);

CREATE TABLE regression_runs (
    regression_run_id uuid PRIMARY KEY,
    workflow_id text NOT NULL REFERENCES workflows(workflow_id),
    engine_source_hash text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    completed_at timestamptz,
    status text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (workflow_id, regression_run_id)
);

CREATE TABLE regression_results (
    result_id bigserial PRIMARY KEY,
    regression_run_id uuid NOT NULL,
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    passed boolean NOT NULL,
    output_hash text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id),
    FOREIGN KEY (workflow_id, regression_run_id)
        REFERENCES regression_runs(workflow_id, regression_run_id)
);

CREATE TABLE receipts (
    receipt_id uuid PRIMARY KEY,
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    receipt_type text NOT NULL,
    engine_source_hash text NOT NULL,
    output_hash text NOT NULL,
    payload jsonb NOT NULL,
    actor_id text NOT NULL REFERENCES developers(developer_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (workflow_id, segment_id, receipt_id),
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE TABLE publication_history (
    publication_id bigserial PRIMARY KEY,
    workflow_id text NOT NULL,
    segment_id text NOT NULL,
    receipt_id uuid NOT NULL REFERENCES receipts(receipt_id),
    action text NOT NULL,
    output_hash text NOT NULL,
    actor_id text NOT NULL REFERENCES developers(developer_id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id),
    CONSTRAINT publication_receipt_scope_fk
    FOREIGN KEY (workflow_id, segment_id, receipt_id)
        REFERENCES receipts(workflow_id, segment_id, receipt_id)
);

CREATE TABLE audit_ledger (
    sequence bigserial PRIMARY KEY,
    action text NOT NULL,
    actor_id text NOT NULL,
    machine_id uuid REFERENCES machines(machine_id),
    workflow_id text,
    segment_id text,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (segment_id IS NULL OR workflow_id IS NOT NULL),
    FOREIGN KEY (workflow_id, segment_id)
        REFERENCES segments(workflow_id, segment_id)
);

CREATE INDEX segments_workflow_segment_idx
    ON segments (workflow_id, segment_id);
CREATE INDEX editing_leases_active_scope_idx
    ON editing_leases (workflow_id, segment_id, expires_at);
CREATE INDEX editing_leases_expiry_cleanup_idx
    ON editing_leases (expires_at, workflow_id, segment_id);
CREATE INDEX jobs_claimable_idx
    ON jobs (priority DESC, available_at, created_at, job_id)
    WHERE status = 'queued';
CREATE INDEX worker_leases_expiry_idx ON worker_leases (expires_at);
CREATE INDEX event_revisions_chronology_idx
    ON event_revisions (
        workflow_id, segment_id, stream, event_key, created_at, event_revision_id
    );
CREATE INDEX state_snapshots_current_version_idx
    ON state_snapshots (workflow_id, segment_id, version DESC);
CREATE INDEX review_decisions_event_time_idx
    ON review_decisions (
        workflow_id, segment_id, proposal_key, created_at DESC, decision_id
    );
CREATE INDEX artifacts_provider_logical_hash_idx
    ON artifacts (provider_id, logical_key, content_hash);
CREATE INDEX artifacts_content_hash_idx
    ON artifacts (content_hash, provider_id, logical_key);
CREATE INDEX regression_runs_status_hash_idx
    ON regression_runs (
        workflow_id, status, engine_source_hash, started_at DESC
    );
CREATE INDEX regression_results_hash_idx
    ON regression_results (workflow_id, output_hash, created_at DESC)
    WHERE output_hash IS NOT NULL;
CREATE INDEX publications_workflow_segment_time_idx
    ON publication_history (
        workflow_id, segment_id, created_at DESC, publication_id
    );
CREATE INDEX audit_actor_machine_time_idx
    ON audit_ledger (actor_id, machine_id, created_at DESC, sequence);
CREATE INDEX audit_workflow_segment_time_idx
    ON audit_ledger (
        workflow_id, segment_id, created_at DESC, sequence
    )
    WHERE workflow_id IS NOT NULL;

CREATE FUNCTION coordination_reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER event_revisions_append_only
    BEFORE UPDATE OR DELETE ON event_revisions
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
CREATE TRIGGER review_activity_append_only
    BEFORE UPDATE OR DELETE ON review_activity
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
CREATE TRIGGER review_decisions_append_only
    BEFORE UPDATE OR DELETE ON review_decisions
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
CREATE TRIGGER engine_verdicts_append_only
    BEFORE UPDATE OR DELETE ON engine_verdicts
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
CREATE TRIGGER engine_confirmations_append_only
    BEFORE UPDATE OR DELETE ON engine_confirmations
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
CREATE TRIGGER output_fingerprints_append_only
    BEFORE UPDATE OR DELETE ON output_fingerprints
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
CREATE TRIGGER job_stages_append_only
    BEFORE UPDATE OR DELETE ON job_stages
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
CREATE TRIGGER job_results_append_only
    BEFORE UPDATE OR DELETE ON job_results
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
CREATE TRIGGER regression_results_append_only
    BEFORE UPDATE OR DELETE ON regression_results
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
CREATE TRIGGER receipts_append_only
    BEFORE UPDATE OR DELETE ON receipts
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
CREATE TRIGGER publication_history_append_only
    BEFORE UPDATE OR DELETE ON publication_history
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
CREATE TRIGGER audit_ledger_append_only
    BEFORE UPDATE OR DELETE ON audit_ledger
    FOR EACH ROW EXECUTE FUNCTION coordination_reject_mutation();
