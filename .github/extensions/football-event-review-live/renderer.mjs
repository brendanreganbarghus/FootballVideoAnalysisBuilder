import { renderHtml as renderSharedHtml } from "../football-event-review/shared/review-renderer.mjs";
import { liveWorkflow } from "../football-event-review/shared/workflow-adapters.mjs";

export function renderHtml(options = {}) {
  return renderSharedHtml({...options, adapter: liveWorkflow});
}
