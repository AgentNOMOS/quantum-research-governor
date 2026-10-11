// DEV-ONLY mock of Qollab's Python bridge (never packaged). Serves fixtures that were
// produced by the REAL Python API (dev/make_fixtures.py) and counts every call.
const cfg = globalThis.__QRG_MOCK__ || { mode: "fixture", fixture: "envelope_A.json" };
globalThis.__QRG_MOCK_CALLS__ = [];

export const run_experiment = {
  async callPromising(backendArg) {
    globalThis.__QRG_MOCK_CALLS__.push({ backendPassed: backendArg !== null && backendArg !== undefined, t: Date.now() });
    await new Promise((r) => setTimeout(r, cfg.delay || 50));
    if (cfg.mode === "reject") throw new Error("PythonError: simulated bridge failure");
    if (cfg.mode === "malformed") return "{not json";
    if (cfg.mode === "null") return null;
    if (cfg.mode === "object") return { status: "COMPLETED" };
    const res = await fetch(new URL(`../fixtures/${cfg.fixture}`, import.meta.url));
    return await res.text(); // exact bytes, like the Python str crossing the bridge
  },
};
