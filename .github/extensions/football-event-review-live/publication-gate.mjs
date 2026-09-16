export function buildPublicationPlan({
  drafts,
  decisions,
  engineEvents,
  engineEventReviews,
  current,
  snapshotMatches,
  verificationIsCurrent,
  regressionFresh,
}) {
  const analyticsTypes = new Set(["completed_pass", "turnover"]);
  const analyticsEngineEvents = engineEvents.filter((event) =>
    analyticsTypes.has(event.type)
  );
  const usedEngineIndexes = new Set();
  const referenceEvents = [];
  const blockers = [];
  const isManualReview = (draft) =>
    ["manual_review", "user_reported"].includes(draft.source);
  const referenceLabel = (draft, index) =>
    `${isManualReview(draft) ? "M" : "C"}${index + 1}`;
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
  const acceptedAnalytics = drafts
    .map((draft, index) => ({
      draft,
      index,
      decision: decisions[String(index)],
    }))
    .filter(({ draft, decision }) =>
      decision?.status === "accepted" && analyticsTypes.has(draft.type)
    );
  acceptedAnalytics.forEach(({ draft, index, decision }) => {
    if (!verificationIsCurrent(decision.engineVerification, current)) {
      blockers.push(
        `Accepted ${referenceLabel(draft, index)} does not have a fresh engine receipt.`,
      );
    }
    if (decision.engineVerification?.status !== "already_agrees") {
      blockers.push(
        `Accepted ${referenceLabel(draft, index)} does not agree with current engine output.`,
      );
    }
  });
  const matchedDrafts = [];
  acceptedAnalytics
    .sort((left, right) =>
      Number(isManualReview(right.draft))
      - Number(isManualReview(left.draft))
    )
    .forEach(({ draft, index, decision }) => {
    if (decision.engineVerification?.status !== "already_agrees") return;
    const sameFrameRequired = (
      isManualReview(draft) || draft.sameFrameEngineReview
    );
    const match = analyticsEngineEvents
      .map((event, engineIndex) => ({ event, engineIndex }))
      .filter(({ event, engineIndex }) =>
        !usedEngineIndexes.has(engineIndex)
        && event.type === draft.type
        && event.team === draft.team
        && (
          sameFrameRequired
            ? Math.round(event.seconds * 25)
              === Math.round(draft.seconds * 25)
            : Math.abs(event.seconds - draft.seconds) <= 1
        )
      )
      .sort((left, right) =>
        Math.abs(left.event.seconds - draft.seconds)
        - Math.abs(right.event.seconds - draft.seconds)
      )[0];
    if (!match) {
      const duplicatesExactManualReference = (
        !isManualReview(draft)
        && matchedDrafts.some(({ draft: matchedDraft }) =>
          isManualReview(matchedDraft)
          && matchedDraft.type === draft.type
          && matchedDraft.team === draft.team
          && Math.abs(matchedDraft.seconds - draft.seconds) <= 1
        )
      );
      if (duplicatesExactManualReference) return;
      blockers.push(
        `Accepted ${referenceLabel(draft, index)} has no unique matching engine event.`,
      );
      return;
    }
    usedEngineIndexes.add(match.engineIndex);
    matchedDrafts.push({ draft, index, engineIndex: match.engineIndex });
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
        `Rejected ${referenceLabel(draft, index)} is still emitted by current engine output.`,
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
