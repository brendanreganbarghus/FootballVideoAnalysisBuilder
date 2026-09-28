import { renderHtml as renderSharedHtml } from "./shared/review-renderer.mjs";
import { reviewWorkflow } from "./shared/workflow-adapters.mjs";

export function renderHtml(options = {}) {
  return renderSharedHtml({...options, adapter: reviewWorkflow});
}
