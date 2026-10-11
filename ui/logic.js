// QRG-R2 pure UI logic (no DOM, no bridge). Imported by main.js / render.js and node tests.

export const ENVELOPE_SCHEMA = "qrg.r2.envelope.v1";

// ---------------------------------------------------------------- SHA-256 (FIPS 180-4)
const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]);

export function utf8Bytes(str) {
  return new TextEncoder().encode(str);
}

export function sha256Hex(input) {
  const msg = typeof input === "string" ? utf8Bytes(input) : input;
  const bitLen = msg.length * 8;
  const padded = new Uint8Array(((msg.length + 9 + 63) >> 6) << 6);
  padded.set(msg);
  padded[msg.length] = 0x80;
  const dv = new DataView(padded.buffer);
  dv.setUint32(padded.length - 8, Math.floor(bitLen / 0x100000000));
  dv.setUint32(padded.length - 4, bitLen >>> 0);
  const H = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
                             0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
  const W = new Uint32Array(64);
  const rotr = (x, n) => (x >>> n) | (x << (32 - n));
  for (let off = 0; off < padded.length; off += 64) {
    for (let i = 0; i < 16; i++) W[i] = dv.getUint32(off + 4 * i);
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(W[i - 15], 7) ^ rotr(W[i - 15], 18) ^ (W[i - 15] >>> 3);
      const s1 = rotr(W[i - 2], 17) ^ rotr(W[i - 2], 19) ^ (W[i - 2] >>> 10);
      W[i] = (W[i - 16] + s0 + W[i - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = H;
    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const t1 = (h + S1 + ch + K[i] + W[i]) >>> 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (S0 + maj) >>> 0;
      h = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    H[0] += a; H[1] += b; H[2] += c; H[3] += d; H[4] += e; H[5] += f; H[6] += g; H[7] += h;
  }
  return Array.from(H, (x) => x.toString(16).padStart(8, "0")).join("");
}

// ---------------------------------------------------------------- envelope
export function coerceBridgeResult(raw) {
  if (typeof raw === "string") return raw;
  if (raw && typeof raw.toString === "function" && raw.constructor !== Object) {
    try { const s = String(raw); if (s.startsWith("{")) return s; } catch (_) { /* fall through */ }
  }
  return null;
}

export function parseEnvelope(raw) {
  const text = coerceBridgeResult(raw);
  if (text === null) return { ok: false, error: `bridge returned ${raw === null ? "null" : typeof raw}, expected a JSON string` };
  let env;
  try { env = JSON.parse(text); } catch (e) { return { ok: false, error: `bridge returned invalid JSON: ${e.message}` }; }
  if (!env || typeof env !== "object") return { ok: false, error: "envelope is not an object" };
  if (env.envelope_schema !== ENVELOPE_SCHEMA) return { ok: false, error: `unexpected envelope schema ${env.envelope_schema}` };
  if (typeof env.status !== "string") return { ok: false, error: "envelope has no status" };
  if (env.status === "COMPLETED") {
    for (const f of ["evidence_text", "evidence_sha256", "circuit", "demonstrations", "verifier_report"]) {
      if (!(f in env)) return { ok: false, error: `completed envelope missing ${f}` };
    }
    if (typeof env.evidence_text !== "string") return { ok: false, error: "evidence_text must be a string" };
  }
  return { ok: true, env };
}

// ---------------------------------------------------------------- decoding
// Raw key (Qiskit order c6..c0) = coin sX sZ d3 d2 d1 d0
export function decodeKey(key) {
  if (typeof key !== "string" || !/^[01]{7}$/.test(key)) return null;
  const data = key.slice(3);
  const parity = [...data].reduce((s, c) => s + (c === "1" ? 1 : 0), 0) % 2;
  return { coin: key[0], sX: key[1], sZ: key[2], data, dataParity: parity,
           parityConsistent: Number(key[2]) === parity };
}

// Independent browser-side cross-check of the exported evidence text. Reads the
// text only to recompute; NEVER re-serialises it.
export function crossCheck(env) {
  const out = { shaRecomputed: null, shaMatches: false, total: 0, sX: 0, sZ: 0, anySyndrome: 0,
                parityViolations: 0, malformedKeys: 0, shotsDeclared: null, totalsMatch: false,
                countsMatchVerifier: false };
  if (typeof env.evidence_text !== "string") return out;
  out.shaRecomputed = sha256Hex(env.evidence_text);
  out.shaMatches = out.shaRecomputed === env.evidence_sha256;
  let bundle;
  try { bundle = JSON.parse(env.evidence_text); } catch (_) { return out; }
  const counts = (bundle.raw_record || {}).counts || {};
  for (const [k, v] of Object.entries(counts)) {
    const d = decodeKey(k);
    if (!d || !Number.isInteger(v) || v <= 0) { out.malformedKeys += 1; continue; }
    out.total += v;
    if (d.sX === "1") out.sX += v;
    if (d.sZ === "1") out.sZ += v;
    if (d.sX === "1" || d.sZ === "1") out.anySyndrome += v;
    if (!d.parityConsistent) out.parityViolations += v;
  }
  out.shotsDeclared = (bundle.raw_record || {}).shots ?? null;
  out.totalsMatch = out.total === out.shotsDeclared;
  const syn = ((env.verifier_report || {}).recomputed || {}).syndromes || {};
  out.countsMatchVerifier = syn.sX_k === out.sX && syn.sZ_k === out.sZ && syn.n === out.total;
  return out;
}

// ---------------------------------------------------------------- presentation helpers
export const VERDICTS = {
  ACCEPT: { tone: "accept", plain: "The evidence supports exactly this bounded claim." },
  REJECT: { tone: "reject", plain: "The claim is contradicted, inadmissible, or the request violates policy." },
  ESCALATE: { tone: "escalate", plain: "Inconclusive or needs a human: no conclusion is granted." },
  FREEZE: { tone: "freeze", plain: "Evidence integrity failed: no conclusion is defensible." },
  CLEARED_TO_EXECUTE: { tone: "accept", plain: "Preflight passed: the experiment may run." },
};

export function verdictMeta(v) {
  return VERDICTS[v] || { tone: "neutral", plain: "Unknown verdict." };
}

export const KIND_LABELS = {
  LOCAL_PREFLIGHT: "Local preflight · no quantum job",
  LIVE_EVIDENCE_COUNTERFACTUAL_CLAIM: "Different claim · evaluated on this Run's evidence · no new job",
  OFFLINE_CUSTODY: "Same evidence treated as an offline paste · no new job",
  LOCAL_EVIDENCE_MUTATION: "Local mutation of a COPY of the evidence · original untouched",
};

export function groupDemos(demos) {
  const g = { ACCEPT: [], REJECT: [], ESCALATE: [], FREEZE: [] };
  for (const d of demos || []) {
    const v = d.governor && d.governor.verdict;
    (g[v] || (g[v] = [])).push(d);
  }
  return g;
}

export function fmtRate(x, digits = 4) {
  return typeof x === "number" && Number.isFinite(x) ? x.toFixed(digits) : "–";
}

// Interval picture on [0, axisMax]: returns percentages for CSS/SVG placement.
export function intervalGeometry(stats, axisMax) {
  const max = axisMax || Math.max(0.05, (stats.cp_upper || 0) * 1.6,
                                  (stats.values && (stats.values.hi || stats.values.eps || stats.values.rho)) * 1.3 || 0);
  const pct = (x) => Math.max(0, Math.min(100, (x / max) * 100));
  const v = stats.values || {};
  let region;
  if (stats.direction === "at_most") region = [0, pct(v.eps)];
  else if (stats.direction === "at_least") region = [pct(v.rho), 100];
  else region = [pct(v.lo), pct(v.hi)];
  return { max, lo: pct(stats.cp_lower), hi: pct(stats.cp_upper), point: pct(stats.rate), region };
}

export function createRunGuard() {
  let claimed = false;
  return { claim() { if (claimed) return false; claimed = true; return true; },
           get claimed() { return claimed; } };
}
