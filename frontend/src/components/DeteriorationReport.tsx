'use client';

import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react';
import { fmt, fmtTime } from '@/lib/format';
import type {
  DeteriorationAssessment, DeteriorationComponent, DeteriorationContext, DeteriorationStatus,
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

function verdict(a: DeteriorationAssessment) {
  const flagged = a.components.filter((c) => c.status !== 'Normal').map((c) => prettyComponent(c.component));
  const veh = `${fmt(a.age_years)}-year-old ${a.vehicle_model} with ${a.odometer_km.toLocaleString()} km`;
  if (!flagged.length) return `This ${veh} is deteriorating as expected for its age and mileage.`;
  const list = flagged.length > 2 ? `${flagged.slice(0, 2).join(', ')} and ${flagged.length - 2} more` : flagged.join(' and ');
  return `${list} ${flagged.length > 1 ? 'are' : 'is'} deteriorating faster than expected for a ${veh}.`;
}

// Median km/year in the training data; used until the chart context has loaded
const DEFAULT_TYPICAL_KM_PER_YEAR = 10888;

export function DeteriorationReport({ a, ctx }: { a: DeteriorationAssessment; ctx: DeteriorationContext | null }) {
  const [showTable, setShowTable] = useState(false);
  const typicalKmPerYear = ctx?.typical_km_per_year ?? DEFAULT_TYPICAL_KM_PER_YEAR;
  const flagged = a.components.filter((c) => c.status !== 'Normal');
  const highUsage = (a.km_per_year ?? 0) > 1.3 * typicalKmPerYear;
  return (
    <div className="det-report">
      <section className={`card status-card ${STATUS_CLASS[a.status]}`}>
        <div className="row spread">
          <DeteriorationPill status={a.status} long />
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

      <div className="fault-layout">
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
    </div>
  );
}
