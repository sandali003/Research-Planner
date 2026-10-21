// Dashboard logic for app.py: every number comes from the Component 4 API (trained Python models).

const SET_LABEL = {
  baseline_market_only: "Market only (baseline)",
  market_plus_C1: "Market + C1 health score",
  market_plus_C2: "Market + C2 faults",
  market_plus_C3: "Market + C3 deterioration",
  condition_aware_C1_C2_C3: "Condition-aware (C1+C2+C3)",
};
const FEATURE_LABEL = {
  vehicle_age: "Vehicle age", vehicle_model: "Model", health_score: "C1 health score",
  deterioration_deviation: "C3 deterioration deviation", mileage_km: "Mileage", engine_capacity_cc: "Engine cc",
  fuel_type: "Fuel type", transmission: "Transmission", deterioration_class: "C3 deterioration class",
  fault_count: "C2 fault count", severity_level: "C2 severity",
};

const fmt = n => Math.round(n).toLocaleString("en-US");
const lkr = n => "LKR " + fmt(n);
const mlkr = n => "LKR " + (n / 1e6).toFixed(2) + "M";
const signed = n => (n >= 0 ? "+" : "−") + fmt(Math.abs(n));
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const $ = id => document.getElementById(id);

async function api(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path} returned ${res.status}: ${await res.text()}`);
  return res.json();
}
function showError(el, err) {
  el.innerHTML = `<div class="none">Could not load data from the server. Check that app.py is running. (${esc(err.message)})</div>`;
}

/* Summary: gauges, charts, table, notes */
function renderSummary({ meta, results, importance }) {
  const b = meta.baseline, c = meta.condition_aware, imp = meta.improvement_over_baseline;
  const cost = meta.repair_cost_lookup_validation;
  $("gauges").innerHTML = `
    <div class="gauge"><span class="label">Baseline MAE · market only</span><span class="value">${lkr(b.test_MAE)}</span><span class="sub">R² ${b.test_R2.toFixed(3)} · ${b.model}</span></div>
    <div class="gauge lead"><span class="label">Condition-aware MAE · C1+C2+C3</span><span class="value">${lkr(c.test_MAE)}</span><span class="sub">R² ${c.test_R2.toFixed(3)} · ${c.model}</span></div>
    <div class="gauge"><span class="label">Error reduction</span><span class="value">${imp["MAE_reduction_%"].toFixed(1)}%</span><span class="sub">${lkr(imp.MAE_reduction_lkr)} less error per vehicle</span></div>
    <div class="gauge"><span class="label">Repair-cost lookup</span><span class="value">${cost["share_within_min_max_%"].toFixed(1)}%</span><span class="sub">of ${fmt(cost.records)} repair records inside the min–max range</span></div>`;

  const best = {};
  results.forEach(r => { if (!best[r.feature_set] || r.cv_MAE < best[r.feature_set].cv_MAE) best[r.feature_set] = r; });
  const sets = Object.keys(SET_LABEL);

  barChart($("chart-mae"), "Test MAE by feature set (lower is better)",
    sets.map(s => ({ label: SET_LABEL[s], value: best[s].test_MAE, text: fmt(best[s].test_MAE / 1000) + "k", s })),
    600000, 100000, t => t / 1000 + "k",
    r => r.s === "baseline_market_only" ? "var(--muted)" : "var(--accent)");
  const top = importance.slice(0, 8);
  const maxImp = Math.ceil(Math.max(...top.map(r => r.MAE_increase_lkr)) / 500000) * 500000;
  barChart($("chart-imp"), "Feature importance, condition-aware model",
    top.map(r => ({ label: FEATURE_LABEL[r.feature] || r.feature, value: Math.max(0, r.MAE_increase_lkr), text: (r.MAE_increase_lkr / 1e6).toFixed(2) + "M", f: r.feature })),
    maxImp, 500000, t => (t / 1e6).toFixed(1) + "M",
    r => /health|deterioration|fault|severity/.test(r.f) ? "var(--accent)" : "var(--muted)");
  $("ev-sub").textContent = "Each bar is the best of four algorithms for that feature set. Importance is the extra MAE (LKR) when a feature is shuffled; condition features are shown in the accent colour.";

  const algos = ["LinearRegression", "RandomForest", "GradientBoosting", "XGBoost"];
  const cell = (s, a) => results.find(r => r.feature_set === s && r.model === a);
  let h = `<thead><tr><th>Feature set</th>${algos.map(a => `<th>${a} MAE</th>`).join("")}<th>Best R²</th><th>Best MAPE</th></tr></thead><tbody>`;
  for (const s of sets)
    h += `<tr><td>${SET_LABEL[s]}</td>${algos.map(a => `<td class="${best[s].model === a ? "best" : ""}">${fmt(cell(s, a).test_MAE)}</td>`).join("")}<td>${best[s].test_R2.toFixed(4)}</td><td>${best[s]["test_MAPE_%"].toFixed(2)}%</td></tr>`;
  $("results-table").innerHTML = h + "</tbody>";

  const hs = meta.health_score_dependency;
  $("notes").innerHTML = [
    `The dataset is synthetic. Results show that the pipeline works and how the comparison is set up, not real Sri Lankan market behaviour. Real listings should be collected with the validation template before final claims.`,
    `The C1 health score is almost fully explained by age, mileage and C3 deterioration (R² ${hs.R2_age_mileage_deterioration.toFixed(4)}). Adding fault features changes nothing, so C1 and C3 carry the same information here. For the same reason, do not read the sign of the health score coefficient as an explanation.`,
    `Fault features (C2) barely move the price: MAE drops from ${fmt(best.baseline_market_only.test_MAE)} to ${fmt(best.market_plus_C2.test_MAE)} LKR. Repair scenarios therefore show small value gains. This comes from how the data was generated.`,
    `Linear Regression beats the tree models on every feature set, which suggests prices were generated with a log-linear formula.`,
    `The original "condition" label (Excellent/Good/Fair/Poor) is a binned copy of the health score, so it is left out to avoid leakage. Estimated repair cost is also left out because it is a Component 4 output.`,
  ].map(t => `<li>${t}</li>`).join("");
}

function barChart(el, title, rows, max, step, tickFmt, colorFn) {
  const W = 560, labelW = 200, rowH = 34, top = 34, bottom = 30, right = 70;
  const H = top + rows.length * rowH + bottom, plotW = W - labelW - right;
  const x = v => labelW + (v / max) * plotW;
  let ticks = "";
  for (let t = 0; t <= max + 1e-9; t += step)
    ticks += `<line class="gridline" x1="${x(t)}" x2="${x(t)}" y1="${top - 6}" y2="${H - bottom}"/><text x="${x(t)}" y="${H - bottom + 18}" text-anchor="middle">${tickFmt(t)}</text>`;
  const bars = rows.map((r, i) => {
    const y = top + i * rowH;
    return `<text class="lbl" x="${labelW - 10}" y="${y + rowH / 2 + 4}" text-anchor="end">${esc(r.label)}</text>
      <rect x="${labelW}" y="${y + 7}" width="${Math.max(1, x(r.value) - labelW)}" height="${rowH - 14}" rx="2" style="fill:${colorFn(r, i)}"/>
      <text x="${x(r.value) + 6}" y="${y + rowH / 2 + 4}">${r.text}</text>`;
  }).join("");
  el.innerHTML = `<h3>${title}</h3><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}">${ticks}${bars}</svg>`;
}

/* Vehicle checker */
let allVehicles = [], selected = null, currentId = null;

function fillVehicles(selectId) {
  const model = $("f-model").value;
  const list = allVehicles.filter(v => !model || v.vehicle_model === model);
  $("f-vehicle").innerHTML = list.map(v => `<option value="${v.vehicle_id}">${v.vehicle_id} · ${v.vehicle_model} ${v.manufacture_year} · ${v.fault_count} fault${v.fault_count === 1 ? "" : "s"}</option>`).join("");
  if (selectId && list.some(v => v.vehicle_id === selectId)) $("f-vehicle").value = selectId;
  loadVehicle($("f-vehicle").value);
}

async function loadVehicle(id, focusIndex) {
  if (!id) return;
  if (id !== currentId) { selected = null; currentId = id; }
  const q = selected ? `?repairs=${[...selected].join(",")}` : "";
  try {
    const res = await api(`/api/vehicles/${encodeURIComponent(id)}${q}`);
    if (id !== currentId) return;  // a newer selection is already loading
    if (!selected) selected = new Set(res.faults.map((_, i) => i));
    renderVehicle(res);
    if (focusIndex !== undefined) $("rep-" + focusIndex)?.focus();
  } catch (err) { showError($("result"), err); }
}

function renderVehicle({ vehicle: v, assessment: a }) {
  const hs = v.health_score;
  $("spec").innerHTML = `
    <div class="group"><span class="group-title">Vehicle</span>
      <h3>${esc(v.vehicle_model)} ${v.manufacture_year}</h3>
      <dl>
        <dt>ID</dt><dd>${v.vehicle_id}</dd>
        <dt>Age</dt><dd>${v.vehicle_age} yrs</dd>
        <dt>Mileage</dt><dd>${fmt(v.mileage_km)} km</dd>
        <dt>Engine</dt><dd>${v.engine_capacity_cc} cc</dd>
        <dt>Fuel</dt><dd>${esc(v.fuel_type)}</dd>
        <dt>Gearbox</dt><dd>${esc(v.transmission)}</dd>
      </dl></div>
    <div class="group"><span class="group-title">C1 · Health</span>
      <dl><dt>Health score</dt><dd>${hs.toFixed(1)} / 100</dd></dl>
      <div class="meter" role="img" aria-label="Health score ${hs.toFixed(1)} of 100"><i style="width:${hs}%"></i></div></div>
    <div class="group"><span class="group-title">C2 · Hidden faults</span>
      <dl><dt>Faults</dt><dd>${v.fault_count}</dd><dt>Worst severity</dt><dd>${esc(v.severity)}</dd></dl></div>
    <div class="group"><span class="group-title">C3 · Deterioration</span>
      <dl><dt>Deviation</dt><dd>${v.deterioration_deviation >= 0 ? "+" : ""}${v.deterioration_deviation.toFixed(2)}</dd><dt>Class</dt><dd>${esc(v.deterioration_class)}</dd></dl></div>`;

  const base = a.baseline_market_value_lkr, cond = a.condition_adjusted_value_lkr;
  const actualErr = (cond - v.listing_price_lkr) / v.listing_price_lkr * 100;
  const recs = a.recommendations, plan = a.scenario_selected;

  $("result").innerHTML = `
    <div class="values">
      <div class="val"><span class="label">Baseline market value</span><span class="amount">${mlkr(base)}</span><span class="delta">market features only</span></div>
      <div class="val primary"><span class="label">Condition-adjusted value</span><span class="amount">${mlkr(cond)}</span><span class="delta">${signed(a.condition_adjustment_lkr)} vs baseline</span></div>
      <div class="val"><span class="label">Listing price in dataset</span><span class="amount">${mlkr(v.listing_price_lkr)}</span><span class="delta">model error ${actualErr >= 0 ? "+" : "−"}${Math.abs(actualErr).toFixed(1)}%</span></div>
    </div>
    <div class="section-head"><h3>Recommended maintenance, ranked</h3>
      <p class="footnote">Ranked by detected severity first, then the fault rule's priority. Tick the repairs to include in the plan.</p></div>
    <div class="recs">${recs.length ? recs.map(r => {
      const i = r.fault_index, c = r.estimated_cost_lkr;
      return `
      <div class="rec" data-sev="${esc(r.severity)}">
        <input type="checkbox" id="rep-${i}" data-i="${i}" ${selected.has(i) ? "checked" : ""} aria-label="Include ${esc(r.fault_code)} repair in plan">
        <span class="rank">${r.rank}</span>
        <label class="what" for="rep-${i}">
          <span class="title"><span class="code">${esc(r.fault_code)}</span> ${esc(r.detected_problem || "Unknown fault code")} <span class="chip ${esc(r.severity)}">${esc(r.severity)}</span></span>
          <span class="action">${esc(r.action)}</span>
          <span class="repair">Repair: ${esc(r.repair_type || "–")}${r.alternative_repair ? " · alternative: " + esc(r.alternative_repair) : ""} · ${esc(r.component || "")}</span>
        </label>
        <span class="money">${c ? `<b>${lkr(c.typical)}</b><span class="muted">${fmt(c.min)}–${fmt(c.max)}</span>` : `<span class="muted">no cost data</span>`}${r.estimated_value_change_lkr !== undefined ? `<span class="${r.estimated_value_change_lkr >= 0 ? "pos" : "neg"}">${signed(r.estimated_value_change_lkr)} value</span>` : ""}</span>
      </div>`;
    }).join("") : `<div class="none">No faults detected for this vehicle. No repairs to recommend.</div>`}</div>
    ${recs.length ? `
    <div class="plan">
      <div><span class="label">Repairs in plan</span><span class="amount">${plan.repair_indices.length} of ${recs.length}</span></div>
      <div><span class="label">Typical repair cost</span><span class="amount">${lkr(plan.total_typical_repair_cost_lkr)}</span></div>
      <div><span class="label">Value after repairs</span><span class="amount">${mlkr(plan.estimated_value_lkr)}</span></div>
      <div><span class="label">Value change − cost</span><span class="amount ${plan.net_after_cost_lkr >= 0 ? "pos" : "neg"}">${signed(plan.net_after_cost_lkr)}</span></div>
    </div>
    <p class="footnote">Value change is a model estimate (${signed(plan.potential_value_change_lkr)} for this plan), not a guaranteed selling-price increase.</p>` : ""}`;

  document.querySelectorAll(".rec input").forEach(cb => cb.addEventListener("change", e => {
    const i = +e.target.dataset.i;
    e.target.checked ? selected.add(i) : selected.delete(i);
    loadVehicle(currentId, i);
  }));
}

async function start() {
  api("/api/summary").then(renderSummary).catch(err => showError($("gauges"), err));
  try {
    allVehicles = await api("/api/vehicles");
  } catch (err) { showError($("result"), err); return; }
  const models = [...new Set(allVehicles.map(v => v.vehicle_model))].sort();
  $("f-model").innerHTML = `<option value="">All models</option>` + models.map(m => `<option>${m}</option>`).join("");
  $("f-model").addEventListener("change", () => fillVehicles());
  $("f-vehicle").addEventListener("change", () => loadVehicle($("f-vehicle").value));
  $("b-random").addEventListener("click", () => {
    const model = $("f-model").value;
    const pool = allVehicles.filter(v => v.fault_count >= 2 && (!model || v.vehicle_model === model));
    $("f-vehicle").value = pool[Math.floor(Math.random() * pool.length)].vehicle_id;
    loadVehicle($("f-vehicle").value);
  });
  fillVehicles("M4TP00002");
}
start();
