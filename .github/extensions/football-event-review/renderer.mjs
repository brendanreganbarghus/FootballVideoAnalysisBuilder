import { renderHtml as renderSharedHtml } from "./shared/review-renderer.mjs";
import { innovationWorkflow } from "./shared/workflow-adapters.mjs";

export function renderHtml(options = {}) {
  return renderSharedHtml({...options, adapter: innovationWorkflow});
}
