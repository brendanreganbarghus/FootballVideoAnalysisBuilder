import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import {
  mkdir,
  readFile,
  rename,
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
} from "./engine-freshness.mjs";
import { buildPublicationPlan } from "./publication-gate.mjs";
import { renderHtml } from "./renderer.mjs";

const extensionRoot = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(extensionRoot, "..", "..", "..");
const alfheimRoot = join(projectRoot, "benchmarks", "alfheim");
const generatedRoot = join(alfheimRoot, "generated");
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
const defaultSegment = "segment-0300-020";
const localServer = "http://127.0.0.1:8080";
const minimumReviewDurationSeconds = 30;
const maximumReviewDurationSeconds = 60;
const engineFiles = [
  "src/football_poc/match_state.py",
  "src/football_poc/player_tracking.py",
  "src/football_poc/possession.py",
  "scripts/process-alfheim-segment.py",
];
const servers = new Map();
const eventStreams = new Set();
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
let session;
let reviewRequestPending = false;

function segmentRoot(segment) {
  return segment === "alfheim-window-555"
    ? join(alfheimRoot, "window-555")
    : join(generatedRoot, segment);
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
    `${localServer}/api/alfheim/segments`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    throw new Error(`Prepared-segment API returned HTTP ${response.status}`);
  }
  const payload = await response.json();
  return payload.segments.map((segment) => {
    const start = Number(segment.source_start_seconds);
    const duration = Number(segment.duration_seconds);
    const validationStatus = segment.validated
      ? "passed"
      : segment.cache_key === defaultSegment
        ? "in_review"
        : segment.state === "ready" ? "ai_ready" : segment.state;
    return {
      key: segment.cache_key,
      startSeconds: start,
      durationSeconds: duration,
      timeLabel: `${formatClock(start)}–${formatClock(start + duration)}`,
      state: segment.state,
      validationStatus,
      validated: Boolean(segment.validated),
      protected: Boolean(segment.protected),
      videoUrl: `${localServer}${segment.video_url}`,
      labelsAvailable: Boolean(segment.labels_url),
    };
  });
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
  })).filter((event) => Number.isFinite(event.seconds));
}

async function loadDrafts(segment, segmentInfo) {
  if (segment === defaultSegment) {
    return test3Drafts.map((draft) => ({
      ...draft,
      source: "copilot_review",
    }));
  }
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
  if (segmentInfo.state !== "ready") return [];
  const predictions = await loadEngineEvents(segment);
  return predictions.map((event) => {
    return {
      seconds: event.seconds,
      team: event.team,
      type: event.type,
      title: eventTitle({ ...event, event_type: event.type }),
      evidence: [
        event.details || "The rules engine produced this event candidate.",
        event.confidence !== null
          ? `Engine confidence: ${(event.confidence * 100).toFixed(1)}%.`
          : "",
      ].filter(Boolean).join(" "),
      rule: analyticsRule(event.type),
      source: "engine_output",
    };
  });
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

async function loadActionFocuses(segment, drafts) {
  try {
    const calibration = await readJson(
      join(
        projectRoot,
        "benchmarks",
        "alfheim",
        "window-555",
        "pitch-calibration.json",
      ),
      null,
    );
    if (!calibration) return drafts.map(() => null);
    const csv = await readFile(
      join(segmentRoot(segment), "ball-ground-truth.csv"),
      "utf8",
    );
    const points = csv.trim().split(/\r?\n/).slice(1).map((line) => {
      const columns = line.split(",");
      return {
        seconds: Number(columns[1]),
        x: Number(columns[4]),
        y: Number(columns[5]),
      };
    }).filter((point) =>
      Number.isFinite(point.seconds)
      && Number.isFinite(point.x)
      && Number.isFinite(point.y)
    );
    return drafts.map((draft) => {
      const point = points.reduce((closest, candidate) =>
        Math.abs(candidate.seconds - draft.seconds)
          < Math.abs(closest.seconds - draft.seconds)
          ? candidate
          : closest
      );
      return {
        sourceSeconds: point.seconds,
        xPercent: Math.min(
          100,
          Math.max(0, point.x / Number(calibration.image_width) * 100),
        ),
        yPercent: Math.min(
          100,
          Math.max(0, point.y / Number(calibration.image_height) * 100),
        ),
      };
    });
  } catch {
    return drafts.map(() => null);
  }
}

async function loadBallTrack(segment) {
  const calibration = await readJson(
    join(
      projectRoot,
      "benchmarks",
      "alfheim",
      "window-555",
      "pitch-calibration.json",
    ),
    null,
  );
  if (!calibration) {
    throw new Error("Pitch calibration is unavailable");
  }
  const csv = await readFile(
    join(segmentRoot(segment), "ball-ground-truth.csv"),
    "utf8",
  );
  const points = csv.trim().split(/\r?\n/).slice(1).map((line) => {
    const columns = line.split(",");
    return [
      Number(columns[0]),
      Number(columns[1]),
      Number(columns[4]),
      Number(columns[5]),
    ];
  }).filter((point) => point.every(Number.isFinite));
  return {
    width: Number(calibration.image_width),
    height: Number(calibration.image_height),
    points,
  };
}

function legacyArtifactDirectory() {
  if (session.workspacePath) {
    return join(session.workspacePath, "files", "football-event-review");
  }
  return join(
    process.env.COPILOT_HOME || join(homedir(), ".copilot"),
    "extensions",
    "football-event-review",
    "artifacts",
    session.sessionId,
  );
}

function artifactDirectory() {
  return sharedArtifactRoot
    ? join(sharedArtifactRoot, "30-shared-baselines", "event-review-state")
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

async function updateSharedChecksum(path, content) {
  if (!sharedArtifactRoot) return;
  const manifestPath = join(
    sharedArtifactRoot,
    "00-governance",
    "checksums.sha256",
  );
  const relativePath = sharedRelativePath(path);
  const checksum = createHash("sha256").update(content).digest("hex")
    .toUpperCase();
  const existing = await readFile(manifestPath, "utf8");
  const lines = existing.split(/\r?\n/).filter((line) =>
    !line.endsWith(`*${relativePath}`)
  );
  lines.push(`${checksum} *${relativePath}`);
  const updated = `${lines.filter(Boolean).join("\n")}\n`;
  const temporaryPath = `${manifestPath}.${process.pid}.tmp`;
  await writeFile(temporaryPath, updated, "utf8");
  await rename(temporaryPath, manifestPath);
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
  const temporaryPath = `${path}.${process.pid}.tmp`;
  await writeFile(temporaryPath, content, "utf8");
  await rename(temporaryPath, path);
}

async function writeJsonAtomically(path, payload) {
  await writeTextAtomically(path, `${JSON.stringify(payload, null, 2)}\n`);
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

async function captureEngineSnapshot(segment) {
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
  const fingerprint = await engineFingerprint();
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

async function loadState(segment, segmentInfo, drafts) {
  const path = statePath(segment);
  let state = await readReviewState(path, null, Boolean(sharedArtifactRoot));
  let changed = false;
  if (!state && sharedArtifactRoot) {
    state = await readReviewState(legacyStatePath(segment), null);
    changed = Boolean(state);
  }
  if (state) {
    state.conversation ||= [];
    state.proposalOverrides ||= {};
    state.additionalProposals ||= [];
    state.copilotAcceptanceAuthorizations ||= {};
    state.engineEventReviews ||= {};
    state.engineEventReviewAuthorizations ||= {};
    state.pendingMissingCandidate ||= null;
    state.pendingClipRequest ||= null;
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
    if (changed) await saveState(segment, state);
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
    segment,
    decisions,
    engineBefore: await captureEngineSnapshot(segment),
    engineAfter: null,
    regression: null,
    conversation: [],
    proposalOverrides: {},
    additionalProposals: [],
    copilotAcceptanceAuthorizations: {},
    engineEventReviews: {},
    engineEventReviewAuthorizations: {},
    pendingMissingCandidate: null,
    pendingClipRequest: null,
    publicationAuthorization: null,
    publishedReference: null,
  };
  await saveState(segment, initial);
  return initial;
}

async function saveState(segment, state) {
  await mkdir(artifactDirectory(), { recursive: true });
  state.schemaVersion = 1;
  state.updatedAt = new Date().toISOString();
  const path = statePath(segment);
  const content = `${JSON.stringify(state, null, 2)}\n`;
  await writeFile(path, content, "utf8");
  await updateSharedChecksum(path, content);
  broadcast("state");
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
    };
  }).filter((event) => Number.isFinite(event.seconds));
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
  const current = await captureEngineSnapshot(segment);
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
  };
  review.state.engineEventReviews[key] = record;
  delete review.state.engineEventReviewAuthorizations[key];
  await saveState(segment, review.state);
  return { segment, index, event, review: record };
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
  const exact = candidates
    .filter((candidate) =>
      candidate.type === draft.type
      && candidate.event.team === draft.team
      && Math.abs(candidate.seconds - draft.seconds) <= 1
    )
    .sort((left, right) =>
      Math.abs(left.seconds - draft.seconds)
      - Math.abs(right.seconds - draft.seconds)
    )[0];
  if (exact) {
    return {
      status: "already_agrees",
      label: "Engine already agrees",
      detail: `Matched at ${exact.seconds.toFixed(3)}s within the 1.0s tolerance.`,
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
      `/api/alfheim/status?cache_key=${encodeURIComponent(selected.key)}`,
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
      await saveState(selected.key, state);
    }
  }
  const allDrafts = [...drafts, ...state.additionalProposals];
  const effectiveDrafts = allDrafts.map((draft, index) => {
    const override = state.proposalOverrides[String(index)];
    return override
      ? {
          ...draft,
          ...override,
          source: "adjusted_proposal",
        }
      : draft;
  });
  const actionFocuses = await loadActionFocuses(
    selected.key,
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
    state,
    actionFocuses,
  };
}

async function publicState(requestedSegment = defaultSegment) {
  const context = await reviewContext(requestedSegment);
  const { segments, selected, drafts, state, actionFocuses } = context;
  if (state.publishedReference && !selected.validated) {
    selected.validationStatus = "published_stale";
  }
  const currentEngine = await captureEngineSnapshot(requestedSegment);
  const regressionFresh = isRegressionCurrent(
    state.regression,
    currentEngine,
  );
  const engineEvents = snapshotEvents(
    state.engineAfter || state.engineBefore,
  ).map((event) => {
    const review = state.engineEventReviews?.[engineEventReviewKey(event)];
    return {
      ...event,
      review: review
        ? {
            ...review,
            fresh:
              review.engineContentHash
                === currentEngine.fingerprint.contentHash
              && review.outputHash === currentEngine.outputHash,
          }
        : null,
    };
  });
  const publication = publicationPlan(drafts, state, currentEngine);
  return {
    segment: selected,
    segments,
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
    engineEvents,
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
    activeConversation: reviewRequestPending ? lastConversationContext : null,
    activity,
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

async function readBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > 16_384) {
      throw new Error("Request body is too large");
    }
    chunks.push(chunk);
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
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

function messagePrompt(segment, draft, index, text, allowChanges = false) {
  const videoArtifact = segment.key === "alfheim-window-555"
    ? "benchmarks\\alfheim\\window-555\\alfheim-window-playable.mp4"
    : (
        `benchmarks\\alfheim\\generated\\${segment.key}`
        + "\\alfheim-window-playable.mp4"
      );
  return [
    "[Football Event Review Canvas]",
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
          + "football-event-review update_review_proposal canvas action. Do "
          + "not say the screen was updated unless that action succeeds."
        )
      : (
          "This is Plan mode: answer and explain only. Do not accept, reject, "
          + "edit, or synchronize the event or engine. If a change is needed, "
          + "tell the user to use Request Adjustment or Verify, Accept & Sync "
          + "Engine in this event's Copilot panel."
        ),
    "Before ending, always use the football-event-review "
      + "publish_review_response canvas action to place your concise final "
      + `answer in this Canvas for segment ${segment.key}, event index ${index}.`,
    "Minimize latency and AI usage: make one targeted adjudication pass. Start "
      + "with the supplied event context and cached artifacts. If visual "
      + "inspection is necessary, inspect only a small window around the "
      + "specified frame (normally ±2 seconds). Do not scan the full video, "
      + "open unrelated segments, rerun detection/tracking, or rerun the "
      + "rules engine. Keep the response concise. Engine changes and "
      + "regressions occur only after the user accepts a changed requirement.",
  ].join("\n");
}

function clipConversationPrompt(
  segment,
  seconds,
  text,
  drafts,
  selectedIndex,
  mode,
  scope,
) {
  const videoArtifact = segment.key === "alfheim-window-555"
    ? "benchmarks\\alfheim\\window-555\\alfheim-window-playable.mp4"
    : (
        `benchmarks\\alfheim\\generated\\${segment.key}`
        + "\\alfheim-window-playable.mp4"
      );
  return [
    "[Football Event Review Canvas - clip conversation]",
    `Review only segment ${segment.timeLabel} (${segment.key}).`,
    `Video artifact: ${videoArtifact}.`,
    `Source window: ${segment.startSeconds.toFixed(3)}s for `
      + `${segment.durationSeconds.toFixed(3)}s.`,
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
      ? "This is an Autopilot inspection, but it authorizes only analysis and "
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
      + " Do not scan another segment or rerun detection, tracking, or the "
      + "rules engine.",
    "If the user is identifying a genuinely missing event, independently "
      + "determine its team and event type and call football-event-review "
      + "recommend_missing_event. If an existing event needs correction, "
      + "identify that event and direct the user to its Request Adjustment "
      + "flow. Otherwise answer normally. Do not add or accept an event, edit "
      + "a proposal, or change the algorithm in this Plan step.",
    "Before ending, always use the football-event-review "
      + "publish_review_response canvas action to place your concise final "
      + `answer in this Canvas for segment ${segment.key}.`,
  ].join("\n");
}

function confirmMissingEventPrompt(segment, candidate) {
  return [
    "[Football Event Review Canvas - approved missing-event handover]",
    `Work only in segment ${segment.timeLabel} (${segment.key}).`,
    `Candidate: ${candidate.team} ${candidate.eventType} at `
      + `${candidate.seconds.toFixed(3)}s.`,
    `Plan evidence: ${candidate.evidence}`,
    `Proposed rule: ${candidate.rule}`,
    projectRulesInstruction,
    "The user explicitly approved moving this planned candidate into "
      + "Autopilot. Call football-event-review add_review_proposal using these "
      + "exact team, event type, and seconds. Then call "
      + "publish_review_response with the returned event index. Do not edit "
      + "the rules engine yet; the newly added event must still pass its own "
      + "Verify, Accept & Sync Engine handover.",
  ].join("\n");
}

function publishValidatedReferencePrompt(segment) {
  return [
    "[Football Event Review Canvas - approved final publication]",
    `Publish only prepared segment ${segment.timeLabel} (${segment.key}).`,
    projectRulesInstruction,
    "The user explicitly authorized the final validation gate through the "
      + "Publish Validated Reference button. Do not review another segment.",
    "Run the protected match-state, possession, and blind-minute regression "
      + "tests once with: $env:PYTHONPATH=\"$PWD\\src\"; python -m pytest "
      + "tests\\test_match_state.py tests\\test_possession.py "
      + "tests\\test_alfheim_blind_regressions.py -q",
    "If they pass, call football-event-review refresh_engine_snapshot for "
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
    "Before ending, call football-event-review publish_review_response without "
      + "an event index so the result appears in the general clip conversation.",
  ].join("\n");
}

function engineEventReviewPrompt(segment, event, index) {
  const videoArtifact = segment.key === "alfheim-window-555"
    ? "benchmarks\\alfheim\\window-555\\alfheim-window-playable.mp4"
    : (
        `benchmarks\\alfheim\\generated\\${segment.key}`
        + "\\alfheim-window-playable.mp4"
      );
  return [
    "[Football Event Review Canvas - engine-only event verification]",
    `Review only segment ${segment.timeLabel} (${segment.key}).`,
    `Video artifact: ${videoArtifact}.`,
    `Selected engine event: E${index + 1}, ${event.title} at `
      + `${event.seconds.toFixed(3)}s.`,
    `Engine detail: ${event.details}`,
    projectRulesInstruction,
    "The user authorized verification of only this rules-engine event. "
      + "Independently inspect the targeted evidence, normally within ±2 "
      + "seconds. Do not treat the engine event as the answer.",
    "If the evidence supports the exact team, canonical type, and completion "
      + "time, call football-event-review confirm_engine_event_reviewed with "
      + "this segment, engine index, and a concise evidence reason. Otherwise "
      + "do not confirm it.",
    "Do not create or accept a Copilot proposal, edit the engine, or rerun "
      + "detection, tracking, or event building.",
    "Before ending, call football-event-review publish_review_response without "
      + "an event index so the result appears in the general clip conversation.",
  ].join("\n");
}

function proposalFingerprint(draft) {
  return createHash("sha256").update(JSON.stringify({
    seconds: draft.seconds,
    team: draft.team,
    type: draft.type,
    title: draft.title,
    evidence: draft.evidence,
    rule: draft.rule,
  })).digest("hex");
}

function copilotAcceptancePrompt(segment, draft, index) {
  return [
    messagePrompt(
      segment,
      draft,
      index,
      "Verify the current proposal and accept it only if the evidence supports it.",
      true,
    ),
    "The user explicitly granted permission, through the Canvas handover "
      + "button, for Copilot to accept only this selected proposal.",
    "If the proposal is correct, call football-event-review "
      + "accept_review_proposal with the segment, event index, and concise "
      + "verification reason. Read the returned engineComparison. If it is "
      + "already_agrees, the current code and cached output hashes are proven "
      + "fresh, so do not edit or rerun the engine. If it is stale, do not edit "
      + "the engine merely because of staleness; rerun only the cached "
      + "event-building stage, refresh the snapshot, and run the relevant "
      + "protected regressions. If it is missing or "
      + "conflicting, implement a general rules-engine correction rather than "
      + "a timestamp-, frame-, clip-, or segment-specific exception. Inspect "
      + "the final diff and reject any condition keyed to this segment ID or "
      + "its exact seconds/frame. Rerun only the cached event-building "
      + "stage for this segment (never detection or tracking), run the relevant "
      + "protected regression tests, then call refresh_engine_snapshot with "
      + "this event index. Do not claim success unless its returned "
      + "engineComparison is already_agrees. Only then call "
      + "record_regression_result with passed=true and this event index. If "
      + "the proposal is not correct, do not "
      + "accept it; update the proposal only when the evidence supports a "
      + "correction.",
  ].join("\n");
}

function copilotBulkAcceptancePrompt(segment, drafts, indexes) {
  return [
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
      + "supported proposal, call football-event-review "
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
    "Before ending, call football-event-review publish_review_response "
      + `without eventIndex so the batch summary appears only in the general `
      + `clip conversation for ${segment.key}.`,
  ].join("\n");
}

function requestedSegment(url, body = {}) {
  return String(
    body.segment || url.searchParams.get("segment") || defaultSegment,
  );
}

async function localJson(path, options = {}) {
  const response = await fetch(`${localServer}${path}`, options);
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || `Local Match Lab HTTP ${response.status}`);
  }
  return payload;
}

async function handleRequest(request, response) {
  const url = new URL(request.url, "http://127.0.0.1");
  if (request.method === "GET" && url.pathname === "/") {
    const html = renderHtml({
      theme: url.searchParams.get("theme") === "innovation"
        ? "innovation"
        : "default",
    });
    response.writeHead(200, {
      "Cache-Control": "no-store",
      "Content-Type": "text/html; charset=utf-8",
      "Content-Length": Buffer.byteLength(html),
    });
    response.end(html);
    return;
  }
  if (request.method === "GET" && url.pathname === "/api/state") {
    sendJson(
      response,
      200,
      await publicState(requestedSegment(url)),
    );
    return;
  }
  if (request.method === "GET" && url.pathname === "/api/ball-track") {
    const segment = requestedSegment(url);
    const segments = await loadPreparedSegments();
    if (!segments.some((candidate) => candidate.key === segment)) {
      sendJson(response, 404, { error: "Prepared segment not found" });
      return;
    }
    sendJson(response, 200, await loadBallTrack(segment));
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
    if (!Number.isFinite(startSeconds) || startSeconds < 0) {
      sendJson(response, 400, {
        error: "Start time must be a non-negative number",
      });
      return;
    }
    if (
      !Number.isFinite(durationSeconds)
      || durationSeconds < minimumReviewDurationSeconds
      || durationSeconds > maximumReviewDurationSeconds
    ) {
      sendJson(response, 400, {
        error: "Review duration must be between 30 and 60 seconds",
      });
      return;
    }
    setActivity(
      "working",
      "Preparing review segment",
      "Video and supplied ball labels are being prepared locally. AI is not running.",
    );
    const prepared = await localJson("/api/alfheim/segment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        start_seconds: startSeconds,
        duration_seconds: durationSeconds,
      }),
    });
    setActivity(
      "ready",
      "Segment prepared",
      "Review the video, then start AI explicitly when you are ready.",
    );
    sendJson(response, 200, await publicState(prepared.cache_key));
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/analyze") {
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    if (!/^segment-\d{4}-\d{3}$/.test(segment)) {
      sendJson(response, 400, {
        error: "Select a generated prepared segment before starting AI",
      });
      return;
    }
    const review = await reviewContext(segment);
    const eventsOnly = review.selected.state === "ready";
    setActivity(
      "working",
      eventsOnly ? "Rerunning event logic" : "Running segment AI",
      eventsOnly
        ? "Cached tracking is retained while event logic is rebuilt."
        : "Events remain hidden until the local AI pipeline completes.",
    );
    const result = await localJson("/api/alfheim/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cache_key: segment,
        events_only: eventsOnly,
      }),
    });
    sendJson(response, 202, {
      ...result,
      segment,
      eventsOnly,
    });
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
    const current = await captureEngineSnapshot(segment);
    const events = snapshotEvents(current);
    const index = Number(body.index);
    const event = events[index];
    if (!Number.isInteger(index) || !event) {
      sendJson(response, 400, {
        error: "Select a rules-engine event first",
      });
      return;
    }
    const key = engineEventReviewKey(event);
    review.state.engineEventReviewAuthorizations[key] = {
      engineContentHash: current.fingerprint.contentHash,
      outputHash: current.outputHash,
      grantedAt: new Date().toISOString(),
    };
    review.state.conversation.push({
      role: "user",
      content: (
        `Permission granted: independently verify E${index + 1} at `
        + `${event.seconds.toFixed(3)}s and mark it reviewed only if supported.`
      ),
      eventIndex: null,
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
        prompt: engineEventReviewPrompt(review.selected, event, index),
        displayPrompt: (
          `Verify E${index + 1} at ${event.seconds.toFixed(3)}s only if correct.`
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
  if (request.method === "POST" && url.pathname === "/api/decision") {
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
    const index = Number(body.index);
    if (!Number.isInteger(index) || !context.drafts[index]) {
      sendJson(response, 400, { error: "Unknown draft event" });
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
    delete state.copilotAcceptanceAuthorizations[String(index)];
    await saveState(segment, state);
    sendJson(response, 200, await publicState(segment));
    return;
  }
  if (request.method === "POST" && url.pathname === "/api/copilot-accept") {
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
    if (reviewRequestPending) {
      sendJson(response, 409, {
        error: "Copilot is already handling a review request",
      });
      return;
    }
    const body = await readBody(request);
    const segment = requestedSegment(url, body);
    const context = await reviewContext(segment);
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
    };
    context.state.conversation.push({
      role: "user",
      content: `${
        scope === "current_time"
          ? `${seconds.toFixed(3)}s ±2s`
          : "Entire clip"
      } · ${mode} · ${text}`,
      eventIndex: null,
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
    handleRequest(request, response).catch((error) => {
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

session = await joinSession({
  canvases: [
    createCanvas({
      id: "football-event-review",
      displayName: "Football Event Review",
      description: "Prepare and review controlled 30–60 second football segments, message Copilot, then verify engine behavior.",
      inputSchema: {
        type: "object",
        properties: {
          segment: { type: "string" },
          theme: { type: "string", enum: ["default", "innovation"] },
        },
        additionalProperties: false,
      },
      actions: [
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
          name: "publish_review_response",
          description: "Publish the final concise Copilot answer into the floating Canvas conversation.",
          inputSchema: {
            type: "object",
            properties: {
              segment: { type: "string" },
              eventIndex: { type: "integer", minimum: 0 },
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
            if (eventIndex !== null && !review.drafts[eventIndex]) {
              throw new CanvasError(
                "review_event_missing",
                "The selected review event does not exist.",
              );
            }
            const previous = review.state.conversation.at(-1);
            let changed = false;
            if (previous?.role !== "assistant" || previous.content !== content) {
              review.state.conversation.push({
                role: "assistant",
                content,
                eventIndex,
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
            } else if (
              Number.isInteger(lastConversationContext?.engineIndex)
              && Object.keys(
                review.state.engineEventReviewAuthorizations,
              ).length
            ) {
              review.state.engineEventReviewAuthorizations = {};
              changed = true;
            } else if (review.state.pendingClipRequest) {
              review.state.pendingClipRequest = null;
              changed = true;
            }
            if (changed) {
              await saveState(segment, review.state);
            }
            if (lastConversationContext?.segment === segment) {
              reviewRequestPending = false;
            }
            setActivity(
              "ready",
              "Copilot result ready",
              "Open Copilot Chat to read the result and continue this event review.",
            );
            broadcast("conversation");
            return { segment, eventIndex, published: true };
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
            review.state.decisions[String(index)] = {
              status: "accepted",
              note: String(context.input.reason),
              decidedAt: new Date().toISOString(),
              source: "copilot_verified",
              engineVerification,
            };
            delete review.state.copilotAcceptanceAuthorizations[String(index)];
            review.state.conversation.push({
              role: "system",
              content: (
                `Copilot verified and accepted Event ${index + 1}: `
                + context.input.reason
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
              engineComparison,
              engineVerification,
            };
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
            review.state.proposalOverrides[String(index)] = {
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
            delete review.state.decisions[String(index)];
            delete review.state
              .copilotAcceptanceAuthorizations[String(index)];
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
              source: "user_reported",
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
            await saveState(segment, state);
            const index = Number.isInteger(context.input?.index)
              ? Number(context.input.index)
              : null;
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
            await saveState(segment, state);
            return state.regression;
          },
        },
      ],
      open: async (context) => {
        const segment = String(context.input?.segment || defaultSegment);
        const theme = context.input?.theme === "innovation"
          ? "innovation"
          : "default";
        const review = await reviewContext(segment);
        let entry = servers.get(context.instanceId);
        if (!entry) {
          entry = await startServer(context.instanceId);
          servers.set(context.instanceId, entry);
        }
        return {
          title: "Football Event Review",
          status: `${review.selected.timeLabel} · ${
            review.selected.validationStatus.replaceAll("_", " ")
          }`,
          url: `${entry.url}?segment=${encodeURIComponent(segment)}&theme=${
            encodeURIComponent(theme)
          }`,
        };
      },
      onClose: async (context) => {
        const entry = servers.get(context.instanceId);
        if (!entry) return;
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
