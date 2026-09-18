INSERT INTO workflows (
    workflow_id,
    display_name,
    artifact_namespace
) VALUES
    (
        'innovation_day_bac',
        'Innovation Day - Frozen BAC',
        'innovation'
    ),
    (
        'live_iteration_25',
        'Live - Raw-video pipeline',
        'live'
    )
ON CONFLICT (workflow_id) DO NOTHING;
