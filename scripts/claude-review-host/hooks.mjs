// Module resolution hook: the review extension imports the Copilot SDK
// extension API; resolve it to the Claude-backed shim instead.
const shimUrl = new URL("./copilot-shim.mjs", import.meta.url).href;

export async function resolve(specifier, context, next) {
  if (specifier === "@github/copilot-sdk/extension") {
    return {url: shimUrl, shortCircuit: true};
  }
  return next(specifier, context);
}
