import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import * as L from "../../ui/logic.js";

const FIX = new URL("../../dev/fixtures/", import.meta.url);
const load = (n) => readFileSync(new URL(n, FIX), "utf8");

test("sha256 matches node:crypto on vectors", () => {
  for (const s of ["", "abc", "a".repeat(55), "a".repeat(56), "a".repeat(64), "x".repeat(1000), "QRG ✓ unicode"]) {
    assert.equal(L.sha256Hex(s), createHash("sha256").update(s, "utf8").digest("hex"));
  }
});

test("parseEnvelope rejects bad bridge payloads", () => {
  assert.equal(L.parseEnvelope(null).ok, false);
  assert.equal(L.parseEnvelope(42).ok, false);
  assert.equal(L.parseEnvelope("not json").ok, false);
  assert.equal(L.parseEnvelope('{"envelope_schema":"other","status":"X"}').ok, false);
  assert.equal(L.parseEnvelope('{"envelope_schema":"qrg.r2.envelope.v1","status":"COMPLETED"}').ok, false);
  assert.equal(L.parseEnvelope({ toString: () => "{}" }).ok, false);
});

for (const name of ["envelope_A.json", "envelope_B.json"]) {
  test(`fixture ${name}: cross-check reproduces Python numbers`, () => {
    const raw = load(name);
    const p = L.parseEnvelope(raw);
    assert.ok(p.ok, p.error);
    const c = L.crossCheck(p.env);
    assert.ok(c.shaMatches);
    assert.ok(c.totalsMatch && c.countsMatchVerifier);
    assert.equal(c.parityViolations, 0);
    assert.equal(c.malformedKeys, 0);
  });

  test(`fixture ${name}: JS re-serialisation would break the evidence hash`, () => {
    const env = JSON.parse(load(name));
    const reser = JSON.stringify(JSON.parse(env.evidence_text));
    // Python floats such as 1.0 / 0.0 become 1 / 0 in JS: the text changes, so the UI must show it verbatim.
    assert.notEqual(reser, env.evidence_text);
    assert.notEqual(L.sha256Hex(reser), env.evidence_sha256);
    assert.equal(L.sha256Hex(env.evidence_text), env.evidence_sha256);
  });
}

test("cross-check detects tampered evidence text", () => {
  const env = JSON.parse(load("envelope_A.json"));
  const t = env.evidence_text.replace('"0000000":', '"0000001":');
  const c = L.crossCheck({ ...env, evidence_text: t });
  assert.equal(c.shaMatches, false);
  assert.ok(c.parityViolations > 0);
});

test("decodeKey", () => {
  assert.deepEqual(L.decodeKey("1100000"), { coin: "1", sX: "1", sZ: "0", data: "0000", dataParity: 0, parityConsistent: true });
  assert.equal(L.decodeKey("0000001").parityConsistent, false);
  assert.equal(L.decodeKey("000000"), null);
});

test("run guard allows exactly one claim", () => {
  const g = L.createRunGuard();
  assert.equal(g.claim(), true);
  assert.equal(g.claim(), false);
  assert.equal(g.claim(), false);
});

test("groupDemos and interval geometry", () => {
  const env = JSON.parse(load("envelope_B.json"));
  const g = L.groupDemos(env.demonstrations);
  for (const v of ["REJECT", "ESCALATE", "FREEZE"]) assert.ok(g[v].length >= 1, v);
  assert.ok(env.demonstrations.every((d) => d.executed_on_backend === false));
  const st = JSON.parse(env.evidence_text).governor_decision.statistics;
  const geo = L.intervalGeometry(st);
  assert.ok(geo.region[0] < geo.lo && geo.hi < geo.region[1]);
});
