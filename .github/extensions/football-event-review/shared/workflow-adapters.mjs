const common = {
  reviewDurationSeconds: [20, 30, 60],
  cameraSampleDurationSeconds: [30, 60],
};

export const reviewWorkflow = Object.freeze({
  ...common,
  key: "review",
  workflowId: "football_review",
  canvasId: "football-event-review",
  displayName: "Football Event Review",
  description:
    "Review prepared Alfheim segments with selectable BAC diagnostics or raw-video ball tracking.",
  defaultSegment: "segment-0540-020",
  theme: "grassroots",
  themeColor: "#080d14",
  homeUrl: "http://127.0.0.1:8080/",
  homeLabel: "Back to Product Home",
  brandLead: "",
  brandDetail: "BAC diagnostics or raw-video ball coordinates · Current engine",
  trackerLoadingLabel: "Ball coordinates: loading",
  scopeLabel: "20–60 second Alfheim segments · single review workflow",
  statisticsLabel: "Segment statistics",
  statisticsTitle: "Match stats",
  conversationPrefix: "Football Review for ",
  processorScript: "process-alfheim-segment.py",
  processorArguments: ["--events-only"],
  preparationMessage:
    "AI and Copilot conversations are disabled. Next: run ball coordinates.",
  processingMessage:
    "Starting ball-coordinate processing for the selected source. BAC runs are BAC-assisted diagnostics only; Detected runs are raw-video cold runs.",
  recoveryMessage:
    "Resuming from saved detections for a raw-video run. This is not a cold-path benchmark and does not invoke Copilot.",
  detectionMessage:
    "Runtime detections and ball-coordinate artifacts are built from the selected source without using review labels or provider event annotations.",
  hiddenSegments: [],
  statusPath: "/api/alfheim/status",
  analyzePath: "/api/alfheim/analyze",
  launcherRegistry: ".football-event-review-urls.json",
  regressionRegistry: "review-regressions.json",
  manualReferenceEnabled: true,
  evidencePreparationEnabled: true,
  coordinateReviewEnabled: true,
  coordinateCorrectionEnabled: true,
  reviewerCorrectedDemoLayer: true,
  analyticsEventTypes: ["completed_pass", "turnover", "shot_on_target"],
  shotsOnTargetCapable: true,
  inspectionDetectionCaches: [
    "developer-runs/reviewed-23-ball-models/yolo26n/detections.jsonl",
  ],
  promptLabel: "Football Event Review Canvas",
  promptBoundary:
    "This is the single Football Event Review workflow. Keep BAC-assisted diagnostics and raw-video ball-tracker evidence explicitly labelled by ball source; never use review labels or provider events as inference inputs.",
  disabledActionNames: [],
  engineFiles: [
    "src/football_poc/match_state.py",
    "src/football_poc/player_tracking.py",
    "src/football_poc/possession.py",
    "src/football_poc/engine/",
    "src/football_poc/possession_cli.py",
    "src/football_poc/shots_on_target.py",
    "src/football_poc/goal_calibration.py",
    "src/football_poc/shot_evidence_adapter.py",
    "src/football_poc/bac_ball_tracks.py",
    "src/football_poc/ball_tracking.py",
    "src/football_poc/ball/",
    "scripts/process-alfheim-segment.py",
  ],
  trackerVersionFiles: [
    "src/football_poc/bac_ball_tracks.py",
    "src/football_poc/ball_tracking.py",
    "src/football_poc/ball/",
  ],
  rulesEngineVersionFiles: [
    "src/football_poc/match_state.py",
    "src/football_poc/player_tracking.py",
    "src/football_poc/possession.py",
    "src/football_poc/engine/",
    "src/football_poc/possession_cli.py",
    "src/football_poc/shots_on_target.py",
    "src/football_poc/goal_calibration.py",
    "src/football_poc/shot_evidence_adapter.py",
  ],
  // Rules-engine regressions run on cached ball tracks. Ball coordinates are
  // already gated (BAC frozen, detected >= 90% direct provenance) before the
  // rules engine runs, so only these files scope the Canvas regression gate.
  rulesRegressionScopeFiles: [
    "src/football_poc/match_state.py",
    "src/football_poc/player_tracking.py",
    "src/football_poc/possession.py",
    "src/football_poc/engine/",
    "src/football_poc/possession_cli.py",
    "src/football_poc/shots_on_target.py",
    "src/football_poc/goal_calibration.py",
    "src/football_poc/shot_evidence_adapter.py",
    "scripts/process-alfheim-segment.py",
  ],
  // Routine acceptance gate: fast rule unit tests (seconds). New rules add a
  // timestamped test under tests/rules or tests/tracking (see
  // tests/RULE_INDEX.md). Published-segment reruns are on demand only.
  regressionTests: [
    "tests/rules",
    "tests/tracking",
    "tests/test_rule_index.py",
    "tests/test_possession.py",
    "tests/test_match_state.py",
    "tests/test_player_tracking.py",
    "tests/test_shots_on_target.py",
    "tests/test_shot_evidence.py",
    "tests/test_possession_regression.py",
    "tests/test_match_state_regression.py",
    "tests/test_review_regressions.py",
  ],
  // Fast ball-tracker gate for tracker changes: timestamped unit tests.
  // The full-video stage goldens (tests/ball_stages, ~18 min) are opt-in via
  // FOOTBALL_RUN_BALL_GOLDENS=1 and reserved for refactors.
  trackerRegressionTests: [
    "tests/tracking",
    "tests/test_ball_tracking.py",
  ],
  palette: {
    backgroundDefault: "#080d14",
    backgroundSubtle: "#101923",
    backgroundMuted: "#162536",
    borderDefault: "#2b4a68",
    borderMuted: "#3a6287",
    panelBackground: "#0b141f",
    panelBorder: "#315f86",
    nestedPanelBackground: "#08111b",
    nestedPanelBorder: "#497ca6",
    textDefault: "#eef6ff",
    textMuted: "#adbecd",
    green: "#68e0aa",
    blue: "#78bfff",
    blueMuted: "#315f86",
    focus: "#78bfff",
    bodyBackground:
      "radial-gradient(circle at 8% 8%, rgb(120 191 255 / 14%), transparent 30rem), radial-gradient(circle at 90% 88%, rgb(91 141 239 / 11%), transparent 32rem), linear-gradient(145deg, #101a27, #05080d 72%)",
  },
});

export function workflowAdapter() {
  return reviewWorkflow;
}
