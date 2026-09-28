export function buildPublicationPlan({
  drafts,
  decisions,
  engineEvents,
  engineEventReviews,
  current,
  snapshotMatches,
  verificationIsCurrent,
  regressionFresh,
  analyticsTypes: analyticsTypeList = ["completed_pass", "turnover"],
  shotsOnTarget = null,
}) {
  const analyticsTypes = new Set(analyticsTypeList);
  const analyticsEngineEvents = engineEvents.filter((event) =>
    analyticsTypes.has(event.type)
  );
  const usedEngineIndexes = new Set();
  const referenceEvents = [];
  const blockers = [];
  if (shotsOnTarget && shotsOnTarget.analysis_status !== "complete") {
    blockers.push(
      `Shots-on-target analysis is ${shotsOnTarget.analysis_status}; complete `
      + "SOT evidence coverage is required before publishing SOT statistics.",
    );
  }
  const reviewComplete = drafts.every((_, index) =>
    ["accepted", "rejected"].includes(decisions[String(index)]?.status)
  );
  if (!reviewComplete) {
    blockers.push("Every proposal must be accepted or rejected.");
  }
  if (!snapshotMatches) {
    blockers.push(
      "The current engine code and cached output must match a reviewed snapshot.",
    );
  }
  drafts.forEach((draft, index) => {
    const decision = decisions[String(index)];
    if (decision?.status !== "accepted") return;
    if (!verificationIsCurrent(decision.engineVerification, current)) {
      blockers.push(`Accepted C${index + 1} does not have a fresh engine receipt.`);
    }
    if (decision.engineVerification?.status !== "already_agrees") {
      blockers.push(`Accepted C${index + 1} does not agree with current engine output.`);
      return;
    }
    if (!analyticsTypes.has(draft.type)) return;
    const match = analyticsEngineEvents
      .map((event, engineIndex) => ({ event, engineIndex }))
      .filter(({ event, engineIndex }) =>
        !usedEngineIndexes.has(engineIndex)
        && event.type === draft.type
        && event.team === draft.team
        && Math.abs(event.seconds - draft.seconds) <= 1
      )
      .sort((left, right) =>
        Math.abs(left.event.seconds - draft.seconds)
        - Math.abs(right.event.seconds - draft.seconds)
      )[0];
    if (!match) {
      blockers.push(`Accepted C${index + 1} has no unique matching engine event.`);
      return;
    }
    usedEngineIndexes.add(match.engineIndex);
    referenceEvents.push({
      clip_seconds: Number(draft.seconds),
      team: draft.team,
      event_type: draft.type,
    });
  });
  drafts.forEach((draft, index) => {
    if (
      decisions[String(index)]?.status !== "rejected"
      || !analyticsTypes.has(draft.type)
    ) {
      return;
    }
    const rejectedMatch = analyticsEngineEvents.findIndex((event) =>
      event.type === draft.type
      && event.team === draft.team
      && Math.abs(event.seconds - draft.seconds) <= 1
    );
    if (rejectedMatch >= 0) {
      usedEngineIndexes.add(rejectedMatch);
      blockers.push(
        `Rejected C${index + 1} is still emitted by current engine output.`,
      );
    }
  });
  analyticsEngineEvents.forEach((event, engineIndex) => {
    if (usedEngineIndexes.has(engineIndex)) return;
    const review = engineEventReviews[event.reviewKey];
    const fresh = Boolean(
      review?.status === "confirmed"
      && review.engineContentHash === current.fingerprint.contentHash
      && review.outputHash === current.outputHash
    );
    if (!fresh) {
      blockers.push(
        `Unmatched E${engineIndex + 1} must be independently confirmed.`,
      );
      return;
    }
    referenceEvents.push({
      clip_seconds: Number(event.seconds),
      team: event.team,
      event_type: event.type,
    });
  });
  referenceEvents.sort((left, right) =>
    left.clip_seconds - right.clip_seconds
  );
  if (referenceEvents.length !== analyticsEngineEvents.length) {
    blockers.push(
      "The publishable reference and current engine output counts differ.",
    );
  }
  if (!regressionFresh) {
    blockers.push("Protected regressions need a fresh passing receipt.");
  }
  return {
    reviewComplete,
    regressionFresh,
    referenceEvents,
    engineEventCount: analyticsEngineEvents.length,
    blockers: [...new Set(blockers)],
    ready: blockers.length === 0,
  };
}
