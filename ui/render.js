// QRG-R2 DOM rendering. Pure presentation: never calls the Python bridge.
import { verdictMeta, KIND_LABELS, groupDemos, fmtRate, intervalGeometry, decodeKey } from "./logic.js";

const SCENES = ["a", "b", "c", "d", "e", "f"];
const SVGNS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const kid of kids.flat()) {
    if (kid === null || kid === undefined || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

function s(tag, attrs, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, String(v));
  for (const kid of kids.flat()) if (kid) el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return el;
}

const badge = (kind) => kind === "live"
  ? h("span", { class: "badge live" }, "LIVE · this Run")
  : h("span", { class: "badge local" }, kind || "LOCAL · no quantum job");

const chip = (verdict, code) =>
  h("span", { class: `chip ${verdictMeta(verdict).tone}` }, verdict, code ? h("small", {}, ` ${code}`) : null);

const card = (title, ...kids) => h("div", { class: "card" }, title ? h("h3", {}, title) : null, ...kids);

const kv = (rows) => h("dl", { class: "kv" }, rows.filter(Boolean).flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]));

function replace(id, ...kids) {
  const el = $(id);
  el.replaceChildren(...kids.flat().filter(Boolean));
  return el;
}

// ------------------------------------------------------------------ navigation
let current = "a";

export function showScene(id, scroll = false) {
  if (!SCENES.includes(id)) return;
  current = id;
  for (const k of SCENES) {
    const tab = $(`tab-${k}`), panel = $(`scene-${k}`);
    const on = k === id;
    tab.setAttribute("aria-selected", String(on));
    tab.tabIndex = on ? 0 : -1;
    panel.hidden = !on;
  }
  const i = SCENES.indexOf(id);
  $("qrg-prev").disabled = i === 0;
  $("qrg-next").disabled = i === SCENES.length - 1;
  $("qrg-next").textContent = i === SCENES.length - 1 ? "End" : "Next scene →";
  if (scroll) {
    const tab = $(`tab-${id}`);
    if (tab.scrollIntoView) tab.scrollIntoView({ block: "nearest", inline: "nearest" });
    const top = $(`scene-${id}`).getBoundingClientRect().top;
    if (top < 0 || top > window.innerHeight * 0.6) $(`scene-${id}`).scrollIntoView({ block: "start" });
  }
}

export function bindNavigation() {
  for (const k of SCENES) {
    const tab = $(`tab-${k}`);
    tab.addEventListener("click", () => showScene(k, true));
    tab.addEventListener("keydown", (ev) => {
      const i = SCENES.indexOf(current);
      if (ev.key === "ArrowRight") { showScene(SCENES[Math.min(i + 1, 5)], true); $(`tab-${current}`).focus(); }
      if (ev.key === "ArrowLeft") { showScene(SCENES[Math.max(i - 1, 0)], true); $(`tab-${current}`).focus(); }
    });
  }
  $("qrg-prev").addEventListener("click", () => showScene(SCENES[Math.max(SCENES.indexOf(current) - 1, 0)], true));
  $("qrg-next").addEventListener("click", () => showScene(SCENES[Math.min(SCENES.indexOf(current) + 1, 5)], true));
  showScene("a");
}

// ------------------------------------------------------------------ status
function setStatus(kind, text) {
  const st = $("qrg-status");
  st.className = `status ${kind}`;
  $("qrg-status-text").textContent = text;
}

export function renderRunning() {
  setStatus("running", "Running: submitting exactly one 7-qubit circuit to the Qollab backend (no seed, no retry)…");
}

export function renderFatal(code, message) {
  setStatus("error", `${code}: ${message}`);
  const msg = (where) => replace(where, card("No result",
    h("p", {}, h("strong", {}, code), " — ", message),
    h("p", { class: "muted" }, "No measurement is displayed and nothing is substituted. Press Run again in Qollab to retry; this page never retries on its own.")));
  for (const k of SCENES) msg(`${k}-body`);
}

// ------------------------------------------------------------------ scenes
function bundleOf(env) { return JSON.parse(env.evidence_text); } // read-only; never re-serialised

function heroVerdict(env, b) {
  const d = b.governor_decision;
  const el = $("qrg-hero-verdict");
  el.hidden = false;
  const stmt = (d.claim_ceiling || {}).observable_statement || b.proposal.claim.type;
  el.replaceChildren(
    h("div", { class: "hv-top" }, badge("live"), chip(d.verdict, d.reason_code)),
    h("p", { class: "hv-claim" }, "Claim tested: ", h("strong", {}, stmt)),
    h("p", { class: "hv-meta" },
      `${env.title} · ${b.backend_identity.name} · ${b.proposal.shots} shots · ${env.backend_run_calls_this_run} backend job`),
  );
  el.className = `hero-verdict ${verdictMeta(d.verdict).tone}`;
}

function sceneA(env, b) {
  const p = b.proposal, pre = b.preflight;
  const stmt = (b.governor_decision.claim_ceiling || {}).observable_statement || JSON.stringify(p.claim);
  const checks = h("ul", { class: "checks" }, pre.checks.map((c) =>
    h("li", { class: c.status === "PASS" ? "ok" : "bad" }, h("span", { class: "tick", "aria-hidden": "true" }, c.status === "PASS" ? "✓" : "✕"),
      h("span", {}, c.check.replaceAll("_", " ")), c.detail ? h("small", {}, ` — ${c.detail}`) : null)));
  const pf = (env.demonstrations || []).filter((d) => d.kind === "LOCAL_PREFLIGHT");
  const sel = h("select", { id: "cf-select", "aria-label": "Counterfactual proposal" },
    h("option", { value: "" }, "Choose a counterfactual proposal…"),
    pf.map((d) => h("option", { value: d.id }, d.label)));
  const out = h("div", { id: "cf-out", class: "cf-out", "aria-live": "polite" },
    h("p", { class: "muted" }, "Pick one to see what the governor would decide before spending a single shot."));
  sel.addEventListener("change", () => {
    const d = pf.find((x) => x.id === sel.value);
    if (!d) { out.replaceChildren(h("p", { class: "muted" }, "Nothing selected.")); return; }
    out.replaceChildren(h("div", { class: "row" }, badge(KIND_LABELS.LOCAL_PREFLIGHT), chip(d.governor.verdict, d.governor.reason_code)),
      h("p", {}, d.explanation),
      h("p", { class: "muted small" }, "Preview only. Changing this menu never authorizes or submits a quantum job."));
  });
  replace("a-body",
    h("div", { class: "grid2" },
      card("Proposal (fixed before Run)", kv([
        ["Experiment", env.title], ["Hypothesis", p.hypothesis],
        ["Requested backend", `${p.backend} (${p.backend_class})`],
        ["Shot budget", `${p.shots} shots · auto-approve limit 2000 · max 4096`],
        ["Claimed conclusion", stmt],
        ["Required measurements", "ZZZZ parity (ancilla q4) and XXXX parity (ancilla q5), every shot"],
      ])),
      card("Governor preflight", h("div", { class: "row" }, badge(null), chip(pre.decision, pre.reason_code)),
        h("p", { class: "small" }, "Authorization, budget, measurement relevance (can this circuit even distinguish the claim from its competitors?) and statistical power are checked before the job."),
        checks)),
    card("Explore counterfactual proposals", h("p", { class: "small" }, "What if someone asked for something else? These are LOCAL preflight evaluations — no quantum job."), sel, out));
}

const SHORT_ROLE = ["data", "data", "data", "data", "ZZZZ check", "XXXX check", "fault ctrl"];
const SEG_LABEL = { encode: "Encode |00⟩_L", fault: "Synthetic fault (labelled)", check_zzzz: "ZZZZ check", check_xxxx: "XXXX check", measure: "Measure" };

function circuitSvg(c) {
  const L = c.layout, cols = Math.max(...L.map((o) => o.layer)) + 1;
  const left = 150, dx = 44, top = 26, dy = 40, W = left + cols * dx + 20, H = top + c.n_qubits * dy;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img",
    "aria-label": `Circuit diagram: ${c.n_qubits} qubits, ${L.length} operations`, class: "circuit" });
  const y = (q) => top + q * dy, x = (l) => left + l * dx + dx / 2;
  c.qubit_roles.forEach((r, q) => {
    svg.append(s("text", { x: 4, y: y(q) + 4, class: "qlabel" }, `q${q} · ${SHORT_ROLE[q]}`));
    svg.append(s("line", { x1: left - 6, y1: y(q), x2: W - 10, y2: y(q), class: "wire" }));
  });
  for (const o of L) {
    const cls = `g ${o.segment}`, cx = x(o.layer);
    if (["cx", "cy", "cz"].includes(o.gate)) {
      const [ctl, tgt] = o.qubits;
      svg.append(s("line", { x1: cx, y1: y(ctl), x2: cx, y2: y(tgt), class: `link ${o.segment}` }));
      svg.append(s("circle", { cx, cy: y(ctl), r: 5, class: `dot ${o.segment}` }));
      if (o.gate === "cx") {
        svg.append(s("circle", { cx, cy: y(tgt), r: 10, class: `oplus ${o.segment}` }));
        svg.append(s("line", { x1: cx - 10, y1: y(tgt), x2: cx + 10, y2: y(tgt), class: `link ${o.segment}` }));
        svg.append(s("line", { x1: cx, y1: y(tgt) - 10, x2: cx, y2: y(tgt) + 10, class: `link ${o.segment}` }));
      } else if (o.gate === "cz") {
        svg.append(s("circle", { cx, cy: y(tgt), r: 5, class: `dot ${o.segment}` }));
      } else {
        svg.append(s("rect", { x: cx - 13, y: y(tgt) - 13, width: 26, height: 26, rx: 5, class: cls }));
        svg.append(s("text", { x: cx, y: y(tgt) + 5, class: "glabel" }, "Y"));
      }
    } else {
      const q = o.qubits[0], wide = o.gate === "ry";
      const w = wide ? 40 : 26;
      svg.append(s("rect", { x: cx - w / 2, y: y(q) - 13, width: w, height: 26, rx: 5, class: cls }));
      svg.append(s("text", { x: cx, y: y(q) + 5, class: "glabel" }, wide ? "RY" : o.label));
    }
  }
  return svg;
}

function sceneB(env, b) {
  const m = env.circuit.metrics || {};
  const legend = h("ul", { class: "seg-legend" }, Object.entries(SEG_LABEL).map(([k, v]) =>
    h("li", {}, h("span", { class: `swatch ${k}`, "aria-hidden": "true" }), v)));
  const rows = env.detection_table.map((r) => h("tr", {},
    h("td", {}, h("code", {}, r.pauli)), h("td", {}, r.note), h("td", {}, String(Math.round(r.sZ))), h("td", {}, String(Math.round(r.sX))),
    h("td", { class: r.detected_full ? "yes" : "no" }, r.detected_full ? "detected" : "SILENT"),
    h("td", { class: r.detected_zzzz_only ? "yes" : "no" }, r.detected_zzzz_only ? "detected" : "missed")));
  const f = env.synthetic_fault;
  replace("b-body",
    card("The executed circuit", h("div", { class: "scroll-x", tabindex: "0", "aria-label": "Circuit diagram, scroll horizontally" }, circuitSvg(env.circuit)), legend,
      kv([["Qubits", String(m.qubits)], ["Circuit depth (Qiskit, incl. measurement)", String(m.depth)],
          ["Depth without measurement", String(m.depth_excl_measure)], ["Two-qubit gates", String(m.two_qubit_gates)],
          ["Gate counts", Object.entries(m.ops || {}).map(([k, v]) => `${k}×${v}`).join(", ")],
          ["Synthetic fault in this package", f.pattern === "IIII" ? "none (q6 idle)" : `${f.pattern} applied with probability ${f.p} via q6 (${f.mode})`]]),
      h("p", { class: "muted small" }, "Numbers above are computed from the actual QuantumCircuit object; the diagram columns are a drawing layout.")),
    h("div", { class: "grid2" },
      card("Roles", h("ul", { class: "plain" },
        h("li", {}, h("b", {}, "q0–q3 data: "), "the logical state |00⟩_L = (|0000⟩+|1111⟩)/√2 of the [[4,2,2]] code."),
        h("li", {}, h("b", {}, "q4 ZZZZ check: "), "flips when a bit-flip (X or Y) fault hit the data."),
        h("li", {}, h("b", {}, "q5 XXXX check: "), "flips when a phase-flip (Z or Y) fault hit the data — invisible to ordinary bit parity."),
        h("li", {}, h("b", {}, "q6 fault control: "), "creates the labelled synthetic fault; its outcome is audit-only and hidden from the governor."))),
      card("Detection is not correction", h("p", {}, "Every single-qubit fault flips a check, but each qubit gives the same syndrome — so the fault cannot be located or corrected (code distance 2)."),
        h("p", {}, "Logical operators such as XXII commute with both checks: they are ", h("strong", {}, "syndrome-silent"), "."))),
    card("What each check sees (exact prediction, no job)", h("div", { class: "scroll-x" }, h("table", { class: "tbl" },
      h("thead", {}, h("tr", {}, ["Fault", "Meaning", "sZ", "sX", "Both checks", "ZZZZ only"].map((t) => h("th", {}, t)))),
      h("tbody", {}, rows)))));
}

function sceneC(env, b) {
  const counts = b.raw_record.counts, n = b.raw_record.shots;
  const syn = b.descriptive_not_governing.syndromes;
  const tile = (name, sObj, hint) => h("div", { class: "tile" }, h("p", { class: "tile-k" }, name),
    h("p", { class: "tile-v" }, `${sObj.k} / ${sObj.n}`), h("p", { class: "tile-r" }, `rate ${fmtRate(sObj.rate)}`),
    h("p", { class: "tile-ci" }, `two-sided 95%: [${fmtRate(sObj.two_sided_95[0])}, ${fmtRate(sObj.two_sided_95[1])}]`),
    h("p", { class: "muted small" }, hint));
  const max = Math.max(...Object.values(counts));
  const bars = Object.entries(counts).sort((a, c) => c[1] - a[1]).map(([k, v]) => {
    const d = decodeKey(k);
    return h("div", { class: "bar-row" },
      h("code", { class: "bar-key", title: "c6..c0 = coin sX sZ d3 d2 d1 d0" }, k),
      h("div", { class: "bar-track" }, h("div", { class: `bar ${d.sX === "1" ? "sx" : d.sZ === "1" ? "sz" : "clean"}`, style: `width:${(v / max) * 100}%` })),
      h("span", { class: "bar-v" }, `${v}`),
      h("span", { class: "bar-d" }, `sX=${d.sX} sZ=${d.sZ} data=${d.data} · fault-control=${d.coin} (audit)`));
  });
  const extra = [];
  if (env.experiment === "B_Z_FAULT") {
    const nc = b.descriptive_not_governing.nominal_comparison;
    extra.push(card("Why ZZZZ alone cannot see this fault",
      h("p", {}, `The XXXX check fired in ${syn.sX_XXXX.k} of ${n} shots; the ZZZZ check in ${syn.sZ_ZZZZ.k}. A Z fault commutes with ZZZZ and leaves every data bit-string unchanged, so an experiment with only the ZZZZ check would report a clean state.`),
      h("p", { class: "small" }, `Nominal synthetic fault probability ${nc.nominal_p}; two-sided 95% interval of the observed rate [${fmtRate(nc.two_sided_95[0])}, ${fmtRate(nc.two_sided_95[1])}] ${nc.nominal_inside_interval ? "contains" : "does not contain"} it. This comparison is descriptive: consistency with 0.2 is not proof of 0.2.`)));
  } else {
    extra.push(card("A clean encoded state", h("p", {}, `No fault was injected. ${syn.any_nontrivial.k} of ${n} shots showed a nontrivial syndrome. The data qubits split between 0000 and 1111 — the two halves of |00⟩_L.`)));
  }
  replace("c-body",
    card(null, h("div", { class: "row" }, badge("live"), h("span", { class: "muted small" }, `backend ${b.backend_identity.name} · ${n} shots · measured ${b.raw_record.created_at}`))),
    h("div", { class: "tiles" },
      tile("XXXX check (sX)", syn.sX_XXXX, "phase-type faults"),
      tile("ZZZZ check (sZ)", syn.sZ_ZZZZ, "bit-flip-type faults"),
      h("div", { class: "tile" }, h("p", { class: "tile-k" }, "Physics check"), h("p", { class: "tile-v" }, `${syn.sZ_vs_data_parity_violations}`),
        h("p", { class: "tile-r" }, "shots where sZ differs from data parity"), h("p", { class: "muted small" }, "must be 0 on an ideal backend"))),
    card("Raw bitstrings returned by the backend", h("div", { class: "bars" }, bars),
      h("p", { class: "muted small" }, "Uncertainty: shot noise only (ideal simulator). Intervals are exact Clopper–Pearson; the governed decision uses one-sided 95% bounds (Scene E).")),
    extra);
}

function sceneD(env, b, cc) {
  const vr = env.verifier_report, rec = vr.recomputed, dd = rec.decision_detail || {};
  const row = (ok, label, detail) => h("li", { class: ok ? "ok" : "bad" },
    h("span", { class: "tick", "aria-hidden": "true" }, ok ? "✓" : "✕"), h("span", {}, label), detail ? h("small", {}, ` — ${detail}`) : null);
  const g = b.governor_decision.statistics || {}, vst = dd.statistics || {};
  const ta = h("textarea", { id: "evidence-text", class: "evidence", readonly: true, rows: 8, spellcheck: "false", "aria-label": "Complete evidence JSON (canonical text)" });
  ta.value = env.evidence_text; // verbatim Python text — never re-serialised
  const copyMsg = h("p", { id: "copy-msg", class: "small", "aria-live": "polite" }, "");
  const copyBtn = h("button", { id: "copy-btn", class: "primary", type: "button" }, "Copy evidence JSON");
  copyBtn.addEventListener("click", () => copyEvidence(ta, copyMsg));
  const selBtn = h("button", { id: "select-btn", class: "ghost", type: "button" }, "Select all");
  selBtn.addEventListener("click", () => { ta.focus(); ta.select(); ta.setSelectionRange(0, ta.value.length); copyMsg.textContent = "Selected — press Ctrl+C / ⌘C to copy."; });
  const as = b.governor_decision.assurance;
  replace("d-body",
    h("div", { class: "grid2" },
      card("Independent verifier (Python, standard library only)", h("div", { class: "row" }, h("span", { class: `chip ${vr.status === "VERIFIED" ? "accept" : "reject"}` }, vr.status)),
        h("ul", { class: "checks" },
          row(rec.raw_counts_sha256_ok && rec.raw_record_sha256_ok, "Raw record hashes recomputed"),
          row(rec.raw_total_shots === b.proposal.shots, "Count total", `${rec.raw_total_shots} = ${b.proposal.shots} shots`),
          row(rec.view_equals_raw_marginal && rec.view_bound_to_raw, "Governor view = raw counts minus fault-control bit"),
          row((rec.view_contains_audit_fields || []).length === 0, "No audit field leaked to the governor"),
          row(dd.physics_out_of_model_shots === 0, "Physics invariant (sZ = data parity)", `${dd.physics_out_of_model_shots} violations`),
          row(dd.measured_stabilizers && dd.measured_stabilizers.sX === "XXXX" && dd.measured_stabilizers.sZ === "ZZZZ", "Authorized circuit: checks parsed from circuit", `sZ=${(dd.measured_stabilizers || {}).sZ}, sX=${(dd.measured_stabilizers || {}).sX}`),
          row(Math.abs((g.cp_upper ?? 0) - (vst.cp_upper ?? 0)) < 1e-8 && Math.abs((g.cp_lower ?? 0) - (vst.cp_lower ?? 0)) < 1e-8, "Statistics recomputed (incomplete-beta method)", `k=${vst.k}, bounds [${fmtRate(vst.cp_lower, 6)}, ${fmtRate(vst.cp_upper, 6)}]`),
          row(rec.verdict === b.governor_decision.verdict, "Policy decision re-derived", `${rec.verdict} / ${rec.reason_code}`)),
        vr.mismatches.length ? h("p", { class: "bad" }, `Mismatches: ${vr.mismatches.join("; ")}`) : null),
      card("Browser cross-check (JavaScript, this page)", h("ul", { class: "checks" },
        row(cc.shaMatches, "SHA-256 of the exported text recomputed in the browser", `${(cc.shaRecomputed || "").slice(0, 16)}…`),
        row(cc.totalsMatch, "Totals from raw counts", `${cc.total} shots`),
        row(cc.countsMatchVerifier, "Syndrome decoding agrees with the verifier", `sX=${cc.sX}, sZ=${cc.sZ}`),
        row(cc.parityViolations === 0 && cc.malformedKeys === 0, "Parity invariant in the browser", `${cc.parityViolations} violations`)),
        h("p", { class: "muted small" }, "Three independent computations (governor, verifier, browser) must agree."))),
    card("Provenance — what these checks do and do not establish", kv([
      ["Evidence consistency", as.evidence_consistency], ["Physical plausibility", as.physical_plausibility],
      ["Reproducibility", as.reproducibility], ["Authenticated provenance", as.authenticated_provenance],
      ["Seed support", b.seed_probe.seed_simulator_advertised ? "advertised by the backend — NOT verified as reproducible" : "not advertised"]])),
    card("Export the complete evidence", h("p", { class: "small" }, "Exact canonical text produced by Python (", h("code", {}, `${env.evidence_bytes} bytes`), "). Declared SHA-256: ", h("code", { class: "hash" }, env.evidence_sha256)),
      ta, h("div", { class: "row" }, copyBtn, selBtn), copyMsg,
      h("p", { class: "muted small" }, "Verify offline: save the text as evidence.json and run ", h("code", {}, "python verifier/verify_qrg.py evidence.json"), ". An offline paste can be checked for consistency, never for origin.")));
}

export async function copyEvidence(ta, msg) {
  const text = ta.value;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      msg.textContent = "Copied to clipboard.";
      return "clipboard";
    }
  } catch (_) { /* sandboxed iframe: fall through */ }
  ta.focus(); ta.select(); ta.setSelectionRange(0, text.length);
  let ok = false;
  try { ok = document.execCommand && document.execCommand("copy"); } catch (_) { ok = false; }
  msg.textContent = ok ? "Copied (fallback)." : "Clipboard blocked here — the text is selected: press Ctrl+C / ⌘C.";
  return ok ? "execCommand" : "manual";
}

function niceStep(raw) {
  const p = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((m) => m * p).find((x) => x >= raw);
}

function niceMax(st) {
  const v = st.values || {};
  const need = Math.max(0.02, (st.cp_upper || 0) * 1.4, (v.hi || v.eps || v.rho || 0) * 1.25);
  const step = niceStep(need / 4);
  return Math.ceil(need / step) * step;
}

function niceTicks(max) {
  const step = niceStep(max / 4), out = [];
  for (let t = 0; t <= max + 1e-12; t += step) out.push(Math.round(t / step) * step);
  return out;
}

function intervalSvg(st) {
  const geo = intervalGeometry(st, niceMax(st)), W = 560, H = 64, pad = 30, w = W - 2 * pad, X = (p) => pad + (p / 100) * w;
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "interval", role: "img",
    "aria-label": `Bounds ${fmtRate(st.cp_lower)} to ${fmtRate(st.cp_upper)} versus claim region` });
  svg.append(s("rect", { x: X(geo.region[0]), y: 10, width: Math.max(2, X(geo.region[1]) - X(geo.region[0])), height: 22, class: "region" }));
  svg.append(s("line", { x1: pad, y1: 21, x2: W - pad, y2: 21, class: "axis" }));
  svg.append(s("rect", { x: X(geo.lo), y: 16, width: Math.max(3, X(geo.hi) - X(geo.lo)), height: 10, rx: 3, class: "ci" }));
  svg.append(s("circle", { cx: X(geo.point), cy: 21, r: 4, class: "pt" }));
  for (const t of niceTicks(geo.max)) {
    svg.append(s("line", { x1: X((t / geo.max) * 100), y1: 34, x2: X((t / geo.max) * 100), y2: 39, class: "axis" }));
    svg.append(s("text", { x: X((t / geo.max) * 100), y: 54, class: "tick" }, t.toFixed(3).replace(/0+$/, "").replace(/\.$/, ".0")));
  }
  return svg;
}

function demoCard(d) {
  const agree = d.verifier ? (d.agree ? "verifier agrees" : "verifier DISAGREES") : "no evidence involved";
  return h("article", { class: `demo ${verdictMeta(d.governor.verdict).tone}` },
    h("div", { class: "row" }, chip(d.governor.verdict, d.governor.reason_code)),
    h("h4", {}, d.label), h("p", { class: "small" }, d.explanation),
    d.mutation ? h("p", { class: "muted small" }, `Mutation: ${d.mutation}`) : null,
    h("p", { class: "kind" }, KIND_LABELS[d.kind] || d.kind, " · ", agree));
}

function sceneE(env, b) {
  const d = b.governor_decision, st = d.statistics;
  const groups = groupDemos(env.demonstrations);
  const live = card(null, h("div", { class: "row" }, badge("live"), chip(d.verdict, d.reason_code)),
    h("p", { class: "big" }, (d.claim_ceiling || {}).observable_statement || ""),
    st ? h("p", { class: "small" }, `k = ${st.k} of n = ${st.n} · one-sided 95% bounds [${fmtRate(st.cp_lower, 5)}, ${fmtRate(st.cp_upper, 5)}] · ${st.rule}`) : null,
    st ? intervalSvg(st) : null,
    st ? h("p", { class: "muted small" }, "Shaded: the claim's region. Bar: one-sided 95% bounds from the live counts. ACCEPT needs the bounds inside the region; it means the opposite was rejected at the 5% level — not proof.") : null,
    h("p", { class: "small" }, verdictMeta(d.verdict).plain));
  const section = (v, title) => h("div", { class: "demo-group" }, h("h3", {}, chip(v), " ", title),
    h("div", { class: "demos" }, (groups[v] || []).map(demoCard)));
  replace("e-body", h("div", { class: "live-verdict" }, live),
    h("p", { class: "notice" }, "Below: demonstrations of the other verdicts. ", h("strong", {}, "None of them was executed on the backend."),
      " They are local preflights, other claims evaluated against this Run's evidence, or mutations of a copy of the evidence. The original evidence is untouched (SHA-256 before and after: ",
      h("code", {}, env.evidence_sha256 === env.evidence_sha256_after_demonstrations ? "identical" : "CHANGED"), ")."),
    section("REJECT", "unsupported claim or policy violation"),
    section("ESCALATE", "inconclusive or human required"),
    section("FREEZE", "evidence integrity failure"));
}

function sceneF(env, b) {
  const items = [
    ["Detection, not correction", "The [[4,2,2]] code flags single-qubit faults but cannot locate or correct them."],
    ["Silent logical errors exist", "Logical operators like XXII commute with both checks. A clean syndrome does not prove that no physical or logical error happened."],
    ["An ideal simulator is not hardware", "These measurements come from Qollab's built-in ideal simulator. They say nothing about hardware noise, fidelity or fault tolerance."],
    ["Synthetic fault, known in advance", "The phase fault in package B is injected with probability 0.2 by construction; measuring it demonstrates the evidence chain, not a discovery."],
    ["A hash is not a signature", "SHA-256 shows the text was not changed after hashing; it does not prove who produced it or that it came from this backend."],
    ["Plausible forgeries pass physics checks", "Counts that obey the parity invariant can still be invented. Physics checks catch impossible records only."],
    ["Advertised seed is not verified replay", `The backend ${b.seed_probe.seed_simulator_advertised ? "advertises" : "does not advertise"} seed_simulator, but seeded reproducibility has not been demonstrated.`],
    ["Statistics are conditional", "ACCEPT holds at one-sided 95% confidence, assuming independent shots and the declared single-qubit Pauli fault model. Under other models the reading as a fault rate may fail."],
    ["No quantum advantage", "Nothing here measures computational speed-up or advantage."],
    ["Deterministic policy, not an AI scientist", "The governor is fixed research-policy software. It has no autonomous scientific authority."],
  ];
  const ne = ((b.governor_decision.claim_ceiling || {}).not_established) || [];
  replace("f-body",
    h("div", { class: "limits" }, items.map(([t, x]) => h("div", { class: "limit" }, h("h4", {}, t), h("p", {}, x)))),
    card("Recorded in this Run's verdict as NOT established", h("ul", { class: "plain" }, ne.map((x) => h("li", {}, x)))));
}

export function renderEnvelope(env, cc) {
  if (env.status !== "COMPLETED") {
    const reason = env.status_message || env.status;
    renderFatal(env.status, reason);
    if (env.status === "INTERNAL_ERROR" && env.traceback) {
      $("d-body").append(h("pre", { class: "trace" }, env.traceback));
    }
    return;
  }
  const b = bundleOf(env);
  setStatus("done", `Run complete · ${env.backend_run_calls_this_run} backend job · governor verdict ${b.governor_decision.verdict} · verifier ${env.verifier_report.status}`);
  heroVerdict(env, b);
  sceneA(env, b); sceneB(env, b); sceneC(env, b); sceneD(env, b, cc); sceneE(env, b); sceneF(env, b);
}
