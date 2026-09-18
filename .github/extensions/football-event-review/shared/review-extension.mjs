import { createHash, randomUUID } from "node:crypto";
import { execFile, execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import {
  mkdir,
  open,
  readFile,
  rename,
  stat,
  unlink,
  writeFile,
} from "node:fs/promises";
import { createServer } from "node:http";
import { homedir } from "node:os";
import {
  dirname,
  join,
  relative,
  resolve,
} from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

import {
  CanvasError,
  createCanvas,
  joinSession,
} from "@github/copilot-sdk/extension";

import {
  engineVerificationReceipt,
  hasReviewHistory,
  isRegressionCurrent,
  isVerificationCurrent,
  matchingStoredSnapshot,
  referenceStoredSnapshot,
  requiresEngineImplementationChange,
  storedSnapshots,
} from "../engine-freshness.mjs";
import {
  buildPublicationPlan as buildInnovationPublicationPlan,
} from "../publication-gate.mjs";
import {
  buildPublicationPlan as buildLivePublicationPlan,
} from "../../football-event-review-live/publication-gate.mjs";
import { renderHtml } from "./review-renderer.mjs";
import { workflowAdapter } from "./workflow-adapters.mjs";

const extensionRoot = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(extensionRoot, "..", "..", "..", "..");
const workflow = workflowAdapter(globalThis.__footballReviewWorkflowKey);
delete globalThis.__footballReviewWorkflowKey;
const buildPublicationPlan = workflow.key === "innovation"
  ? buildInnovationPublicationPlan
  : buildLivePublicationPlan;
const alfheimRoot = join(projectRoot, "benchmarks", "alfheim");
const generatedRoot = join(alfheimRoot, "generated");
const soccertrackReviewRoot = join(
  projectRoot,
  "benchmarks",
  "soccertrack-117093-preview",
);
const sharedArtifactRoot = (() => {
  const configured = String(
    process.env.FOOTBALL_ARTIFACT_ROOT || "",
  ).trim();
  if (configured) return resolve(configured);
  const oneDrive = String(
    process.env.ONEDRIVECOMMERCIAL || process.env.ONEDRIVE || "",
  ).trim();
  const candidate = oneDrive
    ? join(oneDrive, "Innovationday Artifacts")
    : "";
  return candidate && existsSync(
    join(candidate, "00-governance", "checksums.sha256"),
  )
    ? candidate
    : null;
})();
const customCameraSourceRoot = sharedArtifactRoot
  ? join(sharedArtifactRoot, "10-master-data", "custom-cameras")
  : null;
const customCameraRunRoot = join(
  projectRoot,
  "benchmarks",
  "custom-cameras",
);
const defaultSegment = workflow.defaultSegment;
const workflowId = workflow.workflowId;
const canvasId = workflow.canvasId;
const disabledActions = new Set(workflow.disabledActionNames);
const localServer = "http://127.0.0.1:8080";
const reviewDurationSeconds = workflow.reviewDurationSeconds;
const cameraSampleDurationSeconds = workflow.cameraSampleDurationSeconds;
const engineFiles = workflow.engineFiles;
const trackerVersionFiles = workflow.trackerVersionFiles;
const rulesEngineVersionFiles = workflow.rulesEngineVersionFiles;
const servers = new Map();
let launcherRegistryUpdate = Promise.resolve();
let adapterRegistryUpdate = Promise.resolve();
const launcherRegistryPath = join(
  projectRoot,
  "benchmarks",
  "alfheim",
  "generated",
  workflow.launcherRegistry,
);
const activeAdapterRegistryPath = join(
  generatedRoot,
  ".football-event-review-active-adapters.json",
);
const regressionRegistryPath = join(
  alfheimRoot,
  workflow.regressionRegistry,
);
const eventStreams = new Set();
let stateSaveQueue = Promise.resolve();
const coordinationSessions = new Map();
let lastConversationContext = null;
let activity = {
  state: "ready",
  label: "Ready for your review",
  detail: "Select an event, discuss it, or record your decision.",
};

const test3Drafts = [
  {
    seconds: 3.8,
    team: "red",
    type: "completed_pass",
    title: "Red goalkeeper completed pass to headed receiver",
    evidence: "The red/white goalkeeper's aerial delivery is completed when "
      + "a red/white teammate controls it with the header at 3.800s. The "
      + "header is the receiving action, not a second pass.",
    rule: "Credit the player who released the ball; confirm completion on "
      + "the receiving teammate's first controlled touch.",
  },
  {
    seconds: 5.0,
    team: "red",
    type: "turnover",
    title: "Red/white turnover",
    evidence: "Black establishes controlled possession after the opening contest.",
    rule: "A turnover belongs to the team that loses possession when an opponent gains control.",
  },
  {
    seconds: 5.2,
    team: "black",
    type: "completed_pass",
    title: "First short black pass",
    evidence: "A direction-supported black touch reaches a different black controller.",
    rule: "Short and one-touch exchanges count when the next controlled touch is by a teammate.",
  },
  {
    seconds: 6.0,
    team: "black",
    type: "completed_pass",
    title: "Black return pass",
    evidence: "The return touch reaches the prior black player under control.",
    rule: "A return pass is counted independently at the receiver's first control.",
  },
  {
    seconds: 7.8,
    team: "black",
    type: "turnover",
    title: "Black turnover",
    evidence: "The contested ball decelerates and red/white subsequently establishes control.",
    rule: "A challenge is not itself a turnover; confirmed opponent control completes it.",
  },
  {
    seconds: 21.256,
    team: null,
    type: "foul_encountered",
    title: "Foul stoppage",
    evidence: "Competitive play stops and the later black ball movement is repositioning.",
    rule: "A foul stops live event tracking without creating a turnover.",
    behavior: {
      kind: "match_state",
      state: "restart_pending",
      from: 19.4,
      to: 25.6,
    },
  },
  {
    seconds: 27.4,
    team: "black",
    type: "completed_pass",
    title: "Free-kick restart pass",
    evidence: "The genuine restart kick is controlled by a black teammate.",
    rule: "A free kick counts as a completed pass when a teammate controls the genuine restart.",
  },
  {
    seconds: 32.0,
    team: "black",
    type: "completed_pass",
    title: "Black completed pass",
    evidence: "The released ball reaches controlled possession by another black player.",
    rule: "Completion time is the receiving teammate's first controlled touch.",
  },
  {
    seconds: 35.0,
    team: "black",
    type: "completed_pass",
    title: "Short black completed pass",
    evidence: "A short release reaches a different black controller.",
    rule: "Distance does not determine whether a controlled teammate reception is a pass.",
  },
  {
    seconds: 46.4,
    team: "black",
    type: "completed_pass",
    title: "Black restart reception",
    evidence: "After the ball leaves play, the same team restarts and a teammate controls it.",
    rule: "A legal restart counts as a pass when its first controlled reception is by a teammate.",
  },
  {
    seconds: 49.2,
    team: "black",
    type: "completed_pass",
    title: "Black retained-possession pass",
    evidence: "Black releases to a teammate who establishes control.",
    rule: "A later loss does not cancel a previously completed pass.",
  },
  {
    seconds: 51.4,
    team: "black",
    type: "turnover",
    title: "Black loses possession",
    evidence: "Red/white sustains control after the black possession phase.",
    rule: "Transient challenges are ignored; sustained opponent control completes the turnover.",
  },
  {
    seconds: 54.4,
    team: "red",
    type: "turnover",
    title: "Red/white loses possession",
    evidence: "Black regains and sustains control.",
    rule: "The team losing possession receives the turnover event.",
  },
  {
    seconds: 56.6,
    team: "black",
    type: "completed_pass",
    title: "Final black completed pass",
    evidence: "The ball transfers between two black controlled-player tracks.",
    rule: "Track changes count only when ball movement and control support a real transfer.",
  },
];

export const innovationManualSeed = [
  ...[3.030, 4.920, 8.100, 10.510, 12.950].map((seconds) => (
    {seconds, team: "black", type: "completed_pass"}
  )),
  {seconds: 16.660, team: "black", type: "turnover"},
  {seconds: 18.180, team: "red", type: "completed_pass"},
  {seconds: 20.330, team: "red", type: "turnover"},
  ...[21.760, 22.700, 24.530, 25.920, 28.630, 34.520, 36.380,
    39.770, 41.600, 42.550].map((seconds) => (
    {seconds, team: "black", type: "completed_pass"}
  )),
  {seconds: 46.180, team: "black", type: "turnover"},
  {seconds: 50.110, team: "red", type: "turnover"},
  ...[52.880, 54.740, 57.210].map((seconds) => (
    {seconds, team: "black", type: "completed_pass"}
  )),
  {seconds: 58.920, team: "black", type: "turnover"},
  {seconds: 60.000, team: "red", type: "completed_pass"},
];

function manualEvent(input, key, revision = 1) {
  const timestampMs = Math.round(Number(input.timestampMs ?? input.seconds * 1000));
  const reviewStatus = input.reviewStatus === "rejected"
    ? "rejected"
    : "active";
  return {
    key,
    timestampMs,
    seconds: timestampMs / 1000,
    sourceFrame: Math.min(1499, Math.round(timestampMs * 25 / 1000)),
    team: input.team,
    type: input.type ?? input.eventType,
    revision,
    active: reviewStatus === "active" && input.active !== false,
    deleted: input.deleted === true,
    reviewStatus,
    rejectedAt: reviewStatus === "rejected" ? input.rejectedAt || null : null,
    source: "manual_review",
  };
}

function activeManualEvents(reference) {
  return (reference?.events || [])
    .filter((event) =>
      event.active
      && !event.deleted
      && event.reviewStatus !== "rejected"
    )
    .sort((left, right) =>
      left.timestampMs - right.timestampMs || left.key.localeCompare(right.key)
    );
}

function visibleManualEvents(reference) {
  return (reference?.events || [])
    .filter((event) =>
      !event.deleted
      && (event.active || event.reviewStatus === "rejected")
    )
    .sort((left, right) =>
      left.timestampMs - right.timestampMs || left.key.localeCompare(right.key)
    );
}

export function ensureInnovationManualReference(state, segment) {
  if (!state.manualReference) {
    const legacy = (state.additionalProposals || [])
      .filter((proposal) =>
        ["manual_review", "user_reported"].includes(proposal.source)
      );
    const seed = segment === "segment-0080-020" && legacy.length === 0
      ? innovationManualSeed
      : legacy;
    state.manualReference = {
      revision: seed.length ? 1 : 0,
      events: seed.map((event, index) => manualEvent(event, `M${index + 1}`)),
      mappings: {},
      audit: seed.length
        ? [{
            revision: 1,
            action: segment === "segment-0080-020" ? "seed" : "migrate",
            at: new Date().toISOString(),
          }]
        : [],
      approved: null,
      approvalHistory: [],
      undoStack: [],
    };
    const legacyIndexState = {
      decisions: {...(state.decisions || {})},
      proposalOverrides: {...(state.proposalOverrides || {})},
      sameFrameReviewRequirements: {
        ...(state.sameFrameReviewRequirements || {}),
      },
      copilotAcceptanceAuthorizations: {
        ...(state.copilotAcceptanceAuthorizations || {}),
      },
    };
    if (Object.values(legacyIndexState).some(
      (value) => Object.keys(value).length
    )) {
      state.legacyCopilotDiagnostics = {
        ...(state.legacyCopilotDiagnostics || {}),
        indexState: legacyIndexState,
        migratedAt: new Date().toISOString(),
      };
    }
    state.decisions = {};
    state.proposalOverrides = {};
    state.sameFrameReviewRequirements = {};
    state.copilotAcceptanceAuthorizations = {};
    state.manualFirstMigratedAt = new Date().toISOString();
    if (legacy.length) {
      state.additionalProposals = (state.additionalProposals || []).filter(
        (proposal) =>
          !["manual_review", "user_reported"].includes(proposal.source)
      );
    }
    return true;
  }
  state.manualReference.events ||= [];
  state.manualReference.mappings ||= {};
  state.manualReference.audit ||= [];
  state.manualReference.approvalHistory ||= [];
  state.manualReference.undoStack ||= [];
  state.manualReference.revision ||= 0;
  let changed = false;
  if (!state.manualFirstMigratedAt) {
    const legacyIndexState = {
      decisions: {...(state.decisions || {})},
      proposalOverrides: {...(state.proposalOverrides || {})},
      sameFrameReviewRequirements: {
        ...(state.sameFrameReviewRequirements || {}),
      },
      copilotAcceptanceAuthorizations: {
        ...(state.copilotAcceptanceAuthorizations || {}),
      },
    };
    if (Object.values(legacyIndexState).some(
      (value) => Object.keys(value).length
    )) {
      state.legacyCopilotDiagnostics = {
        ...(state.legacyCopilotDiagnostics || {}),
        indexState: legacyIndexState,
        migratedAt: new Date().toISOString(),
      };
    }
    state.decisions = {};
    state.proposalOverrides = {};
    state.sameFrameReviewRequirements = {};
    state.copilotAcceptanceAuthorizations = {};
    state.manualFirstMigratedAt = new Date().toISOString();
    changed = true;
  }
  if (
    segment === "segment-0080-020"
    && state.manualReference.events.length === 0
    && state.manualReference.revision === 0
    && !state.manualReference.approved
  ) {
    state.manualReference.events = innovationManualSeed.map(
      (event, index) => manualEvent(event, `M${index + 1}`)
    );
    state.manualReference.revision = 1;
    state.manualReference.audit.push({
      revision: 1,
      action: "seed",
      at: new Date().toISOString(),
    });
    changed = true;
  }
  return changed;
}

function snapshotManualReference(reference) {
  return {
    events: reference.events.map((event) => ({...event})),
    mappings: {...reference.mappings},
  };
}

function appendManualRevision(reference, action, detail, before) {
  reference.revision += 1;
  reference.undoStack ||= [];
  reference.undoStack.push(before);
  reference.audit.push({
    revision: reference.revision,
    action,
    detail,
    at: new Date().toISOString(),
    before,
  });
}

export function suggestManualMappings(manualEvents, engineEvents) {
  const maximumDeltaMs = 1000;
  const result = {};
  const active = [...manualEvents]
    .filter((event) => event.active && !event.deleted)
    .sort((left, right) => left.timestampMs - right.timestampMs);
  const candidatesByManual = new Map(active.map((manual) => [
    manual.key,
    engineEvents
      .map((engine, index) => ({
        engine,
        key: engine.key || `E${index + 1}`,
      }))
      .filter((candidate) =>
        candidate.engine.team === manual.team
        && candidate.engine.type === manual.type
        && Math.abs(
          Math.round(candidate.engine.seconds * 1000) - manual.timestampMs
        ) <= maximumDeltaMs
      ),
  ]));
  const engineCandidateCounts = new Map();
  candidatesByManual.forEach((candidates) => {
    candidates.forEach((candidate) => {
      engineCandidateCounts.set(
        candidate.key,
        Number(engineCandidateCounts.get(candidate.key) || 0) + 1,
      );
    });
  });
  active.forEach((manual) => {
    const candidates = candidatesByManual.get(manual.key) || [];
    if (
      candidates.length !== 1
      || engineCandidateCounts.get(candidates[0].key) !== 1
    ) return;
    const selected = candidates[0];
    const deltaSeconds = selected.engine.seconds - manual.seconds;
    result[manual.key] = {
      engineKey: selected.key,
      deltaSeconds,
      highConfidence: true,
      exact: Math.round(deltaSeconds * 1000) === 0,
      withinTolerance: true,
      teamConflict: false,
      typeConflict: false,
    };
  });
  return result;
}

export function publicManualReferenceState(
  workflowKey,
  state,
  copilotEvents,
  engineEvents,
) {
  if (workflowKey !== "innovation") {
    return {
      manualEvents: [],
      rejectedManualEvents: [],
      copilotEvents: [],
      manualReference: null,
    };
  }
  const manualEvents = activeManualEvents(state.manualReference);
  const rejectedManualEvents = visibleManualEvents(state.manualReference)
    .filter((event) => event.reviewStatus === "rejected");
  return {
    manualEvents,
    rejectedManualEvents,
    copilotEvents: copilotEvents.map(
      (event, index) => ({...event, key: `C${index + 1}`})
    ),
    manualReference: {
      revision: state.manualReference.revision,
      mappings: {...state.manualReference.mappings},
      suggestions: suggestManualMappings(
        manualEvents,
        engineEvents,
      ),
      audit: state.manualReference.audit,
      canUndo: Boolean(state.manualReference.undoStack?.length),
      approved: state.manualReference.approved,
      approvalHistory: state.manualReference.approvalHistory,
    },
  };
}

export function mutateInnovationManualReference(reference, mutation) {
  const before = snapshotManualReference(reference);
  const active = activeManualEvents(reference);
  const findEvent = () => reference.events.find(
    (event) => event.key === mutation.manualKey
  );
  if (mutation.action === "create") {
    const nextNumber = reference.events.reduce(
      (maximum, event) =>
        Math.max(maximum, Number(String(event.key).replace(/^M/, "")) || 0),
      0,
    ) + 1;
    const event = manualEvent(mutation, `M${nextNumber}`);
    reference.events.push(event);
    appendManualRevision(reference, "create", {manualKey: event.key}, before);
    return event;
  }
  if (mutation.action === "edit") {
    const event = findEvent();
    if (!event || !event.active || event.deleted) throw new Error("Unknown active M#");
    const replacement = manualEvent(
      {...event, ...mutation},
      event.key,
      Number(event.revision || 0) + 1,
    );
    Object.assign(event, replacement);
    appendManualRevision(reference, "edit", {manualKey: event.key}, before);
    return event;
  }
  if (mutation.action === "delete") {
    const event = findEvent();
    if (
      !event
      || event.deleted
      || (!event.active && event.reviewStatus !== "rejected")
    ) throw new Error("Unknown visible M#");
    event.active = false;
    event.deleted = true;
    event.reviewStatus = "removed";
    event.rejectedAt = null;
    event.revision = Number(event.revision || 0) + 1;
    delete reference.mappings[event.key];
    appendManualRevision(reference, "delete", {manualKey: event.key}, before);
    return event;
  }
  if (mutation.action === "reject") {
    const event = findEvent();
    if (!event || !event.active || event.deleted) throw new Error("Unknown active M#");
    event.active = false;
    event.deleted = false;
    event.reviewStatus = "rejected";
    event.rejectedAt = new Date().toISOString();
    event.revision = Number(event.revision || 0) + 1;
    delete reference.mappings[event.key];
    appendManualRevision(reference, "reject", {manualKey: event.key}, before);
    return event;
  }
  if (mutation.action === "restore") {
    const event = findEvent();
    if (
      !event
      || event.deleted
      || event.reviewStatus !== "rejected"
    ) throw new Error("Unknown rejected M#");
    event.active = true;
    event.reviewStatus = "active";
    event.rejectedAt = null;
    event.revision = Number(event.revision || 0) + 1;
    appendManualRevision(reference, "restore", {manualKey: event.key}, before);
    return event;
  }
  if (mutation.action === "map") {
    const event = findEvent();
    if (!event || !event.active || event.deleted) throw new Error("Unknown active M#");
    const engineKey = String(mutation.engineKey || "");
    if (!/^E[1-9]\d*$/.test(engineKey)) throw new Error("Unknown E#");
    Object.entries(reference.mappings).forEach(([manualKey, mappedEngine]) => {
      if (manualKey !== event.key && mappedEngine === engineKey) {
        delete reference.mappings[manualKey];
      }
    });
    reference.mappings[event.key] = engineKey;
    appendManualRevision(
      reference,
      "map",
      {manualKey: event.key, engineKey},
      before,
    );
    return event;
  }
  if (mutation.action === "unmap") {
    const event = findEvent();
    if (!event) throw new Error("Unknown M#");
    delete reference.mappings[event.key];
    appendManualRevision(reference, "unmap", {manualKey: event.key}, before);
    return event;
  }
  if (mutation.action === "undo") {
    const previous = reference.undoStack?.pop();
    if (!previous) throw new Error("There is no manual change to undo");
    reference.events = previous.events.map((event) => ({...event}));
    reference.mappings = {...previous.mappings};
    reference.revision += 1;
    reference.audit.push({
      revision: reference.revision,
      action: "undo",
      at: new Date().toISOString(),
    });
    return null;
  }
  if (mutation.action === "approve") {
    const events = active.map((event) => ({...event}));
    const mappings = {...reference.mappings};
    const approvedAt = new Date().toISOString();
    const fingerprint = createHash("sha256").update(
      JSON.stringify({events, mappings}),
    ).digest("hex");
    if (reference.approved) {
      reference.approvalHistory.push({...reference.approved});
    }
    reference.revision += 1;
    reference.approved = {
      revision: reference.revision,
      fingerprint,
      approvedAt,
      events,
      mappings,
    };
    reference.audit.push({
      revision: reference.revision,
      action: "approve",
      at: approvedAt,
    });
    reference.undoStack = [];
    return reference.approved;
  }
  if (mutation.action === "reopen") {
    if (!reference.approved) throw new Error("The minute is not approved");
    reference.approvalHistory.push({...reference.approved});
    reference.approved = null;
    reference.revision += 1;
    reference.undoStack = [];
    reference.audit.push({
      revision: reference.revision,
      action: "reopen",
      at: new Date().toISOString(),
      nonUndoable: true,
    });
    return null;
  }
  throw new Error("Unsupported manual-reference action");
}
let session;
let reviewRequestPending = false;
let registeredCanvasActions = [];
const activeSegmentRegressions = new Set();
const segmentRegressionProgress = new Map();
const segmentRegressionJobs = new Map();
const execFileAsync = promisify(execFile);

function startSegmentRegressionProgress(segment) {
  const progress = {
    segment,
    status: "running",
    startedAt: new Date().toISOString(),
    completedAt: null,
    message: null,
    steps: [
      {key: "baseline", label: "Verify published baseline", status: "running"},
      {
        key: "engine",
        label: "Run cached Innovation rules engine",
        status: "waiting",
      },
      {
        key: "compare",
        label: "Compare current and published outputs",
        status: "waiting",
      },
      {key: "persist", label: "Save regression result", status: "waiting"},
      {
        key: "restore",
        label: "Restore trusted published output",
        status: "waiting",
      },
    ],
  };
  segmentRegressionProgress.set(segment, progress);
  return progress;
}

function updateSegmentRegressionProgress(
  progress,
  stepKey,
  status,
  message = null,
) {
  const step = progress.steps.find((candidate) => candidate.key === stepKey);
  if (step) step.status = status;
  if (message !== null) progress.message = message;
}

function publicSegmentRegressionProgress() {
  return Object.fromEntries(
    [...segmentRegressionProgress.entries()].map(([segment, progress]) => [
      segment,
      {
        ...progress,
        steps: progress.steps.map((step) => ({...step})),
      },
    ]),
  );
}

function preparedSegmentRoot(segment) {
  return segment === "alfheim-window-555"
    ? join(alfheimRoot, "window-555")
    : join(generatedRoot, segment);
}

function segmentRoot(segment) {
  return join(preparedSegmentRoot(segment), workflow.artifactNamespace);
}

async function liveStageTiming(selected) {
  const stageKey = {
    detecting: "detection",
    ball_track: "ball_tracking",
    tracking: "player_tracking",
    events: "event_inference",
    publishing: "chunk_publication",
  }[selected.stage];
  if (!stageKey) return null;

  const statusPath = join(segmentRoot(selected.key), "analysis-status.json");
  const baseline = await readJson(
    join(
      segmentRoot(defaultSegment),
      "analytics-data",
      "performance-report.json",
    ),
    null,
  );
  if (!baseline?.stage_seconds?.[stageKey] || !baseline.sampled_frames) {
    return null;
  }

  let statusMetadata;
  let rawStatus;
  try {
    [statusMetadata, rawStatus] = await Promise.all([
      stat(statusPath),
      readJson(statusPath, {}),
    ]);
  } catch {
    return null;
  }

  const frameScale = Math.max(
    1,
    Number(selected.expectedFrames || baseline.sampled_frames)
      / Number(baseline.sampled_frames),
  );
  const precedingStages = {
    ball_tracking: ["detection"],
    player_tracking: ["detection", "ball_tracking"],
    event_inference: ["detection", "ball_tracking", "player_tracking"],
    chunk_publication: [
      "detection",
      "ball_tracking",
      "player_tracking",
      "event_inference",
    ],
  }[stageKey] || [];
  const baselineBeforeStage = precedingStages.reduce(
    (total, key) => total + Number(baseline.stage_seconds?.[key] || 0),
    0,
  ) * frameScale;
  const observedBeforeStage = Number(rawStatus?.elapsed_seconds || 0);
  const runRateAdjustment = baselineBeforeStage > 0
    ? Math.min(4, Math.max(0.5, observedBeforeStage / baselineBeforeStage))
    : 1;

  return {
    startedAtUtc: statusMetadata.mtime.toISOString(),
    estimatedSeconds: Math.round(
      Number(baseline.stage_seconds[stageKey])
      * frameScale
      * runRateAdjustment,
    ),
    basisSegment: defaultSegment,
    runRateAdjustment: Number(runRateAdjustment.toFixed(2)),
  };
}

function copilotReviewPath(segment) {
  return join(preparedSegmentRoot(segment), "copilot-review.json");
}

function formatClock(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds - minutes * 60;
  return `${String(minutes).padStart(2, "0")}:${
    String(seconds).padStart(2, "0")
  }`;
}

async function loadPreparedSegments() {
  const response = await fetch(
    `${localServer}/api/alfheim/segments?workflow=${workflow.segmentCatalogWorkflow}`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Prepared-segment API returned HTTP ${response.status}`);
  }
  const payload = await response.json();
  const hiddenSegments = new Set(workflow.hiddenSegments || []);
  return payload.segments
    .filter((segment) => !hiddenSegments.has(segment.cache_key))
    .map((segment) => {
      const start = Number(segment.source_start_seconds);
      const duration = Number(segment.duration_seconds);
      const validationStatus = segment.validated
        ? "passed"
        : segment.cache_key === defaultSegment
          ? "in_review"
          : segment.state === "ready" ? "ai_ready" : segment.state;
      return {
        key: segment.cache_key,
        datasetId: segment.dataset_id,
        datasetName: segment.dataset_name,
        clubId: segment.club_id,
        clubName: segment.club_name,
        venueId: segment.venue_id,
        venueName: segment.venue_name,
        cameraId: segment.camera_id,
        cameraName: segment.camera_name,
        cameraPosition: segment.camera_position,
        serialNumber: segment.serial_number,
        serialSource: segment.serial_source,
        recordingId: segment.recording_id,
        calibrationId: segment.calibration_id,
        calibrationStatus: segment.calibration_status,
        imageWidth: Number(segment.image_width || 0),
        imageHeight: Number(segment.image_height || 0),
        attribution: segment.attribution,
        processingSupported: Boolean(segment.processing_supported),
        preparationSupported: Boolean(segment.preparation_supported),
        evidencePreparationSupported: Boolean(
          segment.evidence_preparation_supported,
        ),
        evidenceReady: Boolean(segment.evidence_ready),
        processedFrames: Number(segment.processed_frames || 0),
        expectedFrames: Number(segment.expected_frames || 0),
        stage: segment.stage || null,
        statusMessage: segment.message || null,
        runProvenance: segment.run_provenance || null,
        performance: segment.performance || null,
        startSeconds: start,
        durationSeconds: duration,
        timeLabel: `${formatClock(start)}–${formatClock(start + duration)}`,
        state: segment.state,
        rawVideoOnly: Boolean(segment.raw_video_only),
        validationStatus,
        validated: Boolean(segment.validated),
        protected: Boolean(segment.protected),
        videoUrl: `${localServer}${segment.video_url}`,
        ballTrackAvailable: Boolean(segment.ball_track_available),
        trackingUrl: segment.tracking_url
          ? `${localServer}${segment.tracking_url}`
          : null,
      };
    })
    .sort((left, right) =>
      left.startSeconds - right.startSeconds
      || left.durationSeconds - right.durationSeconds
      || left.key.localeCompare(right.key)
    );
}

function analyticsRule(type) {
  return {
    completed_pass: (
      "A pass completes on the receiving teammate's first controlled touch."
    ),
    turnover: (
      "A turnover completes when an opponent establishes controlled possession."
    ),
    foul_encountered: (
      "A foul stops ordinary event tracking unless advantage keeps play live."
    ),
  }[type] || "Apply the accepted analytics definition for this event.";
}

function eventTitle(event) {
  const team = event.team === "red"
    ? "Red/white"
    : event.team === "black" ? "Black" : "Match";
  const type = {
    completed_pass: "completed pass",
    turnover: "turnover",
    foul_encountered: "foul stoppage",
  }[event.event_type] || event.event_type.replaceAll("_", " ");
  return `${team} ${type}`;
}

async function loadEngineEvents(segment) {
  const predictions = await readJson(
    join(segmentRoot(segment), "analytics-data", "predicted-events.json"),
    [],
  );
  return predictions.map((event) => ({
    seconds: Number(event.completion_seconds ?? event.clip_seconds),
    team: event.team,
    type: canonicalType(event.event_type),
    confidence: Number.isFinite(Number(event.confidence))
      ? Number(event.confidence)
      : null,
    details: event.details || null,
    ballEvidence: event.ball_evidence || null,
  })).filter((event) => Number.isFinite(event.seconds));
}

async function loadDrafts(segment, segmentInfo) {
  const manual = await readJson(
    join(segmentRoot(segment), "manual-reference.json"),
    null,
  );
  if (manual?.events && segmentInfo.validated) {
    return manual.events.map((event) => ({
      seconds: Number(event.clip_seconds),
      team: event.team,
      type: event.event_type,
      title: eventTitle(event),
      evidence: (
        "This event belongs to the independently reviewed and locked "
        + "reference for this passed segment."
      ),
      rule: analyticsRule(event.event_type),
      source: "validated_reference",
    }));
  }
  const copilotReview = await readJson(copilotReviewPath(segment), null);
  if (Array.isArray(copilotReview?.proposals)) {
    return copilotReview.proposals.map((proposal) => ({
      ...proposal,
      source: "copilot_review",
    }));
  }
  if (segment === "segment-0300-020") {
    return test3Drafts.map((draft) => ({
      ...draft,
      source: "copilot_review",
    }));
  }
  if (segmentInfo.state !== "ready") return [];
  return [];
}

async function buildReplayRuns(segments) {
  const ready = segments
    .filter((segment) =>
      segment.state === "ready"
      && Number(segment.durationSeconds) === 60
    )
    .sort((left, right) => left.startSeconds - right.startSeconds);
  const groups = [];
  for (const segment of ready) {
    const current = groups.at(-1);
    const expectedStart = current
      ? current.at(-1).startSeconds + current.at(-1).durationSeconds
      : null;
    if (
      !current
      || current[0].datasetId !== segment.datasetId
      || Math.abs(segment.startSeconds - expectedStart) > 0.001
    ) {
      groups.push([segment]);
    } else {
      current.push(segment);
    }
  }
  const runs = await Promise.all(groups.map(async (group) => {
    const replaySegments = await Promise.all(group.map(async (segment) => ({
      key: segment.key,
      timeLabel: segment.timeLabel,
      startSeconds: segment.startSeconds,
      durationSeconds: segment.durationSeconds,
      videoUrl: segment.videoUrl,
      validated: segment.validated,
      protected: segment.protected,
      events: await loadEngineEvents(segment.key),
    })));
    const start = group[0].startSeconds;
    const end = group.at(-1).startSeconds + group.at(-1).durationSeconds;
    return {
      id: `${group[0].key}--${group.at(-1).key}`,
      timeLabel: `${formatClock(start)}–${formatClock(end)}`,
      continuityVerified: group.every((segment, index) =>
        index === 0
        || Math.abs(
          segment.startSeconds
          - (
            group[index - 1].startSeconds
            + group[index - 1].durationSeconds
          ),
        ) <= 0.001
      ),
      readyMinutes: group.length,
      targetMinutes: 10,
      complete: group.length >= 10,
      segments: replaySegments,
    };
  }));
  return runs.sort((left, right) =>
    right.readyMinutes - left.readyMinutes
    || left.segments[0].startSeconds - right.segments[0].startSeconds
  );
}

async function loadDetectedBallTrack(
  segment,
  { allowDetectionOnly = false } = {},
) {
  const payload = await readJson(
    join(segmentRoot(segment.key), "analytics-cache", "ball-tracks.json"),
    null,
  );
  if (workflow.key === "innovation") {
    if (!payload) return null;
    if (
      payload.source_kind !== "evaluation_only_provider_coordinates"
      || payload.pipeline_mode !== "innovation_day_bac_assisted"
    ) {
      throw new CanvasError(
        "innovation_ball_source_mismatch",
        "Innovation Day requires the frozen BAC coordinate artifact.",
      );
    }
    const manifest = await readJson(
      join(segmentRoot(segment.key), "runtime-manifest.json"),
      {},
    );
    const coordinateStates = (payload.tracks || []).flatMap((track) =>
      (track.points || []).map((point) => ({
        frame: Number(point.source_frame),
        seconds: Number(point.clip_seconds),
        x: Number(point.x),
        y: Number(point.y),
        confidence: Number.isFinite(Number(point.confidence))
          ? Number(point.confidence)
          : null,
        evidence: "Frozen BAC coordinate",
        state: "frozen_bac",
        uncertaintyRadius: null,
        direct: true,
        trackId: Number(track.track_id),
      }))
    ).filter((point) =>
      Number.isFinite(point.frame)
      && Number.isFinite(point.seconds)
      && Number.isFinite(point.x)
      && Number.isFinite(point.y)
    ).sort((left, right) => left.frame - right.frame);
    const points = coordinateStates.map((point) => [
      point.frame,
      point.seconds,
      point.x,
      point.y,
      point.trackId,
    ]);
    if (!points.length) return null;
    let yoloCandidates = {};
    let yoloCandidateSource = null;
    for (const relativePath of workflow.inspectionDetectionCaches || []) {
      const candidateText = await readFile(
        join(preparedSegmentRoot(segment.key), relativePath),
        "utf8",
      ).catch(() => "");
      if (!candidateText) continue;
      for (const line of candidateText.split(/\r?\n/)) {
        if (!line.trim()) continue;
        const record = JSON.parse(line);
        if (record.type !== "frame") continue;
        const candidates = (record.detections || [])
          .filter((detection) => detection.class_name === "sports ball")
          .map((detection) => ({
            confidence: Number(detection.confidence),
            x: (Number(detection.x1) + Number(detection.x2)) / 2,
            y: (Number(detection.y1) + Number(detection.y2)) / 2,
          }));
        if (candidates.length) {
          yoloCandidates[String(record.source_frame)] = candidates;
        }
      }
      if (Object.keys(yoloCandidates).length) {
        yoloCandidateSource = relativePath;
        break;
      }
    }
    return {
      width: Number(segment.imageWidth),
      height: Number(segment.imageHeight),
      fps: Number(manifest.fps || 25),
      frameCount: Number(
        manifest.end_frame
        || Math.round(segment.durationSeconds * Number(manifest.fps || 25)),
      ),
      sourceKind: payload.source_kind,
      pipelineMode: payload.pipeline_mode,
      coordinateMode: "frozen_bac",
      integrityRejectedFrames: [],
      yoloCandidates,
      yoloCandidateSource,
      points,
      states: coordinateStates,
    };
  }
  const manifest = await readJson(
    join(segmentRoot(segment.key), "manifest.json"),
    {},
  );
  const detectionText = await readFile(
    join(segmentRoot(segment.key), "analytics-cache", "detections.jsonl"),
    "utf8",
  ).catch(() => "");
  const yoloCandidates = {};
  const sampledFrames = [];
  for (const line of detectionText.split(/\r?\n/)) {
    if (!line.trim()) continue;
    const record = JSON.parse(line);
    if (record.type !== "frame") continue;
    const frame = Number(record.source_frame);
    const seconds = Number(record.clip_seconds);
    if (Number.isFinite(frame) && Number.isFinite(seconds)) {
      sampledFrames.push({ frame, seconds });
    }
    const candidates = (record.detections || [])
      .filter((detection) => detection.class_name === "sports ball")
      .map((detection) => ({
        confidence: Number(detection.confidence),
        x: (Number(detection.x1) + Number(detection.x2)) / 2,
        y: (Number(detection.y1) + Number(detection.y2)) / 2,
      }));
    if (candidates.length) {
      yoloCandidates[String(record.source_frame)] = candidates;
    }
  }
  if (!payload) {
    if (!allowDetectionOnly || !sampledFrames.length) return null;
    return {
      width: Number(segment.imageWidth),
      height: Number(segment.imageHeight),
      fps: Number(manifest.fps || 25),
      frameCount: Number(
        manifest.end_frame
        || Math.round(segment.durationSeconds * Number(manifest.fps || 25)),
      ),
      pendingEngineOutput: true,
      integrityRejectedFrames: [],
      yoloCandidates,
      points: [],
      states: sampledFrames.map(({ frame, seconds }) => ({
        frame,
        seconds,
        x: null,
        y: null,
        confidence: null,
        evidence: "Engine coordinate pending current replay",
        state: "engine_pending",
        uncertaintyRadius: null,
        direct: false,
      })),
    };
  }
  const statePayload = await readJson(
    join(
      segmentRoot(segment.key),
      "analytics-cache",
      "ball-state-estimates.json",
    ),
    null,
  );
  const points = (payload.tracks || []).flatMap((track) =>
    (track.points || []).map((point) => [
      Number(point.source_frame),
      Number(point.clip_seconds),
      Number(point.x),
      Number(point.y),
      Number(track.track_id),
    ])
  ).filter((point) => point.every(Number.isFinite));
  if (!points.length) return null;
  return {
    width: Number(segment.imageWidth),
    height: Number(segment.imageHeight),
    fps: Number(manifest.fps || 25),
    frameCount: Number(
      manifest.end_frame
      || Math.round(segment.durationSeconds * Number(manifest.fps || 25)),
    ),
    integrityRejectedFrames: (
      payload.final_trajectory_integrity?.rejected_frames || []
    ).map(Number).filter(Number.isFinite),
    yoloCandidates,
    points,
    states: (statePayload?.states || []).map((state) => ({
      frame: Number(state.source_frame),
      seconds: Number(state.clip_seconds),
      x: Number(state.x),
      y: Number(state.y),
      confidence: Number.isFinite(Number(state.confidence))
        ? Number(state.confidence)
        : null,
      evidence: String(state.evidence || "unavailable"),
      state: String(state.state || "unavailable"),
      uncertaintyRadius: Number.isFinite(
        Number(state.uncertainty_radius_pixels),
      )
        ? Number(state.uncertainty_radius_pixels)
        : null,
      direct: Boolean(state.event_evidence_eligible),
    })).filter((state) =>
      Number.isFinite(state.frame)
      && Number.isFinite(state.seconds)
      && Number.isFinite(state.x)
      && Number.isFinite(state.y)
    ),
  };
}

async function loadActionFocuses(segment, drafts) {
  const track = await loadDetectedBallTrack(segment);
  if (!track) return drafts.map(() => null);
  return drafts.map((draft) => {
    const point = track.points.reduce((closest, candidate) =>
      Math.abs(candidate[1] - draft.seconds)
        < Math.abs(closest[1] - draft.seconds)
        ? candidate
        : closest
    );
    return {
      sourceSeconds: point[1],
      xPercent: Math.min(
        100,
        Math.max(0, point[2] / track.width * 100),
      ),
      yPercent: Math.min(
        100,
        Math.max(0, point[3] / track.height * 100),
      ),
    };
  });
}

function legacyArtifactDirectory() {
  if (session.workspacePath) {
    return join(session.workspacePath, "files", canvasId);
  }
  return join(
    process.env.COPILOT_HOME || join(homedir(), ".copilot"),
    "extensions",
    canvasId,
    "artifacts",
    session.sessionId,
  );
}

function artifactDirectory() {
  return sharedArtifactRoot
    ? join(sharedArtifactRoot, "30-shared-baselines", workflow.stateDirectory)
    : legacyArtifactDirectory();
}

function statePath(segment) {
  return join(artifactDirectory(), `${segment}-review-state.json`);
}

function legacyStatePath(segment) {
  return join(
    legacyArtifactDirectory(),
    segment === defaultSegment
      ? "test3-review-state.json"
      : `${segment}-review-state.json`,
  );
}

function sharedRelativePath(path) {
  return relative(sharedArtifactRoot, path).replaceAll("\\", "/");
}

async function updateSharedChecksum(path, content = null) {
  if (!sharedArtifactRoot) return;
  const manifestPath = join(
    sharedArtifactRoot,
    "00-governance",
    "checksums.sha256",
  );
  const relativePath = sharedRelativePath(path);
  const digest = createHash("sha256");
  if (content !== null) {
    digest.update(content);
  } else {
    const handle = await open(path, "r");
    const buffer = Buffer.allocUnsafe(1024 * 1024);
    try {
      let bytesRead;
      do {
        ({bytesRead} = await handle.read(buffer, 0, buffer.length, null));
        if (bytesRead) digest.update(buffer.subarray(0, bytesRead));
      } while (bytesRead);
    } finally {
      await handle.close();
    }
  }
  const checksum = digest.digest("hex").toUpperCase();
  const lockPath = `${manifestPath}.lock`;
  let lockHandle;
  for (let attempt = 0; attempt < 100 && !lockHandle; attempt += 1) {
    try {
      lockHandle = await open(lockPath, "wx");
    } catch (error) {
      if (error?.code !== "EEXIST") throw error;
      try {
        const lockStat = await stat(lockPath);
        if (Date.now() - lockStat.mtimeMs > 30_000) {
          await unlink(lockPath);
          continue;
        }
      } catch (lockError) {
        if (lockError?.code !== "ENOENT") throw lockError;
      }
      await new Promise((resolveDelay) => setTimeout(resolveDelay, 50));
    }
  }
  if (!lockHandle) {
    throw new Error("Timed out waiting to update the shared checksum manifest");
  }
  try {
    const existing = await readFile(manifestPath, "utf8");
    const lines = existing.split(/\r?\n/).filter((line) =>
      !line.endsWith(`*${relativePath}`)
    );
    lines.push(`${checksum} *${relativePath}`);
    const updated = `${lines.filter(Boolean).join("\n")}\n`;
    const temporaryPath =
      `${manifestPath}.${process.pid}.${randomUUID()}.tmp`;
    await writeFile(temporaryPath, updated, "utf8");
    try {
      for (let attempt = 0; ; attempt += 1) {
        try {
          await rename(temporaryPath, manifestPath);
          break;
        } catch (error) {
          if (
            !["EACCES", "EPERM"].includes(error?.code)
            || attempt >= 99
          ) {
            throw error;
          }
          await new Promise((resolveDelay) => setTimeout(resolveDelay, 100));
        }
      }
    } catch (error) {
      await unlink(temporaryPath).catch(() => {});
      throw error;
    }
  } finally {
    await lockHandle.close();
    await unlink(lockPath).catch((error) => {
      if (error?.code !== "ENOENT") throw error;
    });
  }
}

async function readReviewState(path, fallback, verifyChecksum = false) {
  let content;
  try {
    content = await readFile(path, "utf8");
  } catch (error) {
    if (error?.code === "ENOENT") return fallback;
    throw error;
  }
  if (verifyChecksum) {
    const relativePath = sharedRelativePath(path);
    const manifest = await readFile(
      join(sharedArtifactRoot, "00-governance", "checksums.sha256"),
      "utf8",
    );
    const entry = manifest.split(/\r?\n/).find((line) =>
      line.endsWith(`*${relativePath}`)
    );
    if (!entry) {
      throw new Error(
        `Shared review-state checksum is missing for ${relativePath}`,
      );
    }
    const expected = entry.slice(0, 64).toLowerCase();
    const actual = createHash("sha256").update(content).digest("hex");
    if (expected !== actual) {
      throw new Error(
        `Shared review-state checksum mismatch for ${relativePath}`,
      );
    }
  }
  return JSON.parse(content);
}

async function readJson(path, fallback) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch (error) {
    if (error?.code === "ENOENT") return fallback;
    throw error;
  }
}

async function writeTextAtomically(path, content) {
  const temporaryPath = `${path}.${process.pid}.${randomUUID()}.tmp`;
  await writeFile(temporaryPath, content, "utf8");
  for (let attempt = 0; attempt < 6; attempt += 1) {
    try {
      await rename(temporaryPath, path);
      return;
    } catch (error) {
      if (
        !["EPERM", "EBUSY", "EACCES"].includes(error.code)
        || attempt === 5
      ) {
        await unlink(temporaryPath).catch(() => {});
        throw error;
      }
      await new Promise((resolveDelay) =>
        setTimeout(resolveDelay, 50 * (attempt + 1))
      );
    }
  }
}

async function writeJsonAtomically(path, payload) {
  await writeTextAtomically(path, `${JSON.stringify(payload, null, 2)}\n`);
}

async function registerWorkflowRegression(segment, reference, current) {
  const registry = await readJson(regressionRegistryPath, {
    schema_version: 1,
    workflow: workflowId,
    segments: [],
  });
  const entry = {
    segment,
    published_at: reference.exported_at,
    event_count: reference.events.length,
    engine_content_hash: current.fingerprint.contentHash,
    output_hash: current.outputHash,
  };
  registry.segments = [
    ...(registry.segments || []).filter((item) => item.segment !== segment),
    entry,
  ].sort((left, right) => left.segment.localeCompare(right.segment));
  await writeJsonAtomically(regressionRegistryPath, registry);
}

async function engineFingerprint() {
  const hash = createHash("sha256");
  for (const relativePath of engineFiles) {
    hash.update(relativePath);
    hash.update(await readFile(join(projectRoot, relativePath)));
  }

  let gitRevision = "unknown";
  try {
    gitRevision = execFileSync("git", ["rev-parse", "HEAD"], {
      cwd: projectRoot,
      encoding: "utf8",
      windowsHide: true,
    }).trim();
  } catch {
    // The content hash still identifies the inference implementation.
  }
  return {
    gitRevision,
    contentHash: hash.digest("hex"),
  };
}

async function sourceVersion(files) {
  const hash = createHash("sha256");
  for (const relativePath of files) {
    hash.update(relativePath);
    hash.update(await readFile(join(projectRoot, relativePath)));
  }
  return hash.digest("hex");
}

async function componentVersions() {
  const [tracker, rulesEngine] = await Promise.all([
    sourceVersion(trackerVersionFiles),
    sourceVersion(rulesEngineVersionFiles),
  ]);
  return {tracker, rulesEngine};
}

async function captureEngineSnapshot(segment, knownFingerprint = null) {
  const root = segmentRoot(segment);
  const predictionsPath = join(
    root,
    "analytics-data",
    "predicted-events.json",
  );
  const matchStatePath = join(
    root,
    "analytics-data",
    "match-state-events.json",
  );
  const predictions = await readJson(predictionsPath, []);
  const matchState = await readJson(matchStatePath, { intervals: [] });
  const fingerprint = knownFingerprint || await engineFingerprint();
  const outputHash = createHash("sha256")
    .update(JSON.stringify({ predictions, matchState }))
    .digest("hex");
  return {
    capturedAt: new Date().toISOString(),
    fingerprint,
    outputHash,
    predictions,
    matchState,
  };
}

async function ensureInnovationRegressionsCurrent(segment, state) {
  if (workflow.key !== "innovation") return null;
  const current = await captureEngineSnapshot(segment);
  const publishedSegments = (await loadPreparedSegments()).filter(
    (candidate) => candidate.validated,
  );
  const publishedSegmentKeys = publishedSegments
    .map((candidate) => candidate.key)
    .sort();
  const registry = await readJson(regressionRegistryPath, {
    schema_version: 1,
    workflow: workflowId,
    segments: [],
  });
  const fullReceipt = registry.last_full_regression;
  if (
    fullReceipt?.passed
    && fullReceipt.engineContentHash === current.fingerprint.contentHash
    && JSON.stringify(fullReceipt.segments || [])
      === JSON.stringify(publishedSegmentKeys)
  ) {
    state.engineAfter = current;
    state.regression = {
      passed: true,
      summary: fullReceipt.summary,
      fingerprint: current.fingerprint,
      outputHash: current.outputHash,
      recordedAt: fullReceipt.recordedAt,
      suite: "innovation",
      trigger: "reused_workflow_receipt",
      coverage: "all_published_segments",
      segmentResults: fullReceipt.segmentResults,
    };
    return {current, reused: true, stale: false, passed: true};
  }

  const segmentResults = await Promise.all(
    publishedSegments.map(async (publishedSegment) => {
      try {
        return await queuePublishedInnovationRegression(
          publishedSegment.key,
          {reuseActive: true},
        );
      } catch (error) {
        return {
          segment: publishedSegment.key,
          timeLabel: publishedSegment.timeLabel,
          passed: false,
          summary: error.message || String(error),
          addedEvents: [],
          missingEvents: [],
        };
      }
    }),
  );
  const segmentFailures = segmentResults.filter((result) => !result.passed);
  if (segmentFailures.length) {
    const refreshedCurrent = await captureEngineSnapshot(segment);
    const recordedAt = new Date().toISOString();
    state.engineAfter = refreshedCurrent;
    state.regression = {
      passed: false,
      summary: "Acceptance pending: "
        + segmentFailures.map((result) =>
          `${result.timeLabel || result.segment} (${result.summary})`
        ).join("; "),
      fingerprint: refreshedCurrent.fingerprint,
      outputHash: refreshedCurrent.outputHash,
      recordedAt,
      suite: "innovation",
      trigger: "acceptance",
      coverage: "all_published_segments",
      segmentResults,
    };
    registry.last_full_regression = {
      passed: false,
      summary: state.regression.summary,
      engineContentHash: refreshedCurrent.fingerprint.contentHash,
      recordedAt,
      segments: publishedSegmentKeys,
      segmentResults,
    };
    await writeJsonAtomically(regressionRegistryPath, registry);
    return {
      current: refreshedCurrent,
      reused: false,
      stale: true,
      passed: false,
      segmentFailures,
    };
  }

  let output;
  try {
    const result = await execFileAsync(
      "python",
      ["-m", "pytest", ...workflow.regressionTests, "-q"],
      {
        cwd: projectRoot,
        encoding: "utf8",
        windowsHide: true,
        env: {
          ...process.env,
          PYTHONPATH: [
            join(projectRoot, "src"),
            process.env.PYTHONPATH || "",
          ].filter(Boolean).join(";"),
        },
      },
    );
    output = String(result.stdout || "").trim();
  } catch (error) {
    const refreshedCurrent = await captureEngineSnapshot(segment);
    const recordedAt = new Date().toISOString();
    state.engineAfter = refreshedCurrent;
    state.regression = {
      passed: false,
      summary: "Acceptance pending because protected tests failed: "
        + String(error.stdout || error.message || error).trim(),
      fingerprint: refreshedCurrent.fingerprint,
      outputHash: refreshedCurrent.outputHash,
      recordedAt,
      suite: "innovation",
      trigger: "acceptance",
      coverage: "all_published_segments",
      segmentResults,
    };
    registry.last_full_regression = {
      passed: false,
      summary: state.regression.summary,
      engineContentHash: refreshedCurrent.fingerprint.contentHash,
      recordedAt,
      segments: publishedSegmentKeys,
      segmentResults,
    };
    await writeJsonAtomically(regressionRegistryPath, registry);
    return {
      current: refreshedCurrent,
      reused: false,
      stale: true,
      passed: false,
      segmentFailures: [],
    };
  }
  const refreshedCurrent = await captureEngineSnapshot(segment);
  state.engineAfter = refreshedCurrent;
  state.regression = {
    passed: true,
    summary: `${segmentResults.length} published Innovation segment(s) `
      + "matched exactly; "
      + (output.split(/\r?\n/).at(-1) || "protected tests passed"),
    fingerprint: refreshedCurrent.fingerprint,
    outputHash: refreshedCurrent.outputHash,
    recordedAt: new Date().toISOString(),
    suite: "innovation",
    trigger: "acceptance",
    coverage: "all_published_segments",
    segmentResults,
  };
  registry.last_full_regression = {
    passed: true,
    summary: state.regression.summary,
    engineContentHash: refreshedCurrent.fingerprint.contentHash,
    recordedAt: state.regression.recordedAt,
    segments: publishedSegmentKeys,
    segmentResults,
  };
  await writeJsonAtomically(regressionRegistryPath, registry);
  return {
    current: refreshedCurrent,
    reused: false,
    stale: false,
    passed: true,
  };
}

function eventRegressionSummary(event) {
  return {
    eventType: canonicalType(event.event_type),
    team: event.team,
    seconds: Number(event.completion_seconds ?? event.clip_seconds),
    releaseSeconds: Number(event.clip_seconds),
  };
}

function eventRegressionDifferences(baselineEvents, currentEvents) {
  const remaining = currentEvents.map((event) => JSON.stringify(event));
  const missingEvents = [];
  for (const event of baselineEvents) {
    const serialized = JSON.stringify(event);
    const index = remaining.indexOf(serialized);
    if (index >= 0) {
      remaining.splice(index, 1);
    } else {
      missingEvents.push(eventRegressionSummary(event));
    }
  }
  return {
    addedEvents: remaining.map((event) =>
      eventRegressionSummary(JSON.parse(event))
    ),
    missingEvents,
  };
}

function matchStateBehavior(matchState) {
  const omitMetadata = (value) => {
    if (Array.isArray(value)) return value.map(omitMetadata);
    if (!value || typeof value !== "object") return value;
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => ![
          "law_profile",
          "law_reference",
          "schema_version",
        ].includes(key))
        .map(([key, child]) => [key, omitMetadata(child)]),
    );
  };
  return omitMetadata(matchState);
}

function describeRegressionEvents(label, events) {
  if (!events.length) return "";
  const visible = events.slice(0, 8).map((event) =>
    `${event.eventType} (${event.team}) at ${event.seconds.toFixed(3)}s`
  );
  const remainder = events.length - visible.length;
  return ` ${label}: ${visible.join("; ")}`
    + (remainder > 0 ? `; plus ${remainder} more` : "")
    + ".";
}

async function executePublishedInnovationRegression(segment, progress) {
  if (workflow.key !== "innovation") {
    throw new CanvasError(
      "regression_unavailable",
      "Per-segment cached regression is available only in Innovation Day.",
    );
  }
  const review = await reviewContext(segment);
  if (!review.selected.validated) {
    throw new CanvasError(
      "regression_requires_published_segment",
      "Only a segment with a published Innovation reference can be rerun.",
    );
  }
  const before = await captureEngineSnapshot(segment);
  const baselineOutputHash = (
    review.state.publishedReference?.outputHash
    || review.state.engineBefore?.outputHash
    || before.outputHash
  );
  if (!baselineOutputHash) {
    throw new CanvasError(
      "regression_baseline_missing",
      "The published segment has no recorded engine-output hash.",
    );
  }

  let baselineSnapshotForRestore = null;
  let completedResult = null;
  try {
    updateSegmentRegressionProgress(progress, "baseline", "completed");
    updateSegmentRegressionProgress(progress, "engine", "running");
    await execFileAsync(
      "python",
      [
        join(projectRoot, "scripts", workflow.processorScript),
        preparedSegmentRoot(segment),
        ...workflow.processorArguments,
      ],
      {
        cwd: projectRoot,
        encoding: "utf8",
        windowsHide: true,
        maxBuffer: 10 * 1024 * 1024,
        env: {
          ...process.env,
          PYTHONPATH: [
            join(projectRoot, "src"),
            process.env.PYTHONPATH || "",
          ].filter(Boolean).join(";"),
        },
      },
    );
    updateSegmentRegressionProgress(progress, "engine", "completed");
    updateSegmentRegressionProgress(progress, "compare", "running");
    const current = await captureEngineSnapshot(segment);
    const exactOutputMatch = current.outputHash === baselineOutputHash;
    const baselineSnapshot = [
      review.state.engineBefore,
      review.state.engineAfter,
      before,
    ].find((snapshot) => snapshot?.outputHash === baselineOutputHash);
    baselineSnapshotForRestore = baselineSnapshot || before;
    const eventDifferences = eventRegressionDifferences(
      baselineSnapshot?.predictions || [],
      current.predictions,
    );
    const matchStateChanged = Boolean(
      baselineSnapshot
      && JSON.stringify(baselineSnapshot.matchState)
        !== JSON.stringify(current.matchState)
    );
    const matchStateBehaviorChanged = Boolean(
      baselineSnapshot
      && JSON.stringify(matchStateBehavior(baselineSnapshot.matchState))
        !== JSON.stringify(matchStateBehavior(current.matchState))
    );
    const matchStateMetadataOnly = (
      matchStateChanged && !matchStateBehaviorChanged
    );
    const passed = exactOutputMatch || matchStateMetadataOnly;
    updateSegmentRegressionProgress(progress, "compare", "completed");
    updateSegmentRegressionProgress(progress, "persist", "running");
    const recordedAt = new Date().toISOString();
    const changeKind = matchStateMetadataOnly
      ? "metadata_only"
      : passed ? "none" : "behavioral";
    review.state.engineAfter = current;
    review.state.regression = {
      passed,
      summary: exactOutputMatch
        ? "Current Innovation engine output exactly matches the published output."
        : matchStateMetadataOnly
          ? "Passed: events and match-state behavior are unchanged; only "
            + "schema and football-law provenance metadata changed."
          : `${eventDifferences.addedEvents.length} added E# event(s), `
          + `${eventDifferences.missingEvents.length} missing E# event(s)`
          + (matchStateBehaviorChanged
            ? ", and changed match-state behavior."
            : ".")
          + describeRegressionEvents(
            "Added",
            eventDifferences.addedEvents,
          )
          + describeRegressionEvents(
            "Missing",
            eventDifferences.missingEvents,
          ),
      fingerprint: current.fingerprint,
      outputHash: baselineSnapshotForRestore.outputHash,
      candidateOutputHash: current.outputHash,
      baselineOutputHash,
      recordedAt,
      suite: "innovation_segment",
      trigger: "manual_rerun",
      changeKind,
    };
    review.state.updatedAt = recordedAt;
    await saveState(segment, review.state);
    updateSegmentRegressionProgress(progress, "persist", "completed");
    completedResult = {
      segment,
      passed,
      summary: review.state.regression.summary,
      baselineOutputHash,
      currentOutputHash: current.outputHash,
      engineContentHash: current.fingerprint.contentHash,
      ...eventDifferences,
      matchStateChanged,
      matchStateBehaviorChanged,
      matchStateMetadataOnly,
      changeKind,
      recordedAt,
    };
    return completedResult;
  } catch (error) {
    progress.status = "failed";
    progress.message = error.message || String(error);
    throw error;
  } finally {
    updateSegmentRegressionProgress(progress, "restore", "running");
    if (baselineSnapshotForRestore) {
      await writeJsonAtomically(
        join(
          segmentRoot(segment),
          "analytics-data",
          "predicted-events.json",
        ),
        baselineSnapshotForRestore.predictions,
      );
      await writeJsonAtomically(
        join(
          segmentRoot(segment),
          "analytics-data",
          "match-state-events.json",
        ),
        baselineSnapshotForRestore.matchState,
      );
    }
    updateSegmentRegressionProgress(progress, "restore", "completed");
    progress.completedAt = new Date().toISOString();
    if (completedResult) {
      progress.status = completedResult.passed ? "passed" : "mismatch";
      progress.message = completedResult.summary;
      progress.changeKind = completedResult.changeKind;
    }
  }
}

function queuePublishedInnovationRegression(
  segment,
  {reuseActive = false} = {},
) {
  const existing = segmentRegressionJobs.get(segment);
  if (existing) {
    if (reuseActive) return existing;
    throw new CanvasError(
      "regression_in_progress",
      `A regression rerun is already active for ${segment}.`,
    );
  }
  const progress = startSegmentRegressionProgress(segment);
  activeSegmentRegressions.add(segment);
  const job = executePublishedInnovationRegression(segment, progress)
    .catch((error) => {
      progress.status = "failed";
      progress.message = error.message || String(error);
      progress.completedAt ||= new Date().toISOString();
      throw error;
    })
    .finally(() => {
      activeSegmentRegressions.delete(segment);
      segmentRegressionJobs.delete(segment);
    });
  segmentRegressionJobs.set(segment, job);
  return job;
}

async function loadState(segment, segmentInfo, drafts) {
  const coordination = await coordinationStatus();
  let coordinatedSnapshot = null;
  let normalizedManualReference = null;
  let state = null;
  if (coordination.mode === "available") {
    coordinatedSnapshot = await localJson(
      "/api/coordination/state?workflow="
        + encodeURIComponent(workflowId)
        + "&segment=" + encodeURIComponent(segment),
    );
    const current = coordinationSessions.get(coordinationKey(segment)) || {};
    coordinationSessions.set(coordinationKey(segment), {
      ...current,
      version: Number(coordinatedSnapshot.version || 0),
    });
    state = coordinatedSnapshot.state;
    if (workflow.key === "innovation") {
      normalizedManualReference = await localJson(
        "/api/coordination/manual-reference?workflow="
          + encodeURIComponent(workflowId)
          + "&segment=" + encodeURIComponent(segment),
      );
    }
  } else {
    state = await readReviewState(
      statePath(segment),
      null,
      Boolean(sharedArtifactRoot),
    );
    if (!state && sharedArtifactRoot) {
      state = await readReviewState(legacyStatePath(segment), null);
    }
  }
  let changed = false;
  if (state) {
    if (state.workflowId && state.workflowId !== workflowId) {
      throw new CanvasError(
        "review_workflow_mismatch",
        `Refusing ${state.workflowId} state in the ${workflowId} Canvas.`,
      );
    }
    if (state.canvasId && state.canvasId !== canvasId) {
      throw new CanvasError(
        "review_canvas_mismatch",
        `Refusing ${state.canvasId} state in the ${canvasId} Canvas.`,
      );
    }
    if (!state.workflowId) {
      state.workflowId = workflowId;
      changed = true;
    }
    if (!state.canvasId) {
      state.canvasId = canvasId;
      changed = true;
    }
    state.conversation ||= [];
    let activeLegacyEngineIndex = null;
    state.conversation.forEach((message) => {
      if (Number.isInteger(message.engineIndex)) {
        activeLegacyEngineIndex = message.engineIndex;
        return;
      }
      if (message.eventIndex !== null && message.eventIndex !== undefined) {
        activeLegacyEngineIndex = null;
        return;
      }
      const engineRequest = String(message.content || "").match(
        /^Permission granted: independently verify E(\d+)/,
      );
      if (engineRequest) {
        activeLegacyEngineIndex = Number(engineRequest[1]) - 1;
      } else if (message.role === "user") {
        activeLegacyEngineIndex = null;
      }
      if (activeLegacyEngineIndex !== null) {
        message.engineIndex = activeLegacyEngineIndex;
        changed = true;
      }
    });
    state.proposalOverrides ||= {};
    state.additionalProposals ||= [];
    state.sameFrameReviewRequirements ||= {};
    state.additionalProposals.forEach((proposal) => {
      if (proposal.source === "user_reported") {
        proposal.source = "manual_review";
        changed = true;
      }
    });
    state.copilotAcceptanceAuthorizations ||= {};
    state.engineEventReviews ||= {};
    state.engineEventReviewAuthorizations ||= {};
    state.pendingMissingCandidate ||= null;
    state.pendingClipRequest ||= null;
    state.automaticCopilotReview ||= null;
    if (workflow.key === "innovation") {
      changed = ensureInnovationManualReference(state, segment) || changed;
      if (normalizedManualReference?.draft || normalizedManualReference?.approved) {
        changed = applyNormalizedManualReference(
          state,
          normalizedManualReference,
        ) || changed;
      }
    }
    if (workflow.coordinateReviewEnabled) {
      state.coordinateReview ||= {
        status: segmentInfo.validationStatus === "in_review"
          || segmentInfo.validated
          ? "finalized"
          : "pending",
        flaggedFrames: [],
        verifiedAt: null,
        trackerHash: null,
        provenanceHash: null,
        summary: null,
      };
      state.coordinateReview.batches ||= [];
      state.coordinateReview.activeBatchId ||= null;
      if (
        !state.coordinateReview.batches.length
        && state.coordinateReview.flaggedFrames?.length
      ) {
        const diagnostic = await readJson(
          join(
            segmentRoot(segment),
            "analytics-data",
            "ball-recovery-diagnostic.json",
          ),
          null,
        );
        const originalFrames = diagnostic?.original_review_frames
          || state.coordinateReview.flaggedFrames;
        const previousEstimated = new Set(originalFrames);
        const sampledFrames = Array.from(
          {length: Number(diagnostic?.sampled_frame_count || 300)},
          (_, index) => index * 5,
        );
        const batch = {
          id: "coordinate-round-1",
          number: 1,
          status: ["processing", "detections_ready", "building"].includes(
            segmentInfo.state,
          )
            ? "rerun_started"
            : diagnostic?.batch_review_completed ? "review_completed" : "ready",
          frames: originalFrames,
          observations: {},
          submittedAt: state.coordinateReview.requestedAt || null,
          reviewCompletedAt: diagnostic?.review_completed_at || null,
          codeFixCompletedAt: diagnostic?.code_fix_completed_at || null,
          testsCompletedAt: diagnostic?.tests_completed_at || null,
          rerunStartedAt: diagnostic?.rerun_started_at || null,
          rerunCompletedAt: null,
          awaitingRunObservation: false,
          before: {
            directFrameCount: Number(
              diagnostic?.persisted_direct_frame_count || 0,
            ),
            sampledFrameCount: sampledFrames.length,
            directFrames: sampledFrames.filter(
              (frame) => !previousEstimated.has(frame),
            ),
          },
          summary: diagnostic?.description || null,
          frameResults: {},
        };
        state.coordinateReview.batches.push(batch);
        state.coordinateReview.activeBatchId = batch.id;
        state.conversation.forEach((message) => {
          if (message.coordinateReview) message.coordinateBatchId = batch.id;
        });
        changed = true;
      }
    } else if (
      state.coordinateReview?.status !== "finalized"
      || state.coordinateReview?.flaggedFrames?.length
      || state.coordinateReview?.batches?.length
      || state.coordinateReview?.activeBatchId
    ) {
      state.coordinateReview = {
        status: "finalized",
        flaggedFrames: [],
        verifiedAt: null,
        trackerHash: null,
        provenanceHash: null,
        summary: "Frozen BAC coordinates are available for every sampled frame.",
        batches: [],
        activeBatchId: null,
      };
      changed = true;
    } else {
      state.coordinateReview ||= {
        status: "finalized",
        flaggedFrames: [],
        verifiedAt: null,
        trackerHash: null,
        provenanceHash: null,
        summary: "Frozen BAC coordinates are available for every sampled frame.",
        batches: [],
        activeBatchId: null,
      };
    }
    state.publicationAuthorization ||= null;
    state.publishedReference ||= null;
    if (segmentInfo.validated && !state.publishedReference) {
      drafts.forEach((_, index) => {
        if (state.decisions[String(index)]?.status === "accepted") return;
        state.decisions[String(index)] = {
          status: "accepted",
          note: "Published validated reference",
          decidedAt: new Date().toISOString(),
          source: "published_reference",
        };
        changed = true;
      });
    }
    if (changed && coordination.mode !== "unavailable") {
      await saveState(segment, state, {allowAutoAcquire: false});
    }
    return state;
  }
  const decisions = {};
  if (segmentInfo.validated) {
    drafts.forEach((_, index) => {
      decisions[String(index)] = {
        status: "accepted",
        note: "Published validated reference",
        decidedAt: new Date().toISOString(),
        source: "published_reference",
      };
    });
  }
  const initial = {
    schemaVersion: 1,
    workflowId,
    canvasId,
    segment,
    decisions,
    engineBefore: await captureEngineSnapshot(segment),
    engineAfter: null,
    regression: null,
    conversation: [],
    proposalOverrides: {},
    additionalProposals: [],
    sameFrameReviewRequirements: {},
    copilotAcceptanceAuthorizations: {},
    engineEventReviews: {},
    engineEventReviewAuthorizations: {},
    pendingMissingCandidate: null,
    pendingClipRequest: null,
    automaticCopilotReview: null,
    manualReference: workflow.key === "innovation"
      ? {
      revision: 0,
      events: [],
      mappings: {},
      audit: [],
          approved: null,
          approvalHistory: [],
          undoStack: [],
        }
      : null,
    coordinateReview: workflow.coordinateReviewEnabled
      ? {
          status: segmentInfo.validationStatus === "in_review"
            || segmentInfo.validated
            ? "finalized"
            : "pending",
          flaggedFrames: [],
          verifiedAt: null,
          trackerHash: null,
          provenanceHash: null,
          summary: null,
          batches: [],
          activeBatchId: null,
        }
      : {
          status: "finalized",
          flaggedFrames: [],
          verifiedAt: null,
          trackerHash: null,
          provenanceHash: null,
          summary: "Frozen BAC coordinates are available for every sampled frame.",
          batches: [],
          activeBatchId: null,
        },
    trajectoryAudit: {
      observations: {},
      updatedAt: null,
    },
    publicationAuthorization: null,
    publishedReference: null,
  };
  if (workflow.key === "innovation") {
    ensureInnovationManualReference(initial, segment);
    if (normalizedManualReference?.draft || normalizedManualReference?.approved) {
      applyNormalizedManualReference(initial, normalizedManualReference);
    }
  }
  if (coordination.mode !== "unavailable") {
    await saveState(segment, initial, {allowAutoAcquire: false});
  }
  return initial;
}

function coordinationKey(segment) {
  return `${workflowId}:${segment}`;
}

function canvasSessionConnection(hostInstanceId, serverInstanceId) {
  const repositoryAvailable = existsSync(join(projectRoot, ".git"));
  if (workflow.key !== "innovation") {
    return {
      connected: true,
      repositoryAvailable,
      message: "Copilot project-session gating is not enabled for this workflow.",
    };
  }
  const connected = Boolean(
    session?.sessionId
    && repositoryAvailable
    && hostInstanceId
    && hostInstanceId === serverInstanceId
    && servers.has(serverInstanceId)
  );
  return {
    connected,
    repositoryAvailable,
    message: connected
      ? "Connected to the active Copilot project session for this worktree."
      : !repositoryAvailable
        ? "This review extension is not running from a Git worktree."
        : !hostInstanceId
          ? "Open this review from the Copilot project session for this repository."
          : "The Copilot Canvas connection is unavailable or stale. Reopen the review from the project session, then retry.",
  };
}

function canvasSessionConnectionFromUrl(url, serverInstanceId) {
  return canvasSessionConnection(
    String(url.searchParams.get("hostInstanceId") || ""),
    serverInstanceId,
  );
}

function canvasSessionConnectionFromRequest(request, serverInstanceId) {
  const referer = String(request.headers.referer || "");
  if (!referer) return canvasSessionConnection("", serverInstanceId);
  try {
    return canvasSessionConnectionFromUrl(new URL(referer), serverInstanceId);
  } catch {
    return canvasSessionConnection("", serverInstanceId);
  }
}

async function coordinationStatus() {
  try {
    return await localJson("/api/coordination/health");
  } catch (error) {
    return {
      mode: "unavailable",
      detail: `Local coordination API is unavailable: ${error.message}`,
    };
  }
}

async function coordinationIdentity() {
  try {
    return await localJson("/api/coordination/identity");
  } catch {
    return {mode: "unavailable", identity: null};
  }
}

async function acquireCoordinationLease(segment, stage = "event-review") {
  const key = coordinationKey(segment);
  const existing = coordinationSessions.get(key);
  if (existing?.leaseToken) {
    try {
      await localJson("/api/coordination/heartbeat", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({leaseToken: existing.leaseToken}),
      });
      return existing;
    } catch {
      coordinationSessions.delete(key);
    }
  }
  const result = await localJson("/api/coordination/acquire", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      workflow: workflowId,
      segment,
      stage,
    }),
  });
  const session = {
    leaseToken: result.lease.leaseToken,
    version: Number(result.version || 0),
  };
  coordinationSessions.set(key, session);
  return session;
}

async function releaseCoordinationLease(segment) {
  const key = coordinationKey(segment);
  const session = coordinationSessions.get(key);
  if (!session?.leaseToken) return false;
  const result = await localJson("/api/coordination/release", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({leaseToken: session.leaseToken}),
  });
  coordinationSessions.delete(key);
  broadcast("state");
  return Boolean(result.released);
}

async function heartbeatCoordinationLease(segment) {
  const session = coordinationSessions.get(coordinationKey(segment));
  if (!session?.leaseToken) {
    throw new CanvasError(
      "coordination_lease_missing",
      "Start working on this segment before refreshing its editing lease.",
    );
  }
  await localJson("/api/coordination/heartbeat", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({leaseToken: session.leaseToken}),
  });
  return true;
}

function applyNormalizedManualReference(state, payload) {
  const normalized = payload?.draft || payload?.approved;
  if (!normalized) return false;
  state.manualReference ||= {};
  const rejectedEvents = (state.manualReference.events || [])
    .filter((event) =>
      !event.deleted
      && event.reviewStatus === "rejected"
    )
    .map((event) => ({...event}));
  const normalizedEvents = normalized.events.map((event) => ({
    ...event,
    active: true,
    deleted: false,
    reviewStatus: "active",
    rejectedAt: null,
    source: "manual_review",
  }));
  const normalizedKeys = new Set(normalizedEvents.map((event) => event.key));
  state.manualReference.events = [
    ...normalizedEvents,
    ...rejectedEvents.filter((event) => !normalizedKeys.has(event.key)),
  ];
  state.manualReference.mappings = {...normalized.mappings};
  state.manualReference.normalizedRevision = normalized.revision;
  const currentApproval = payload.draft ? null : payload.approved;
  if (currentApproval) {
    const approvedEvents = currentApproval.events.map((event) => ({
      ...event,
      active: true,
      deleted: false,
      source: "manual_review",
    }));
    state.manualReference.approved = {
      revision: currentApproval.revision,
      approvedAt: currentApproval.approvedAt,
      events: approvedEvents,
      mappings: {...currentApproval.mappings},
      fingerprint: createHash("sha256").update(JSON.stringify({
        events: approvedEvents,
        mappings: currentApproval.mappings,
      })).digest("hex"),
    };
  } else {
    state.manualReference.approved = null;
  }
  return true;
}

async function persistNormalizedManualReference(segment, state, approve = false) {
  if (workflow.key !== "innovation") return null;
  const coordination = await coordinationStatus();
  if (coordination.mode !== "available") return null;
  let coordinated = coordinationSessions.get(coordinationKey(segment));
  if (!coordinated?.leaseToken) {
    coordinated = await acquireCoordinationLease(segment);
  }
  const reference = state.manualReference;
  const result = await localJson("/api/coordination/manual-reference", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      workflow: workflowId,
      segment,
      leaseToken: coordinated.leaseToken,
      events: activeManualEvents(reference),
      mappings: reference.mappings,
      approve,
    }),
  });
  applyNormalizedManualReference(state, {
    draft: result.reference.status === "draft" ? result.reference : null,
    approved: result.reference.status === "approved" ? result.reference : null,
  });
  return result.reference;
}

async function saveState(
  segment,
  state,
  {allowAutoAcquire = true} = {},
) {
  if (
    (state.workflowId && state.workflowId !== workflowId)
    || (state.canvasId && state.canvasId !== canvasId)
  ) {
    throw new CanvasError(
      "review_workflow_mismatch",
      "Refusing to save review state owned by another workflow or Canvas.",
    );
  }
  const coordination = await coordinationStatus();
  if (coordination.mode === "unavailable") {
    throw new CanvasError(
      "coordination_unavailable",
      coordination.detail
        || "Shared coordination is unavailable; review state is read-only.",
    );
  }
  if (coordination.mode === "available") {
    const existing = coordinationSessions.get(coordinationKey(segment));
    if (!allowAutoAcquire && !existing?.leaseToken) return;
    const save = stateSaveQueue.catch(() => {}).then(async () => {
      const key = coordinationKey(segment);
      let coordinated = coordinationSessions.get(key);
      if (!coordinated?.leaseToken) {
        if (!allowAutoAcquire) return;
        coordinated = await acquireCoordinationLease(segment);
      }
      state.schemaVersion = 1;
      state.workflowId = workflowId;
      state.canvasId = canvasId;
      state.updatedAt = new Date().toISOString();
      const saved = await localJson("/api/coordination/state", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          workflow: workflowId,
          segment,
          leaseToken: coordinated.leaseToken,
          expectedVersion: coordinated.version,
          state,
        }),
      });
      coordinated.version = Number(saved.version);
      broadcast("state");
    });
    stateSaveQueue = save;
    await save;
    return;
  }
  await mkdir(artifactDirectory(), { recursive: true });
  state.schemaVersion = 1;
  const save = stateSaveQueue.catch(() => {}).then(async () => {
    state.workflowId = workflowId;
    state.canvasId = canvasId;
    state.updatedAt = new Date().toISOString();
    const path = statePath(segment);
    const content = `${JSON.stringify(state, null, 2)}\n`;
    await writeFile(path, content, "utf8");
    await updateSharedChecksum(path, content);
    broadcast("state");
  });
  stateSaveQueue = save;
  await save;
}

function canonicalType(type) {
  return {
    pass_candidate: "completed_pass",
    restart_pass_candidate: "completed_pass",
    turnover_candidate: "turnover",
  }[type] || type;
}

function snapshotEvents(snapshot) {
  return (snapshot?.predictions || []).map((event, index) => {
    const type = canonicalType(event.event_type);
    return {
      index,
      seconds: Number(event.completion_seconds ?? event.clip_seconds),
      releaseSeconds: Number(event.clip_seconds),
      team: event.team,
      type,
      title: eventTitle({...event, event_type: type}),
      details: event.details || "The rules engine produced this event.",
      confidence: Number.isFinite(Number(event.confidence))
        ? Number(event.confidence)
        : null,
      ballEvidence: event.ball_evidence || null,
    };
  }).filter((event) => Number.isFinite(event.seconds));
}

function engineReviewSnapshot(state, current) {
  return (
      isRegressionCurrent(state.regression, current)
      && state.regression?.passed === false
      && state.engineAfter?.outputHash
        === state.regression?.candidateOutputHash
    )
    ? state.engineAfter
    : current;
}

function engineEventReviewKey(event) {
  return [
    event.type,
    event.team,
    Number(event.seconds).toFixed(3),
  ].join("|");
}

async function confirmEngineEventReviewed(segment, index, reason) {
  const review = await reviewContext(segment);
  const cachedCurrent = await captureEngineSnapshot(segment);
  const current = engineReviewSnapshot(review.state, cachedCurrent);
  const events = snapshotEvents(current);
  const event = events[index];
  if (!Number.isInteger(index) || !event) {
    throw new CanvasError(
      "engine_event_missing",
      "The selected rules-engine event does not exist.",
    );
  }
  const key = engineEventReviewKey(event);
  const authorization = review.state.engineEventReviewAuthorizations[key];
  const clipConversationAuthorized = Boolean(
    reviewRequestPending
    && lastConversationContext?.segment === segment
    && lastConversationContext?.eventIndex === null
    && review.state.pendingClipRequest?.mode === "autopilot"
  );
  if (!authorization && !clipConversationAuthorized) {
    throw new CanvasError(
      "engine_event_review_not_authorized",
      "Verify this engine event through its Canvas button or an Autopilot clip conversation first.",
    );
  }
  if (
    authorization
    && (
      authorization.engineContentHash !== current.fingerprint.contentHash
      || authorization.outputHash !== current.outputHash
    )
  ) {
    throw new CanvasError(
      "engine_event_review_stale",
      "Engine code or output changed after verification was requested.",
    );
  }
  const record = {
    status: "confirmed",
    reviewedAt: new Date().toISOString(),
    reason: String(reason || "").trim(),
    engineContentHash: current.fingerprint.contentHash,
    outputHash: current.outputHash,
    userClaimedCorrect: Boolean(authorization?.userClaimedCorrect),
    userVerdict: authorization?.userVerdict || null,
  };
  review.state.engineEventReviews[key] = record;
  delete review.state.engineEventReviewAuthorizations[key];
  review.state.conversation.push({
    role: "system",
    content: (
      `E${index + 1} independently confirmed at `
      + `${event.seconds.toFixed(3)}s: ${record.reason}`
    ),
    eventIndex: null,
    engineIndex: index,
    timestamp: record.reviewedAt,
  });
  await saveState(segment, review.state);
  return { segment, index, event, review: record };
}

async function confirmEngineEventByProfessionalReviewer(segment, index) {
  const review = await reviewContext(segment);
  const cachedCurrent = await captureEngineSnapshot(segment);
  const current = engineReviewSnapshot(review.state, cachedCurrent);
  const events = snapshotEvents(current);
  const event = events[index];
  if (!Number.isInteger(index) || !event) {
    throw new CanvasError(
      "engine_event_missing",
      "The selected rules-engine event does not exist.",
    );
  }
  const key = engineEventReviewKey(event);
  const reviewedAt = new Date().toISOString();
  const record = {
    status: "confirmed",
    reviewedAt,
    reason: "Professional reviewer confirmed the exact team, canonical event type, and completion time from the targeted video evidence.",
    engineContentHash: current.fingerprint.contentHash,
    outputHash: current.outputHash,
    reviewSource: "professional_reviewer",
    userClaimedCorrect: true,
    userVerdict: "correct",
  };
  review.state.engineEventReviews[key] = record;
  delete review.state.engineEventReviewAuthorizations[key];
  review.state.conversation.push({
    role: "system",
    content: (
      `E${index + 1} approved by professional reviewer at `
      + `${event.seconds.toFixed(3)}s without a Copilot review.`
    ),
    eventIndex: null,
    engineIndex: index,
    timestamp: reviewedAt,
  });
  await saveState(segment, review.state);
  return { segment, index, event, review: record };
}

async function recordEngineEventNotConfirmed(segment, index, reason) {
  const review = await reviewContext(segment);
  const cachedCurrent = await captureEngineSnapshot(segment);
  const current = engineReviewSnapshot(review.state, cachedCurrent);
  const events = snapshotEvents(current);
  const event = events[index];
  if (!Number.isInteger(index) || !event) {
    throw new CanvasError(
      "engine_event_missing",
      "The selected rules-engine event does not exist.",
    );
  }
  const key = engineEventReviewKey(event);
  const authorization = review.state.engineEventReviewAuthorizations[key];
  const record = {
    status: "not_confirmed",
    reviewedAt: new Date().toISOString(),
    reason: String(reason || "").trim(),
    engineContentHash: current.fingerprint.contentHash,
    outputHash: current.outputHash,
    userClaimedCorrect: Boolean(authorization?.userClaimedCorrect),
    userVerdict: authorization?.userVerdict || null,
  };
  review.state.engineEventReviews[key] = record;
  delete review.state.engineEventReviewAuthorizations[key];
  review.state.conversation.push({
    role: "system",
    content: (
      `E${index + 1} was not confirmed at `
      + `${event.seconds.toFixed(3)}s: ${record.reason}`
    ),
    eventIndex: null,
    engineIndex: index,
    timestamp: record.reviewedAt,
  });
  await saveState(segment, review.state);
  return { segment, index, event, review: record };
}

async function cancelReviewAdjustment(segment, index, reason) {
  const review = await reviewContext(segment);
  if (!Number.isInteger(index) || !review.drafts[index]) {
    throw new CanvasError(
      "review_event_missing",
      "The selected review event does not exist.",
    );
  }
  if (review.state.decisions[String(index)]?.status !== "adjust") {
    throw new CanvasError(
      "review_adjustment_not_pending",
      "This event does not have a pending adjustment request.",
    );
  }
  delete review.state.decisions[String(index)];
  delete review.state.copilotAcceptanceAuthorizations[String(index)];
  review.state.conversation.push({
    role: "system",
    content: (
      `Adjustment request for Event ${index + 1} was cancelled without `
      + `changing the proposal: ${reason}`
    ),
    eventIndex: index,
    timestamp: new Date().toISOString(),
  });
  await saveState(segment, review.state);
  reviewRequestPending = false;
  if (
    lastConversationContext?.segment === segment
    && lastConversationContext?.eventIndex === index
  ) {
    lastConversationContext = null;
  }
  setActivity(
    "ready",
    `Event ${index + 1} adjustment cancelled`,
    "The proposal is unchanged and ready for review.",
  );
  return { segment, index, cancelled: true, proposalChanged: false };
}

function compareWithEngine(draft, snapshot) {
  if (!snapshot) {
    return {
      status: "not_run",
      label: "Engine not rerun",
      detail: "No post-change engine snapshot exists yet.",
    };
  }
  if (draft.behavior?.kind === "match_state") {
    const interval = snapshot.matchState?.intervals?.find((candidate) =>
      candidate.state === draft.behavior.state
      && Number(candidate.start_seconds) <= draft.behavior.from
      && Number(candidate.end_seconds) >= draft.behavior.to
    );
    const leakedEvents = snapshot.predictions.filter((event) => {
      const seconds = Number(
        event.completion_seconds ?? event.clip_seconds,
      );
      return seconds >= draft.behavior.from
        && seconds < draft.behavior.to;
    });
    if (interval && leakedEvents.length === 0) {
      return {
        status: "already_agrees",
        label: "Engine already agrees",
        detail: "Restart-pending covers the stoppage and no ordinary event leaks through.",
      };
    }
    return {
      status: "conflicting",
      label: "Engine behavior conflicts",
      detail: interval
        ? `${leakedEvents.length} ordinary event(s) occur during the stoppage.`
        : "The accepted restart-pending interval is missing.",
    };
  }

  const candidates = snapshot.predictions.map((event) => ({
    event,
    seconds: Number(event.completion_seconds ?? event.clip_seconds),
    type: canonicalType(event.event_type),
  }));
  const manualReview = ["manual_review", "user_reported"].includes(
    draft.source,
  );
  const sameFrameRequired = manualReview || draft.sameFrameEngineReview;
  const timesMatch = (seconds) => sameFrameRequired
    ? Math.round(seconds * 25) === Math.round(draft.seconds * 25)
    : Math.abs(seconds - draft.seconds) <= 1;
  const exact = candidates
    .filter((candidate) =>
      candidate.type === draft.type
      && candidate.event.team === draft.team
      && timesMatch(candidate.seconds)
    )
    .sort((left, right) =>
      Math.abs(left.seconds - draft.seconds)
      - Math.abs(right.seconds - draft.seconds)
    )[0];
  if (exact) {
    return {
      status: "already_agrees",
      label: "Engine already agrees",
      detail: sameFrameRequired
        ? `${manualReview ? "Matched manual reference" : "Matched strict C# timing"} on frame ${Math.round(draft.seconds * 25)} at ${exact.seconds.toFixed(3)}s.`
        : `Matched at ${exact.seconds.toFixed(3)}s within the 1.0s tolerance.`,
    };
  }
  const nearby = candidates
    .filter((candidate) =>
      Math.abs(candidate.seconds - draft.seconds) <= 1
    )
    .sort((left, right) =>
      Math.abs(left.seconds - draft.seconds)
      - Math.abs(right.seconds - draft.seconds)
    )[0];
  if (nearby) {
    return {
      status: "conflicting",
      label: "Engine result conflicts",
      detail: `Nearby engine event is ${canonicalType(nearby.type)} for ${nearby.event.team}.`,
    };
  }
  return {
    status: "missing",
    label: "Accepted event is missing",
    detail: "A general inference change is required before verification.",
  };
}

async function compareWithCurrentEngine(segment, draft, state) {
  const current = await captureEngineSnapshot(segment);
  const snapshots = storedSnapshots(state);
  const matched = matchingStoredSnapshot(current, state);
  if (matched) {
    const [snapshotKind, snapshot] = matched;
    return {
      engineComparison: compareWithEngine(draft, snapshot),
      engineVerification: engineVerificationReceipt(
        current,
        snapshot,
        snapshotKind,
      ),
    };
  }
  const reference = referenceStoredSnapshot(current, state);
  const [snapshotKind, snapshot] = reference;
  const codeMatches =
    snapshot?.fingerprint?.contentHash === current.fingerprint.contentHash;
  const outputMatches = snapshot?.outputHash === current.outputHash;
  const staleReasons = [
    ...(!codeMatches ? ["engine_code"] : []),
    ...(!outputMatches ? ["cached_output"] : []),
  ];
  const detail = !codeMatches && !outputMatches
    ? "Current engine code and cached event output differ from the stored snapshots."
    : !codeMatches
      ? "Current engine code differs from the code that produced the stored snapshot."
      : "Current cached event output differs from the stored snapshot.";
  return {
    engineComparison: {
      status: "stale",
      label: "Engine snapshot is stale",
      detail: `${detail} Rerun only the cached event-building stage before claiming agreement.`,
    },
    engineVerification: engineVerificationReceipt(
      current,
      snapshot,
      snapshotKind,
      false,
      staleReasons,
    ),
  };
}

function acceptedEngineComparison(draft, state, decision, current) {
  const verification = decision?.engineVerification;
  if (verification?.fresh === false) {
    return {
      status: "stale",
      label: "Engine snapshot is stale",
      detail: "The acceptance check found changed engine code or cached output; a cached event-stage rerun is required.",
    };
  }
  if (verification) {
    if (!isVerificationCurrent(verification, current)) {
      return {
        status: "stale",
        label: "Engine snapshot is stale",
        detail: "Engine code or cached output changed after this event was accepted.",
      };
    }
    return compareWithEngine(draft, current);
  }
  return compareWithEngine(draft, state.engineAfter || state.engineBefore);
}

function publicationFingerprint(drafts, state) {
  return createHash("sha256").update(JSON.stringify(
    drafts.map((draft, index) => ({
      proposal: proposalFingerprint(draft),
      decision: state.decisions[String(index)]?.status || null,
    })),
  )).digest("hex");
}

function publicationPlan(drafts, state, current) {
  const engineEvents = snapshotEvents(current).map((event) => ({
    ...event,
    reviewKey: engineEventReviewKey(event),
  }));
  const decisions = Object.fromEntries(
    Object.entries(state.decisions).map(([index, decision]) => [
      index,
      decision?.status !== "accepted"
        ? decision
        : {
            ...decision,
            engineVerification: {
              ...decision.engineVerification,
              status: compareWithEngine(
                drafts[Number(index)],
                current,
              ).status,
            },
          },
    ]),
  );
  return buildPublicationPlan({
    drafts,
    decisions,
    engineEvents,
    engineEventReviews: state.engineEventReviews || {},
    current,
    snapshotMatches: Boolean(matchingStoredSnapshot(current, state)),
    verificationIsCurrent: isVerificationCurrent,
    regressionFresh: Boolean(
      state.regression?.passed
      && isRegressionCurrent(state.regression, current)
    ),
  });
}

async function reviewContext(requestedSegment = defaultSegment) {
  const segments = await loadPreparedSegments();
  const selected = segments.find(
    (segment) => segment.key === requestedSegment,
  );
  if (!selected) {
    throw new Error(`Prepared segment not found: ${requestedSegment}`);
  }
  if (/^segment-\d{4}-\d{3}$/.test(selected.key)) {
    const status = await localJson(
      `${workflow.statusPath}?cache_key=${encodeURIComponent(selected.key)}`,
    );
    selected.state = status.state;
    selected.validationStatus = selected.validated
      ? "passed"
      : selected.key === defaultSegment
        ? "in_review"
        : status.state === "ready" ? "ai_ready" : status.state;
    selected.processedFrames = Number(status.processed_frames || 0);
    selected.expectedFrames = Number(status.expected_frames || 0);
    selected.stage = status.stage || null;
    selected.statusMessage = status.message || null;
    selected.runProvenance = status.run_provenance || null;
    selected.performance = status.performance || null;
    selected.recoveryAvailable = workflow.key === "live" && Boolean(
      selected.state === "failed"
      && selected.expectedFrames > 0
      && selected.processedFrames >= selected.expectedFrames
    );
    selected.stageTiming = workflow.key === "live"
      ? await liveStageTiming(selected)
      : null;
    selected.coordinateMode = workflow.coordinateMode;
    selected.trackingUrl = status.tracking_url
      ? `${localServer}${status.tracking_url}`
      : null;
  }
  let drafts = await loadDrafts(selected.key, selected);
  const state = await loadState(selected.key, selected, drafts);
  if (state.publishedReference && !selected.validated) {
    drafts = await loadDrafts(
      selected.key,
      {...selected, validated: true},
    );
  }
  if (
    selected.state === "ready"
    && !selected.validated
    && !state.publishedReference
    && selected.key !== defaultSegment
  ) {
    const snapshot = await captureEngineSnapshot(selected.key);
    if (state.engineCandidateOutputHash !== snapshot.outputHash) {
      if (!hasReviewHistory(state)) {
        state.proposalOverrides = {};
        state.engineBefore = snapshot;
        state.engineAfter = null;
      }
      state.regression = null;
      state.engineCandidateOutputHash = snapshot.outputHash;
      await saveState(selected.key, state, {allowAutoAcquire: false});
    }
  }
  const copilotEvents = [
    ...drafts,
    ...(state.additionalProposals || []).filter(
      (proposal) => proposal.source !== "manual_review"
    ),
  ];
  const allDrafts = workflow.key === "innovation"
    ? activeManualEvents(state.manualReference)
    : [...drafts, ...state.additionalProposals];
  const effectiveDrafts = allDrafts.map((draft, index) => {
    const override = state.proposalOverrides[String(index)];
    const effective = override
      ? {
          ...draft,
          ...override,
          source: ["manual_review", "user_reported"].includes(draft.source)
            ? "manual_review"
            : "adjusted_proposal",
        }
      : draft;
    return {
      ...effective,
      sameFrameEngineReview:
        Boolean(state.sameFrameReviewRequirements[String(index)]),
    };
  });
  const actionFocuses = await loadActionFocuses(
    selected,
    effectiveDrafts,
  );
  if (
    selected.state === "ready"
    && activity.state === "working"
    && /segment AI|event logic/i.test(activity.label)
  ) {
    setActivity(
      "ready",
      "AI events ready for review",
      effectiveDrafts.length
        ? `${effectiveDrafts.length} event candidate(s) are now available.`
        : "The AI run completed without producing event candidates.",
    );
  } else if (
    selected.state === "failed"
    && selected.ballTrackAvailable
    && /ball provenance review required/i.test(selected.statusMessage || "")
  ) {
    setActivity(
      "waiting",
      "Ball coordinates need review",
      selected.statusMessage,
    );
  } else if (selected.state === "failed") {
    setActivity(
      "error",
      "Segment AI failed",
      selected.statusMessage || "See the segment analysis log.",
    );
  }
  return {
    segments,
    selected,
    drafts: effectiveDrafts,
    copilotEvents,
    state,
    actionFocuses,
  };
}

function displayedActivity(selected, state) {
  if (reviewRequestPending) return activity;
  if (
    workflow.key === "innovation"
    && selected.state === "prepared"
    && !selected.evidenceReady
  ) {
    return {
      state: "waiting",
      label: "Innovation segment prepared",
      detail: "The playable video is ready. Frozen BAC coordinates and YOLO "
        + "player context have not been prepared, and no football events exist.",
    };
  }
  if (
    workflow.key === "innovation"
    && ["processing", "detections_ready", "building"].includes(selected.state)
  ) {
    const preparingEvidence = [
        "bac_coordinates",
        "player_detection",
        "player_tracking",
    ].includes(selected.stage);
    return {
        state: "working",
        label: preparingEvidence
          ? "Preparing Innovation evidence"
          : "Processing Innovation rules engine",
        detail: selected.statusMessage || (
          preparingEvidence
            ? "Preparing frozen BAC coordinates and YOLO player context."
            : "Building football events from prepared evidence."
        ),
    };
  }
  if (workflow.key === "innovation" && selected.state === "evidence_ready") {
    return {
      state: "waiting",
      label: "Innovation evidence ready",
      detail: "Frozen BAC coordinates and YOLO player context are ready. "
        + "No football events exist until the Innovation engine is run.",
    };
  }
  if (state.coordinateReview?.status === "finalized") {
    if (workflow.key === "innovation") {
      return {
        state: "ready",
        label: selected.validated
          ? "Passed Innovation segment"
          : "Innovation segment ready for review",
        detail: "Frozen BAC coordinates and Innovation engine output are loaded. "
          + "No Live ball-tracking gate is required.",
      };
    }
    return {
      state: "ready",
      label: "Segment in review",
      detail: "The rules-engine run was authorized after the 90% coordinate minimum.",
    };
  }
  if (state.coordinateReview?.status === "verified") {
    if (workflow.key === "innovation") {
      return {
        state: "waiting",
        label: "Frozen BAC coordinates ready",
        detail: "The read-only BAC coordinate artifact is available for event review.",
      };
    }
    return {
      state: "waiting",
      label: "Ball coordinate gate passed",
      detail: "Choose Finalize to proceed now, or continue reviewing the remaining frames.",
    };
  }
  if (["processing", "detections_ready", "building"].includes(selected.state)) {
    const progress = selected.expectedFrames
      ? `${selected.processedFrames}/${selected.expectedFrames} sampled frames. `
      : "";
    return {
      state: "working",
      label: "AI processing locally",
      detail: progress + (
        selected.statusMessage || "The current pipeline stage is still running."
      ),
    };
  }
  if (selected.state === "failed") {
    if (
      selected.ballTrackAvailable
      && /ball provenance review required/i.test(selected.statusMessage || "")
    ) {
      return {
        state: "waiting",
        label: "Ball coordinates need review",
        detail: "Tracking completed. Review the estimated coordinates and "
          + "recover every additional frame supported by raw-video evidence; "
          + "90% is the minimum gate, not the target.",
      };
    }
    return {
      state: "error",
      label: "Segment AI failed",
      detail: "Open the run status below for recovery guidance.",
    };
  }
  if (selected.state === "prepared") {
    return {
      state: "waiting",
      label: "Segment prepared — AI not started",
      detail: "Start AI when you are ready to process the raw video.",
    };
  }
  return activity;
}

function ballCoordinateReviewRequired(selected) {
  return Boolean(
    selected.state === "failed"
    && selected.ballTrackAvailable
    && /ball provenance review required/i.test(selected.statusMessage || "")
  );
}

function ballCoordinateReviewCanBeVerified(selected) {
  return selected.state === "ready" || ballCoordinateReviewRequired(selected);
}

async function ballCoordinateReviewSnapshot(segment) {
  const provenancePath = join(
    segmentRoot(segment),
    "analytics-data",
    "ball-provenance.json",
  );
  const provenanceContent = await readFile(provenancePath);
  const provenance = JSON.parse(provenanceContent.toString("utf8"));
  return {
    directFrameCount: Number(provenance.direct_frame_count),
    sampledFrameCount: Number(provenance.sampled_frame_count),
    directProvenance: Number(provenance.direct_provenance),
    trackerHash: (await componentVersions()).tracker,
    provenanceHash: createHash("sha256")
      .update(provenanceContent)
      .digest("hex"),
  };
}

function activeCoordinateBatch(state) {
  const id = state.coordinateReview?.activeBatchId;
  return state.coordinateReview?.batches?.find((batch) => batch.id === id)
    || null;
}

async function coordinateOutputSnapshot(selected) {
  const [track, provenance] = await Promise.all([
    loadDetectedBallTrack(selected),
    readJson(
      join(
        segmentRoot(selected.key),
        "analytics-data",
        "ball-provenance.json",
      ),
      null,
    ),
  ]);
  const directFrames = (track?.states || [])
    .filter((point) => point.direct)
    .map((point) => point.frame)
    .sort((left, right) => left - right);
  return {
    directFrameCount: Number(
      provenance?.direct_frame_count ?? directFrames.length,
    ),
    sampledFrameCount: Number(
      provenance?.sampled_frame_count ?? track?.states?.length ?? 0,
    ),
    directProvenance: Number(
      provenance?.direct_provenance
      ?? (
        track?.states?.length
          ? directFrames.length / track.states.length
          : 0
      ),
    ),
    directFrames,
    yoloCandidateCounts: Object.fromEntries(
      Object.entries(track?.yoloCandidates || {}).map(
        ([frame, candidates]) => [frame, candidates.length],
      ),
    ),
  };
}

function coordinateCarryForward(batch, frames) {
  return Object.fromEntries(frames.map((frame) => {
    const observation = batch.observations?.[String(frame)] || {};
    const status = batch.frameResults?.[String(frame)]?.status || "unresolved";
    const candidateCount = Number(
      batch.after?.yoloCandidateCounts?.[String(frame)] || 0,
    );
    let reason;
    if (status === "regressed") {
      reason = "A previously direct coordinate disappeared in the persisted rerun; this is a tracker regression that requires fresh inspection.";
    } else if (observation.decision === "yolo_candidate") {
      reason = `The reported YOLO candidate remained unselected: ${candidateCount} raw candidate${candidateCount === 1 ? " was" : "s were"} present, but the persisted tracker did not publish one after its trajectory and visual-consistency gates.`;
    } else if (observation.decision === "undefined") {
      reason = "No direct coordinate was independently published. The previous review found the ball occluded or not visually locatable, so the runtime estimate was retained.";
    } else if (observation.decision === "specified") {
      reason = candidateCount
        ? `The reported visible ball, including possible aerial motion, was not independently recovered. Raw YOLO produced ${candidateCount} candidate${candidateCount === 1 ? "" : "s"}, but none was published by the tracker after selection and visual-consistency checks.`
        : "The reported visible ball, including possible aerial motion, was not independently recovered because raw YOLO produced no sports-ball candidate and focused reacquisition did not publish direct evidence.";
    } else if (observation.decision === "agree") {
      reason = "The previously supported coordinate was not retained as direct evidence by the persisted rerun and requires fresh inspection.";
    } else if (observation.decision === "needs_more_checking") {
      reason = "The previous evidence remained visually ambiguous and the persisted rerun did not produce an independently supported direct coordinate.";
    } else {
      reason = "The persisted rerun did not produce an independently supported direct coordinate.";
    }
    return [String(frame), {
      sourceBatchId: batch.id,
      sourceRound: batch.number,
      status,
      reason,
    }];
  }));
}

async function reconcileCoordinateReviewBatch(context) {
  const {selected, state} = context;
  const batch = activeCoordinateBatch(state);
  if (!batch || batch.status !== "rerun_started") return;
  const running = ["processing", "detections_ready", "building"].includes(
    selected.state,
  );
  if (running) {
    if (batch.awaitingRunObservation) {
      batch.awaitingRunObservation = false;
      await saveState(selected.key, state, {allowAutoAcquire: false});
    }
    return;
  }
  if (batch.awaitingRunObservation) return;
  if (!selected.ballTrackAvailable) {
    batch.status = "failed";
    batch.failedAt = new Date().toISOString();
    batch.failure = selected.statusMessage || "Ball-coordinate rerun failed.";
    state.coordinateReview.status = "pending";
    await saveState(selected.key, state, {allowAutoAcquire: false});
    return;
  }
  const after = await coordinateOutputSnapshot(selected);
  const beforeDirect = new Set(batch.before?.directFrames || []);
  const afterDirect = new Set(after.directFrames);
  const reviewedFrames = new Set(batch.frames || []);
  const regressions = [...beforeDirect]
    .filter((frame) => !afterDirect.has(frame))
    .sort((left, right) => left - right);
  const results = {};
  [...new Set([...(batch.frames || []), ...regressions])]
    .sort((left, right) => left - right)
    .forEach((frame) => {
      results[String(frame)] = {
        status: afterDirect.has(frame)
          ? beforeDirect.has(frame) ? "unchanged_direct" : "fixed"
          : beforeDirect.has(frame) ? "regressed" : "unresolved",
      };
    });
  const unresolved = [...reviewedFrames]
    .filter((frame) => !afterDirect.has(frame));
  const nextFrames = [...new Set([...unresolved, ...regressions])]
    .sort((left, right) => left - right);
  batch.status = "done";
  batch.rerunCompletedAt = new Date().toISOString();
  batch.after = after;
  batch.frameResults = results;
  batch.fixedFrames = (batch.frames || []).filter(
    (frame) => !beforeDirect.has(frame) && afterDirect.has(frame),
  );
  batch.unresolvedFrames = unresolved;
  batch.regressionFrames = regressions;
  state.coordinateReview.status = "pending";
  state.coordinateReview.activeBatchId = null;
  if (after.directProvenance < 0.90 && nextFrames.length) {
    const nextNumber = Math.max(
      0,
      ...state.coordinateReview.batches.map(
        (candidate) => Number(candidate.number || 0),
      ),
    ) + 1;
    const nextBatch = {
      id: `coordinate-round-${nextNumber}`,
      number: nextNumber,
      status: "ready",
      frames: nextFrames,
      observations: {},
      createdAt: batch.rerunCompletedAt,
      before: after,
      frameResults: {},
      carryForward: coordinateCarryForward(batch, nextFrames),
    };
    state.coordinateReview.batches.push(nextBatch);
    state.coordinateReview.activeBatchId = nextBatch.id;
    state.coordinateReview.flaggedFrames = nextFrames;
  }
  await saveState(selected.key, state, {allowAutoAcquire: false});
}

const publicStateRequests = new Map();

async function coalescedPublicState(requestedSegment, copilotSession) {
  const requestKey = JSON.stringify([
    requestedSegment,
    copilotSession.connected,
    copilotSession.repositoryAvailable,
    copilotSession.message,
  ]);
  const existing = publicStateRequests.get(requestKey);
  if (existing) return existing;
  const pending = publicState(requestedSegment, copilotSession).finally(() => {
    if (publicStateRequests.get(requestKey) === pending) {
      publicStateRequests.delete(requestKey);
    }
  });
  publicStateRequests.set(requestKey, pending);
  return pending;
}

export async function publicState(
  requestedSegment = defaultSegment,
  copilotSession = {
    connected: false,
    repositoryAvailable: false,
    message: "Copilot project session status is unavailable.",
  },
  runtimeFixture = null,
) {
  if (runtimeFixture) {
    return {
      ...publicManualReferenceState(
        runtimeFixture.workflowKey,
        runtimeFixture.state,
        runtimeFixture.copilotEvents || [],
        runtimeFixture.engineEvents || [],
      ),
      engineEvents: runtimeFixture.engineEvents || [],
    };
  }
  const context = await reviewContext(requestedSegment);
  await reconcileCoordinateReviewBatch(context);
  const {
    segments,
    selected,
    drafts,
    copilotEvents,
    state,
    actionFocuses,
  } = context;
  const coordinationHealth = await coordinationStatus();
  const identityResult = coordinationHealth.mode === "available"
    ? await coordinationIdentity()
    : {identity: null};
  let activeLeases = [];
  if (coordinationHealth.mode === "available") {
    try {
      activeLeases = (
        await localJson(
          "/api/coordination/leases?workflow="
            + encodeURIComponent(workflowId),
        )
      ).leases || [];
    } catch (error) {
      coordinationHealth.mode = "unavailable";
      coordinationHealth.detail = error.message;
    }
  }
  const leasesBySegment = new Map(
    activeLeases.map((lease) => [lease.segment, lease]),
  );
  const publicLease = (segment) => {
    const lease = leasesBySegment.get(segment);
    if (!lease) return {active: false, heldByCurrent: false};
    const heldByCurrent = Boolean(
      coordinationSessions.get(coordinationKey(segment))?.leaseToken
      && identityResult.identity
      && lease.holderId === identityResult.identity.developerId
      && lease.machineId === identityResult.identity.machineId
    );
    return {
      active: true,
      heldByCurrent,
      holderName: lease.holderName,
      machineLabel: heldByCurrent
        ? identityResult.identity.machineLabel
        : lease.machineLabel,
      stage: lease.stage,
      heartbeatAt: lease.heartbeatAt,
      expiresAt: lease.expiresAt,
    };
  };
  segments.forEach((segment) => {
    segment.coordinationLease = publicLease(segment.key);
  });
  if (state.publishedReference && !selected.validated) {
    selected.validationStatus = "published_stale";
  }
  const currentEngine = await captureEngineSnapshot(requestedSegment);
  let ballProvenance;
  let ballRecoveryDiagnostic;
  if (workflow.key === "innovation") {
    const frozenBallTrack = await loadDetectedBallTrack(selected);
    const frozenCoordinateCount = frozenBallTrack?.states?.length || 0;
    ballProvenance = {
      direct_frame_count: frozenCoordinateCount,
      sampled_frame_count: frozenCoordinateCount,
      direct_provenance: frozenCoordinateCount ? 1 : 0,
      source_kind: frozenBallTrack?.sourceKind || null,
      pipeline_mode: frozenBallTrack?.pipelineMode || null,
      review_required: false,
    };
    ballRecoveryDiagnostic = null;
  } else {
    ballProvenance = await readJson(
      join(
        segmentRoot(requestedSegment),
        "analytics-data",
        "ball-provenance.json",
      ),
      null,
    );
    const storedBallRecoveryDiagnostic = await readJson(
      join(
        segmentRoot(requestedSegment),
        "analytics-data",
        "ball-recovery-diagnostic.json",
      ),
      null,
    );
    ballRecoveryDiagnostic = state.coordinateReview?.batches?.some(
      (batch) => batch.status === "done" && batch.rerunCompletedAt,
    )
      ? null
      : storedBallRecoveryDiagnostic;
  }
  const regressionFresh = isRegressionCurrent(
    state.regression,
    currentEngine,
  );
  const displayedEngine = engineReviewSnapshot(state, currentEngine);
  const showRegressionCandidate = displayedEngine !== currentEngine;
  const publishedEventPayloads = new Set(
    (state.engineBefore?.predictions || []).map((event) =>
      JSON.stringify(event)
    ),
  );
  const engineEvents = snapshotEvents(displayedEngine).map((event, index) => {
    const review = state.engineEventReviews?.[engineEventReviewKey(event)];
    return {
      ...event,
      key: `E${index + 1}`,
      regressionChange: showRegressionCandidate
        && !publishedEventPayloads.has(
          JSON.stringify(displayedEngine.predictions[event.index]),
        )
          ? "added"
          : null,
      review: review
        ? {
            ...review,
            fresh:
              review.engineContentHash
                === displayedEngine.fingerprint.contentHash
              && review.outputHash === displayedEngine.outputHash,
          }
        : null,
    };
  });
  const manualPublicState = publicManualReferenceState(
    workflow.key,
    state,
    copilotEvents,
    engineEvents,
  );
  const publication = publicationPlan(drafts, state, currentEngine);
  if (
    ballCoordinateReviewCanBeVerified(selected)
    && state.coordinateReview?.status === "finalized"
    && !selected.validated
  ) {
    selected.validationStatus = "in_review";
  }
  const sharedReviewStatus = await Promise.all(segments.map(async (segment) => {
    let stored;
    try {
      if (segment.key === selected.key) {
        stored = state;
      } else if (coordinationHealth.mode === "available") {
        const snapshot = await localJson(
          "/api/coordination/state?workflow="
            + encodeURIComponent(workflowId)
            + "&segment=" + encodeURIComponent(segment.key),
        );
        stored = snapshot.state;
      } else {
        stored = await readReviewState(
          statePath(segment.key),
          null,
          Boolean(sharedArtifactRoot),
        );
        if (!stored && sharedArtifactRoot) {
          stored = await readReviewState(
            legacyStatePath(segment.key),
            null,
          );
        }
      }
    } catch (error) {
      return {
        segment: segment.key,
        accepted: 0,
        rejected: 0,
        reviewed: 0,
        regression: "unavailable",
        published: false,
        integrityError: true,
        blockers: [
          `Review state unavailable: ${String(error.message || error)}`,
        ],
        updatedAt: null,
      };
    }
    if (!stored) {
      return {
        segment: segment.key,
        accepted: 0,
        rejected: 0,
        reviewed: 0,
        regression: "not_run",
        published: Boolean(segment.validated),
        blockers: ["Review has not started."],
        updatedAt: null,
      };
    }
    const storedDrafts = segment.key === selected.key
      ? drafts
      : [
          ...await loadDrafts(segment.key, segment),
          ...(stored.additionalProposals || []),
        ].map((draft, index) => ({
          ...draft,
          ...(stored.proposalOverrides?.[String(index)] || {}),
        }));
    const current = segment.key === selected.key
      ? currentEngine
      : await captureEngineSnapshot(segment.key, currentEngine.fingerprint);
    const decisions = Object.values(stored.decisions || {});
    const published = Boolean(
      stored.publishedReference || segment.validated,
    );
    const unavailableProposalData = Object.keys(stored.decisions || {}).some(
      (index) => !storedDrafts[Number(index)],
    );
    const plan = published
      ? {blockers: []}
      : unavailableProposalData
      ? {
          blockers: [
            "Stored decisions reference proposal data that is no longer "
              + "available; this segment must be reopened before publication.",
          ],
        }
      : publicationPlan(storedDrafts, stored, current);
    const storedMetadataOnly = Boolean(
      stored.regression
      && stored.engineBefore
      && stored.engineAfter
      && JSON.stringify(stored.engineBefore.predictions)
        === JSON.stringify(stored.engineAfter.predictions)
      && JSON.stringify(matchStateBehavior(stored.engineBefore.matchState))
        === JSON.stringify(matchStateBehavior(stored.engineAfter.matchState))
      && JSON.stringify(stored.engineBefore.matchState)
        !== JSON.stringify(stored.engineAfter.matchState)
    );
    const regressionChangeKind = (
      stored.regression?.changeKind
      || (storedMetadataOnly ? "metadata_only" : null)
    );
    return {
      segment: segment.key,
      accepted: decisions.filter(
        (decision) => decision?.status === "accepted",
      ).length,
      rejected: decisions.filter(
        (decision) => decision?.status === "rejected",
      ).length,
      reviewed: decisions.length,
      proposalCount: Math.max(storedDrafts.length, decisions.length),
      regression: !stored.regression
        ? "not_run"
        : isRegressionCurrent(stored.regression, current)
          ? stored.regression.passed || storedMetadataOnly
            ? "passed"
            : "failed"
          : "stale",
      regressionSummary: storedMetadataOnly
        ? "Passed: events and match-state behavior are unchanged; the current "
          + "output adds schema v2 football-law provenance metadata."
        : stored.regression?.summary || null,
      regressionChangeKind,
      regressionBaselineOutputHash:
        stored.regression?.baselineOutputHash || null,
      regressionCandidateOutputHash:
        stored.regression?.candidateOutputHash || null,
      published,
      blockers: plan.blockers,
      updatedAt: stored.updatedAt || null,
    };
  }));
  const workflowRegression = workflow.key === "innovation"
    ? (
        await readJson(regressionRegistryPath, {
          last_full_regression: null,
        })
      ).last_full_regression || null
    : null;
  return {
    segment: selected,
    segments,
    copilotSession,
    coordination: {
      mode: coordinationHealth.mode,
      message: coordinationHealth.detail,
      identity: identityResult.identity,
      lease: publicLease(selected.key),
      stateVersion: Number(
        coordinationSessions.get(coordinationKey(selected.key))?.version || 0,
      ),
    },
    drafts: drafts.map((draft, index) => {
      const decision = state.publishedReference
        ? {
            status: "accepted",
            note: "Published validated reference",
            decidedAt: state.publishedReference.publishedAt,
            source: "published_reference",
          }
        : state.decisions[String(index)] || null;
      return {
        ...draft,
        index,
        actionFocus: actionFocuses[index],
        decision,
        comparison: decision?.status === "accepted"
          ? acceptedEngineComparison(draft, state, decision, currentEngine)
          : null,
        afterComparison: decision?.status === "accepted" && state.engineAfter
          ? compareWithEngine(draft, state.engineAfter)
          : null,
      };
    }),
    ...manualPublicState,
    engineEvents,
    engineDisplayMode: showRegressionCandidate
      ? "regression_candidate"
      : "published",
    ballProvenance,
    ballRecoveryDiagnostic,
    coordinateReview: state.coordinateReview,
    trajectoryAudit: state.trajectoryAudit || {
      observations: {},
      updatedAt: null,
    },
    engineBefore: {
      capturedAt: state.engineBefore.capturedAt,
      fingerprint: state.engineBefore.fingerprint,
      outputHash: state.engineBefore.outputHash,
    },
    engineAfter: state.engineAfter
      ? {
          capturedAt: state.engineAfter.capturedAt,
          fingerprint: state.engineAfter.fingerprint,
          outputHash: state.engineAfter.outputHash,
        }
      : null,
    regression: state.regression
      ? {...state.regression, fresh: regressionFresh}
      : null,
    conversation: state.conversation,
    pendingMissingCandidate: state.pendingMissingCandidate,
    automaticCopilotReview: state.automaticCopilotReview,
    publication: {
      reviewComplete: publication.reviewComplete,
      regressionFresh: publication.regressionFresh,
      ready: publication.ready,
      blockers: publication.blockers,
      referenceEventCount: publication.referenceEvents.length,
      engineEventCount: publication.engineEventCount,
      published: Boolean(state.publishedReference || selected.validated),
      currentlyValidated: Boolean(selected.validated),
    },
    sharedReviewStatus,
    workflowRegression,
    regressionJobs: publicSegmentRegressionProgress(),
    activeConversation: reviewRequestPending ? lastConversationContext : null,
    activity: displayedActivity(selected, state),
    componentVersions: await componentVersions(),
    replayRuns: await buildReplayRuns(segments),
  };
}

function sendJson(response, status, payload) {
  const body = JSON.stringify(payload);
  response.writeHead(status, {
    "Cache-Control": "no-store",
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": Buffer.byteLength(body),
  });
  response.end(body);
}

async function readBody(request, maximumBytes = 16_384) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > maximumBytes) {
      throw new Error("Request body is too large");
    }
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

async function saveCustomCameraSample(request, url) {
  if (!customCameraSourceRoot) {
    throw new Error(
      "Shared artifact storage is unavailable. Set FOOTBALL_ARTIFACT_ROOT "
        + "before adding a camera.",
    );
  }
  const cameraName = String(url.searchParams.get("name") || "").trim();
  const clubName = String(url.searchParams.get("club") || "").trim();
  const venueName = String(url.searchParams.get("venue") || "").trim();
  const cameraPosition = String(url.searchParams.get("position") || "").trim();
  const serialNumber = String(url.searchParams.get("serial") || "").trim();
  const originalName = String(url.searchParams.get("file") || "").trim();
  const width = Number(url.searchParams.get("width"));
  const height = Number(url.searchParams.get("height"));
  const duration = Number(url.searchParams.get("duration"));
  if (!cameraName || cameraName.length > 80) {
    throw new Error("Camera name must contain 1 to 80 characters");
  }
  for (const [label, value] of [
    ["Club", clubName],
    ["Venue", venueName],
    ["Camera position", cameraPosition],
  ]) {
    if (!value || value.length > 100) {
      throw new Error(`${label} must contain 1 to 100 characters`);
    }
  }
  if (serialNumber.length > 120) {
    throw new Error("Serial number must not exceed 120 characters");
  }
  if (
    !Number.isInteger(width) || width <= 0
    || !Number.isInteger(height) || height <= 0
  ) {
    throw new Error("Video dimensions are invalid");
  }
  if (
    !Number.isFinite(duration)
    || !cameraSampleDurationSeconds
      .some((allowed) => Math.abs(duration - allowed) <= 0.25)
  ) {
    throw new Error("Camera sample must be exactly 30 or 60 seconds");
  }
  const extension = originalName.toLowerCase().match(/\.(mp4|mov|webm)$/)?.[0];
  if (!extension) {
    throw new Error("Camera sample must be MP4, MOV, or WebM");
  }
  const contentLength = Number(request.headers["content-length"]);
  if (
    !Number.isFinite(contentLength) || contentLength <= 0
    || contentLength > 2_000_000_000
  ) {
    throw new Error("Camera sample must be a non-empty file below 2 GB");
  }
  const cameraId = randomUUID();
  const key = `custom-${cameraId}`;
  const root = join(customCameraSourceRoot, key);
  const finalPath = join(root, `sample${extension}`);
  const temporaryPath = join(root, `sample-uploading${extension}`);
  await mkdir(root, {recursive: true});
  const handle = await open(temporaryPath, "w");
  let received = 0;
  try {
    for await (const chunk of request) {
      received += chunk.length;
      if (received > contentLength || received > 2_000_000_000) {
        throw new Error("Camera sample exceeded the declared upload size");
      }
      await handle.write(chunk);
    }
  } finally {
    await handle.close();
  }
  if (received !== contentLength) {
    await unlink(temporaryPath).catch(() => {});
    throw new Error("Camera sample upload was incomplete");
  }
  await rename(temporaryPath, finalPath);
  const metadataPath = join(root, "camera.json");
  const metadata = {
    schema_version: 2,
    cache_key: key,
    club_id: randomUUID(),
    camera_id: cameraId,
    camera_name: cameraName,
    club_name: clubName,
    venue_id: randomUUID(),
    venue_name: venueName,
    camera_position: cameraPosition,
    manufacturer_serial_number: serialNumber || null,
    recording_id: randomUUID(),
    video_filename: `sample${extension}`,
    image_width: width,
    image_height: height,
    duration_seconds: duration,
    added_at: new Date().toISOString(),
  };
  await writeJsonAtomically(metadataPath, metadata);
  if (sharedArtifactRoot) {
    await updateSharedChecksum(finalPath);
    await updateSharedChecksum(
      metadataPath,
      `${JSON.stringify(metadata, null, 2)}\n`,
    );
  }
  return {segment: key};
}

function broadcast(eventName) {
  for (const response of eventStreams) {
    response.write(`event: ${eventName}\ndata: {}\n\n`);
  }
}

function setActivity(state, label, detail) {
  activity = { state, label, detail };
  broadcast("activity");
}

const projectRulesInstruction =
  "Apply the shared project definitions and match-state gates in "
  + "docs\\RULES_ENGINE_ARCHITECTURE.md. The proposal's Rule basis is "
  + "event-specific context, not a replacement for those global rules.";

function joinPrompt(lines) {
  return lines.join("\n").replaceAll("football-event-review-live", canvasId);
}

function messagePrompt(segment, draft, index, text, allowChanges = false) {
  const videoArtifact = segment.key === "alfheim-window-555"
    ? "benchmarks\\alfheim\\window-555\\alfheim-window-playable.mp4"
    : (
        `benchmarks\\alfheim\\generated\\${segment.key}`
        + "\\alfheim-window-playable.mp4"
      );
  return joinPrompt([
    `[${workflow.promptLabel}]`,
    `Workflow ID: ${workflowId}. Canvas ID: ${canvasId}.`,
    workflow.promptBoundary,
    `We are reviewing only prepared segment ${segment.timeLabel} `
      + `(${segment.key}).`,
    `Video artifact: ${videoArtifact}.`,
    `Source window: ${segment.startSeconds.toFixed(3)}s for `
      + `${segment.durationSeconds.toFixed(3)}s.`,
    `Selected event: Event ${index + 1}; canvas action index: ${index}.`,
    `Selected proposal: ${draft.title} at clip ${draft.seconds.toFixed(3)}s `
      + `(frame ${Math.round(draft.seconds * 25)} at 25 fps).`,
    `Proposed event: ${draft.team || "neutral"} ${draft.type}.`,
    `Evidence: ${draft.evidence}`,
    `Rule basis: ${draft.rule}`,
    projectRulesInstruction,
    `User message from the review screen: ${text}`,
    "Respond to the user's review question and keep all work limited to this "
      + "selected 30–60 second segment. Do not scan the full recording.",
    allowChanges
      ? (
          "The user explicitly selected an action that permits changes. If "
          + "the requested adjustment is supported, use the "
          + "football-event-review-live update_review_proposal canvas action. Do "
          + "not say the screen was updated unless that action succeeds."
        )
      : (
          "This is Plan mode: answer and explain only. Do not accept, reject, "
          + "edit, or synchronize the event or engine. If a change is needed, "
          + "tell the user to use Request Adjustment or Verify, Accept & Sync "
          + "Engine in this event's Copilot panel."
        ),
    "Before ending, always use the football-event-review-live "
      + "publish_review_response canvas action to place your concise final "
      + `answer in this Canvas for segment ${segment.key}, event index ${index}.`,
    "Minimize latency and AI usage: make one targeted adjudication pass. Start "
      + "with the supplied event context and cached artifacts. If visual "
      + "inspection is necessary, inspect only a small window around the "
      + "specified frame (normally ±2 seconds). Do not scan the full video, "
      + "open unrelated segments, rerun detection/tracking, or rerun the "
      + "rules engine. Keep the response concise. Engine changes and "
      + "regressions occur only after the user accepts a changed requirement.",
  ]);
}

function clipConversationPrompt(
  segment,
  seconds,
  text,
  drafts,
  selectedIndex,
  mode,
  scope,
  flaggedFrames,
  coordinateObservations,
) {
  const videoArtifact = segment.key === "alfheim-window-555"
    ? "benchmarks\\alfheim\\window-555\\alfheim-window-playable.mp4"
    : (
        `benchmarks\\alfheim\\generated\\${segment.key}`
        + "\\alfheim-window-playable.mp4"
      );
  return joinPrompt([
    "[Football Event Review Canvas - clip conversation]",
    `Review only segment ${segment.timeLabel} (${segment.key}).`,
    `Video artifact: ${videoArtifact}.`,
    `Source window: ${segment.startSeconds.toFixed(3)}s for `
      + `${segment.durationSeconds.toFixed(3)}s.`,
    flaggedFrames.length
      ? "User-flagged ball-coordinate source frames for this batch review: "
        + flaggedFrames.join(", ") + ". Treat these only as an inspection "
        + "scope. They are manual review selections, not inference evidence, "
        + "labels, thresholds, or proof that a coordinate is wrong."
      : "No ball-coordinate frames were flagged for this request.",
    coordinateObservations.length
      ? "User coordinate-review outcomes for independent review: "
        + coordinateObservations.map(observation =>
          observation.decision === "undefined"
            ? `frame ${observation.frame}: ball undefined / not visible`
            : observation.decision === "needs_more_checking"
              ? `frame ${observation.frame}: needs more checking`
            : observation.decision === "yolo_candidate"
              ? `frame ${observation.frame}: YOLO candidate `
                + `${observation.candidateIndex + 1} visibly correct at (`
                + `${observation.x.toFixed(1)}, `
                + `${observation.y.toFixed(1)}), detector confidence `
                + `${(observation.confidence * 100).toFixed(1)}%`
            : observation.decision === "agree"
              ? `frame ${observation.frame}: user agrees with current `
                + `coordinate (${observation.x.toFixed(1)}, `
                + `${observation.y.toFixed(1)})`
              : `frame ${observation.frame}: user-specified coordinate (`
                + `${observation.x.toFixed(1)}, `
                + `${observation.y.toFixed(1)})`
        ).join("; ") + ". Interpret agree as the user's claim that the current "
        + "coordinate is visible and supported; specified as the claim that the "
        + "ball is visible at the supplied coordinate; undefined as not "
        + "visually locatable by the current camera, including occlusion; and "
        + "yolo_candidate as the claim that the numbered raw YOLO detection is "
        + "visibly correct but candidate selection failed; needs_more_checking "
        + "as unresolved visual ambiguity. Independently "
        + "verify each claim against raw video and challenge unsupported "
        + "claims explicitly. These are diagnostic leads only, never reference "
        + "coordinates, ground truth, or expected engine targets. Never copy "
        + "them into predictions, make the engine match them, use them as "
        + "candidate or threshold inputs, narrow inference from them, calculate "
        + "success against them, or create frame-specific code."
      : "No user coordinate hypotheses were supplied.",
    scope === "current_time"
      ? `Evidence scope: current time ${seconds.toFixed(3)}s, limited to the `
        + `local ±2-second window (frame ${Math.round(seconds * 25)} at 25 fps).`
      : "Evidence scope: the entire prepared clip. The current playhead is "
        + `${seconds.toFixed(3)}s, but it does not limit this question.`,
    Number.isInteger(selectedIndex) && drafts[selectedIndex]
      ? `Currently selected event: Event ${selectedIndex + 1}, `
        + `${drafts[selectedIndex].title} at `
        + `${drafts[selectedIndex].seconds.toFixed(3)}s.`
      : "No event is currently selected.",
    "Review-event catalog:",
    ...drafts.map((draft, index) =>
      `- Event ${index + 1}: ${draft.title} at `
      + `${draft.seconds.toFixed(3)}s (${draft.team || "neutral"} `
      + `${draft.type}).`
    ),
    `User question or observation: ${text}`,
    projectRulesInstruction,
    mode === "autopilot"
      ? flaggedFrames.length
        ? "The user explicitly authorized one Autopilot ball-coordinate "
          + "recovery batch. Independently inspect every flagged raw-video "
          + "window first, group common failure patterns, and make at most one "
          + "general evidence-based tracker improvement. Never use flags or "
          + "user hypotheses as inference inputs, thresholds, frame-specific "
          + "exceptions, or proof. Run focused/protected tests, then perform "
          + "no manual rerun. Call update_ball_coordinate_batch after review, "
          + "after the code fix, and after tests. The tests_completed update "
          + "automatically starts exactly one bounded focused recovery from "
          + "saved detections and the persisted runtime track. Never rerun "
          + "once per frame or launch the broad tracker recovery. The Canvas "
          + "will compare persisted output, complete this immutable batch, "
          + "and create the next unresolved batch automatically. If output "
          + "reaches at least 90% direct provenance, call "
          + "confirm_ball_coordinate_review only after the persisted rerun "
          + "finishes. Never put the segment into review; only the user can "
          + "finalize that transition."
        : "This is an Autopilot inspection, but it authorizes only analysis and "
          + "a proposed plan. Do not add or accept an event, edit a proposal, or "
          + "change the engine. A supported missing event still requires the "
          + "separate Add as Review Event confirmation."
      : "This is the segment-level conversation in Plan mode. Do not make "
        + "changes.",
    "Answer questions "
      + "about any event, the current frame, or the overall clip without "
      + "placing the reply in an event-specific conversation. Use existing "
      + "cached artifacts first. "
      + (
        scope === "current_time"
          ? "If visual inspection is necessary, stay within the specified "
            + "±2-second window."
          : "If visual inspection is necessary, inspect only this prepared "
            + "30–60 second segment."
      )
      + (
        flaggedFrames.length && mode === "autopilot"
          ? " Do not scan another segment, rerun raw detection, or run the "
            + "rules engine. The single permitted tracker recovery rerun must "
            + "reuse saved raw-video detections and remain labelled recovery."
          : " Do not scan another segment or rerun detection, tracking, or the "
            + "rules engine."
      ),
    flaggedFrames.length
      ? "This is coordinate recovery, not event adjudication. Do not create, "
        + "accept, or alter any football event."
      : "If the user is identifying a genuinely missing event, independently "
        + "determine its team and event type and call football-event-review-live "
        + "recommend_missing_event. If an existing event needs correction, "
        + "identify that event and direct the user to its Request Adjustment "
        + "flow. Otherwise answer normally. Do not add or accept an event, edit "
        + "a proposal, or change the algorithm in this Plan step.",
    "Before ending, always use the football-event-review-live "
      + "publish_review_response canvas action to place your concise final "
      + `answer in this Canvas for segment ${segment.key}.`,
  ]);
}

function independentClipReviewPrompt(segment) {
  const videoArtifact = segment.key === "alfheim-window-555"
    ? "benchmarks\\alfheim\\window-555\\alfheim-window-playable.mp4"
    : (
        `benchmarks\\alfheim\\generated\\${segment.key}`
        + "\\alfheim-window-playable.mp4"
      );
  return joinPrompt([
    "[Football Event Review Canvas - automatic independent clip review]",
    `Independently review only segment ${segment.timeLabel} (${segment.key}).`,
    `Video artifact: ${videoArtifact}.`,
    `Source window: ${segment.startSeconds.toFixed(3)}s for `
      + `${segment.durationSeconds.toFixed(3)}s.`,
    projectRulesInstruction,
    "The user explicitly authorized this independent review by clicking "
      + "Process AI rules engine. Construct C# proposals only from the "
      + "prepared video, frozen BAC coordinates, and prepared player context.",
    "Do not read, inspect, summarize, count, or use E# rules-engine events or "
      + "predicted-events.json while constructing the C# proposals. C# must be "
      + "complete and frozen before any later C↔E comparison.",
    "Inspect the entire prepared clip and adjudicate every supported completed "
      + "pass and turnover. Shots and fouls are outside the current Innovation "
      + "review scope. Abstain where pass or turnover evidence is insufficient.",
    "Call football-event-review-live replace_copilot_review exactly once with "
      + "the complete independently constructed proposal list, including an "
      + "empty list if no events are supported.",
    "Then call football-event-review-live publish_review_response without an "
      + "event index to report that the independent C# review is complete. Do "
      + "not accept proposals, confirm E# events, change the engine, rerun "
      + "detection/tracking, or publish the segment.",
  ]);
}

function confirmMissingEventPrompt(segment, candidate) {
  return joinPrompt([
    "[Football Event Review Canvas - approved missing-event handover]",
    `Work only in segment ${segment.timeLabel} (${segment.key}).`,
    `Candidate: ${candidate.team} ${candidate.eventType} at `
      + `${candidate.seconds.toFixed(3)}s.`,
    `Plan evidence: ${candidate.evidence}`,
    `Proposed rule: ${candidate.rule}`,
    projectRulesInstruction,
    "The user explicitly approved moving this planned candidate into "
      + "Autopilot. Call football-event-review-live add_review_proposal using these "
      + "exact team, event type, and seconds. Then call "
      + "publish_review_response with the returned event index. Do not edit "
      + "the rules engine yet; the newly added event must still pass its own "
      + "Verify, Accept & Sync Engine handover.",
  ]);
}

function publishValidatedReferencePrompt(segment) {
  return joinPrompt([
    "[Football Event Review Canvas - approved final publication]",
    `Publish only prepared segment ${segment.timeLabel} (${segment.key}).`,
    projectRulesInstruction,
    "The user explicitly authorized the final validation gate through the "
      + "Publish Validated Reference button. Do not review another segment.",
    `Run the ${workflow.key === "innovation" ? "Innovation" : "live raw-video and rules-engine"} `
      + "regression tests once with: $env:PYTHONPATH=\"$PWD\\src\"; "
      + `python -m pytest ${workflow.regressionTests.join(" ")} -q`,
    "If they pass, call football-event-review-live refresh_engine_snapshot for "
      + `segment ${segment.key} without an event index, then call `
      + "record_regression_result with passed=true, the segment, and the exact "
      + "test summary. Then call publish_validated_reference.",
    "The publication action must enforce every gate: all proposals finalized, "
      + "accepted C# events fresh and matched, rejected proposals excluded, "
      + "unmatched E# events independently confirmed, exact reference/output "
      + "counts, and a fresh passing regression receipt. Do not write the "
      + "reference manually or bypass a failed gate.",
    "Do not rerun detection, tracking, or event building and do not edit the "
      + "rules engine during final publication. If any gate fails, stop and "
      + "report the blocker.",
    "Before ending, call football-event-review-live publish_review_response with "
      + "neither eventIndex nor engineIndex so the result appears in the "
      + "general clip conversation.",
  ]);
}

function engineEventConversationPrompt(segment, event, index, text) {
  return joinPrompt([
    "[Football Event Review Canvas - engine event conversation]",
    `Review only segment ${segment.timeLabel} (${segment.key}).`,
    `Selected engine event: E${index + 1}, ${event.title} at `
      + `${event.seconds.toFixed(3)}s.`,
    `User question: ${text}`,
    projectRulesInstruction,
    "This is a follow-up discussion in Plan mode. Explain the evidence and "
      + "current review result, but do not confirm the engine event, create or "
      + "accept a Copilot proposal, edit the engine, or rerun any pipeline stage.",
    "Before ending, call football-event-review-live publish_review_response "
      + `with engineIndex ${index} and without a C# eventIndex so the reply `
      + `appears in the E${index + 1} event conversation.`,
  ]);
}

function manualEngineDiscrepancyPrompt(
  segment,
  event,
  index,
  reviewerVerdict,
) {
  const eventLabel = (
    `${event.team === "red" ? "Red/white" : "Black"} `
    + `${
      event.type === "completed_pass"
        ? "completed pass"
        : event.type === "turnover"
          ? "turnover"
          : event.type
    }`
  );
  const videoArtifact = segment.key === "alfheim-window-555"
    ? "benchmarks\\alfheim\\window-555\\alfheim-window-playable.mp4"
    : (
        `benchmarks\\alfheim\\generated\\${segment.key}`
        + "\\alfheim-window-playable.mp4"
      );
  return joinPrompt([
    "[Football Event Review Canvas - unmatched manual event review]",
    `Review only segment ${segment.timeLabel} (${segment.key}).`,
    `Video artifact: ${videoArtifact}.`,
    `Selected manual event: M${index + 1}, ${eventLabel} at `
      + `${event.seconds.toFixed(3)}s.`,
    projectRulesInstruction,
    "The professional reviewer recorded this M# independently, but the current "
      + "rules-engine output has no unique E# with the same team and canonical "
      + "event type within one second.",
    reviewerVerdict === "correct"
      ? "The professional reviewer explicitly says this M# is correct and the "
        + "engine missed it. Treat that as a review observation, then verify "
        + "the raw-video evidence before changing the engine."
      : "The professional reviewer is unsure and asked for independent "
        + "adjudication. Do not assume either M# or the engine is correct.",
    "Independently inspect the targeted raw-video evidence, normally within "
      + "±3 seconds. Treat the M# time only as a search anchor. Never use the "
      + "manual event or its timestamp as an inference input, hidden threshold, "
      + "or segment-specific exception.",
    "If the video does not support this M#, do not change the engine or rewrite "
      + "M#. Explain the missing or conflicting evidence so the reviewer can "
      + "edit or delete M# themselves.",
    "If the video supports M# and the engine genuinely missed it, diagnose the "
      + "general rules-engine cause, implement only a general evidence-based "
      + "fix in the Innovation engine, rerun cached event building, refresh the "
      + "engine snapshot, and run the focused and protected regressions. Do not "
      + "rerun detection or tracking.",
    "Do not create C#, accept or edit M#, confirm another E#, or publish the "
      + "segment.",
    "Before ending, call football-event-review-live publish_review_response "
      + `with eventIndex ${index} and without an engineIndex so the result `
      + `appears in the M${index + 1} conversation.`,
  ]);
}

function engineEventReviewPrompt(
  segment,
  event,
  index,
  reviewFocus = "",
  userVerdict = null,
) {
  const reviewerInstruction = userVerdict === "incorrect"
    ? [
        "The professional reviewer has explicitly rejected this E# as "
          + "incorrect. Do not spend time re-adjudicating the football event.",
        "First call record_engine_event_not_confirmed for this exact E#. Then "
          + "diagnose why the general engine logic produced it from cached "
          + "runtime evidence, implement only a general evidence-based fix, "
          + "rebuild cached events, and run the focused and protected "
          + "regressions. Never add a segment, timestamp, track, or reviewer-"
          + "label exception.",
      ]
    : userVerdict === "correct"
      ? [
          "The professional reviewer explicitly confirmed this E# as correct. "
            + "Do not spend time re-adjudicating the football event.",
          "Immediately call confirm_engine_event_reviewed for this exact E#, "
            + "then check whether the current engine output already contains "
            + "the exact team, canonical event type, and completion time. Do "
            + "not edit or rerun the engine when it already agrees.",
        ]
    : [
        "Independently inspect the targeted evidence, normally within ±2 "
          + "seconds. Do not treat either the engine event or reviewer verdict "
          + "as the answer.",
      ];
  const videoArtifact = segment.key === "alfheim-window-555"
    ? "benchmarks\\alfheim\\window-555\\alfheim-window-playable.mp4"
    : (
        `benchmarks\\alfheim\\generated\\${segment.key}`
        + "\\alfheim-window-playable.mp4"
      );
  return joinPrompt([
    "[Football Event Review Canvas - engine-only event verification]",
    `Review only segment ${segment.timeLabel} (${segment.key}).`,
    `Video artifact: ${videoArtifact}.`,
    `Selected engine event: E${index + 1}, ${event.title} at `
      + `${event.seconds.toFixed(3)}s.`,
    `Engine detail: ${event.details}`,
    reviewFocus
      ? `User-specified verification focus: ${reviewFocus}`
      : "User-specified verification focus: none; inspect the exact event normally within ±2 seconds.",
    userVerdict
      ? `Reviewer verdict: ${userVerdict}. Treat this professional human `
        + "judgment as a review observation and independently assess it "
        + "against the video and rules."
      : "Reviewer verdict: none supplied.",
    projectRulesInstruction,
    "The user authorized action on only this rules-engine event.",
    ...reviewerInstruction,
    "If the evidence supports the exact team, canonical type, and completion "
      + "time, call football-event-review-live confirm_engine_event_reviewed with "
      + "this segment, engine index, and a concise evidence reason. Otherwise "
      + "call football-event-review-live record_engine_event_not_confirmed with "
      + "the same identifiers and the precise unsupported or uncertain evidence.",
    "Do not create or accept a Copilot proposal, edit the engine, or rerun "
      + "detection, tracking, or event building.",
    "Before ending, call football-event-review-live publish_review_response "
      + `with engineIndex ${index} and without a C# eventIndex so the result `
      + `appears in the E${index + 1} conversation.`,
  ]);
}

function proposalFingerprint(draft) {
  return createHash("sha256").update(JSON.stringify({
    seconds: draft.seconds,
    team: draft.team,
    type: draft.type,
    title: draft.title,
    evidence: draft.evidence,
    rule: draft.rule,
    sameFrameEngineReview: Boolean(draft.sameFrameEngineReview),
  })).digest("hex");
}

function copilotAcceptancePrompt(segment, draft, index) {
  const manualReview = ["manual_review", "user_reported"].includes(
    draft.source,
  );
  return joinPrompt([
    messagePrompt(
      segment,
      draft,
      index,
      "Verify the current proposal and accept it only if the evidence supports it.",
      true,
    ),
    "The user explicitly granted permission, through the Canvas handover "
      + "button, for Copilot to accept only this selected proposal.",
    "Treat the proposal timestamp as a search anchor. Inspect up to ±3 seconds "
      + "when needed to locate the earliest supported completion. If only the "
      + "time or other proposal details need correction and the same event is "
      + "supported, call update_review_proposal with "
      + "preserveAcceptanceAuthorization=true, then accept that corrected C# "
      + "within this same authorized review. Do not require another C# or "
      + "another user handover.",
    draft.sameFrameEngineReview
      ? "The user requested strict timing review for this C#. Correct its "
        + "timestamp to the earliest supported completion frame when needed. "
        + "C#/E# agreement for this proposal requires the same rounded 25-fps "
        + "source-video frame; the normal one-second association tolerance "
        + "must not be used to claim engine agreement."
      : "This C# uses the normal one-second C#/E# association tolerance unless "
        + "the user explicitly enables same-frame timing review in the Canvas.",
    manualReview
      ? "For this manual M#, do not call accept_review_proposal until a fresh "
        + "rules-only engine run produces an E# with the same team, canonical "
        + "event type, and rounded 25-fps frame. If the current engine does not "
        + "already agree, implement a general evidence-based correction, rerun "
        + "only cached event building, run the protected regressions, and call "
        + "refresh_engine_snapshot first. Never use this M# as inference input. "
        + "Only after refresh_engine_snapshot returns already_agrees may you "
        + "call accept_review_proposal, followed by record_regression_result."
      : "If the proposal is correct, call football-event-review-live "
        + "accept_review_proposal with the segment, event index, and concise "
        + "verification reason. Read the returned engineComparison. If it is "
        + "already_agrees, do not edit or rerun the engine. If it is stale, "
        + "rerun only cached event building and refresh the snapshot. If it is "
        + "missing or conflicting, implement a general evidence-based rule, "
        + "never a timestamp-, frame-, clip-, or segment-specific exception; "
        + "then rerun cached event building and the protected regressions.",
    "If the proposal is not correct, do not accept it; update the proposal "
      + "only when the evidence supports a correction.",
  ]);
}

function acceptedEngineRecheckPrompt(segment, draft, index, comparison) {
  return joinPrompt([
    "[Football Event Review Canvas - accepted event engine re-check]",
    `Review only prepared segment ${segment.timeLabel} (${segment.key}).`,
    `Accepted proposal: C${index + 1}, ${draft.title} at `
      + `${draft.seconds.toFixed(3)}s.`,
    `Current engine status: ${comparison.label}. ${comparison.detail}`,
    projectRulesInstruction,
    "The user explicitly authorized an engine re-check for this already "
      + "accepted C# through the Canvas button. Do not accept the proposal "
      + "again and do not change its football judgment.",
    "Inspect the current review status and hashes first. If the exact current "
      + "engine version already agrees, make no engine change and do not rerun. "
      + "If the stored engine source or cached-output hash is stale, rerun only "
      + "cached event building for this segment, refresh the engine snapshot, "
      + "and run the focused and protected regressions. If the accepted C# is "
      + "missing or conflicting, implement only a general evidence-based rule; "
      + "never add a timestamp, frame, segment, track-ID, or label exception.",
    "Record refreshed snapshots and regression results through the existing "
      + "football-event-review-live tools. Before ending, call "
      + "football-event-review-live publish_review_response with eventIndex "
      + `${index} so the complete result appears in the C${index + 1} conversation.`,
  ]);
}

function copilotBulkAcceptancePrompt(segment, drafts, indexes) {
  return joinPrompt([
    "[Football Event Review Canvas - approved batch verification]",
    `Review only prepared segment ${segment.timeLabel} (${segment.key}).`,
    projectRulesInstruction,
    "The user explicitly authorized one batch verification through the "
      + "Verify & Accept All Events button. Verify every listed proposal, but "
      + "never accept an event merely because the proposal and engine counts "
      + "are equal.",
    ...indexes.map((index) => {
      const draft = drafts[index];
      return `- Event ${index + 1}: ${draft.title} at `
        + `${draft.seconds.toFixed(3)}s; ${draft.team || "neutral"} `
        + `${draft.type}. Evidence: ${draft.evidence} Rule: ${draft.rule}`;
    }),
    "Use cached evidence and the current engine output first. For each "
      + "supported proposal, call football-event-review-live "
      + "accept_review_proposal with its exact index and a concise reason. "
      + "Leave unsupported or uncertain proposals unaccepted and identify "
      + "them in the final response. Do not silently revise them.",
    "Treat foul/stoppage annotations as yellow match-state context rather "
      + "than forcing them to pair with an analytics engine event. Treat "
      + "unpaired or conflicting C/E rows as differences requiring review.",
    "If accepted proposals expose an engine mismatch, make only a general "
      + "rules-engine correction with no timestamp-, frame-, track-, clip-, "
      + "or segment-specific exception. Rebuild cached events once, run the "
      + "protected regressions once, refresh the engine snapshot, and record "
      + "the regression result.",
    "Before ending, call football-event-review-live publish_review_response "
      + `without eventIndex so the batch summary appears only in the general `
      + `clip conversation for ${segment.key}.`,
  ]);
}

function requestedSegment(url, body = {}) {
  return String(
    body.segment || url.searchParams.get("segment") || defaultSegment,
  );
}

async function localJson(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const maximumAttempts = method === "GET" ? 3 : 1;
  for (let attempt = 1; attempt <= maximumAttempts; attempt += 1) {
    try {
      const response = await fetch(`${localServer}${path}`, options);
      const payload = await response.json();
      if (!response.ok) {
        const error = new Error(
          payload.error || `Local Match Lab HTTP ${response.status}`,
        );
        error.status = response.status;
        error.code = payload.code;
        throw error;
      }
      return payload;
    } catch (error) {
      if (error.status || attempt === maximumAttempts) throw error;
      await new Promise((resolve) => {
        setTimeout(resolve, attempt * 75);
      });
    }
  }
  throw new Error("Local Match Lab request failed");
}

async function adapterUrl(workflowKey) {
  const adapter = workflowAdapter(workflowKey);
  const launchers = await readJson(
    join(generatedRoot, adapter.launcherRegistry),
    {},
  );
  const candidates = [
    launchers[workflowKey],
    ...Object.values(launchers),
  ].filter(Boolean);
  for (const candidate of [...new Set(candidates)]) {
    try {
      await fetch(candidate, {cache: "no-store"});
      return candidate;
    } catch {
      // Stale loopback URLs are expected briefly while extensions reload.
    }
  }
  return null;
}

async function setActiveAdapter(instanceId, workflowKey) {
  if (!instanceId) return;
  const update = adapterRegistryUpdate.then(async () => {
    const registry = await readJson(activeAdapterRegistryPath, {});
    registry[instanceId] = workflowKey;
    await writeJsonAtomically(activeAdapterRegistryPath, registry);
  });
  adapterRegistryUpdate = update.catch(() => {});
  await update;
}

async function activeAdapter(instanceId) {
  if (!instanceId) return workflow.key;
  const registry = await readJson(activeAdapterRegistryPath, {});
  return registry[instanceId] || workflow.key;
}

async function proxyCanvasAction(workflowKey, actionName, context) {
  const baseUrl = await adapterUrl(workflowKey);
  if (!baseUrl) {
    throw new CanvasError(
      "review_adapter_unavailable",
      `The ${workflowKey} review adapter is not available.`,
    );
  }
  const response = await fetch(new URL("/api/agent-action", baseUrl), {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      actionName,
      input: context.input || {},
      instanceId: context.instanceId,
    }),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new CanvasError(
      payload.code || "review_adapter_action_failed",
      payload.error || "The selected review adapter action failed.",
    );
  }
  return payload.result;
}

async function dispatchCanvasAction(action, context) {
  const selectedWorkflow = workflow.key === "innovation"
    ? await activeAdapter(context.instanceId)
    : workflow.key;
  if (selectedWorkflow !== workflow.key) {
    return proxyCanvasAction(selectedWorkflow, action.name, context);
  }
  if (workflow.disabledActionNames.includes(action.name)) {
    throw new CanvasError(
      "review_action_unavailable",
      `${action.name} is unavailable in the ${workflow.key} workflow.`,
    );
  }
  return action.handler(context);
}

async function handleRequest(request, response, serverInstanceId) {
  const url = new URL(request.url, "http://127.0.0.1");
  if (request.method === "GET" && url.pathname === "/") {
    const html = renderHtml({adapter: workflow});
    response.writeHead(200, {
      "Cache-Control": "no-store",
      "Content-Type": "text/html; charset=utf-8",
      "Content-Length": Buffer.byteLength(html),
    });
    response.end(html);
    return;
  }
  if (
    workflow.key === "innovation"
    &&
    request.method !== "GET"
    && url.pathname !== "/api/agent-action"
    && !canvasSessionConnectionFromRequest(
      request,
      serverInstanceId,
    ).connected
  ) {
    sendJson(response, 403, {
      code: "copilot_session_required",
      error: (
        "This review is read-only until it is connected to the active "
        + "Copilot project session for this repository."
      ),
    });
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/switch-workflow") {
    const body = await readBody(request);
    const target = workflowAdapter(String(body.workflow || ""));
    const hostInstanceId = String(
      body.hostInstanceId || serverInstanceId || "",
    );
    const targetResponse = await fetch(
      `${localServer}/api/alfheim/segments?workflow=${
        target.segmentCatalogWorkflow
      }`,
      {cache: "no-store"},
    );
    if (!targetResponse.ok) {
      sendJson(response, 502, {error: "Could not load target segments"});
      return;
    }
    const payload = await targetResponse.json();
    const hiddenSegments = new Set(target.hiddenSegments || []);
    const segments = (payload.segments || []).filter(
      (candidate) => !hiddenSegments.has(candidate.cache_key),
    );
    const requested = String(body.segment || "");
    const segment = segments.some((candidate) => candidate.cache_key === requested)
      ? requested
      : target.defaultSegment;
    const baseUrl = await adapterUrl(target.key);
    if (!baseUrl) {
      sendJson(response, 503, {
        error: `${target.displayName} is not available yet`,
      });
      return;
    }
    await setActiveAdapter(hostInstanceId, target.key);
    const targetUrl = new URL(baseUrl);
    targetUrl.searchParams.set("segment", segment);
    targetUrl.searchParams.set("theme", target.theme);
    targetUrl.searchParams.set("hostInstanceId", hostInstanceId);
    sendJson(response, 200, {
      workflow: target.key,
      segment,
      url: targetUrl.toString(),
    });
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/agent-action") {
    const body = await readBody(request);
    const action = registeredCanvasActions.find(
      (candidate) => candidate.name === body.actionName,
    );
    if (!action || workflow.disabledActionNames.includes(action.name)) {
      sendJson(response, 404, {
        code: "review_action_unavailable",
        error: "The requested action is unavailable in this workflow.",
      });
      return;
    }
    try {
      const result = await action.handler({
        input: body.input || {},
        instanceId: String(body.instanceId || serverInstanceId || ""),
      });
      sendJson(response, 200, {result});
    } catch (error) {
      sendJson(response, 409, {
        code: error.code || "review_adapter_action_failed",
        error: error.message,
      });
    }
    return;
  }
  if (request.method === "GET" && url.pathname === "/api/calibration") {
    const segment = requestedSegment(url);
    const segments = await loadPreparedSegments();
    const selected = segments.find((candidate) => candidate.key === segment);
    const calibration = selected?.datasetId === "alfheim"
      ? await readJson(
          join(
            projectRoot,
            "benchmarks",
            "alfheim",
            "window-555",
            "pitch-calibration.json",
          ),
          null,
        )
      : (
          selected?.datasetId === "soccertrack-v2"
          || selected?.datasetId?.startsWith("custom-")
        )
        ? await readJson(
            join(
              selected.datasetId?.startsWith("custom-")
                ? customCameraSourceRoot
                : segmentRoot(segment),
              selected.datasetId?.startsWith("custom-") ? segment : "",
              "pitch-calibration.json",
            ),
            {
              camera_id: selected.calibrationId,
              dataset_id: selected.datasetId,
              calibration_status: "not_calibrated",
              image_width: selected.imageWidth,
              image_height: selected.imageHeight,
              features: {},
            },
          )
        : null;
    if (!calibration) {
      sendJson(response, 404, {error: "Pitch calibration is unavailable"});
      return;
    }
    sendJson(response, 200, calibration);
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/calibration") {
    const body = await readBody(request);
    const segment = String(body.segment || "");
    const segments = await loadPreparedSegments();
    const selected = segments.find((candidate) => candidate.key === segment);
    if (
      selected?.datasetId !== "soccertrack-v2"
      && !selected?.datasetId?.startsWith("custom-")
    ) {
      sendJson(response, 400, {
        error: "Select a SoccerTrack or custom camera before saving calibration",
      });
      return;
    }
    const calibration = body.calibration;
    const requiredFeatures = [
      "left_goal_line",
      "far_touchline",
      "right_goal_line",
      "near_touchline",
      "left_goal_mouth",
      "right_goal_mouth",
    ];
    if (
      !calibration
      || Number(calibration.image_width) !== Number(selected.imageWidth)
      || Number(calibration.image_height) !== Number(selected.imageHeight)
      || requiredFeatures.some(
        (feature) => !Array.isArray(calibration.features?.[feature])
          || calibration.features[feature].length < 2
      )
    ) {
      sendJson(response, 400, {
        error: "Complete all four pitch edges and both goal frames first",
      });
      return;
    }
    const saved = {
      ...calibration,
      camera_id: selected.calibrationId,
      dataset_id: selected.datasetId,
      calibration_status: "calibrated",
      status: "user-calibrated-pending-event-validation",
    };
    const calibrationPath = join(
      selected.datasetId.startsWith("custom-")
        ? join(customCameraSourceRoot, segment)
        : segmentRoot(segment),
      "pitch-calibration.json",
    );
    await writeJsonAtomically(calibrationPath, saved);
    await updateSharedChecksum(
      calibrationPath,
      `${JSON.stringify(saved, null, 2)}\n`,
    );
    sendJson(response, 200, saved);
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/custom-camera") {
    try {
      const result = await saveCustomCameraSample(request, url);
      sendJson(response, 201, result);
    } catch (error) {
      sendJson(response, 400, {error: error.message});
    }
    return;
  }
  if (
    request.method === "POST"
    && [
      "/api/coordination/acquire",
      "/api/coordination/heartbeat",
      "/api/coordination/release",
    ].includes(url.pathname)
  ) {
    try {
      const body = await readBody(request);
      const segment = requestedSegment(url, body);
      const action = url.pathname.split("/").pop();
      let result;
      if (action === "acquire") {
        const status = await coordinationStatus();
        if (status.mode !== "available") {
          const error = new Error(
            status.detail || "Shared coordination is unavailable",
          );
          error.status = 503;
          error.code = "coordination_unavailable";
          throw error;
        }
        result = await acquireCoordinationLease(segment);
      } else if (action === "heartbeat") {
        result = {
          heartbeat: await heartbeatCoordinationLease(segment),
        };
      } else {
        result = {
          released: await releaseCoordinationLease(segment),
        };
      }
      sendJson(response, 200, {
        ...result,
        leaseToken: undefined,
        lease: result.lease
          ? {...result.lease, leaseToken: undefined}
          : undefined,
      });
    } catch (error) {
      sendJson(response, Number(error.status || 400), {
        code: error.code || "coordination_request_failed",
        error: error.message || String(error),
      });
    }
    return;
  }
  if (request.method === "GET" && url.pathname === "/api/state") {
    const copilotSession = canvasSessionConnectionFromUrl(
      url,
      serverInstanceId,
    );
    sendJson(
      response,
      200,
      await coalescedPublicState(requestedSegment(url), copilotSession),
    );
    return;
  }
  if (
    request.method === "GET"
    && url.pathname === "/api/innovation/regression-status"
  ) {
    const segment = requestedSegment(url);
    sendJson(
      response,
      200,
      segmentRegressionProgress.get(segment) || {
        segment,
        status: "not_started",
        steps: [],
      },
    );
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/innovation/regression"
  ) {
    try {
      const body = await readBody(request);
      const segment = requestedSegment(url, body);
      queuePublishedInnovationRegression(segment).catch(() => {
        // Progress remains available through the status API.
      });
      sendJson(response, 202, {
        accepted: true,
        segment,
        status: "running",
      });
    } catch (error) {
      sendJson(response, 400, {
        error: error.message || String(error),
        code: error.code || "regression_failed",
      });
    }
    return;
  }
  if (request.method === "GET" && url.pathname === "/api/ball-track") {
    const segment = requestedSegment(url);
    const audit = url.searchParams.get("audit") === "1";
    const segments = await loadPreparedSegments();
    const selected = segments.find((candidate) => candidate.key === segment);
    if (!selected) {
      sendJson(response, 404, { error: "Prepared segment not found" });
      return;
    }
    if (
      selected.state !== "ready"
      && !(
        workflow.key === "innovation"
        && selected.state === "evidence_ready"
      )
      && !selected.validated
      && !(selected.state === "failed" && selected.ballTrackAvailable)
      && !audit
    ) {
      sendJson(response, 409, {
        error: "Detected ball tracks are available only after AI completes",
      });
      return;
    }
    const track = await loadDetectedBallTrack(
      selected,
      { allowDetectionOnly: audit },
    );
    if (!track) {
      sendJson(response, 404, {
        error: workflow.key === "innovation"
          ? "No frozen BAC coordinate track is available"
          : "No raw-video-derived ball track is available",
      });
      return;
    }
    sendJson(response, 200, track);
    return;
  }
  if (request.method === "GET" && url.pathname === "/events") {
    response.writeHead(200, {
      "Cache-Control": "no-cache",
      "Connection": "keep-alive",
      "Content-Type": "text/event-stream",
    });
    response.write("event: ready\ndata: {}\n\n");
    eventStreams.add(response);
    request.on("close", () => eventStreams.delete(response));
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/prepare") {
    const body = await readBody(request);
    const startSeconds = Number(body.start_seconds);
    const durationSeconds = Number(body.duration_seconds);
    const sourceId = String(body.source_id || "");
    const sourceSegment = String(body.source_segment || "");
    if (!Number.isFinite(startSeconds) || startSeconds < 0) {
      sendJson(response, 400, {
        error: "Start time must be a non-negative number",
      });
      return;
    }
    if (
      !reviewDurationSeconds.includes(durationSeconds)
    ) {
      sendJson(response, 400, {
        error: "Review duration must be exactly 20, 30, or 60 seconds",
      });
      return;
    }
    const sources = await loadPreparedSegments();
    const selectedSource = sources.find(
      (candidate) =>
        candidate.key === sourceSegment
        && candidate.datasetId === sourceId,
    );
    if (!selectedSource) {
      sendJson(response, 400, {
        error: "The selected camera/source no longer matches this request",
      });
      return;
    }
    if (!selectedSource.preparationSupported) {
      sendJson(response, 400, {
        error: (
          `${selectedSource.datasetName} does not yet have full-recording `
          + "segmentation configured"
        ),
      });
      return;
    }
    setActivity(
      "working",
      "Preparing review segment",
      "The playable raw-video window and workflow registration are being prepared locally. AI is not running.",
    );
    const prepared = await localJson("/api/alfheim/segment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_seconds: startSeconds,
        duration_seconds: durationSeconds,
        source_id: sourceId,
        workflow_id: workflowId,
      }),
    });
    setActivity(
      "ready",
      "Segment prepared",
      "Review the video, then start AI explicitly when you are ready.",
    );
    sendJson(
      response,
      200,
      await publicState(
        prepared.cache_key,
        canvasSessionConnectionFromRequest(request, serverInstanceId),
      ),
    );
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/analyze") {
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const resumeAfterDetection = body.resumeAfterDetection === true;
    if (!/^segment-\d{4}-\d{3}$/.test(segment)) {
      sendJson(response, 400, {
        error: "Select a generated prepared segment before starting AI",
      });
      return;
    }
    const review = await reviewContext(segment);
    if (![20, 30, 60].includes(Number(review.selected.durationSeconds))) {
      sendJson(response, 400, {
        error: "AI can run only on a prepared 20-, 30-, or 60-second segment",
      });
      return;
    }
    if (workflow.key === "innovation" && !review.selected.evidenceReady) {
      sendJson(response, 409, {
        code: "innovation_evidence_required",
        error: (
          "Prepare frozen BAC coordinates and YOLO player context before "
          + "running the Innovation rules engine."
        ),
      });
      return;
    }
    setActivity(
      "working",
      workflow.key === "innovation"
        ? "Running BAC-assisted Innovation analysis"
        : resumeAfterDetection
          ? "Recovering from completed detections"
          : "Running cold raw-video AI",
      workflow.key === "innovation"
        ? "YOLO derives player context from the prepared raw video; frozen "
          + "Alfheim BAC coordinates supply the ball path. The Live ball "
          + "tracker is not used."
        : resumeAfterDetection
          ? "Completed raw-video detections are reused; every downstream "
            + "artifact is rebuilt. This is not a cold-path benchmark."
          : "Prior detections, ball tracks, player tracks, events, review labels, "
            + "and provider annotations are excluded.",
    );
    const result = await localJson(
      workflow.analyzePath,
      {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cache_key: segment,
        events_only: workflow.key === "innovation",
        ...(workflow.key === "live"
          ? {resume_after_detection: resumeAfterDetection}
          : {}),
      }),
      },
    );
    sendJson(response, 202, {
      ...result,
      segment,
      eventsOnly: workflow.key === "innovation",
    });
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/innovation/start-independent-review"
  ) {
    if (workflow.key !== "innovation") {
      sendJson(response, 404, {error: "Not found"});
      return;
    }
    sendJson(response, 409, {
      error: "Automatic C# generation is disabled in the manual-first Innovation workflow",
      code: "manual_first_workflow",
    });
    return;
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already handling a review request",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const review = await reviewContext(segment);
    if (review.selected.state !== "ready") {
      sendJson(response, 409, {
        error: "The Innovation rules engine must complete before Copilot review",
      });
      return;
    }
    if (review.state.automaticCopilotReview?.status === "complete") {
      sendJson(response, 200, {segment, status: "complete"});
      return;
    }
    if (review.state.automaticCopilotReview?.status === "reviewing") {
      sendJson(response, 202, {segment, status: "reviewing"});
      return;
    }
    const startedAt = new Date().toISOString();
    review.state.automaticCopilotReview = {
      ...(review.state.automaticCopilotReview || {}),
      status: "reviewing",
      authorizedAt: (
        review.state.automaticCopilotReview?.authorizedAt || startedAt
      ),
      startedAt,
      completedAt: null,
      error: null,
    };
    await saveState(segment, review.state);
    lastConversationContext = {segment, eventIndex: null};
    reviewRequestPending = true;
    setActivity(
      "working",
      "Copilot is independently reviewing the clip",
      "C# proposals are being constructed without using E# output.",
    );
    sendJson(response, 202, {segment, status: "reviewing"});
    setTimeout(() => {
      session.send({
        prompt: independentClipReviewPrompt(review.selected),
        displayPrompt: (
          `Independently review ${review.selected.timeLabel} and create C# proposals.`
        ),
        agentMode: "autopilot",
      }).catch(async (error) => {
        reviewRequestPending = false;
        const failedReview = await reviewContext(segment);
        failedReview.state.automaticCopilotReview = {
          ...(failedReview.state.automaticCopilotReview || {}),
          status: "failed",
          completedAt: new Date().toISOString(),
          error: error.message,
        };
        await saveState(segment, failedReview.state);
        setActivity(
          "error",
          "Independent Copilot review failed",
          error.message,
        );
      });
    }, 0);
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/innovation/prepare-evidence"
  ) {
    if (workflow.key !== "innovation") {
      sendJson(response, 404, {error: "Not found"});
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const review = await reviewContext(segment);
    if (
      !review.selected.evidencePreparationSupported
      || ![20, 30, 60].includes(Number(review.selected.durationSeconds))
    ) {
      sendJson(response, 400, {
        error: "Select a prepared Innovation segment first",
      });
      return;
    }
    setActivity(
      "working",
      "Preparing Innovation evidence",
      "Frozen BAC coordinates and YOLO player context are being prepared. "
        + "No football events are being generated.",
    );
    const result = await localJson(workflow.analyzePath, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        cache_key: segment,
        evidence_only: true,
      }),
    });
    sendJson(response, 202, {
      ...result,
      segment,
      evidenceOnly: true,
    });
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/reviewer-confirm-engine"
  ) {
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const index = Number(body.index);
    if (body.userVerdict !== "correct") {
      sendJson(response, 400, {
        error: "Direct confirmation requires an explicit correct verdict",
      });
      return;
    }
    const result = await confirmEngineEventByProfessionalReviewer(
      segment,
      index,
    );
    sendJson(response, 200, result);
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/copilot-verify-engine"
  ) {
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already handling a review request",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const review = await reviewContext(segment);
    const cachedCurrent = await captureEngineSnapshot(segment);
    const current = engineReviewSnapshot(review.state, cachedCurrent);
    const events = snapshotEvents(current);
    const index = Number(body.index);
    const event = events[index];
    const reviewFocus = String(body.note || "").trim();
    const userVerdict = ["correct", "incorrect", "unsure"].includes(
      body.userVerdict,
    )
      ? body.userVerdict
      : body.userClaimedCorrect === true
        ? "correct"
        : null;
    const userClaimedCorrect = userVerdict === "correct";
    if (!Number.isInteger(index) || !event) {
      sendJson(response, 400, {
        error: "Select a rules-engine event first",
      });
      return;
    }
    if (reviewFocus.length > 4_000) {
      sendJson(response, 400, {
        error: "Verification focus must be at most 4,000 characters",
      });
      return;
    }
    const key = engineEventReviewKey(event);
    review.state.engineEventReviewAuthorizations[key] = {
      engineContentHash: current.fingerprint.contentHash,
      outputHash: current.outputHash,
      userClaimedCorrect,
      userVerdict,
      grantedAt: new Date().toISOString(),
    };
    review.state.conversation.push({
      role: "user",
      content: (
        `Permission granted: independently verify E${index + 1} at `
        + `${event.seconds.toFixed(3)}s and mark it reviewed only if supported.`
        + (
          reviewFocus
            ? ` Verification focus: ${reviewFocus}`
            : ""
        )
        + (
          userVerdict
            ? ` Reviewer verdict: ${userVerdict}.`
            : ""
        )
      ),
      eventIndex: null,
      engineIndex: index,
      timestamp: new Date().toISOString(),
    });
    await saveState(segment, review.state);
    lastConversationContext = {
      segment,
      eventIndex: null,
      engineIndex: index,
    };
    reviewRequestPending = true;
    setActivity(
      "working",
      `Copilot is verifying E${index + 1}`,
      "The engine event will be confirmed only if independent evidence supports it.",
    );
    sendJson(response, 202, { sent: true, index });
    setTimeout(() => {
      session.send({
        prompt: engineEventReviewPrompt(
          review.selected,
          event,
          index,
          reviewFocus,
          userVerdict,
        ),
        displayPrompt: (
          userVerdict === "incorrect"
            ? `Reject E${index + 1} and diagnose the general engine cause.`
          : reviewFocus
            ? `Re-verify E${index + 1}: ${reviewFocus.slice(0, 180)}`
            : `Verify E${index + 1} at ${event.seconds.toFixed(3)}s only if correct.`
        ),
        agentMode: "autopilot",
      }).catch(async (error) => {
        reviewRequestPending = false;
        const failedReview = await reviewContext(segment);
        delete failedReview.state.engineEventReviewAuthorizations[key];
        failedReview.state.conversation.push({
          role: "system",
          content: `Engine-event verification failed: ${error.message}`,
          eventIndex: null,
          engineIndex: index,
          timestamp: new Date().toISOString(),
        });
        await saveState(segment, failedReview.state);
        setActivity(
          "error",
          "The engine event could not be verified",
          error.message,
        );
      });
    }, 0);
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/copilot-review-manual-engine"
  ) {
    if (workflow.key !== "innovation") {
      sendJson(response, 409, {
        error: "Manual M# engine review is available only in Innovation",
      });
      return;
    }
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already handling a review request",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    const manualKey = String(body.manualKey || "");
    const index = context.drafts.findIndex((event) => event.key === manualKey);
    const event = context.drafts[index];
    const reviewerVerdict = ["correct", "unsure"].includes(body.userVerdict)
      ? body.userVerdict
      : null;
    if (!Number.isInteger(index) || !event) {
      sendJson(response, 400, {error: "Select a manual M# first"});
      return;
    }
    if (!reviewerVerdict) {
      sendJson(response, 400, {
        error: "Choose whether M# is correct or needs independent adjudication",
      });
      return;
    }
    if (
      context.selected.validated
      || context.state.publishedReference
      || context.state.manualReference?.approved
    ) {
      sendJson(response, 409, {
        error: "Reopen the approved manual minute before reviewing a missing E#",
      });
      return;
    }
    const current = engineReviewSnapshot(
      context.state,
      await captureEngineSnapshot(segment),
    );
    const suggestions = suggestManualMappings(
      context.drafts,
      snapshotEvents(current),
    );
    if (suggestions[event.key]) {
      sendJson(response, 409, {
        error: `${event.key} already has a current matching E#`,
      });
      return;
    }
    context.state.conversation.push({
      role: "user",
      content: (
        `Permission granted: independently review why ${event.key} at `
        + `${event.seconds.toFixed(3)}s has no matching rules-engine E#. `
        + `Reviewer verdict: ${reviewerVerdict}.`
      ),
      eventIndex: index,
      engineIndex: null,
      timestamp: new Date().toISOString(),
    });
    await saveState(segment, context.state);
    lastConversationContext = {segment, eventIndex: index, engineIndex: null};
    reviewRequestPending = true;
    setActivity(
      "working",
      `Copilot is reviewing unmatched ${event.key}`,
      "The manual event remains unchanged while the video and general engine rule are checked.",
    );
    sendJson(response, 202, {sent: true, index, manualKey: event.key});
    setTimeout(() => {
      session.send({
        prompt: manualEngineDiscrepancyPrompt(
          context.selected,
          event,
          index,
          reviewerVerdict,
        ),
        displayPrompt: (
          `Review why ${event.key} at ${event.seconds.toFixed(3)}s has no `
          + "matching engine event."
        ),
        agentMode: "autopilot",
      }).catch(async (error) => {
        reviewRequestPending = false;
        const failedReview = await reviewContext(segment);
        failedReview.state.conversation.push({
          role: "system",
          content: `${event.key} missing-engine review failed: ${error.message}`,
          eventIndex: index,
          engineIndex: null,
          timestamp: new Date().toISOString(),
        });
        await saveState(segment, failedReview.state);
        setActivity(
          "error",
          `${event.key} missing-engine review failed`,
          error.message,
        );
      });
    }, 0);
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/engine-message") {
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already reviewing an event",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const review = await reviewContext(segment);
    const cachedCurrent = await captureEngineSnapshot(segment);
    const current = engineReviewSnapshot(review.state, cachedCurrent);
    const events = snapshotEvents(current);
    const index = Number(body.index);
    const event = events[index];
    const text = String(body.text || "").trim();
    if (!Number.isInteger(index) || !event) {
      sendJson(response, 400, { error: "Select a rules-engine event first" });
      return;
    }
    if (!text || text.length > 4_000) {
      sendJson(response, 400, {
        error: "Message must contain 1–4,000 characters",
      });
      return;
    }
    review.state.conversation.push({
      role: "user",
      content: text,
      eventIndex: null,
      engineIndex: index,
      timestamp: new Date().toISOString(),
    });
    await saveState(segment, review.state);
    lastConversationContext = { segment, eventIndex: null, engineIndex: index };
    reviewRequestPending = true;
    setActivity(
      "working",
      `Copilot is answering about E${index + 1}`,
      "The reply will remain in this engine-event conversation.",
    );
    sendJson(response, 202, { sent: true, index });
    setTimeout(() => {
      session.send({
        prompt: engineEventConversationPrompt(review.selected, event, index, text),
        displayPrompt: `Discuss E${index + 1}: ${text.slice(0, 180)}`,
        agentMode: "plan",
      }).catch(async (error) => {
        reviewRequestPending = false;
        const failedReview = await reviewContext(segment);
        failedReview.state.conversation.push({
          role: "system",
          content: `E${index + 1} conversation failed: ${error.message}`,
          eventIndex: null,
          engineIndex: index,
          timestamp: new Date().toISOString(),
        });
        await saveState(segment, failedReview.state);
        setActivity(
          "error",
          `The E${index + 1} question could not be processed`,
          error.message,
        );
      });
    }, 0);
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/decision") {
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    const index = Number(body.index);
    if (!Number.isInteger(index) || !context.drafts[index]) {
      sendJson(response, 400, { error: "Unknown draft event" });
      return;
    }
    if (
      request.method === "POST"
      && url.pathname === "/api/cancel-adjustment"
    ) {
      const body = await readBody(request);
      const segment = requestedSegment(url, body);
      try {
        await cancelReviewAdjustment(
          segment,
          Number(body.index),
          String(body.reason || "Cancelled from the review panel."),
        );
      } catch (error) {
        sendJson(response, 409, { error: error.message });
        return;
      }
      sendJson(response, 200, await publicState(segment));
      return;
    }
    if (!["accepted", "adjust", "rejected"].includes(body.status)) {
      sendJson(response, 400, { error: "Invalid decision status" });
      return;
    }
    const state = context.state;
    const engineCheck = body.status === "accepted"
      ? await compareWithCurrentEngine(
          segment,
          context.drafts[index],
          state,
        )
      : null;
    state.decisions[String(index)] = {
      status: body.status,
      note: String(body.note || "").trim(),
      decidedAt: new Date().toISOString(),
      ...(engineCheck
        ? {
            source: "user_accepted",
            engineVerification: engineCheck.engineVerification,
          }
        : {}),
    };
    const regressionResult = body.status === "accepted"
      ? await ensureInnovationRegressionsCurrent(segment, state)
      : null;
    const event = context.drafts[index];
    const decisionLabel = {
      accepted: "accepted",
      adjust: "sent back for adjustment",
      rejected: "rejected",
    }[body.status];
    state.conversation.push({
      role: "user",
      content: (
        `Decision: Event ${index + 1} at ${event.seconds.toFixed(3)}s was `
        + `${decisionLabel}.`
        + (
          String(body.note || "").trim()
            ? ` Reason: ${String(body.note).trim()}`
            : ""
        )
        + (
          engineCheck
            ? ` Engine check: ${engineCheck.engineComparison.label}. `
              + engineCheck.engineComparison.detail
            : ""
        )
        + (
          regressionResult && !regressionResult.passed
            ? ` Acceptance remains pending regression: ${
                state.regression.summary
              }`
            : ""
        )
      ),
      eventIndex: index,
      timestamp: state.decisions[String(index)].decidedAt,
    });
    delete state.copilotAcceptanceAuthorizations[String(index)];
    await saveState(segment, state);
    sendJson(response, 200, await publicState(segment));
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/copilot-recheck-accepted"
  ) {
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already handling a review request",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    const index = Number(body.index);
    const draft = context.drafts[index];
    const decision = context.state.decisions[String(index)];
    if (!Number.isInteger(index) || !draft) {
      sendJson(response, 400, { error: "Select a review event first" });
      return;
    }
    if (decision?.status !== "accepted") {
      sendJson(response, 409, {
        error: "Only an already accepted C# can use this engine re-check",
      });
      return;
    }
    if (
      context.selected.validated
      || context.state.publishedReference
    ) {
      sendJson(response, 409, {
        error: "Published passed references are already locked",
      });
      return;
    }
    const current = await captureEngineSnapshot(segment);
    const comparison = acceptedEngineComparison(
      draft,
      context.state,
      decision,
      current,
    );
    if (comparison.status === "already_agrees") {
      sendJson(response, 409, {
        error: (
          "The accepted C# already agrees with the current engine and output "
          + "hashes; no recalculation is needed"
        ),
      });
      return;
    }
    context.state.conversation.push({
      role: "user",
      content: (
        `Permission granted: re-check the engine workflow for accepted C${
          index + 1
        }. Current status: ${comparison.label}.`
      ),
      eventIndex: index,
      timestamp: new Date().toISOString(),
    });
    await saveState(segment, context.state);
    lastConversationContext = { segment, eventIndex: index };
    reviewRequestPending = true;
    setActivity(
      "working",
      `Copilot is re-checking accepted C${index + 1}`,
      "Current hashes decide whether no action, cached recalculation, or general engine synchronization is required.",
    );
    sendJson(response, 202, { sent: true, index });
    setTimeout(() => {
      session.send({
        prompt: acceptedEngineRecheckPrompt(
          context.selected,
          draft,
          index,
          comparison,
        ),
        displayPrompt: (
          `Re-check accepted C${index + 1} against the current engine and `
          + "recalculate only if required."
        ),
        agentMode: "autopilot",
      }).catch(async (error) => {
        reviewRequestPending = false;
        const failedReview = await reviewContext(segment);
        failedReview.state.conversation.push({
          role: "system",
          content: `Accepted-event engine re-check failed: ${error.message}`,
          eventIndex: index,
          timestamp: new Date().toISOString(),
        });
        await saveState(segment, failedReview.state);
        setActivity(
          "error",
          `The accepted C${index + 1} engine re-check failed`,
          error.message,
        );
      });
    }, 0);
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/copilot-accept") {
    if (workflow.key === "innovation") {
      sendJson(response, 409, {
        error: "C# acceptance is disabled in the manual-first Innovation workflow",
      });
      return;
    }
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already handling a review request",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    const index = Number(body.index);
    if (!Number.isInteger(index) || !context.drafts[index]) {
      sendJson(response, 400, { error: "Select a draft event first" });
      return;
    }
    if (
      context.selected.validated
      || context.state.publishedReference
    ) {
      sendJson(response, 409, {
        error: "Published passed references are already locked",
      });
      return;
    }
    const draft = context.drafts[index];
    context.state.copilotAcceptanceAuthorizations[String(index)] = {
      proposalFingerprint: proposalFingerprint(draft),
      grantedAt: new Date().toISOString(),
    };
    context.state.conversation.push({
      role: "user",
      content: (
        `Permission granted: verify Event ${index + 1} and accept it only `
        + "if the current video evidence and rule support it."
      ),
      eventIndex: index,
      timestamp: new Date().toISOString(),
    });
    await saveState(segment, context.state);
    lastConversationContext = { segment, eventIndex: index };
    reviewRequestPending = true;
    setActivity(
      "working",
      `Copilot is verifying Event ${index + 1}`,
      "Acceptance is authorized only for this proposal and only if it is supported.",
    );
    sendJson(response, 202, { sent: true, index });
    setTimeout(() => {
      session.send({
        prompt: copilotAcceptancePrompt(
          context.selected,
          draft,
          index,
        ),
        displayPrompt: (
          `Verify and accept Event ${index + 1} at `
          + `${draft.seconds.toFixed(3)}s only if it is correct.`
        ),
        agentMode: "autopilot",
      }).catch(async (error) => {
        reviewRequestPending = false;
        const failedReview = await reviewContext(segment);
        delete failedReview.state
          .copilotAcceptanceAuthorizations[String(index)];
        failedReview.state.conversation.push({
          role: "system",
          content: `Copilot acceptance check failed: ${error.message}`,
          eventIndex: index,
          timestamp: new Date().toISOString(),
        });
        await saveState(segment, failedReview.state);
        setActivity(
          "error",
          "Copilot could not verify this event",
          error.message,
        );
      });
    }, 0);
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/copilot-accept-all"
  ) {
    if (workflow.key === "innovation") {
      sendJson(response, 409, {
        error: "Bulk C# acceptance is disabled in the manual-first Innovation workflow",
      });
      return;
    }
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already handling a review request",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    if (context.state.coordinateReview?.status !== "finalized") {
      sendJson(response, 409, {
        error: "Ball-coordinate review must be explicitly finalized before event review",
      });
      return;
    }
    if (!context.drafts.length) {
      sendJson(response, 409, {
        error: "No review events exist to verify",
      });
      return;
    }
    if (
      context.selected.validated
      || context.state.publishedReference
    ) {
      sendJson(response, 409, {
        error: "Published passed references are already locked",
      });
      return;
    }
    const indexes = context.drafts
      .map((_, index) => index)
      .filter((index) => !context.state.decisions[String(index)]);
    if (!indexes.length) {
      sendJson(response, 409, {
        error: "Every proposal has already been reviewed",
      });
      return;
    }
    const grantedAt = new Date().toISOString();
    indexes.forEach((index) => {
      context.state.copilotAcceptanceAuthorizations[String(index)] = {
        proposalFingerprint: proposalFingerprint(context.drafts[index]),
        grantedAt,
        scope: "batch",
      };
    });
    context.state.conversation.push({
      role: "user",
      content: (
        `Batch handover granted: verify ${indexes.length} unaccepted `
        + "proposals and accept only those supported by the evidence."
      ),
      eventIndex: null,
      timestamp: grantedAt,
    });
    await saveState(segment, context.state);
    lastConversationContext = { segment, eventIndex: null };
    reviewRequestPending = true;
    setActivity(
      "working",
      "Copilot is verifying all events",
      `${indexes.length} unaccepted proposals are being checked as one batch.`,
    );
    sendJson(response, 202, { sent: true, indexes });
    setTimeout(() => {
      session.send({
        prompt: copilotBulkAcceptancePrompt(
          context.selected,
          context.drafts,
          indexes,
        ),
        displayPrompt: (
          `Verify all ${indexes.length} unaccepted events in `
          + `${context.selected.timeLabel}; accept only supported events.`
        ),
        agentMode: "autopilot",
      }).catch(async (error) => {
        reviewRequestPending = false;
        const failedReview = await reviewContext(segment);
        indexes.forEach((index) => {
          const authorization = failedReview.state
            .copilotAcceptanceAuthorizations[String(index)];
          if (authorization?.grantedAt === grantedAt) {
            delete failedReview.state
              .copilotAcceptanceAuthorizations[String(index)];
          }
        });
        failedReview.state.conversation.push({
          role: "system",
          content: `Batch acceptance check failed: ${error.message}`,
          eventIndex: null,
          timestamp: new Date().toISOString(),
        });
        await saveState(segment, failedReview.state);
        setActivity(
          "error",
          "The batch event review could not be completed",
          error.message,
        );
      });
    }, 0);
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/publish-reference"
  ) {
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already handling a review request",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    if (context.state.coordinateReview?.status !== "finalized") {
      sendJson(response, 409, {
        error: "Ball-coordinate review must be explicitly finalized before publication",
      });
      return;
    }
    if (!context.drafts.length) {
      sendJson(response, 409, {
        error: "No review events exist to publish",
      });
      return;
    }
    if (
      context.selected.validated
      || context.state.publishedReference
    ) {
      sendJson(response, 409, {
        error: "This reference has already passed and is locked",
      });
      return;
    }
    const current = await captureEngineSnapshot(segment);
    const plan = publicationPlan(context.drafts, context.state, current);
    if (!plan.reviewComplete) {
      sendJson(response, 409, {
        error: "Review every proposal before publishing the reference",
      });
      return;
    }
    const preRegressionBlockers = plan.blockers.filter((blocker) =>
      !blocker.includes("regressions")
      && !blocker.includes("fresh engine receipt")
    );
    if (preRegressionBlockers.length) {
      sendJson(response, 409, {
        error: preRegressionBlockers.join(" "),
      });
      return;
    }
    context.state.publicationAuthorization = {
      grantedAt: new Date().toISOString(),
      reviewFingerprint: publicationFingerprint(
        context.drafts,
        context.state,
      ),
      engineContentHash: current.fingerprint.contentHash,
      outputHash: current.outputHash,
    };
    context.state.conversation.push({
      role: "user",
      content: (
        "Final publication handover granted: run protected regressions and "
        + "publish the completed accepted reference only if every gate passes."
      ),
      eventIndex: null,
      timestamp: context.state.publicationAuthorization.grantedAt,
    });
    await saveState(segment, context.state);
    lastConversationContext = { segment, eventIndex: null };
    reviewRequestPending = true;
    setActivity(
      "working",
      "Copilot is running final validation",
      "Protected regressions and exact reference/output matching are required.",
    );
    sendJson(response, 202, { sent: true });
    setTimeout(() => {
      session.send({
        prompt: publishValidatedReferencePrompt(context.selected),
        displayPrompt: (
          `Run the final validation gate and publish ${context.selected.timeLabel}.`
        ),
        agentMode: "autopilot",
      }).catch(async (error) => {
        reviewRequestPending = false;
        const failedReview = await reviewContext(segment);
        failedReview.state.publicationAuthorization = null;
        failedReview.state.conversation.push({
          role: "system",
          content: `Final publication failed: ${error.message}`,
          eventIndex: null,
          timestamp: new Date().toISOString(),
        });
        await saveState(segment, failedReview.state);
        setActivity(
          "error",
          "The final validation gate could not complete",
          error.message,
        );
      });
    }, 0);
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/continue-coordinate-review"
  ) {
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    if (context.state.coordinateReview?.status !== "verified") {
      sendJson(response, 409, {
        error: "The 90% coordinate gate must be verified before extending review",
      });
      return;
    }
    if (activeCoordinateBatch(context.state)) {
      sendJson(response, 409, {
        error: "A coordinate review round is already active",
      });
      return;
    }
    const completed = [...(context.state.coordinateReview.batches || [])]
      .reverse()
      .find((candidate) => candidate.status === "done");
    const frames = [...new Set([
      ...(completed?.unresolvedFrames || []),
      ...(completed?.regressionFrames || []),
    ])].sort((left, right) => left - right);
    if (!completed || !frames.length) {
      sendJson(response, 409, {
        error: "The latest completed round has no leftover frames",
      });
      return;
    }
    if (Number(completed.after?.directProvenance || 0) < 0.90) {
      sendJson(response, 409, {
        error: "Coverage is below 90%; the required next round is already part of the recovery workflow",
      });
      return;
    }
    const nextNumber = Math.max(
      0,
      ...context.state.coordinateReview.batches.map(
        (candidate) => Number(candidate.number || 0),
      ),
    ) + 1;
    const nextBatch = {
      id: `coordinate-round-${nextNumber}`,
      number: nextNumber,
      status: "ready",
      frames,
      observations: {},
      createdAt: new Date().toISOString(),
      before: completed.after,
      frameResults: {},
      continuedAfterGate: true,
      carryForward: coordinateCarryForward(completed, frames),
    };
    context.state.coordinateReview = {
      ...context.state.coordinateReview,
      status: "pending",
      activeBatchId: nextBatch.id,
      flaggedFrames: frames,
      verifiedAt: null,
      trackerHash: null,
      provenanceHash: null,
      summary: null,
    };
    context.state.coordinateReview.batches.push(nextBatch);
    context.state.conversation.push({
      role: "system",
      content: `The user chose to improve ${frames.length} unresolved ball-coordinate frames after the 90% gate.`,
      eventIndex: null,
      coordinateReview: true,
      coordinateBatchId: nextBatch.id,
      timestamp: nextBatch.createdAt,
    });
    await saveState(segment, context.state);
    sendJson(response, 200, {
      created: true,
      batchId: nextBatch.id,
      frameCount: frames.length,
    });
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/finalize-ball-coordinate-review"
  ) {
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    if (!ballCoordinateReviewCanBeVerified(context.selected)) {
      sendJson(response, 409, {
        error: "Local AI must complete before this segment can enter review",
      });
      return;
    }
    const snapshot = await ballCoordinateReviewSnapshot(segment);
    if (
      snapshot.directProvenance < 0.90
      || snapshot.directFrameCount < Math.ceil(
        snapshot.sampledFrameCount * 0.90,
      )
    ) {
      sendJson(response, 409, {
        error: "Direct ball-coordinate provenance is still below the 90% minimum",
      });
      return;
    }
    const run = await localJson(
      workflow.analyzePath,
      {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          cache_key: segment,
          events_only: true,
        }),
      },
    );
    context.state.coordinateReview = {
      ...context.state.coordinateReview,
      status: "finalized",
      finalizedAt: new Date().toISOString(),
      trackerHash: snapshot.trackerHash,
      provenanceHash: snapshot.provenanceHash,
      finalizedDirectFrameCount: snapshot.directFrameCount,
      finalizedSampledFrameCount: snapshot.sampledFrameCount,
    };
    context.state.conversation.push({
      role: "system",
      content: "The user authorized the rules-engine run after the current "
        + `${snapshot.directFrameCount}/${snapshot.sampledFrameCount} direct `
        + "coordinates met the 90% minimum. Unresolved and disputed frames "
        + "remain recorded for optional improvement.",
      eventIndex: null,
      coordinateReview: true,
      timestamp: context.state.coordinateReview.finalizedAt,
    });
    await saveState(segment, context.state);
    setActivity(
      "working",
      "Rules engine running",
      "Building events from the current coordinate output.",
    );
    sendJson(response, 200, {
      finalized: true,
      rulesEngineStarted: true,
      run,
      validationStatus: "in_review",
    });
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/coordinate-batch-draft"
  ) {
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    const batch = context.state.coordinateReview?.batches?.find(
      (candidate) => candidate.id === String(body.batchId || ""),
    );
    if (!batch || batch.status !== "ready") {
      sendJson(response, 409, {
        error: "Only the current ready coordinate batch can be edited",
      });
      return;
    }
    const frames = [...new Set(
      (Array.isArray(body.frames) ? body.frames : [])
        .map(Number)
        .filter(Number.isInteger),
    )].sort((left, right) => left - right);
    if (!frames.length || frames.length > 300) {
      sendJson(response, 400, {
        error: "A coordinate batch must contain 1–300 frames",
      });
      return;
    }
    const observations = (Array.isArray(body.observations)
      ? body.observations
      : []
    ).map((observation) => ({
      frame: Number(observation?.frame),
      decision: String(observation?.decision || ""),
      x: Number(observation?.x),
      y: Number(observation?.y),
      candidateIndex: Number(observation?.candidateIndex),
      confidence: Number(observation?.confidence),
      approved: observation?.approved === true,
    })).filter((observation) =>
      Number.isInteger(observation.frame)
      && frames.includes(observation.frame)
      && [
        "agree",
        "undefined",
        "specified",
        "yolo_candidate",
        "needs_more_checking",
      ].includes(observation.decision)
      && (
        ["undefined", "needs_more_checking"].includes(observation.decision)
        || (
          Number.isFinite(observation.x)
          && observation.x >= 0
          && observation.x <= context.selected.imageWidth
          && Number.isFinite(observation.y)
          && observation.y >= 0
          && observation.y <= context.selected.imageHeight
        )
      )
      && (
        observation.decision !== "yolo_candidate"
        || (
          Number.isInteger(observation.candidateIndex)
          && observation.candidateIndex >= 0
          && Number.isFinite(observation.confidence)
          && observation.confidence >= 0
          && observation.confidence <= 1
        )
      )
    );
    batch.frames = frames;
    batch.observations = Object.fromEntries(
      observations.map((observation) => [
        String(observation.frame),
        observation,
      ]),
    );
    batch.draftUpdatedAt = new Date().toISOString();
    context.state.coordinateReview.flaggedFrames = frames;
    await saveState(segment, context.state);
    sendJson(response, 200, {
      saved: true,
      batchId: batch.id,
      frameCount: frames.length,
      observationCount: observations.length,
    });
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/trajectory-audit-draft"
  ) {
    const body = await readBody(request, 131_072);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    const validFrames = new Set(
      (
        await loadDetectedBallTrack(
          context.selected,
          {allowDetectionOnly: true},
        )
      )?.states?.map((state) => Number(state.frame)) || [],
    );
    const observations = (Array.isArray(body.observations)
      ? body.observations
      : []
    ).map((observation) => ({
      frame: Number(observation?.frame),
      decision: String(observation?.decision || ""),
      x: Number(observation?.x),
      y: Number(observation?.y),
      candidateIndex: Number(observation?.candidateIndex),
      confidence: Number(observation?.confidence),
      approved: observation?.approved === true,
    })).filter((observation) =>
      Number.isInteger(observation.frame)
      && validFrames.has(observation.frame)
      && [
        "agree",
        "undefined",
        "specified",
        "yolo_candidate",
        "needs_more_checking",
      ].includes(observation.decision)
      && (
        ["undefined", "needs_more_checking"].includes(observation.decision)
        || (
          Number.isFinite(observation.x)
          && observation.x >= 0
          && observation.x <= context.selected.imageWidth
          && Number.isFinite(observation.y)
          && observation.y >= 0
          && observation.y <= context.selected.imageHeight
        )
      )
      && (
        observation.decision !== "yolo_candidate"
        || (
          Number.isInteger(observation.candidateIndex)
          && observation.candidateIndex >= 0
          && Number.isFinite(observation.confidence)
          && observation.confidence >= 0
          && observation.confidence <= 1
        )
      )
    );
    context.state.trajectoryAudit = {
      observations: Object.fromEntries(
        observations.map((observation) => [
          String(observation.frame),
          observation,
        ]),
      ),
      updatedAt: new Date().toISOString(),
    };
    await saveState(segment, context.state);
    sendJson(response, 200, {
      saved: true,
      observationCount: observations.length,
    });
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/message") {
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already reviewing an event",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    const index = Number(body.index);
    const text = String(body.text || "").trim();
    const allowChanges = body.mode === "autopilot";
    if (!Number.isInteger(index) || !context.drafts[index]) {
      sendJson(response, 400, { error: "Select a draft event first" });
      return;
    }
    if (context.state.decisions[String(index)]?.status === "accepted") {
      sendJson(response, 409, {
        error: "This event is accepted; use Request Adjustment to reopen it",
      });
      return;
    }
    if (context.state.decisions[String(index)]?.status === "rejected") {
      sendJson(response, 409, {
        error: "This event is rejected; use Request Adjustment to reopen it",
      });
      return;
    }
    if (!text || text.length > 4_000) {
      sendJson(response, 400, {
        error: "Message must contain 1–4,000 characters",
      });
      return;
    }
    context.state.conversation.push({
      role: "user",
      content: text,
      eventIndex: index,
      timestamp: new Date().toISOString(),
    });
    await saveState(segment, context.state);
    lastConversationContext = { segment, eventIndex: index };
    reviewRequestPending = true;
    setActivity(
      "working",
      "Copilot is reviewing this event",
      "You can remain on this screen while the selected event is evaluated.",
    );
    sendJson(response, 202, { sent: true });
    setTimeout(() => {
      session.send({
        prompt: messagePrompt(
          context.selected,
          context.drafts[index],
          index,
          text,
          allowChanges,
        ),
        displayPrompt: (
          `Review Event ${index + 1} at `
          + `${context.drafts[index].seconds.toFixed(3)}s: `
          + text.slice(0, 180)
        ),
        agentMode: allowChanges ? "autopilot" : "plan",
      })
        .catch(async (error) => {
          reviewRequestPending = false;
          const failedReview = await reviewContext(segment);
          failedReview.state.conversation.push({
            role: "system",
            content: `Message failed: ${error.message}`,
            eventIndex: index,
            timestamp: new Date().toISOString(),
          });
          await saveState(segment, failedReview.state);
          setActivity(
            "error",
            "The canvas message could not be processed",
            error.message,
          );
        });
    }, 0);
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/cancel-review") {
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const review = await reviewContext(segment);
    const active = lastConversationContext?.segment === segment
      ? lastConversationContext
      : null;
    if (Number.isInteger(active?.engineIndex)) {
      const cachedCurrent = await captureEngineSnapshot(segment);
      const current = engineReviewSnapshot(review.state, cachedCurrent);
      const event = snapshotEvents(current)[active.engineIndex];
      if (event) {
        delete review.state.engineEventReviewAuthorizations[
          engineEventReviewKey(event)
        ];
      }
    }
    if (Number.isInteger(active?.eventIndex)) {
      delete review.state.copilotAcceptanceAuthorizations[
        String(active.eventIndex)
      ];
    }
    review.state.pendingClipRequest = null;
    if (review.state.automaticCopilotReview?.status === "reviewing") {
      review.state.automaticCopilotReview = {
        ...review.state.automaticCopilotReview,
        status: "cancelled",
        completedAt: new Date().toISOString(),
        error: null,
      };
    }
    await saveState(segment, review.state);
    reviewRequestPending = false;
    lastConversationContext = null;
    setActivity(
      "ready",
      "Copilot review cancelled",
      "No pending review may change this segment.",
    );
    sendJson(response, 200, {segment, cancelled: true});
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/clip-message") {
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already reviewing an event",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    const seconds = Number(body.seconds);
    const text = String(body.text || "").trim();
    const mode = body.mode === "autopilot" ? "autopilot" : "plan";
    const scope = body.scope === "current_time"
      ? "current_time"
      : "entire_clip";
    const flaggedFrames = Array.from(new Set(
      Array.isArray(body.flaggedFrames)
        ? body.flaggedFrames
          .map(Number)
          .filter(frame => Number.isInteger(frame) && frame >= 0)
        : [],
    )).sort((left, right) => left - right);
    if (flaggedFrames.length > 300) {
      sendJson(response, 400, {
        error: "A batch review is limited to 300 flagged frames",
      });
      return;
    }
    const coordinateObservations = Array.isArray(body.coordinateObservations)
      ? body.coordinateObservations.map(observation => ({
          frame: Number(observation?.frame),
          decision: String(observation?.decision || ""),
          x: Number(observation?.x),
          y: Number(observation?.y),
          candidateIndex: Number(observation?.candidateIndex),
          confidence: Number(observation?.confidence),
        })).filter(observation =>
          Number.isInteger(observation.frame)
          && flaggedFrames.includes(observation.frame)
          && [
            "agree",
            "undefined",
            "specified",
            "yolo_candidate",
            "needs_more_checking",
          ].includes(
            observation.decision,
          )
          && (
            ["undefined", "needs_more_checking"].includes(
              observation.decision,
            )
            || (
              Number.isFinite(observation.x)
              && observation.x >= 0
              && observation.x <= context.selected.imageWidth
              && Number.isFinite(observation.y)
              && observation.y >= 0
              && observation.y <= context.selected.imageHeight
            )
          )
          && (
            observation.decision !== "yolo_candidate"
            || (
              Number.isInteger(observation.candidateIndex)
              && observation.candidateIndex >= 0
              && Number.isFinite(observation.confidence)
              && observation.confidence >= 0
              && observation.confidence <= 1
            )
          )
        )
      : [];
    if (
      !Number.isFinite(seconds)
      || seconds < 0
      || seconds > context.selected.durationSeconds
    ) {
      sendJson(response, 400, {
        error: "The current time is outside this segment",
      });
      return;
    }
    if (!text || text.length > 1_000) {
      sendJson(response, 400, {
        error: "Enter a clip question or observation in 1–1,000 characters",
      });
      return;
    }
    const requestedAt = new Date().toISOString();
    const selectedIndex = Number.isInteger(body.selectedIndex)
      && context.drafts[Number(body.selectedIndex)]
      ? Number(body.selectedIndex)
      : null;
    context.state.pendingClipRequest = {
      seconds,
      text,
      selectedIndex,
      requestedAt,
      mode,
      scope,
      flaggedFrames,
      coordinateObservations,
    };
    if (flaggedFrames.length) {
      if (context.state.coordinateReview?.status === "finalized") {
        sendJson(response, 409, {
          error: "Ball-coordinate review is closed because this segment is already in review",
        });
        return;
      }
      context.state.coordinateReview.batches ||= [];
      const before = await coordinateOutputSnapshot(context.selected);
      let batch = activeCoordinateBatch(context.state);
      if (!batch || batch.status === "done" || batch.status === "failed") {
        const number = Math.max(
          0,
          ...context.state.coordinateReview.batches.map(
            (candidate) => Number(candidate.number || 0),
          ),
        ) + 1;
        batch = {
          id: `coordinate-round-${number}`,
          number,
          status: "ready",
          frames: flaggedFrames,
          observations: {},
          createdAt: requestedAt,
          before,
          frameResults: {},
        };
        context.state.coordinateReview.batches.push(batch);
      }
      batch.status = "working";
      batch.frames = flaggedFrames;
      batch.observations = Object.fromEntries(
        coordinateObservations.map((observation) => [
          String(observation.frame),
          observation,
        ]),
      );
      batch.submittedAt = requestedAt;
      batch.reviewCompletedAt = null;
      batch.codeFixCompletedAt = null;
      batch.testsCompletedAt = null;
      batch.rerunStartedAt = null;
      batch.rerunCompletedAt = null;
      batch.failure = null;
      batch.before = before;
      context.state.coordinateReview.activeBatchId = batch.id;
      context.state.coordinateReview = {
        ...context.state.coordinateReview,
        status: "reviewing",
        flaggedFrames,
        requestedAt,
        verifiedAt: null,
        trackerHash: null,
        provenanceHash: null,
        summary: null,
      };
    }
    context.state.conversation.push({
      role: "user",
      content: `${
        scope === "current_time"
          ? `${seconds.toFixed(3)}s ±2s`
          : "Entire clip"
      } · ${mode}${
        flaggedFrames.length
          ? ` · ${flaggedFrames.length} flagged ball frames`
          : ""
      } · ${text}`,
      eventIndex: null,
      coordinateReview: flaggedFrames.length > 0,
      coordinateBatchId: flaggedFrames.length
        ? context.state.coordinateReview.activeBatchId
        : null,
      timestamp: requestedAt,
    });
    await saveState(segment, context.state);
    lastConversationContext = { segment, eventIndex: null };
    reviewRequestPending = true;
    setActivity(
      "working",
      "Copilot is reviewing the clip",
      `Considering the ${
        scope === "current_time"
          ? `question around ${seconds.toFixed(3)}s`
          : "whole-clip question"
      } in ${mode === "autopilot"
        ? "Autopilot inspection mode"
        : "Plan mode"}.`,
    );
    sendJson(response, 202, { sent: true, seconds });
    setTimeout(() => {
      session.send({
        prompt: clipConversationPrompt(
          context.selected,
          seconds,
          text,
          context.drafts,
          selectedIndex,
          mode,
          scope,
          flaggedFrames,
          coordinateObservations,
        ),
        displayPrompt: (
          `Ask about ${
            scope === "current_time"
              ? `this clip at ${seconds.toFixed(3)}s`
              : "the entire clip"
          } (${mode}): `
          + text.slice(0, 180)
        ),
        agentMode: mode,
      }).catch(async (error) => {
        reviewRequestPending = false;
        const failedReview = await reviewContext(segment);
        failedReview.state.conversation.push({
          role: "system",
          content: `Clip conversation failed: ${error.message}`,
          eventIndex: null,
          timestamp: new Date().toISOString(),
        });
        await saveState(segment, failedReview.state);
        setActivity(
          "error",
          "The clip question could not be processed",
          error.message,
        );
      });
    }, 0);
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/manual-review-event"
  ) {
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const review = await reviewContext(segment);
    if (workflow.key === "innovation") {
      ensureInnovationManualReference(review.state, segment);
      const reference = review.state.manualReference;
      const action = String(body.action || "create");
      if (reference.approved && action !== "reopen") {
        sendJson(response, 409, {
          error: "Reopen the approved minute before changing its manual draft",
          code: "manual_reference_approved",
        });
        return;
      }
      if (
        action === "approve"
        && Math.round(review.selected.durationSeconds * 1000) !== 60_000
      ) {
        sendJson(response, 400, {
          error: "Golden approval is available only for a complete 60-second minute",
        });
        return;
      }
      const timestampMs = body.timestampMs === undefined
        ? Math.round(Number(body.seconds) * 1000)
        : Number(body.timestampMs);
      if (["create", "edit"].includes(action)) {
        if (
          !Number.isInteger(timestampMs)
          || timestampMs < 0
          || timestampMs > Math.round(review.selected.durationSeconds * 1000)
        ) {
          sendJson(response, 400, {
            error: "Use an integer millisecond within this segment",
          });
          return;
        }
        if (!["red", "black"].includes(String(body.team))) {
          sendJson(response, 400, {error: "Choose the event team"});
          return;
        }
        if (
          !["completed_pass", "turnover"].includes(String(body.eventType))
        ) {
          sendJson(response, 400, {error: "Choose a supported event type"});
          return;
        }
      }
      if (action === "map") {
        const engineCount = (await loadEngineEvents(segment)).length;
        const engineNumber = Number(String(body.engineKey || "").slice(1));
        if (
          !/^E[1-9]\d*$/.test(String(body.engineKey || ""))
          || engineNumber > engineCount
        ) {
          sendJson(response, 400, {error: "Choose an available E#"});
          return;
        }
      }
      try {
        const result = mutateInnovationManualReference(reference, {
          action,
          manualKey: String(body.manualKey || ""),
          engineKey: String(body.engineKey || ""),
          timestampMs,
          team: String(body.team || ""),
          eventType: String(body.eventType || ""),
        });
        await persistNormalizedManualReference(
          segment,
          review.state,
          action === "approve",
        );
        await saveState(segment, review.state);
        sendJson(response, action === "create" ? 201 : 200, {
          ok: true,
          action,
          event: result?.key ? result : null,
          approved: action === "approve" ? result : reference.approved,
          revision: reference.revision,
        });
      } catch (error) {
        sendJson(response, 400, {error: error.message});
      }
      return;
    }
    if (review.selected.validated || review.state.publishedReference) {
      sendJson(response, 409, {
        error: "Published passed references must be deliberately reopened before adding events",
      });
      return;
    }
    const seconds = Number(body.seconds);
    const team = String(body.team);
    const eventType = String(body.eventType);
    const note = String(body.note || "").trim();
    if (
      !Number.isFinite(seconds)
      || seconds < 0
      || seconds > review.selected.durationSeconds
    ) {
      sendJson(response, 400, {
        error: "The selected event time is outside this segment",
      });
      return;
    }
    if (!["red", "black"].includes(team)) {
      sendJson(response, 400, { error: "Choose the event team" });
      return;
    }
    if (!["completed_pass", "turnover"].includes(eventType)) {
      sendJson(response, 400, { error: "Choose a supported event type" });
      return;
    }
    if (!note || note.length > 1_000) {
      sendJson(response, 400, {
        error: "Describe the review event in 1–1,000 characters",
      });
      return;
    }
    const duplicate = review.drafts.find((draft) =>
      ["manual_review", "user_reported"].includes(draft.source)
      && draft.team === team
      && draft.type === eventType
      && Math.round(draft.seconds * 25) === Math.round(seconds * 25)
    );
    if (duplicate) {
      sendJson(response, 409, {
        error: "An equivalent manual M# already exists on this frame",
      });
      return;
    }
    const teamLabel = team === "red" ? "Red/white" : "Black";
    const eventLabel = eventType === "completed_pass"
      ? "completed pass"
      : "turnover";
    const index = review.drafts.length;
    review.state.additionalProposals.push({
      seconds: Math.round(seconds * 1000) / 1000,
      team,
      type: eventType,
      title: `${teamLabel} ${eventLabel}`,
      evidence: (
        `Manual review candidate at ${seconds.toFixed(3)}s: ${note} `
        + "This observation still requires independent video verification."
      ),
      rule: eventType === "completed_pass"
        ? "A completed pass requires a deliberate play followed by the first controlled teammate touch."
        : "A turnover requires the opposing team to establish controlled possession.",
      reportReason: note,
      reportedAt: new Date().toISOString(),
      source: "manual_review",
    });
    review.state.conversation.push({
      role: "system",
      content: (
        `Manual M${index + 1} was added at ${seconds.toFixed(3)}s. `
        + "It is not accepted and must be independently verified."
      ),
      eventIndex: index,
      timestamp: new Date().toISOString(),
    });
    await saveState(segment, review.state);
    setActivity(
      "ready",
      `Manual M${index + 1} ready`,
      "Verify the candidate, then accept or reject it in the event panel.",
    );
    sendJson(response, 201, { created: true, index });
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/require-same-frame-review"
  ) {
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const review = await reviewContext(segment);
    const index = Number(body.index);
    const draft = review.drafts[index];
    if (!Number.isInteger(index) || !draft) {
      sendJson(response, 404, {error: "Review event not found"});
      return;
    }
    if (
      review.selected.validated
      || review.state.publishedReference
    ) {
      sendJson(response, 409, {
        error: "Published passed references must be reopened before changing timing requirements",
      });
      return;
    }
    if (["manual_review", "user_reported"].includes(draft.source)) {
      sendJson(response, 409, {
        error: "Manual M# events already require same-frame engine agreement",
      });
      return;
    }
    review.state.sameFrameReviewRequirements ||= {};
    review.state.sameFrameReviewRequirements[String(index)] = true;
    review.state.regression = null;
    review.state.conversation.push({
      role: "user",
      content: (
        `Strict timing requested: C${index + 1} must be reviewed and corrected `
        + "to the supported completion frame, and C↔E agreement now requires "
        + "the same rounded 25-fps source-video frame."
      ),
      eventIndex: index,
      timestamp: new Date().toISOString(),
    });
    await saveState(segment, review.state);
    setActivity(
      "ready",
      `Same-frame review required for C${index + 1}`,
      "Use Verify & Accept to review the timing and synchronize the engine when needed.",
    );
    sendJson(response, 200, {updated: true, index});
    return;
  }
  if (
    request.method === "POST"
    && url.pathname === "/api/confirm-missing-event"
  ) {
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already reviewing an event",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    const candidate = context.state.pendingMissingCandidate;
    if (!candidate?.supported) {
      sendJson(response, 409, {
        error: "No supported missing-event plan is ready for handover",
      });
      return;
    }
    candidate.autopilotAuthorizedAt = new Date().toISOString();
    context.state.conversation.push({
      role: "user",
      content: (
        `Autopilot handover granted: add the planned ${candidate.team} `
        + `${candidate.eventType.replaceAll("_", " ")} at `
        + `${candidate.seconds.toFixed(3)}s as a review candidate.`
      ),
      eventIndex: null,
      timestamp: new Date().toISOString(),
    });
    await saveState(segment, context.state);
    lastConversationContext = { segment, eventIndex: null };
    reviewRequestPending = true;
    setActivity(
      "working",
      "Copilot is adding the planned event",
      "It will remain a proposal until separately verified and accepted.",
    );
    sendJson(response, 202, { sent: true });
    setTimeout(() => {
      session.send({
        prompt: confirmMissingEventPrompt(context.selected, candidate),
        displayPrompt: (
          `Add the planned ${candidate.eventType.replaceAll("_", " ")} at `
          + `${candidate.seconds.toFixed(3)}s for review.`
        ),
        agentMode: "autopilot",
      }).catch(async (error) => {
        reviewRequestPending = false;
        const failedReview = await reviewContext(segment);
        if (failedReview.state.pendingMissingCandidate) {
          delete failedReview.state.pendingMissingCandidate
            .autopilotAuthorizedAt;
        }
        failedReview.state.conversation.push({
          role: "system",
          content: `Missing-event handover failed: ${error.message}`,
          eventIndex: null,
          timestamp: new Date().toISOString(),
        });
        await saveState(segment, failedReview.state);
        setActivity(
          "error",
          "The planned event could not be added",
          error.message,
        );
      });
    }, 0);
    return;
  }
  sendJson(response, 404, { error: "Not found" });
}

async function startServer(instanceId) {
  const server = createServer((request, response) => {
    handleRequest(request, response, instanceId).catch((error) => {
      setActivity(
        "error",
        "Review operation failed",
        error.message,
      );
      sendJson(response, 500, { error: error.message });
    });
  });
  const portSeed = `${process.env.SESSION_ID || "copilot"}:${instanceId}`;
  const preferredPort = 52_000 + (
    Number.parseInt(
      createHash("sha256").update(portSeed).digest("hex").slice(0, 8),
      16,
    ) % 10_000
  );
  const listen = (port) => new Promise((resolvePromise, rejectPromise) => {
    const onError = (error) => {
      server.off("listening", onListening);
      rejectPromise(error);
    };
    const onListening = () => {
      server.off("error", onError);
      resolvePromise();
    };
    server.once("error", onError);
    server.once("listening", onListening);
    server.listen(port, "127.0.0.1");
  });
  try {
    await listen(preferredPort);
  } catch (error) {
    if (error?.code !== "EADDRINUSE") throw error;
    await listen(0);
  }

  const address = server.address();
  const port = typeof address === "object" && address ? address.port : 0;
  return {
    server,
    url: `http://127.0.0.1:${port}/`,
    instanceId,
  };
}

async function registerLauncherUrl(theme, url) {
  const update = launcherRegistryUpdate.then(async () => {
    const registry = await readJson(launcherRegistryPath, {});
    registry[theme] = url;
    await mkdir(dirname(launcherRegistryPath), {recursive: true});
    await writeJsonAtomically(launcherRegistryPath, registry);
  });
  launcherRegistryUpdate = update.catch(() => {});
  await update;
}

session = await joinSession({
  canvases: [
    createCanvas({
      id: workflow.canvasId,
      displayName: workflow.displayName,
      description: workflow.description,
      inputSchema: {
        type: "object",
        properties: {
          segment: { type: "string" },
          theme: { type: "string", enum: [workflow.theme] },
        },
        additionalProperties: false,
      },
      actions: (registeredCanvasActions = [
        {
          name: "get_review_status",
          description: "Read one prepared segment's review progress without changing it.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              index: { type: "integer", minimum: 0 },
            },
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input?.segment || defaultSegment);
            const review = await reviewContext(segment);
            const state = review.state;
            const currentEngine = await captureEngineSnapshot(segment);
            const accepted = Object.values(state.decisions)
              .filter((decision) => decision.status === "accepted").length;
            const index = Number.isInteger(context.input?.index)
              ? Number(context.input.index)
              : null;
            const decision = index !== null
              ? state.decisions[String(index)]
              : null;
            return {
              segment: state.segment,
              validationStatus: review.selected.validationStatus,
              totalDrafts: review.drafts.length,
              reviewed: Object.keys(state.decisions).length,
              accepted,
              hasPostChangeSnapshot: Boolean(state.engineAfter),
              engineSnapshotFresh: Boolean(
                matchingStoredSnapshot(currentEngine, state),
              ),
              currentEngineContentHash:
                currentEngine.fingerprint.contentHash,
              currentOutputHash: currentEngine.outputHash,
              regression: state.regression
                ? {
                    ...state.regression,
                    fresh: isRegressionCurrent(
                      state.regression,
                      currentEngine,
                    ),
                  }
                : null,
              eventComparison:
                index !== null
                && decision?.status === "accepted"
                  ? acceptedEngineComparison(
                      review.drafts[index],
                      state,
                      decision,
                      currentEngine,
                    )
                  : null,
              beforeFingerprint: state.engineBefore.fingerprint,
            };
          },
        },
        {
          name: "publish_review_progress",
          description: "Publish an in-progress Copilot update into the Canvas conversation without completing the review.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              eventIndex: { type: "integer", minimum: 0 },
              engineIndex: { type: "integer", minimum: 0 },
              content: { type: "string", minLength: 1, maxLength: 4_000 },
            },
            required: ["segment", "content"],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const content = String(context.input.content).trim();
            const review = await reviewContext(segment);
            const eventIndex = Number.isInteger(context.input.eventIndex)
              ? Number(context.input.eventIndex)
              : null;
            const engineIndex = Number.isInteger(context.input.engineIndex)
              ? Number(context.input.engineIndex)
              : null;
            if (eventIndex !== null && engineIndex !== null) {
              throw new CanvasError(
                "review_conversation_ambiguous",
                "Choose either a C# eventIndex or an E# engineIndex.",
              );
            }
            if (eventIndex !== null && !review.drafts[eventIndex]) {
              throw new CanvasError(
                "review_event_missing",
                "The selected review event does not exist.",
              );
            }
            if (engineIndex !== null) {
              const cachedCurrent = await captureEngineSnapshot(segment);
              const events = snapshotEvents(
                engineReviewSnapshot(review.state, cachedCurrent),
              );
              if (!events[engineIndex]) {
                throw new CanvasError(
                  "engine_event_missing",
                  "The selected rules-engine event does not exist.",
                );
              }
            }
            const coordinateBatch = eventIndex === null
              && engineIndex === null
              && review.state.pendingClipRequest?.flaggedFrames?.length
              ? activeCoordinateBatch(review.state)
              : null;
            review.state.conversation.push({
              role: "assistant",
              content,
              eventIndex,
              engineIndex,
              coordinateReview: Boolean(coordinateBatch),
              coordinateBatchId: coordinateBatch?.id || null,
              timestamp: new Date().toISOString(),
            });
            await saveState(segment, review.state);
            broadcast("conversation");
            return {
              segment,
              eventIndex,
              engineIndex,
              published: true,
              completed: false,
            };
          },
        },
        {
          name: "update_ball_coordinate_batch",
          description: "Advance the active ball-coordinate batch after review, code correction, or tests. Passing tests automatically starts the saved-detection tracker/YOLO rerun.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              stage: {
                type: "string",
                enum: [
                  "review_completed",
                  "code_fix_completed",
                  "tests_completed",
                ],
              },
              summary: {
                type: "string",
                minLength: 1,
                maxLength: 2_000,
              },
              passed: { type: "boolean" },
            },
            required: ["segment", "stage", "summary"],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const stage = String(context.input.stage);
            const summary = String(context.input.summary).trim();
            const review = await reviewContext(segment);
            const batch = activeCoordinateBatch(review.state);
            if (!batch || !["working", "review_completed", "code_fix_completed", "tests_completed"].includes(batch.status)) {
              throw new CanvasError(
                "ball_coordinate_batch_missing",
                "No active ball-coordinate batch is awaiting this update.",
              );
            }
            const requiredStatus = {
              review_completed: "working",
              code_fix_completed: "review_completed",
              tests_completed: "code_fix_completed",
            }[stage];
            if (batch.status !== requiredStatus) {
              throw new CanvasError(
                "ball_coordinate_batch_stage_invalid",
                `Batch ${batch.number} must be ${requiredStatus} before ${stage}.`,
              );
            }
            const now = new Date().toISOString();
            if (stage === "review_completed") {
              batch.status = "review_completed";
              batch.reviewCompletedAt = now;
              batch.reviewSummary = summary;
            } else if (stage === "code_fix_completed") {
              batch.status = "code_fix_completed";
              batch.codeFixCompletedAt = now;
              batch.codeFixSummary = summary;
            } else {
              if (context.input.passed !== true) {
                batch.status = "failed";
                batch.testsCompletedAt = now;
                batch.failure = summary;
                review.state.coordinateReview.status = "pending";
                await saveState(segment, review.state);
                setActivity(
                  "error",
                  "Coordinate correction tests failed",
                  summary,
                );
                return {segment, batchId: batch.id, rerunStarted: false};
              }
              batch.status = "tests_completed";
              batch.testsCompletedAt = now;
              batch.testsSummary = summary;
              await saveState(segment, review.state);
              setActivity(
                "working",
                "Starting corrected ball-coordinate rerun",
                "Running bounded focused recovery while preserving all accepted coordinates.",
              );
              try {
                const result = await localJson(
                  workflow.analyzePath,
                  {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                      cache_key: segment,
                      events_only: false,
                      focused_recovery: true,
                    }),
                  },
                );
                batch.status = "rerun_started";
                batch.rerunStartedAt = new Date().toISOString();
                batch.awaitingRunObservation = true;
                review.state.coordinateReview.status = "rerunning";
                review.state.pendingClipRequest = null;
                await saveState(segment, review.state);
                return {
                  ...result,
                  segment,
                  batchId: batch.id,
                  rerunStarted: true,
                };
              } catch (error) {
                batch.status = "failed";
                batch.failedAt = new Date().toISOString();
                batch.failure = error.message;
                review.state.coordinateReview.status = "pending";
                await saveState(segment, review.state);
                setActivity(
                  "error",
                  "Corrected ball-coordinate rerun failed to start",
                  error.message,
                );
                throw new CanvasError(
                  "ball_coordinate_rerun_failed",
                  error.message,
                );
              }
            }
            await saveState(segment, review.state);
            setActivity(
              "working",
              stage === "review_completed"
                ? "Coordinate review complete"
                : "Coordinate code correction complete",
              summary,
            );
            return {
              segment,
              batchId: batch.id,
              stage,
              rerunStarted: false,
            };
          },
        },
        {
          name: "reject_ball_coordinate_review",
          description: "Reject a completed coordinate rerun when independent raw-video review finds unsupported direct coordinates. Blocks verification and opens a new diagnostic round with reasons; it does not alter tracker output.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              summary: { type: "string", minLength: 1, maxLength: 2_000 },
              disputes: {
                type: "array",
                minItems: 1,
                maxItems: 100,
                items: {
                  type: "object",
                  properties: {
                    frame: { type: "integer", minimum: 0 },
                    reason: { type: "string", minLength: 1, maxLength: 1_000 },
                  },
                  required: ["frame", "reason"],
                  additionalProperties: false,
                },
              },
            },
            required: ["segment", "summary", "disputes"],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const review = await reviewContext(segment);
            if (activeCoordinateBatch(review.state)) {
              throw new CanvasError(
                "ball_coordinate_round_active",
                "A coordinate review round is already active.",
              );
            }
            const completed = [...(
              review.state.coordinateReview?.batches || []
            )].reverse().find((candidate) => candidate.status === "done");
            if (!completed) {
              throw new CanvasError(
                "ball_coordinate_rerun_missing",
                "No completed coordinate rerun is available to reject.",
              );
            }
            const completedFrames = new Set(completed.frames || []);
            const disputes = context.input.disputes.map((dispute) => ({
              frame: Number(dispute.frame),
              reason: String(dispute.reason).trim(),
            }));
            if (disputes.some((dispute) => !completedFrames.has(dispute.frame))) {
              throw new CanvasError(
                "ball_coordinate_dispute_out_of_scope",
                "Every disputed frame must belong to the completed round.",
              );
            }
            const frames = [...new Set([
              ...(completed.unresolvedFrames || []),
              ...(completed.regressionFrames || []),
              ...disputes.map((dispute) => dispute.frame),
            ])].sort((left, right) => left - right);
            const nextNumber = Math.max(
              0,
              ...(review.state.coordinateReview?.batches || []).map(
                (candidate) => Number(candidate.number || 0),
              ),
            ) + 1;
            const carryForward = coordinateCarryForward(completed, frames);
            disputes.forEach((dispute) => {
              carryForward[String(dispute.frame)] = {
                sourceBatchId: completed.id,
                sourceRound: completed.number,
                status: "disputed_direct",
                reason: dispute.reason,
              };
            });
            completed.reviewRejectedAt = new Date().toISOString();
            completed.reviewRejection = String(context.input.summary).trim();
            completed.disputedFrames = disputes.map(
              (dispute) => dispute.frame,
            );
            const nextBatch = {
              id: `coordinate-round-${nextNumber}`,
              number: nextNumber,
              status: "ready",
              frames,
              observations: {},
              createdAt: completed.reviewRejectedAt,
              before: completed.after,
              frameResults: {},
              carryForward,
              createdFromRejectedReview: completed.id,
            };
            review.state.coordinateReview = {
              ...review.state.coordinateReview,
              status: "pending",
              activeBatchId: nextBatch.id,
              flaggedFrames: frames,
              verifiedAt: null,
              trackerHash: null,
              provenanceHash: null,
              summary: completed.reviewRejection,
            };
            review.state.coordinateReview.batches.push(nextBatch);
            review.state.conversation.push({
              role: "system",
              content: `Copilot rejected Round ${completed.number} validation after independent raw-video review and opened Round ${nextNumber} with ${frames.length} unresolved or disputed frames.`,
              eventIndex: null,
              coordinateReview: true,
              coordinateBatchId: nextBatch.id,
              timestamp: completed.reviewRejectedAt,
            });
            await saveState(segment, review.state);
            return {
              segment,
              rejectedBatchId: completed.id,
              nextBatchId: nextBatch.id,
              frameCount: frames.length,
            };
          },
        },
        {
          name: "confirm_ball_coordinate_review",
          description: "Confirm that the completed local AI output has at least 90% direct ball provenance and that the current tracker code and coordinate output were independently reviewed. This does not put the segment into review; the user must finalize it in the Canvas.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              summary: { type: "string", minLength: 1, maxLength: 2_000 },
            },
            required: ["segment", "summary"],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const review = await reviewContext(segment);
            if (!ballCoordinateReviewCanBeVerified(review.selected)) {
              throw new CanvasError(
                "ball_coordinate_ai_incomplete",
                "Local AI must complete before ball coordinates can be verified.",
              );
            }
            if (!review.state.coordinateReview?.flaggedFrames?.length) {
              throw new CanvasError(
                "ball_coordinate_review_missing",
                "No flagged-frame batch has been reviewed.",
              );
            }
            const snapshot = await ballCoordinateReviewSnapshot(segment);
            if (
              snapshot.directProvenance < 0.90
              || snapshot.directFrameCount < Math.ceil(
                snapshot.sampledFrameCount * 0.90,
              )
            ) {
              throw new CanvasError(
                "ball_coordinate_provenance_below_gate",
                "Direct ball-coordinate provenance is below the 90% minimum.",
              );
            }
            review.state.coordinateReview = {
              ...review.state.coordinateReview,
              status: "verified",
              verifiedAt: new Date().toISOString(),
              trackerHash: snapshot.trackerHash,
              provenanceHash: snapshot.provenanceHash,
              summary: String(context.input.summary).trim(),
            };
            review.state.conversation.push({
              role: "system",
              content: "Copilot verified the current ball-coordinate code and "
                + "output. The user may now choose Finalize and put in review.",
              eventIndex: null,
              coordinateReview: true,
              timestamp: review.state.coordinateReview.verifiedAt,
            });
            await saveState(segment, review.state);
            return {
              segment,
              verified: true,
              directFrameCount: snapshot.directFrameCount,
              sampledFrameCount: snapshot.sampledFrameCount,
              directProvenance: snapshot.directProvenance,
              finalized: false,
            };
          },
        },
        {
          name: "publish_review_response",
          description: "Publish the final concise Copilot answer into the floating Canvas conversation.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              eventIndex: { type: "integer", minimum: 0 },
              engineIndex: { type: "integer", minimum: 0 },
              content: { type: "string", minLength: 1, maxLength: 4_000 },
            },
            required: ["segment", "content"],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const content = String(context.input.content).trim();
            const review = await reviewContext(segment);
            const eventIndex = Number.isInteger(context.input.eventIndex)
              ? Number(context.input.eventIndex)
              : null;
            const engineIndex = Number.isInteger(context.input.engineIndex)
              ? Number(context.input.engineIndex)
              : null;
            if (eventIndex !== null && engineIndex !== null) {
              throw new CanvasError(
                "review_conversation_ambiguous",
                "Choose either a C# eventIndex or an E# engineIndex.",
              );
            }
            if (eventIndex !== null && !review.drafts[eventIndex]) {
              throw new CanvasError(
                "review_event_missing",
                "The selected review event does not exist.",
              );
            }
            let engineEvent = null;
            if (engineIndex !== null) {
              const cachedCurrent = await captureEngineSnapshot(segment);
              const events = snapshotEvents(
                engineReviewSnapshot(review.state, cachedCurrent),
              );
              engineEvent = events[engineIndex];
              if (!engineEvent) {
                throw new CanvasError(
                  "engine_event_missing",
                  "The selected rules-engine event does not exist.",
                );
              }
            }
            const previous = review.state.conversation.at(-1);
            const coordinateReviewResponse = Boolean(
              eventIndex === null
              && engineIndex === null
              && review.state.pendingClipRequest?.flaggedFrames?.length
            );
            const coordinateBatch = coordinateReviewResponse
              ? activeCoordinateBatch(review.state)
              : null;
            let changed = false;
            if (
              previous?.role !== "assistant"
              || previous.content !== content
              || previous.eventIndex !== eventIndex
              || previous.engineIndex !== engineIndex
            ) {
              review.state.conversation.push({
                role: "assistant",
                content,
                eventIndex,
                engineIndex,
                coordinateReview: coordinateReviewResponse,
                coordinateBatchId: coordinateBatch?.id || null,
                timestamp: new Date().toISOString(),
              });
              changed = true;
            }
            if (eventIndex !== null) {
              const authorization = review.state
                .copilotAcceptanceAuthorizations[String(eventIndex)];
              if (authorization) {
                delete review.state
                  .copilotAcceptanceAuthorizations[String(eventIndex)];
                changed = true;
              }
            } else if (engineEvent) {
              const key = engineEventReviewKey(engineEvent);
              if (review.state.engineEventReviewAuthorizations[key]) {
                delete review.state.engineEventReviewAuthorizations[key];
                changed = true;
              }
            } else if (review.state.pendingClipRequest) {
              if (coordinateReviewResponse) {
                if (review.state.coordinateReview.status === "reviewing") {
                  review.state.coordinateReview.status = "pending";
                }
              }
              review.state.pendingClipRequest = null;
              changed = true;
            }
            if (changed) {
              await saveState(segment, review.state);
            }
            reviewRequestPending = false;
            setActivity(
              "ready",
              "Copilot result ready",
              "Open Copilot Chat to read the result and continue this event review.",
            );
            broadcast("conversation");
            return { segment, eventIndex, engineIndex, published: true };
          },
        },
        {
          name: "record_copilot_proposal",
          description: "Record an independently inferred Copilot review proposal so it appears as C# and can match an E# without accepting either event.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              seconds: { type: "number", minimum: 0, maximum: 60 },
              team: {
                type: "string",
                enum: ["red", "black", "match_state"],
              },
              eventType: {
                type: "string",
                enum: [
                  "completed_pass",
                  "turnover",
                  "foul_encountered",
                  "shot_candidate",
                  "shot_on_target",
                ],
              },
              title: { type: "string", minLength: 1 },
              evidence: { type: "string", minLength: 1 },
              rule: { type: "string", minLength: 1 },
              reason: { type: "string", minLength: 1 },
            },
            required: [
              "segment",
              "seconds",
              "team",
              "eventType",
              "title",
              "evidence",
              "rule",
              "reason",
            ],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const review = await reviewContext(segment);
            if (review.state.automaticCopilotReview?.status === "cancelled") {
              throw new CanvasError(
                "automatic_review_cancelled",
                "This automatic Copilot review was cancelled.",
              );
            }
            if (
              review.selected.validated
              || review.state.publishedReference
            ) {
              throw new CanvasError(
                "validated_reference_locked",
                "Published passed references must be deliberately reopened before adding proposals.",
              );
            }
            const seconds = Number(context.input.seconds);
            if (seconds > review.selected.durationSeconds) {
              throw new CanvasError(
                "review_time_out_of_range",
                "The proposed event time is outside the selected segment.",
              );
            }
            const team = String(context.input.team);
            const eventType = String(context.input.eventType);
            const duplicateIndex = review.drafts.findIndex((draft) =>
              draft.source === "copilot_review"
              && draft.team === team
              && draft.type === eventType
              && Math.abs(draft.seconds - seconds) <= 0.04
            );
            if (duplicateIndex >= 0) {
              return {
                segment,
                index: duplicateIndex,
                added: false,
                duplicate: true,
              };
            }
            const proposal = {
              seconds,
              team,
              type: eventType,
              title: String(context.input.title),
              evidence: String(context.input.evidence),
              rule: String(context.input.rule),
              reviewReason: String(context.input.reason),
              reviewedAt: new Date().toISOString(),
              source: "copilot_review",
            };
            review.state.additionalProposals.push(proposal);
            const index = review.drafts.length;
            await saveState(segment, review.state);
            setActivity(
              "ready",
              "Copilot proposal ready",
              `C${index + 1} is visible for independent review.`,
            );
            broadcast("state");
            return {
              segment,
              index,
              added: true,
              seconds,
              team,
              eventType,
            };
          },
        },
        {
          name: "replace_copilot_review",
          description: "Atomically replace unreviewed Copilot C# proposals for a segment with an independently inferred raw-video review.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              proposals: {
                type: "array",
                minItems: 0,
                maxItems: 100,
                items: {
                  type: "object",
                  properties: {
                    seconds: { type: "number", minimum: 0, maximum: 60 },
                    team: {
                      type: "string",
                      enum: ["red", "black", "match_state"],
                    },
                    eventType: {
                      type: "string",
                      enum: [
                        "completed_pass",
                        "turnover",
                        "foul_encountered",
                        "shot_candidate",
                        "shot_on_target",
                      ],
                    },
                    title: { type: "string", minLength: 1 },
                    evidence: { type: "string", minLength: 1 },
                    rule: { type: "string", minLength: 1 },
                    reason: { type: "string", minLength: 1 },
                  },
                  required: [
                    "seconds",
                    "team",
                    "eventType",
                    "title",
                    "evidence",
                    "rule",
                    "reason",
                  ],
                  additionalProperties: false,
                },
              },
            },
            required: ["segment", "proposals"],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const review = await reviewContext(segment);
            if (
              review.selected.validated
              || review.state.publishedReference
            ) {
              throw new CanvasError(
                "validated_reference_locked",
                "Published passed references must be deliberately reopened before replacing proposals.",
              );
            }
            if (Object.keys(review.state.decisions).length) {
              throw new CanvasError(
                "copilot_review_already_started",
                "Copilot proposals cannot be replaced after manual review decisions begin.",
              );
            }
            const proposals = context.input.proposals.map((input) => ({
              seconds: Number(input.seconds),
              team: String(input.team),
              type: String(input.eventType),
              title: String(input.title),
              evidence: String(input.evidence),
              rule: String(input.rule),
              reviewReason: String(input.reason),
              reviewedAt: new Date().toISOString(),
              source: "copilot_review",
            }));
            if (
              proposals.some(
                (proposal) =>
                  proposal.seconds > review.selected.durationSeconds,
              )
            ) {
              throw new CanvasError(
                "review_time_out_of_range",
                "A proposed event time is outside the selected segment.",
              );
            }
            review.state.additionalProposals = [
              ...review.state.additionalProposals.filter(
                (proposal) => proposal.source !== "copilot_review",
              ),
            ];
            if (proposals.length) {
              await writeJsonAtomically(copilotReviewPath(segment), {
                schemaVersion: 1,
                segment,
                evidenceScope: "raw_video",
                reviewedAt: new Date().toISOString(),
                proposals,
              });
            } else {
              await unlink(copilotReviewPath(segment)).catch((error) => {
                if (error?.code !== "ENOENT") throw error;
              });
            }
            if (review.state.automaticCopilotReview?.status === "reviewing") {
              review.state.automaticCopilotReview = {
                ...review.state.automaticCopilotReview,
                status: "complete",
                completedAt: new Date().toISOString(),
                proposalCount: proposals.length,
                error: null,
              };
            }
            await saveState(segment, review.state);
            setActivity(
              "ready",
              proposals.length ? "Copilot review ready" : "Copilot review cleared",
              proposals.length
                ? `${proposals.length} independent C# proposals are visible.`
                : "No C# proposal is recorded until the raw-video review completes.",
            );
            broadcast("state");
            return {
              segment,
              replaced: true,
              proposalCount: proposals.length,
            };
          },
        },
        {
          name: "confirm_engine_event_reviewed",
          description: "Mark one independently verified rules-engine event as reviewed without creating or accepting a Copilot proposal.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              index: { type: "integer", minimum: 0 },
              reason: { type: "string", minLength: 1, maxLength: 1_000 },
            },
            required: ["segment", "index", "reason"],
            additionalProperties: false,
          },
          handler: async (context) => confirmEngineEventReviewed(
            String(context.input.segment),
            Number(context.input.index),
            context.input.reason,
          ),
        },
        {
          name: "record_engine_event_not_confirmed",
          description: "Record that an independently reviewed E# is unsupported or uncertain without creating a C# or editing the engine.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              index: { type: "integer", minimum: 0 },
              reason: { type: "string", minLength: 1, maxLength: 1_000 },
            },
            required: ["segment", "index", "reason"],
            additionalProperties: false,
          },
          handler: async (context) => recordEngineEventNotConfirmed(
            String(context.input.segment),
            Number(context.input.index),
            context.input.reason,
          ),
        },
        {
          name: "accept_review_proposal",
          description: "Accept one proposal only after the user explicitly grants Copilot permission through the Canvas handover button.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              index: { type: "integer", minimum: 0 },
              reason: { type: "string", minLength: 1, maxLength: 1_000 },
            },
            required: ["segment", "index", "reason"],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const index = Number(context.input.index);
            const review = await reviewContext(segment);
            if (
              review.selected.validated
              || review.state.publishedReference
            ) {
              throw new CanvasError(
                "validated_reference_locked",
                "Published passed references are already locked.",
              );
            }
            if (!Number.isInteger(index) || !review.drafts[index]) {
              throw new CanvasError(
                "review_event_missing",
                "The selected review event does not exist.",
              );
            }
            const authorization = review.state
              .copilotAcceptanceAuthorizations[String(index)];
            if (
              !authorization
              || authorization.proposalFingerprint
                !== proposalFingerprint(review.drafts[index])
            ) {
              throw new CanvasError(
                "copilot_acceptance_not_authorized",
                "The user has not authorized Copilot to accept this exact proposal.",
              );
            }
            const {
              engineComparison,
              engineVerification,
            } = await compareWithCurrentEngine(
              segment,
              review.drafts[index],
              review.state,
            );
            const manualReview = [
              "manual_review",
              "user_reported",
            ].includes(review.drafts[index].source);
            if (
              manualReview
              && engineComparison.status !== "already_agrees"
            ) {
              throw new CanvasError(
                "manual_engine_alignment_required",
                "This M# cannot be accepted until a fresh rules-only engine run produces an exact same-frame E#.",
              );
            }
            review.state.decisions[String(index)] = {
              status: "accepted",
              note: String(context.input.reason),
              decidedAt: new Date().toISOString(),
              source: "copilot_verified",
              engineVerification,
            };
            const regressionResult =
              await ensureInnovationRegressionsCurrent(segment, review.state);
            delete review.state.copilotAcceptanceAuthorizations[String(index)];
            review.state.conversation.push({
              role: "system",
              content: (
                `Copilot verified and accepted Event ${index + 1}: `
                + context.input.reason
                + ` Engine check: ${engineComparison.label}. `
                + engineComparison.detail
                + (
                  regressionResult && !regressionResult.passed
                    ? ` Acceptance remains pending regression: ${
                        review.state.regression.summary
                      }`
                    : ""
                )
              ),
              eventIndex: index,
              timestamp: new Date().toISOString(),
            });
            await saveState(segment, review.state);
            setActivity(
              reviewRequestPending ? "working" : "ready",
              reviewRequestPending
                ? `Event ${index + 1} accepted · checking engine`
                : `Event ${index + 1} accepted`,
              engineComparison.status === "already_agrees"
                ? (
                    reviewRequestPending
                      ? "The engine agrees; Copilot is preparing the final response."
                      : "Copilot agreed, and the rules engine already detects this event."
                  )
                : engineComparison.status === "stale"
                  ? "Copilot agreed, but the engine snapshot is stale; the cached event stage must be rerun."
                  : "Copilot agreed and is synchronizing the general rule with the engine.",
            );
            return {
              segment,
              index,
              accepted: true,
              regressionPassed: regressionResult?.passed !== false,
              regressionFailures: regressionResult?.segmentFailures || [],
              engineComparison,
              engineVerification,
            };
          },
        },
        {
          name: "cancel_review_adjustment",
          description: "Cancel an adjustment request made against the wrong C# event without changing the proposal.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              index: { type: "integer", minimum: 0 },
              reason: { type: "string", minLength: 1, maxLength: 1_000 },
            },
            required: ["segment", "index", "reason"],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const index = Number(context.input.index);
            return cancelReviewAdjustment(
              segment,
              index,
              String(context.input.reason),
            );
          },
        },
        {
          name: "update_review_proposal",
          description: "Publish a re-reviewed correction to one event so the user can verify it again before acceptance.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              index: { type: "integer", minimum: 0 },
              seconds: { type: "number", minimum: 0, maximum: 60 },
              team: {
                type: "string",
                enum: ["red", "black", "match_state"],
              },
              eventType: {
                type: "string",
                enum: [
                  "completed_pass",
                  "turnover",
                  "foul_encountered",
                  "shot_candidate",
                  "shot_on_target",
                ],
              },
              title: { type: "string", minLength: 1 },
              evidence: { type: "string", minLength: 1 },
              rule: { type: "string", minLength: 1 },
              reason: { type: "string", minLength: 1 },
              preserveAcceptanceAuthorization: { type: "boolean" },
            },
            required: [
              "segment",
              "index",
              "seconds",
              "team",
              "eventType",
              "title",
              "evidence",
              "rule",
              "reason",
            ],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const index = Number(context.input.index);
            const review = await reviewContext(segment);
            if (
              review.selected.validated
              || review.state.publishedReference
            ) {
              throw new CanvasError(
                "validated_reference_locked",
                "Published passed references must be deliberately reopened before editing.",
              );
            }
            if (!Number.isInteger(index) || !review.drafts[index]) {
              throw new CanvasError(
                "review_event_missing",
                "The selected review event does not exist.",
              );
            }
            const authorization = review.state
              .copilotAcceptanceAuthorizations[String(index)];
            const acceptanceCorrectionAuthorized = Boolean(
              context.input.preserveAcceptanceAuthorization
              && authorization
              && authorization.proposalFingerprint
                === proposalFingerprint(review.drafts[index]),
            );
            if (
              review.state.decisions[String(index)]?.status !== "adjust"
              && !acceptanceCorrectionAuthorized
            ) {
              throw new CanvasError(
                "review_adjustment_not_authorized",
                "No adjustment or active acceptance review authorizes this correction.",
              );
            }
            const seconds = Number(context.input.seconds);
            if (seconds > review.selected.durationSeconds) {
              throw new CanvasError(
                "review_time_out_of_range",
                "The revised event time is outside the selected segment.",
              );
            }
            const neutralEvent = context.input.eventType === "foul_encountered";
            if (
              (neutralEvent && context.input.team !== "match_state")
              || (!neutralEvent && context.input.team === "match_state")
            ) {
              throw new CanvasError(
                "review_team_invalid",
                "Only a foul annotation may use match-state instead of a team.",
              );
            }
            const revisedProposal = {
              seconds,
              team: context.input.team === "match_state"
                ? null
                : context.input.team,
              type: context.input.eventType,
              title: String(context.input.title),
              evidence: String(context.input.evidence),
              rule: String(context.input.rule),
              adjustmentReason: String(context.input.reason),
              adjustedAt: new Date().toISOString(),
            };
            review.state.proposalOverrides[String(index)] = revisedProposal;
            delete review.state.decisions[String(index)];
            if (acceptanceCorrectionAuthorized) {
              review.state.copilotAcceptanceAuthorizations[String(index)] = {
                ...authorization,
                proposalFingerprint: proposalFingerprint({
                  ...review.drafts[index],
                  ...revisedProposal,
                }),
                correctedAt: new Date().toISOString(),
              };
            } else {
              delete review.state
                .copilotAcceptanceAuthorizations[String(index)];
            }
            review.state.conversation.push({
              role: "system",
              content: (
                `Event ${index + 1} was re-reviewed and updated: `
                + context.input.reason
              ),
              eventIndex: index,
              timestamp: new Date().toISOString(),
            });
            await saveState(segment, review.state);
            setActivity(
              "ready",
              "Revised proposal ready",
              `Event ${index + 1} is ready for your second review.`,
            );
            return {
              segment,
              index,
              updated: true,
              seconds,
              team: context.input.team,
              eventType: context.input.eventType,
            };
          },
        },
        {
          name: "recommend_missing_event",
          description: "Record a Plan-mode evaluation of a possible missing event without adding or accepting it.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              supported: { type: "boolean" },
              seconds: { type: "number", minimum: 0, maximum: 60 },
              team: { type: "string", enum: ["red", "black"] },
              eventType: {
                type: "string",
                enum: ["completed_pass", "turnover"],
              },
              title: { type: "string" },
              evidence: { type: "string" },
              rule: { type: "string" },
              reason: { type: "string", minLength: 1 },
            },
            required: [
              "segment",
              "supported",
              "seconds",
              "reason",
            ],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const review = await reviewContext(segment);
            const pending = review.state.pendingClipRequest;
            if (!pending) {
              throw new CanvasError(
                "missing_event_plan_not_requested",
                "No clip-level Plan request is waiting for evaluation.",
              );
            }
            if (
              Math.abs(pending.seconds - Number(context.input.seconds)) > 0.04
            ) {
              throw new CanvasError(
                "missing_event_plan_mismatch",
                "The evaluation does not match the user-marked frame.",
              );
            }
            if (
              context.input.supported
              && (
                !["red", "black"].includes(context.input.team)
                || !["completed_pass", "turnover"].includes(
                  context.input.eventType,
                )
                || !String(context.input.title || "").trim()
                || !String(context.input.evidence || "").trim()
                || !String(context.input.rule || "").trim()
              )
            ) {
              throw new CanvasError(
                "missing_event_plan_incomplete",
                "A supported candidate requires a title, evidence, and rule.",
              );
            }
            review.state.pendingMissingCandidate = {
              supported: Boolean(context.input.supported),
              seconds: pending.seconds,
              explanation: pending.text,
              requestedAt: pending.requestedAt,
              team: context.input.supported
                ? String(context.input.team)
                : null,
              eventType: context.input.supported
                ? String(context.input.eventType)
                : null,
              title: String(context.input.title || "").trim(),
              evidence: String(context.input.evidence || "").trim(),
              rule: String(context.input.rule || "").trim(),
              reason: String(context.input.reason),
              evaluatedAt: new Date().toISOString(),
            };
            review.state.pendingClipRequest = null;
            await saveState(segment, review.state);
            setActivity(
              "ready",
              context.input.supported
                ? "Missing-event plan ready"
                : "Missing event not supported",
              context.input.supported
                ? "Review the Plan result, then choose whether to hand it to Autopilot."
                : "No event or engine change was made.",
            );
            return {
              segment,
              supported: Boolean(context.input.supported),
              candidate: review.state.pendingMissingCandidate,
            };
          },
        },
        {
          name: "add_review_proposal",
          description: "Add a verified user-reported missing event for review before it becomes an engine requirement.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              seconds: { type: "number", minimum: 0, maximum: 60 },
              team: { type: "string", enum: ["red", "black"] },
              eventType: {
                type: "string",
                enum: ["completed_pass", "turnover"],
              },
              title: { type: "string", minLength: 1 },
              evidence: { type: "string", minLength: 1 },
              rule: { type: "string", minLength: 1 },
              reason: { type: "string", minLength: 1 },
            },
            required: [
              "segment",
              "seconds",
              "team",
              "eventType",
              "title",
              "evidence",
              "rule",
              "reason",
            ],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const review = await reviewContext(segment);
            if (
              review.selected.validated
              || review.state.publishedReference
            ) {
              throw new CanvasError(
                "validated_reference_locked",
                "Published passed references must be deliberately reopened before adding events.",
              );
            }
            const seconds = Number(context.input.seconds);
            if (seconds > review.selected.durationSeconds) {
              throw new CanvasError(
                "review_time_out_of_range",
                "The reported event time is outside the selected segment.",
              );
            }
            const team = String(context.input.team);
            const eventType = String(context.input.eventType);
            const planned = review.state.pendingMissingCandidate;
            if (
              !planned?.supported
              || !planned.autopilotAuthorizedAt
              || planned.team !== team
              || planned.eventType !== eventType
              || Math.abs(planned.seconds - seconds) > 0.04
            ) {
              throw new CanvasError(
                "missing_event_handover_not_authorized",
                "This exact missing-event plan has not been handed to Autopilot.",
              );
            }
            const duplicate = review.drafts.find((draft) =>
              draft.team === team
              && draft.type === eventType
              && Math.abs(draft.seconds - seconds) <= 0.5
            );
            if (duplicate) {
              throw new CanvasError(
                "review_event_duplicate",
                "An equivalent event already exists within 0.5 seconds.",
              );
            }
            const proposal = {
              seconds,
              team,
              type: eventType,
              title: String(context.input.title),
              evidence: String(context.input.evidence),
              rule: String(context.input.rule),
              reportReason: String(context.input.reason),
              reportedAt: new Date().toISOString(),
              source: "manual_review",
            };
            review.state.additionalProposals.push(proposal);
            const index = review.drafts.length;
            review.state.pendingMissingCandidate = null;
            review.state.conversation.push({
              role: "system",
              content: (
                `A possible missing event was verified and added as Event `
                + `${index + 1}. Review and accept it before any engine change.`
              ),
              eventIndex: index,
              timestamp: new Date().toISOString(),
            });
            await saveState(segment, review.state);
            setActivity(
              "ready",
              "Missing-event proposal ready",
              `Event ${index + 1} is ready for your review.`,
            );
            return {
              segment,
              index,
              added: true,
              seconds,
              team,
              eventType,
            };
          },
        },
        {
          name: "publish_validated_reference",
          description: "Publish and lock a completed review only after every final validation gate passes.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
            },
            required: ["segment"],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment);
            const review = await reviewContext(segment);
            if (
              review.selected.validated
              || review.state.publishedReference
            ) {
              throw new CanvasError(
                "reference_already_published",
                "This reference has already passed and is locked.",
              );
            }
            const authorization = review.state.publicationAuthorization;
            if (!authorization) {
              throw new CanvasError(
                "reference_publication_not_authorized",
                "Use Publish Validated Reference in the Canvas first.",
              );
            }
            const current = await captureEngineSnapshot(segment);
            if (
              authorization.reviewFingerprint
                !== publicationFingerprint(review.drafts, review.state)
              || authorization.engineContentHash
                !== current.fingerprint.contentHash
              || authorization.outputHash !== current.outputHash
            ) {
              throw new CanvasError(
                "reference_publication_stale",
                "Review decisions, engine code, or cached output changed after publication was authorized.",
              );
            }
            const storedSnapshot = matchingStoredSnapshot(
              current,
              review.state,
            );
            Object.entries(review.state.decisions).forEach(
              ([index, decision]) => {
                if (decision?.status !== "accepted") return;
                decision.engineVerification = engineVerificationReceipt(
                  current,
                  storedSnapshot?.[1],
                  storedSnapshot?.[0],
                );
              },
            );
            const plan = publicationPlan(
              review.drafts,
              review.state,
              current,
            );
            if (!plan.ready) {
              throw new CanvasError(
                "reference_publication_blocked",
                plan.blockers.join(" "),
              );
            }
            const reference = {
              schema_version: 2,
              video: segment,
              source_start_seconds: review.selected.startSeconds,
              duration_seconds: review.selected.durationSeconds,
              definition: (
                "Same-team first controlled touch completes a pass, including "
                + "legal restarts. A turnover completes only when an opponent "
                + "establishes control. Match-state stoppages suppress ordinary "
                + "events and are not analytics events."
              ),
              exported_at: new Date().toISOString(),
              events: plan.referenceEvents,
            };
            const path = join(segmentRoot(segment), "manual-reference.json");
            const previousReference = existsSync(path)
              ? await readFile(path, "utf8")
              : null;
            await writeJsonAtomically(path, reference);
            const publishedSegment = (await loadPreparedSegments()).find(
              (candidate) => candidate.key === segment,
            );
            if (!publishedSegment?.validated) {
              if (previousReference === null) {
                await unlink(path).catch(() => {});
              } else {
                await writeTextAtomically(path, previousReference);
              }
              throw new CanvasError(
                "reference_exact_match_failed",
                "The published reference did not exactly match current engine output.",
              );
            }
            review.state.publicationAuthorization = null;
            review.state.publishedReference = {
              publishedAt: reference.exported_at,
              eventCount: reference.events.length,
              engineContentHash: current.fingerprint.contentHash,
              outputHash: current.outputHash,
              regressionRecordedAt: review.state.regression.recordedAt,
            };
            review.state.conversation.push({
              role: "system",
              content: (
                `Validated reference published with ${reference.events.length} `
                + "events after exact engine-output matching and protected "
                + "regression verification."
              ),
              eventIndex: null,
              timestamp: reference.exported_at,
            });
            await registerWorkflowRegression(segment, reference, current);
            await saveState(segment, review.state);
            setActivity(
              "working",
              "Validated reference published",
              `${reference.events.length} events passed exact engine validation.`,
            );
            return {
              segment,
              published: true,
              validationStatus: "passed",
              eventCount: reference.events.length,
              engineEventCount: plan.engineEventCount,
              referencePath: relative(projectRoot, path),
            };
          },
        },
        {
          name: "refresh_engine_snapshot",
          description: "Capture one segment's current engine fingerprint and output for regression verification.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              index: { type: "integer", minimum: 0 },
            },
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input?.segment || defaultSegment);
            const review = await reviewContext(segment);
            const state = review.state;
            state.engineAfter = await captureEngineSnapshot(segment);
            state.regression = null;
            const index = Number.isInteger(context.input?.index)
              ? Number(context.input.index)
              : null;
            state.conversation.push({
              role: "system",
              content: (
                "Current rules-engine source and cached event output were "
                + `refreshed: engine ${
                  state.engineAfter.fingerprint.contentHash.slice(0, 12)
                } · output ${state.engineAfter.outputHash.slice(0, 12)}.`
              ),
              eventIndex: index,
              timestamp: new Date().toISOString(),
            });
            await saveState(segment, state);
            const engineComparison = index !== null && review.drafts[index]
              ? compareWithEngine(review.drafts[index], state.engineAfter)
              : null;
            return {
              captured: true,
              fingerprint: state.engineAfter.fingerprint,
              outputHash: state.engineAfter.outputHash,
              engineComparison,
            };
          },
        },
        {
          name: "record_regression_result",
          description: "Record whether the protected regression suite passed for the current post-change engine fingerprint.",
          inputSchema: {
            type: "object",
            properties: {
              passed: { type: "boolean" },
              summary: { type: "string" },
              segment: { type: "string" },
              index: { type: "integer", minimum: 0 },
            },
            required: ["passed", "summary"],
            additionalProperties: false,
          },
          handler: async (context) => {
            const segment = String(context.input.segment || defaultSegment);
            const review = await reviewContext(segment);
            const state = review.state;
            if (!state.engineAfter) {
              throw new CanvasError(
                "engine_snapshot_missing",
                "Capture the post-change engine snapshot before recording regressions.",
              );
            }
            const index = Number.isInteger(context.input.index)
              ? Number(context.input.index)
              : null;
            if (context.input.passed && index !== null) {
              const draft = review.drafts[index];
              const decision = state.decisions[String(index)];
              if (!draft || decision?.status !== "accepted") {
                throw new CanvasError(
                  "accepted_review_event_missing",
                  "The regression result must reference an accepted review event.",
                );
              }
              const beforeComparison = compareWithEngine(
                draft,
                state.engineBefore,
              );
              const afterComparison = compareWithEngine(
                draft,
                state.engineAfter,
              );
              if (afterComparison.status !== "already_agrees") {
                throw new CanvasError(
                  "engine_fix_not_verified",
                  "The post-change engine output still does not match the accepted event.",
                );
              }
              const current = await captureEngineSnapshot(segment);
              if (
                current.fingerprint.contentHash
                  !== state.engineAfter.fingerprint.contentHash
                || current.outputHash !== state.engineAfter.outputHash
              ) {
                throw new CanvasError(
                  "engine_snapshot_stale",
                  "Engine code or cached output changed after the snapshot; refresh it and rerun protected regressions.",
                );
              }
              if (requiresEngineImplementationChange(
                beforeComparison.status,
                state.engineBefore.fingerprint.contentHash,
                state.engineAfter.fingerprint.contentHash,
                decision.engineVerification,
              )) {
                throw new CanvasError(
                  "engine_implementation_unchanged",
                  "The output changed without a corresponding general rules-engine implementation change.",
                );
              }
              decision.engineVerification = engineVerificationReceipt(
                current,
                state.engineAfter,
                "after",
              );
              decision.engineVerification.verifiedAfterRerun = true;
              Object.entries(state.decisions).forEach(
                ([decisionIndex, acceptedDecision]) => {
                  const candidate = review.drafts[Number(decisionIndex)];
                  if (
                    acceptedDecision.status !== "accepted"
                    || !candidate
                    || compareWithEngine(candidate, current).status
                      !== "already_agrees"
                  ) {
                    return;
                  }
                  acceptedDecision.engineVerification =
                    engineVerificationReceipt(
                      current,
                      state.engineAfter,
                      "after",
                    );
                  acceptedDecision.engineVerification.verifiedAfterRerun = true;
                },
              );
            }
            state.regression = {
              passed: context.input.passed,
              summary: context.input.summary,
              fingerprint: state.engineAfter.fingerprint,
              outputHash: state.engineAfter.outputHash,
              recordedAt: new Date().toISOString(),
            };
            state.conversation.push({
              role: "system",
              content: (
                `Protected regressions ${context.input.passed ? "passed" : "failed"}: `
                + context.input.summary
              ),
              eventIndex: index,
              timestamp: state.regression.recordedAt,
            });
            await saveState(segment, state);
            return state.regression;
          },
        },
      ]).map((action) => ({
        ...action,
        handler: (context) => dispatchCanvasAction(action, context),
      })),
      open: async (context) => {
        const segment = String(context.input?.segment || defaultSegment);
        const theme = workflow.theme;
        const review = await reviewContext(segment);
        let entry = servers.get(context.instanceId);
        if (!entry) {
          entry = await startServer(context.instanceId);
          servers.set(context.instanceId, entry);
        }
        const url = `${entry.url}?segment=${encodeURIComponent(segment)}&theme=${
          encodeURIComponent(theme)
        }&hostInstanceId=${encodeURIComponent(context.instanceId)}`;
        await setActiveAdapter(context.instanceId, workflow.key);
        await registerLauncherUrl(workflow.key, url);
        const reviewStatus = workflow.coordinateReviewEnabled
          ? review.state.coordinateReview?.status === "verified"
            ? "ball coordinate gate passed"
            : ballCoordinateReviewRequired(review.selected)
              ? "ball coordinates need review"
              : review.selected.validationStatus.replaceAll("_", " ")
          : review.selected.validationStatus.replaceAll("_", " ");
        return {
          title: workflow.displayName,
          status: `${review.selected.timeLabel} · ${reviewStatus}`,
          url,
        };
      },
      onClose: async (context) => {
        const entry = servers.get(context.instanceId);
        if (!entry) return;
        await Promise.allSettled(
          [...coordinationSessions.keys()]
            .filter((key) => key.startsWith(`${workflowId}:`))
            .map((key) => releaseCoordinationLease(
              key.slice(workflowId.length + 1),
            )),
        );
        servers.delete(context.instanceId);
        await new Promise((resolvePromise) => {
          entry.server.close(() => resolvePromise());
        });
      },
    }),
  ],
});

session.on("tool.execution_start", (event) => {
  if (!reviewRequestPending) return;
  const toolName = String(event.data?.toolName || "");
  const runningTests = toolName.includes("powershell");
  setActivity(
    "working",
    runningTests ? "Updating or verifying the rules engine" : "Copilot is working",
    runningTests
      ? "Cached inference and regression commands may be running. Stay on this event."
      : "The selected event and your place in the review are preserved.",
  );
});

session.on("session.error", (event) => {
  if (!reviewRequestPending) return;
  reviewRequestPending = false;
  setActivity(
    "error",
    "Copilot needs attention",
    String(event.data?.message || "The current operation did not complete."),
  );
});
