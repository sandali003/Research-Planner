'use client';

import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react';
import { fmt, fmtTime } from '@/lib/format';
import type {
  ContextualAssessment, ContextualDecision, ContextualResult, DecisionKey, DeteriorationAssessment, DeteriorationComponent,
  DeteriorationContext, NextTestRisk, RiskLevel,
  DeteriorationStatus,
} from '@/lib/types';

export const STATUS_CLASS: Record<DeteriorationStatus, string> = {
  Normal: 'sev-none',
  'Slightly high': 'sev-low',
  High: 'sev-high',
};

const STATUS_ICON: Record<DeteriorationStatus, ReactNode> = {
  Normal: <path d="M5 12l5 5L20 7" />,
  'Slightly high': <path d="M12 6v7M12 17.5h.01" />,
  High: <path d="M12 3l10 18H2zM12 10v4M12 17.5h.01" />,
};

/** Status pill: icon + label, so the state never depends on colour alone. */
export function DeteriorationPill({ status, long }: { status: DeteriorationStatus; long?: boolean }) {
  return (
    <span className={`sev det-pill ${STATUS_CLASS[status]}`}>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"
        strokeLinejoin="round" aria-hidden="true">{STATUS_ICON[status]}</svg>
      {status}{long ? ' deterioration' : ''}
    </span>
  );
}

export const prettyComponent = (c: string) => c.replace(/_/g, ' ');
const signed = (v: number) => `${v > 0 ? '+' : ''}${fmt(v)}`;

/** Small hover tooltip shared by the charts. */
function useTip() {
  const [tip, setTip] = useState<{ x: number; y: number; html: ReactNode } | null>(null);
  const show = (html: ReactNode) => (e: MouseEvent) => {
    const box = (e.currentTarget as Element).closest('.chart-wrap')!.getBoundingClientRect();
    setTip({ x: e.clientX - box.left, y: e.clientY - box.top, html });
  };
  const hide = () => setTip(null);
  const node = tip && (
    <div className="chart-tip" style={{ left: tip.x, top: tip.y }} role="tooltip">{tip.html}</div>
  );
  return { show, hide, node };
}

/** Width of the chart container, so charts draw at real size (text stays readable on phones). */
function useWidth(fallback: number) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([entry]) => setWidth(Math.max(300, Math.round(entry.contentRect.width))));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/* ---------- component-wise chart: expected (ring) vs observed (dot) ---------- */
function ComponentChart({ components }: { components: DeteriorationComponent[] }) {
  const { show, hide, node } = useTip();
  const [ref, W] = useWidth(640);
  const narrow = W < 480;
  const L = narrow ? 100 : 132, R = narrow ? 104 : 118, rowH = 40, top = 6;
  const H = top + components.length * rowH + 26;
  const x = (v: number) => L + (Math.max(0, Math.min(100, v)) / 100) * (W - L - R);
  const ticks = narrow ? [0, 50, 100] : [0, 25, 50, 75, 100];
  return (
    <div className="chart-wrap" ref={ref}>
      <svg className="det-chart" viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label="Expected and observed condition score for each inspected component">
        {ticks.map((t) => (
          <g key={t}>
            <line className="grid" x1={x(t)} x2={x(t)} y1={top} y2={H - 22} />
            <text x={x(t)} y={H - 6} textAnchor="middle">{t}</text>
          </g>
        ))}
        {components.map((c, i) => {
          const y = top + i * rowH + rowH / 2;
          return (
            <g key={c.component} onMouseMove={show(
              <><b>{prettyComponent(c.component)}</b> · reported {c.component_state}<br />
                Expected {fmt(c.expected_score)} · Observed {fmt(c.observed_score)}<br />
                Deviation {signed(c.deviation)} · {c.status}</>,
            )} onMouseLeave={hide}>
              <rect x={0} y={y - rowH / 2} width={W} height={rowH} fill="transparent" />
              <text className="lbl" x={0} y={y + 4}>{prettyComponent(c.component)}</text>
              <line x1={x(c.expected_score)} x2={x(c.observed_score)} y1={y} y2={y} className="link" />
              <circle cx={x(c.expected_score)} cy={y} r={6} className="mark-expected" />
              <circle cx={x(c.observed_score)} cy={y} r={6} className="mark-observed" />
              <text className="val" x={W - R + 12} y={y + 4}>{signed(c.deviation)}</text>
              <circle cx={W - R + 56} cy={y} r={5} className={`dot-${STATUS_CLASS[c.status]}`} />
              <text className="val" x={W - R + 66} y={y + 4}>{c.status === 'Slightly high' ? 'Slight' : c.status}</text>
            </g>
          );
        })}
      </svg>
      {node}
    </div>
  );
}

/* ---------- age vs condition chart ---------- */
function AgeChart({ a, ctx }: { a: DeteriorationAssessment; ctx: DeteriorationContext }) {
  const { show, hide, node } = useTip();
  const [ref, W] = useWidth(640);
  const H = W < 480 ? 240 : 300, L = 36, R = 14, T = 10, B = 36;
  const x0 = Math.floor(Math.min(ctx.trained_range.age_years[0], a.age_years)) - 0.5;
  const x1 = Math.ceil(Math.max(ctx.trained_range.age_years[1], a.age_years)) + 0.5;
  const x = (v: number) => L + ((v - x0) / (x1 - x0)) * (W - L - R);
  const y = (v: number) => T + (1 - (v - 20) / 80) * (H - T - B);
  const curve = ctx.curve.filter((p) => p.age_years >= x0 && p.age_years <= x1);
  const step = x1 - x0 > 12 || W < 480 ? 4 : 2;
  const ticks: number[] = [];
  for (let t = Math.ceil(x0 / step) * step; t <= x1; t += step) ticks.push(t);
  const ax = x(a.age_years), ey = y(a.expected_score), oy = y(a.observed_score);
  const labelLeft = ax > W - 170;
  return (
    <div className="chart-wrap" ref={ref}>
      <svg className="det-chart" viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`Inspection score by vehicle age for ${a.vehicle_model}, with the expected curve and this vehicle`}>
        {[20, 40, 60, 80, 100].map((t) => (
          <g key={t}>
            <line className="grid" x1={L} x2={W - R} y1={y(t)} y2={y(t)} />
            <text x={L - 6} y={y(t) + 4} textAnchor="end">{t}</text>
          </g>
        ))}
        {ticks.map((t) => <text key={t} x={x(t)} y={H - 18} textAnchor="middle">{t}</text>)}
        <text x={(L + W - R) / 2} y={H - 2} textAnchor="middle">Vehicle age (years)</text>
        {ctx.points.map((p, i) => (
          <circle key={i} cx={x(p.age_years)} cy={y(p.inspection_score)} r={2.5} className="mark-history" />
        ))}
        <path className="curve" d={curve.map((p, i) => `${i ? 'L' : 'M'}${x(p.age_years).toFixed(1)} ${y(p.expected).toFixed(1)}`).join(' ')} />
        {curve.map((p) => (
          <circle key={p.age_years} cx={x(p.age_years)} cy={y(p.expected)} r={9} fill="transparent"
            onMouseMove={show(<>Age {p.age_years} yrs · {fmt(p.age_years * (a.km_per_year ?? 0), 0)} km<br />Expected condition <b>{fmt(p.expected)}</b></>)}
            onMouseLeave={hide} />
        ))}
        <line x1={ax} x2={ax} y1={ey} y2={oy} className="link" />
        <circle cx={ax} cy={ey} r={6} className="mark-expected" />
        <g onMouseMove={show(<><b>This vehicle</b><br />Age {fmt(a.age_years)} yrs · {a.odometer_km.toLocaleString()} km<br />
          Expected {fmt(a.expected_score)} · Observed {fmt(a.observed_score)}</>)} onMouseLeave={hide}>
          <circle cx={ax} cy={oy} r={12} fill="transparent" />
          <circle cx={ax} cy={oy} r={7} className="mark-observed" />
        </g>
        <text className="lbl halo" x={labelLeft ? ax - 12 : ax + 12} y={oy + (oy > ey ? 18 : -10)}
          textAnchor={labelLeft ? 'end' : 'start'}>This vehicle · {fmt(a.observed_score)}</text>
      </svg>
      {node}
    </div>
  );
}

/* ---------- real-data contextual assessment (Component 3, step 3) ---------- */
const GRADES = ['Dangerous', 'Major', 'Minor', 'Wear', 'Good'] as const;   // worst first, stacked from the bottom
const GRADE_CLASS: Record<(typeof GRADES)[number], string> = {
  Dangerous: 'g-danger', Major: 'g-major', Minor: 'g-minor', Wear: 'g-wear', Good: 'g-good',
};
const MAX_AGE = 25;

/** Condition-equivalent age as text; outside the real data it is a bound. */
function effAge(r: ContextualResult) {
  if (r.effective_age_bound === 'younger') return '< 1';
  if (r.effective_age_bound === 'older') return `> ${MAX_AGE}`;
  return fmt(r.effective_age);
}
function ageGap(r: ContextualResult) {
  if (r.effective_age_bound === 'older') return `≥ ${signed(r.age_gap)}`;
  if (r.effective_age_bound === 'younger') return `≤ ${signed(r.age_gap)}`;
  return signed(r.age_gap);
}

/** Share of comparable cars in each condition grade by age, with this car's real and effective age. */
function ConditionByAgeChart({ curve, age, effective, status }: {
  curve: NonNullable<ContextualAssessment['curve']>; age: number; effective: number; status: DeteriorationStatus;
}) {
  const { show, hide, node } = useTip();
  const [ref, W] = useWidth(640);
  const H = W < 480 ? 230 : 280, L = 40, R = 14, T = 10, B = 36;
  const x = (v: number) => L + ((v - 1) / (MAX_AGE - 1)) * (W - L - R);
  const y = (v: number) => T + (1 - v) * (H - T - B);
  const stacks = curve.map((p) => {
    let base = 0;
    return GRADES.map((g) => { const lo = base; base += p[g] ?? 0; return [lo, base] as const; });
  });
  const band = (gi: number) => {
    const upper = curve.map((p, i) => `${x(p.age_years).toFixed(1)},${y(stacks[i][gi][1]).toFixed(1)}`);
    const lower = curve.map((p, i) => `${x(p.age_years).toFixed(1)},${y(stacks[i][gi][0]).toFixed(1)}`).reverse();
    return `M${upper.join('L')}L${lower.join('L')}Z`;
  };
  const step = W < 480 ? 6 : 4;
  const ticks = Array.from({ length: Math.floor((MAX_AGE - 1) / step) + 1 }, (_, i) => 1 + i * step);
  const ax = x(Math.min(Math.max(age, 1), MAX_AGE)), ex = x(Math.min(Math.max(effective, 1), MAX_AGE));
  return (
    <div className="chart-wrap" ref={ref}>
      <svg className="det-chart ctx-chart" viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label="Share of comparable cars in each condition grade by age, with this vehicle's real and condition-equivalent age">
        {GRADES.map((g, gi) => <path key={g} d={band(gi)} className={GRADE_CLASS[g]} />)}
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line className="grid" x1={L} x2={W - R} y1={y(t)} y2={y(t)} />
            <text x={L - 6} y={y(t) + 4} textAnchor="end">{t * 100}%</text>
          </g>
        ))}
        {ticks.map((t) => <text key={t} x={x(t)} y={H - 18} textAnchor="middle">{t}</text>)}
        <text x={(L + W - R) / 2} y={H - 2} textAnchor="middle">Vehicle age (years)</text>
        {curve.map((p) => (
          <rect key={p.age_years} x={x(p.age_years) - (W - L - R) / (2 * (MAX_AGE - 1))} y={T}
            width={(W - L - R) / (MAX_AGE - 1)} height={H - T - B} fill="transparent"
            onMouseMove={show(<><b>Age {p.age_years} yrs</b><br />
              {[...GRADES].reverse().map((g) => <span key={g}>{g} {fmt((p[g] ?? 0) * 100, 0)}%<br /></span>)}</>)}
            onMouseLeave={hide} />
        ))}
        <line className="age-real" x1={ax} x2={ax} y1={T} y2={H - B} />
        <line className={`age-eff dot-${STATUS_CLASS[status]}`} x1={ex} x2={ex} y1={T} y2={H - B} />
        <text className="lbl halo" x={ax + (ax > ex ? 6 : -6)} y={T + 14} textAnchor={ax > ex ? 'start' : 'end'}>Real age</text>
        <text className="lbl halo" x={ex + (ex >= ax ? 6 : -6)} y={T + 30} textAnchor={ex >= ax ? 'start' : 'end'}>Condition age</text>
      </svg>
      {node}
    </div>
  );
}

/* ---------- second output: risk at the next inspection ---------- */
const RISK_CLASS: Record<RiskLevel, string> = { Low: 'sev-none', Elevated: 'sev-low', High: 'sev-high' };
const pct = (v: number) => `${fmt(v * 100, 0)}%`;

function RiskPill({ risk }: { risk: NextTestRisk }) {
  return <span className={`sev det-pill ${RISK_CLASS[risk.level]}`}>{risk.level} risk</span>;
}

const DECISION_CLASS: Record<DecisionKey, string> = {
  repair_now: 'sev-high', monitor: 'sev-low', plan: 'sev-low', routine: 'sev-none',
};

/** Peer status (rows) x next-test risk (columns); the car's cell is highlighted. */
function DecisionMatrix({ decision }: { decision: ContextualDecision }) {
  const cells: { key: DecisionKey; label: string; hint: string }[][] = [
    [{ key: 'monitor', label: 'Monitor', hint: 'early wear, not failing yet' },
      { key: 'repair_now', label: 'Repair now', hint: 'worn and likely to fail' }],
    [{ key: 'routine', label: 'Routine', hint: 'normal and low risk' },
      { key: 'plan', label: 'Plan maintenance', hint: 'normal for its age, but old cars fail' }],
  ];
  return (
    <div className="decision-matrix" role="table" aria-label="Decision from peer comparison and next-inspection risk">
      <span />
      <span className="dm-head" role="columnheader">Low risk next inspection</span>
      <span className="dm-head" role="columnheader">Elevated / high risk</span>
      {cells.map((row, i) => (
        <div key={i} role="row" style={{ display: 'contents' }}>
          <span className="dm-head dm-row" role="rowheader">{i === 0 ? 'Worse than comparable cars' : 'Normal for age & mileage'}</span>
          {row.map((c) => (
            <div key={c.key} role="cell" aria-current={c.key === decision.key ? 'true' : undefined}
              className={`dm-cell ${c.key === decision.key ? `on ${DECISION_CLASS[c.key]}` : ''}`}>
              <strong>{c.label}</strong><small>{c.hint}</small>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

const EVIDENCE_ROWS: [string, string][] = [
  ['A Age + mileage only', 'Age + mileage only'],
  ['B Current condition only', 'Current condition only'],
  ['C-tail Tail percentile', 'Peer percentile (output 1)'],
  ['F Ablation: E without percentile', 'Condition + age/mileage risk (output 2)'],
  ['E Combined (dual output)', 'Output 2 + peer percentile'],
];

/** Held-out evidence that "worse than peers" and "about to fail" are different signals. */
function Evidence({ evidence }: { evidence: NonNullable<ContextualAssessment['evidence']> }) {
  const rows = EVIDENCE_ROWS.filter(([k]) => evidence[k]);
  if (!rows.length) return null;
  return (
    <details className="det-evidence">
      <summary>Why two outputs?</summary>
      <p className="muted small">
        Tested on held-out UK cars against their next MOT test. Being worse than comparable cars and failing the next
        inspection are different signals: the peer percentile alone predicts failure poorly, and adding it to the
        risk model does not change the result. The percentile compares a car fairly with cars of its age; the risk
        tells whether it is likely to fail. One cannot replace the other.
      </p>
      <table>
        <thead><tr><th>Predictor of a major defect at the next test</th><th>ROC-AUC</th><th>Within same age band</th></tr></thead>
        <tbody>
          {rows.map(([k, label]) => (
            <tr key={k}><td>{label}</td><td>{fmt(evidence[k].auc, 3)}</td><td>{fmt(evidence[k].auc_within_age, 3)}</td></tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

function ContextualPanel({ a }: { a: DeteriorationAssessment }) {
  const c = a.contextual;
  if (!c) return null;
  if (!c.available || !c.overall) {
    return c.notes.length ? (
      <section className="card" style={{ marginTop: 16 }}>
        <h2>Compared with real vehicles</h2>
        {c.notes.map((n) => <p key={n} className="notice info small">{n}</p>)}
      </section>
    ) : null;
  }
  const o = c.overall;
  const status = c.status ?? o.status;
  const risk = o.next_test_risk;
  const eff = o.effective_age_bound === 'within'
    ? `a typical ${fmt(o.effective_age)}-year-old`
    : o.effective_age_bound === 'older' ? `a car older than ${MAX_AGE} years` : 'an almost new car';
  const hasRisk = c.components.some((r) => r.next_test_risk);
  return (
    <section className={`card status-card ctx-card ${c.decision ? DECISION_CLASS[c.decision.key] : STATUS_CLASS[status]}`}>
      <div className="row spread">
        <h2 style={{ margin: 0 }}>Compared with real vehicles of the same age &amp; mileage</h2>
        <span className="muted small">{fmtTime(a.created_at)}{a.latency_ms != null && ` · ${a.latency_ms} ms`}</span>
      </div>

      {c.decision && (
        <div className={`decision-banner ${DECISION_CLASS[c.decision.key]}`}>
          <strong>{c.decision.label}</strong>
          <span>{c.decision.text}</span>
        </div>
      )}

      <div className="dual-out">
        <div className="out-box">
          <div className="row spread">
            <h3>1 · Condition vs comparable cars</h3>
            <DeteriorationPill status={status} />
          </div>
          <p className="det-verdict">
            This {fmt(a.age_years)}-year-old {a.vehicle_model} is in the condition of {eff} {c.platform} driven{' '}
            {c.km_per_year?.toLocaleString()} km/year
            {o.worse_than_pct > 0
              ? <>, worse than <strong>{o.worse_than_pct}%</strong> of comparable cars.</>
              : <>; no comparable car is in a better condition.</>}
          </p>
          <div className="det-tiles det-tiles-3">
            <div><span>Condition-equivalent age</span><strong>{effAge(o)}</strong><small>real age {fmt(a.age_years)} years</small></div>
            <div><span>Age gap</span><strong className={o.age_gap > 0 ? 'ctx-worse' : 'ctx-better'}>{ageGap(o)}</strong><small>years older (+) or younger (−)</small></div>
            <div><span>Comparable cars in better condition</span><strong>{o.worse_than_pct}%</strong><small>overall: {o.observed_label}</small></div>
          </div>
        </div>

        <div className="out-box">
          <div className="row spread">
            <h3>2 · Risk at the next inspection</h3>
            {risk && <RiskPill risk={risk} />}
          </div>
          {risk ? (
            <>
              <p className="det-verdict">
                <strong>{pct(risk.probability)}</strong> chance of a major defect at the {c.risk_horizon ?? 'next inspection'}.
              </p>
              <p className="muted small" style={{ marginTop: -6 }}>Assumes defects found now are repaired.</p>
              <div className="det-tiles det-tiles-3">
                <div><span>This vehicle</span><strong>{pct(risk.probability)}</strong><small>major defect, next test</small></div>
                <div><span>Comparable cars now</span><strong>{pct(risk.comparable_defect_rate)}</strong><small>same age &amp; mileage, major defect</small></div>
                <div><span>All cars</span><strong>{pct(risk.base_rate)}</strong><small>major defect, next test</small></div>
              </div>
            </>
          ) : (
            <p className="muted small">Not available yet: the next-inspection risk model has not been trained.</p>
          )}
        </div>
      </div>

      {c.decision && (
        <>
          <h3>What to do</h3>
          <DecisionMatrix decision={c.decision} />
        </>
      )}

      <div className="row spread" style={{ marginTop: 16 }}>
        <h3 style={{ margin: 0 }}>Condition of comparable {c.platform}s by age</h3>
        <div className="det-legend">
          {[...GRADES].reverse().map((g) => <span key={g}><i className={`key-grade ${GRADE_CLASS[g]}`} />{g}</span>)}
        </div>
      </div>
      <p className="muted small" style={{ margin: '4px 0 8px' }}>
        Share of cars driven {c.km_per_year?.toLocaleString()} km/year in each MOT condition grade. The condition age is
        where this car&apos;s condition is the typical (middle) one.
      </p>
      {c.curve && <ConditionByAgeChart curve={c.curve} age={a.age_years} effective={o.effective_age} status={status} />}

      <h3>Components</h3>
      <div style={{ overflowX: 'auto' }}>
        <table>
          <thead>
            <tr>
              <th>Component</th><th>Reported</th><th>MOT grade</th><th>Better-condition cars</th><th>Condition age</th>
              <th>Gap</th><th>Vs peers</th>{hasRisk && <th>Next-test risk</th>}
            </tr>
          </thead>
          <tbody>
            {c.components.map((r) => (
              <tr key={r.component}>
                <td>{prettyComponent(r.component)}</td><td>{r.component_state}</td><td>{r.observed_label}</td>
                <td>{r.worse_than_pct}%</td><td>{effAge(r)}</td><td>{ageGap(r)}</td>
                <td><DeteriorationPill status={r.status} /></td>
                {hasRisk && (
                  <td>{r.next_test_risk ? <>{pct(r.next_test_risk.probability)} <RiskPill risk={r.next_test_risk} /></> : '—'}</td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">
        Vs peers: High = worst 10% of comparable cars, Slightly high = worst 10–25%.
        {hasRisk && ' Next-test risk: High = top 10% of cars, Elevated = top 10–25%.'} {c.method}.
      </p>
      {c.evidence && <Evidence evidence={c.evidence} />}
      {c.notes.map((n) => <p key={n} className="notice info small">{n}</p>)}
    </section>
  );
}

function verdict(a: DeteriorationAssessment) {
  const flagged = a.components.filter((c) => c.status !== 'Normal').map((c) => prettyComponent(c.component));
  const veh = `${fmt(a.age_years)}-year-old ${a.vehicle_model} with ${a.odometer_km.toLocaleString()} km`;
  if (!flagged.length) return `This ${veh} is deteriorating as expected for its age and mileage.`;
  const list = flagged.length > 2 ? `${flagged.slice(0, 2).join(', ')} and ${flagged.length - 2} more` : flagged.join(' and ');
  return `${list} ${flagged.length > 1 ? 'are' : 'is'} deteriorating faster than expected for a ${veh}.`;
}

function ObdCard({ a }: { a: DeteriorationAssessment }) {
  return (
    <section className="card">
      <h2>OBD-II evidence</h2>
      {a.obd?.reading ? (
        <>
          <p style={{ marginTop: 0 }}>
            {a.obd.anomaly
              ? <span className="sev sev-high">Unusual engine reading</span>
              : <span className="sev sev-none">Normal engine reading</span>}
            <span className="muted small"> · {a.obd_source === 'session' ? 'from the vehicle’s IoT device' : 'entered manually'}</span>
          </p>
          <table className="kv">
            <tbody>
              <tr><th>Engine RPM</th><td>{fmt(a.obd.reading.engine_rpm, 0)}</td></tr>
              <tr><th>Engine load</th><td>{fmt(a.obd.reading.engine_load)} %</td></tr>
              <tr><th>Coolant temp</th><td>{fmt(a.obd.reading.coolant_temp)} °C</td></tr>
              <tr><th>Anomaly score</th><td>{fmt(a.obd.anomaly_score, 3)}</td></tr>
            </tbody>
          </table>
          <p className="muted small">Supporting evidence; not part of the deviation score yet.</p>
        </>
      ) : (
        <p className="muted small" style={{ margin: 0 }}>
          No OBD-II reading was available. Connect the vehicle&apos;s device or enter a reading manually.
        </p>
      )}
    </section>
  );
}

// Median km/year in the training data; used until the chart context has loaded
const DEFAULT_TYPICAL_KM_PER_YEAR = 10888;

/** Inspection-data model (synthetic training data): covers every component, including those the MOT does not inspect. */
function InspectionModel({ a, ctx, withObd }: { a: DeteriorationAssessment; ctx: DeteriorationContext | null; withObd: boolean }) {
  const [showTable, setShowTable] = useState(false);
  const typicalKmPerYear = ctx?.typical_km_per_year ?? DEFAULT_TYPICAL_KM_PER_YEAR;
  const flagged = a.components.filter((c) => c.status !== 'Normal');
  const highUsage = (a.km_per_year ?? 0) > 1.3 * typicalKmPerYear;
  const status = a.legacy_status ?? a.status;
  return (
    <>
      <section className={`card status-card ${STATUS_CLASS[status]}`}>
        <div className="row spread">
          <DeteriorationPill status={status} long />
          <span className="muted small">{fmtTime(a.created_at)}{a.latency_ms != null && ` · ${a.latency_ms} ms`}</span>
        </div>
        <p className="det-verdict">{verdict(a)}</p>
        <div className="det-tiles">
          <div><span><i className="key-expected" />Expected condition</span><strong>{fmt(a.expected_score)}</strong><small>for this age &amp; mileage</small></div>
          <div><span><i className="key-observed" />Observed condition</span><strong>{fmt(a.observed_score)}</strong><small>average of {a.components.length} component{a.components.length > 1 ? 's' : ''}</small></div>
          <div><span>Worst deviation</span><strong>{signed(a.deviation)}</strong><small>{prettyComponent(a.component)}</small></div>
          <div><span>Usage</span><strong>{a.km_per_year != null ? `${fmt(a.km_per_year / 1000)}k` : '—'}</strong><small>km/year · typical {fmt(typicalKmPerYear / 1000)}k</small></div>
        </div>
        {a.warnings.map((w) => <p key={w} className="notice det-notice">{w}</p>)}
      </section>

      <div className="fault-layout" style={{ marginTop: 16 }}>
        <section className="card">
          <div className="row spread">
            <h2>Component-wise deterioration</h2>
            <div className="det-legend"><span><i className="key-expected" />Expected</span><span><i className="key-observed" />Observed</span></div>
          </div>
          <p className="muted small" style={{ margin: '4px 0 8px' }}>Condition score 0–100, worst first. Deviation = observed − expected.</p>
          <ComponentChart components={a.components} />
          <button type="button" className="link-btn small" onClick={() => setShowTable(!showTable)}>
            {showTable ? 'Hide table' : 'Show as table'}
          </button>
          {showTable && (
            <table style={{ marginTop: 8 }}>
              <thead><tr><th>Component</th><th>Reported</th><th>Expected</th><th>Observed</th><th>Deviation</th><th>Status</th></tr></thead>
              <tbody>
                {a.components.map((c) => (
                  <tr key={c.component}>
                    <td>{prettyComponent(c.component)}</td><td>{c.component_state}</td>
                    <td>{fmt(c.expected_score)}</td><td>{fmt(c.observed_score)}</td><td>{signed(c.deviation)}</td>
                    <td><DeteriorationPill status={c.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <div className="fault-side">
          <section className="card">
            <h2>Insights &amp; recommendations</h2>
            {flagged.length === 0 && (
              <div className="all-clear">
                <strong>All inspected components are within the expected range</strong>
                <p className="muted small">No component is clearly worse than expected for this age and mileage.</p>
              </div>
            )}
            {flagged.map((c) => (
              <article key={c.component} className={`issue ${STATUS_CLASS[c.status]}`}>
                <div className="row spread">
                  <h3>{prettyComponent(c.component)}</h3>
                  <DeteriorationPill status={c.status} />
                </div>
                <p className="muted small">{fmt(Math.abs(c.deviation))} points below expected · {c.reasons.join(' · ')}</p>
                {c.advice && <p><strong>Suggested:</strong> {c.advice}</p>}
              </article>
            ))}
            {highUsage && (
              <p className="notice info small">
                High usage: {a.km_per_year?.toLocaleString()} km/year vs a typical {typicalKmPerYear.toLocaleString()} km/year.
              </p>
            )}
          </section>
          {withObd && <ObdCard a={a} />}
        </div>
      </div>

      <section className="card" style={{ marginTop: 16 }}>
        <div className="row spread">
          <h2>Age vs condition</h2>
          <div className="det-legend">
            <span><i className="key-history" />Past {a.vehicle_model} inspections</span>
            <span><i className="key-line" />Expected at this usage</span>
            <span><i className="key-observed" />This vehicle</span>
          </div>
        </div>
        {ctx ? <AgeChart a={a} ctx={ctx} /> : <p className="muted small">Loading chart…</p>}
      </section>
    </>
  );
}

export function DeteriorationReport({ a, ctx }: { a: DeteriorationAssessment; ctx: DeteriorationContext | null }) {
  // The real-data assessment (two outputs) leads when it covers the vehicle; the
  // synthetic inspection-data model stays available below for every component.
  if (!a.contextual?.available) {
    return (
      <div className="det-report">
        <InspectionModel a={a} ctx={ctx} withObd />
        <ContextualPanel a={a} />
      </div>
    );
  }
  return (
    <div className="det-report">
      <ContextualPanel a={a} />
      {a.warnings.map((w) => <p key={w} className="notice det-notice">{w}</p>)}
      <div style={{ marginTop: 16 }}><ObdCard a={a} /></div>
      <details className="det-legacy">
        <summary>
          Inspection-data model, all components
          <span className="muted small"> · synthetic training data, also covers components the MOT does not inspect</span>
        </summary>
        <InspectionModel a={a} ctx={ctx} withObd={false} />
      </details>
    </div>
  );
}
