const EVENT_TYPES = new Set(["completed_pass", "turnover"]);
const TEAMS = new Set(["black", "red"]);

export function recordAssistedReview(
  state,
  {engine, review, snapshot, submitted, durationSeconds},
) {
  if (
    !engine
    || review?.status !== "confirmed"
    || review.reviewSource !== "professional_reviewer"
    || review.engineContentHash !== snapshot.fingerprint.contentHash
    || review.outputHash !== snapshot.outputHash
  ) {
    throw new Error("The selected E# needs a current human confirmation");
  }
  if (
    submitted.engineContentHash !== snapshot.fingerprint.contentHash
    || submitted.outputHash !== snapshot.outputHash
    || submitted.engineTeam !== engine.team
    || submitted.engineType !== engine.type
    || submitted.engineSeconds !== engine.seconds
    || submitted.engineReleaseSeconds !== engine.releaseSeconds
  ) {
    throw new Error("The E# changed while the assisted review was open");
  }
  const timestampMs = Number(submitted.timestampMs);
  if (
    !Number.isInteger(timestampMs)
    || timestampMs < 0
    || timestampMs > Math.round(durationSeconds * 1000)
    || !TEAMS.has(submitted.team)
    || !EVENT_TYPES.has(submitted.type)
  ) {
    throw new Error("Enter a valid observed time, team, and event type");
  }
  state.assistedReviewEntries ||= [];
  if (state.assistedReviewEntries.some(entry =>
    entry.engineContentHash === snapshot.fingerprint.contentHash
    && entry.outputHash === snapshot.outputHash
    && entry.engine.team === engine.team
    && entry.engine.type === engine.type
    && entry.engine.seconds === engine.seconds
    && entry.engine.releaseSeconds === engine.releaseSeconds
  )) {
    throw new Error("This exact E# already has an assisted review entry");
  }
  const entry = {
    id: `A${state.assistedReviewEntries.length + 1}`,
    source: "engine_assisted",
    engine: {
      team: engine.team,
      type: engine.type,
      seconds: engine.seconds,
      releaseSeconds: engine.releaseSeconds,
    },
    observed: {
      seconds: timestampMs / 1000,
      team: submitted.team,
      type: submitted.type,
    },
    engineContentHash: snapshot.fingerprint.contentHash,
    outputHash: snapshot.outputHash,
    confirmedAt: new Date().toISOString(),
  };
  state.assistedReviewEntries.push(entry);
  return entry;
}

export function publicAssistedReviews(state, snapshot, engineEvents) {
  return (state.assistedReviewEntries || []).map(entry => {
    const engine = engineEvents.find(event =>
      event.team === entry.engine.team
      && event.type === entry.engine.type
      && event.seconds === entry.engine.seconds
      && event.releaseSeconds === entry.engine.releaseSeconds
    );
    return {
      ...entry,
      fresh: Boolean(
        engine?.review?.status === "confirmed"
        && engine.review.reviewSource === "professional_reviewer"
        && engine.review.fresh
        && entry.engineContentHash === snapshot.fingerprint.contentHash
        && entry.outputHash === snapshot.outputHash
      ),
    };
  });
}
