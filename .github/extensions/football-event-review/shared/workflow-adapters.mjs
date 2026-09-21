const common = {
  reviewDurationSeconds: [20, 30, 60],
  cameraSampleDurationSeconds: [30, 60],
};

export const innovationWorkflow = Object.freeze({
  ...common,
  key: "innovation",
  workflowId: "innovation_day_bac",
  canvasId: "football-event-review",
  displayName: "Innovation Day Football Event Review",
  description:
    "Review prepared Innovation Day segments with frozen BAC coordinates and the Innovation football engine.",
  defaultSegment: "segment-0540-060",
  theme: "innovation",
  themeColor: "#100d12",
  homeUrl: "http://127.0.0.1:8080/showcase/innovation-day/",
  homeLabel: "Back to Innovation Day",
  brandLead: "Xebia · Innovation Day",
  brandDetail: "Frozen BAC coordinates · Innovation engine",
  trackerLoadingLabel: "BAC coordinates: loading",
  scopeLabel: "Prepared Alfheim segments · BAC assisted",
  statisticsLabel: "Innovation segment statistics",
  statisticsTitle: "Match stats",
  conversationPrefix: "Innovation Copilot for ",
  processorScript: "process-alfheim-innovation-segment.py",
  processorArguments: ["--events-only"],
  preparationMessage:
    "AI and Copilot conversations are disabled. Next: run the BAC-assisted Innovation analysis.",
  processingMessage:
    "Starting BAC-assisted Innovation analysis. YOLO will derive player context from the prepared video, while Alfheim BAC supplies the ball coordinates. This does not launch an independent C# review. The Live ball tracker is not used.",
  recoveryMessage:
    "Starting BAC-assisted Innovation analysis. YOLO will derive player context from the prepared video, while Alfheim BAC supplies the ball coordinates. This does not launch an independent C# review. The Live ball tracker is not used.",
  detectionMessage:
    "Player detections come from the prepared raw video. Frozen BAC coordinates supply the ball path; the Live ball tracker is not used.",
  hiddenSegments: ["segment-0540-020"],
  segmentCatalogWorkflow: "innovation",
  statusPath: "/api/alfheim/innovation/status",
  analyzePath: "/api/alfheim/innovation/analyze",
  artifactNamespace: "innovation",
  stateDirectory: "event-review-state-innovation",
  launcherRegistry: ".football-event-review-urls.json",
  regressionRegistry: "innovation-regressions.json",
  coordinateMode: "frozen_bac",
  evidencePreparationEnabled: true,
  coordinateReviewEnabled: false,
  coordinateCorrectionEnabled: true,
  reviewerCorrectedDemoLayer: true,
  inspectionDetectionCaches: [
    "developer-runs/reviewed-23-ball-models/yolo26n/detections.jsonl",
  ],
  promptLabel: "Innovation Day Football Event Review Canvas",
  promptBoundary:
    "This is the BAC-assisted Innovation workflow. Never invoke Live Canvas actions, read Live review state, or use Live engine outputs.",
  disabledActionNames: [
    "update_ball_coordinate_batch",
    "reject_ball_coordinate_review",
    "confirm_ball_coordinate_review",
  ],
  engineFiles: [
    "src/football_poc/innovation_day_snapshot/snapshot-manifest.json",
    "src/football_poc/innovation_day_snapshot/match_state.py",
    "src/football_poc/innovation_day_snapshot/player_tracking.py",
    "src/football_poc/innovation_day_snapshot/possession.py",
    "scripts/process-alfheim-innovation-segment.py",
  ],
  trackerVersionFiles: [
    "src/football_poc/innovation_day_snapshot/snapshot-manifest.json",
  ],
  rulesEngineVersionFiles: [
    "src/football_poc/innovation_day_snapshot/snapshot-manifest.json",
    "src/football_poc/innovation_day_snapshot/match_state.py",
    "src/football_poc/innovation_day_snapshot/player_tracking.py",
    "src/football_poc/innovation_day_snapshot/possession.py",
  ],
  regressionTests: [
    "tests/test_innovation_day_snapshot.py",
    "tests/test_innovation_match_state_regression.py",
    "tests/test_innovation_possession_regression.py",
    "tests/test_innovation_review_regressions.py",
  ],
  palette: {
    backgroundDefault: "#100d12",
    backgroundSubtle: "#19131b",
    backgroundMuted: "#2a1c2c",
    borderDefault: "#4b354d",
    borderMuted: "#634566",
    panelBackground: "#161018",
    panelBorder: "#5b3e5f",
    nestedPanelBackground: "#0f0b11",
    nestedPanelBorder: "#6c4a70",
    textDefault: "#fbf8fb",
    textMuted: "#c5bac6",
    green: "#68e0c1",
    blue: "#ba4ca6",
    blueMuted: "#6c1d5f",
    focus: "#cf6fbe",
    bodyBackground:
      "radial-gradient(circle at 84% 2%, rgb(108 29 95 / 32%), transparent 34rem), linear-gradient(145deg, #100d12, #0c090e 74%)",
  },
});

export const liveWorkflow = Object.freeze({
  ...common,
  key: "live",
  workflowId: "live_iteration_25",
  canvasId: "football-event-review-live",
  displayName: "Live Football Event Review",
  description:
    "Review Alfheim segments with raw-video iteration-25 ball tracking and the current football engine.",
  defaultSegment: "segment-0540-020",
  theme: "grassroots",
  themeColor: "#080d14",
  homeUrl: "http://127.0.0.1:8080/",
  homeLabel: "Back to Product Home",
  brandLead: "",
  brandDetail: "Raw-video ball coordinates · Current engine",
  trackerLoadingLabel: "Ball tracker: loading",
  scopeLabel: "20–60 second Alfheim segments · Live pipeline",
  statisticsLabel: "Live segment statistics",
  statisticsTitle: "Live stats",
  conversationPrefix: "Live Copilot for ",
  processorScript: "process-alfheim-segment.py",
  processorArguments: ["--artifact-namespace", "live", "--events-only"],
  preparationMessage:
    "AI and Copilot conversations are disabled. Next: start the full raw-video AI run.",
  processingMessage:
    "Starting a local rerun from the raw video. Existing detections, ball coordinates, tracks, events, review labels, and provider annotations will not be used. This does not invoke Copilot.",
  recoveryMessage:
    "Resuming after interrupted processing. Completed raw-video detections are preserved; ball coordinates and every later artifact will be rebuilt. This is not a cold-path benchmark and does not invoke Copilot.",
  detectionMessage:
    "No prior detections, ball/player tracks, events, review labels, or provider annotations are used. Next: build ball coordinates.",
  hiddenSegments: [],
  segmentCatalogWorkflow: "live",
  statusPath: "/api/alfheim/live/status",
  analyzePath: "/api/alfheim/live/analyze",
  artifactNamespace: "live",
  stateDirectory: "event-review-state-live",
  launcherRegistry: ".football-event-review-live-urls.json",
  regressionRegistry: "live-regressions.json",
  coordinateMode: "raw_video",
  evidencePreparationEnabled: false,
  coordinateReviewEnabled: true,
  coordinateCorrectionEnabled: true,
  reviewerCorrectedDemoLayer: false,
  promptLabel: "Live Football Event Review Canvas",
  promptBoundary:
    "This is the raw-video iteration-25 live workflow. Never invoke Innovation Canvas actions, read Innovation review state, or use Innovation/BAC engine outputs.",
  disabledActionNames: [],
  engineFiles: [
    "src/football_poc/ball_tracking.py",
    "src/football_poc/match_state.py",
    "src/football_poc/player_tracking.py",
    "src/football_poc/possession.py",
    "scripts/process-alfheim-segment.py",
  ],
  trackerVersionFiles: [
    "src/football_poc/ball_tracking.py",
  ],
  rulesEngineVersionFiles: [
    "src/football_poc/match_state.py",
    "src/football_poc/player_tracking.py",
    "src/football_poc/possession.py",
  ],
  regressionTests: [
    "tests/test_ball_tracking.py",
    "tests/test_match_state.py",
    "tests/test_possession.py",
    "tests/test_live_review_regressions.py",
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

export function workflowAdapter(key) {
  if (key === "innovation") return innovationWorkflow;
  if (key === "live") return liveWorkflow;
  throw new Error(`Unknown football review workflow: ${key}`);
}
