export function storedSnapshots(state) {
  return [
    ["after", state.engineAfter],
    ["before", state.engineBefore],
  ].filter(([, snapshot]) => Boolean(snapshot));
}

export function matchingStoredSnapshot(current, state) {
  return storedSnapshots(state).find(([, snapshot]) =>
    snapshot.fingerprint?.contentHash === current.fingerprint.contentHash
    && snapshot.outputHash === current.outputHash
  ) || null;
}

export function referenceStoredSnapshot(current, state) {
  const snapshots = storedSnapshots(state);
  return snapshots.find(([, snapshot]) =>
    snapshot.fingerprint?.contentHash === current.fingerprint.contentHash
  ) || snapshots.find(([, snapshot]) =>
    snapshot.outputHash === current.outputHash
  ) || snapshots[0] || [null, null];
}

export function engineVerificationReceipt(
  current,
  snapshot,
  snapshotKind,
  fresh = Boolean(snapshot),
  staleReasons = [],
) {
  return {
    checkedAt: current.capturedAt,
    fresh,
    staleReasons,
    currentEngineContentHash: current.fingerprint.contentHash,
    currentGitRevision: current.fingerprint.gitRevision,
    currentOutputHash: current.outputHash,
    snapshotKind: snapshotKind || null,
    snapshotCapturedAt: snapshot?.capturedAt || null,
    snapshotEngineContentHash:
      snapshot?.fingerprint?.contentHash || null,
    snapshotOutputHash: snapshot?.outputHash || null,
  };
}

export function isVerificationCurrent(verification, current) {
  return Boolean(
    verification?.fresh
    && verification.currentEngineContentHash
      === current.fingerprint.contentHash
    && verification.currentOutputHash === current.outputHash
  );
}

export function isRegressionCurrent(regression, current) {
  return Boolean(
    regression
    && regression.fingerprint?.contentHash
      === current.fingerprint.contentHash
    && regression.outputHash === current.outputHash
  );
}

export function hasReviewHistory(state) {
  return Object.keys(state.decisions || {}).length > 0;
}

export function requiresEngineImplementationChange(
  beforeStatus,
  beforeContentHash,
  afterContentHash,
  verification,
) {
  if (
    beforeStatus === "already_agrees"
    || afterContentHash !== beforeContentHash
  ) {
    return false;
  }
  return !(
    verification?.fresh === false
    && verification.staleReasons?.includes("cached_output")
  );
}
