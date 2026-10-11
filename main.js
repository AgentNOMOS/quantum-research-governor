// QRG-R2 entry point (Qollab JS/Qiskit project).
// One Qollab Run = one evaluation of this module = at most ONE bridge call =
// at most ONE backend job. No UI control can trigger another call.
import * as qrgApi from "qrg.js_api";
import { createRunGuard, parseEnvelope, crossCheck } from "./ui/logic.js";
import { bindNavigation, renderRunning, renderEnvelope, renderFatal } from "./ui/render.js";

const guard = createRunGuard(); // module-scoped: a fresh Run gets a fresh module

async function start() {
  bindNavigation();
  if (!guard.claim()) return;
  renderRunning();
  let raw;
  try {
    // `backend` is injected by Qollab. Pass null if absent: Python then refuses with
    // ERROR_NO_INJECTED_BACKEND instead of creating any fallback simulator.
    const injected = typeof backend !== "undefined" ? backend : null; // eslint-disable-line no-undef
    raw = await qrgApi.run_experiment.callPromising(injected);
  } catch (err) {
    renderFatal("BRIDGE_ERROR", `The JS→Python bridge call failed: ${err && err.message ? err.message : err}`);
    return;
  }
  const parsed = parseEnvelope(raw);
  if (!parsed.ok) {
    renderFatal("BRIDGE_PAYLOAD_INVALID", parsed.error);
    return;
  }
  renderEnvelope(parsed.env, crossCheck(parsed.env));
}

start().catch((err) => renderFatal("UI_ERROR", String(err && err.stack ? err.stack : err)));
