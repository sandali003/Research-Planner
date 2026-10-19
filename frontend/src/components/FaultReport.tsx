import { fmt, fmtTime } from '@/lib/format';
import type { FaultInputs, FaultIssue, FaultResult, Severity, ShapExplanation } from '@/lib/types';

export const SEVERITY_CLASS: Record<Severity, string> = {
  High: 'sev-high',
  Medium: 'sev-medium',
  Low: 'sev-low',
  None: 'sev-none',
};

export function SeverityPill({ severity }: { severity: Severity }) {
  return <span className={`sev ${SEVERITY_CLASS[severity]}`}>{severity === 'None' ? 'No risk' : `${severity} severity`}</span>;
}

/** A check from the API, in one shape for both new and stored checks. */
export interface FaultCheckView {
  id: number;
  source: 'iot' | 'manual';
  created_at: string;
  latency_ms: number | null;
  features: FaultInputs;
  result: FaultResult;
}

const MODEL_LABEL: Record<string, string> = {
  fault_classifier: 'XGBoost classifier',
  obd_rules_and_anomaly: 'Rules + anomaly model',
};

/** SHAP diverging bars: positive impact (towards the fault / abnormal) grows right in red. */
function ShapBars({ explanation, title }: { explanation: ShapExplanation; title: string }) {
  const max = Math.max(...explanation.factors.map((f) => Math.abs(f.impact)), 1e-9);
  return (
    <div className="shap-block">
      <h3>{title}</h3>
      <p className="muted small">{explanation.method} · red pushes towards the result, blue pushes away</p>
      {explanation.factors.map((f) => {
        const widthPct = (Math.abs(f.impact) / max) * 50;
        const negative = f.impact < 0;
        return (
          <div key={f.feature} className="bar-row">
            <span>{f.label} <span className="muted small">({fmt(f.value, 2)})</span></span>
            <div className="bar-track" role="img"
              aria-label={`${f.label} ${negative ? 'pushes away from' : 'pushes towards'} the result by ${Math.abs(f.impact).toFixed(2)}`}>
              <div className="bar-mid" />
              <div className="bar-fill" style={{
                width: `${widthPct}%`,
                left: negative ? `${50 - widthPct}%` : '50%',
                background: negative ? 'var(--accent-light)' : 'var(--critical)',
              }} />
            </div>
            <span className="shap-value">{f.impact > 0 ? '+' : ''}{f.impact.toFixed(2)}</span>
          </div>
        );
      })}
    </div>
  );
}

function IssueCard({ issue }: { issue: FaultIssue }) {
  const targeted = new Set(issue.targeted_actions ?? []);
  const mainCauses = (issue.key_factors ?? []).filter((f) => f.impact > 0).slice(0, 2);
  return (
    <article className={`issue ${SEVERITY_CLASS[issue.severity]}`}>
      <div className="row spread">
        <h3>{issue.display_name}</h3>
        <SeverityPill severity={issue.severity} />
      </div>
      <div className="issue-meta">
        {issue.sources.map((s) => <span key={s} className="chip">{s}</span>)}
        {issue.confidence != null && <span className="chip">Confidence {(issue.confidence * 100).toFixed(0)}%</span>}
        <span className="chip chip-time">Act: {issue.timeframe}</span>
      </div>
      <p>{issue.message}</p>
      {issue.reasons.length > 0 && (
        <p className="muted small">Why: {issue.reasons.join(' · ')}</p>
      )}
      {mainCauses.length > 0 && (
        <p className="small main-cause">
          Main cause (SHAP): {mainCauses.map((f) => `${f.label} ${fmt(f.value, 2)}`).join(', ')}
        </p>
      )}
      <h4>Immediate actions</h4>
      <ul>
        {issue.immediate_actions.map((a) => (
          <li key={a} className={targeted.has(a) ? 'targeted' : undefined}>
            {targeted.has(a) && <span className="chip chip-target">Based on main cause</span>} {a}
          </li>
        ))}
      </ul>
      {issue.notes.map((n) => <p key={n} className="muted small">⚠️ {n}</p>)}
    </article>
  );
}

function Readings({ f }: { f: FaultInputs }) {
  const rows: [string, string][] = [
    ['Engine RPM', fmt(f.engine_rpm, 0)],
    ['Engine load', f.engine_load_pct == null ? '—' : `${fmt(f.engine_load_pct)} %`],
    ['Coolant temp', f.coolant_temp_c == null ? '—' : `${fmt(f.coolant_temp_c)} °C`],
    ['Engine temp (DS18B20)', f.ds18b20_temp_c == null ? '—' : `${fmt(f.ds18b20_temp_c)} °C`],
    ['Battery voltage', f.battery_voltage_v == null ? '—' : `${fmt(f.battery_voltage_v, 2)} V`],
    ['Vibration X / Y / Z', [f.vibration_x_g, f.vibration_y_g, f.vibration_z_g].every((v) => v == null)
      ? '—' : `${fmt(f.vibration_x_g, 2)} / ${fmt(f.vibration_y_g, 2)} / ${fmt(f.vibration_z_g, 2)} g`],
    ['Trouble codes', f.dtc_codes?.length ? f.dtc_codes.join(', ') : 'None'],
  ];
  return (
    <table className="kv">
      <tbody>{rows.map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}</tbody>
    </table>
  );
}

export function FaultReport({ check }: { check: FaultCheckView }) {
  const r = check.result;
  const ok = r.issues.length === 0;

  return (
    <div className="fault-report">
      <div className="grid cols-3">
        <div className={`card stat status-card ${SEVERITY_CLASS[r.overall_severity]}`}>
          <span className="muted small">Overall result</span>
          <strong>{ok ? 'No hidden faults' : `${r.issues.length} issue${r.issues.length > 1 ? 's' : ''} found`}</strong>
          <SeverityPill severity={r.overall_severity} />
          <span className="muted small">{r.timeframe}</span>
        </div>
        <div className="card stat">
          <span className="muted small">AI anomaly check</span>
          {r.anomaly ? (
            <>
              <strong>{r.anomaly.is_anomaly ? 'Unusual pattern' : 'Looks healthy'}</strong>
              <span className="muted small">Score {fmt(r.anomaly.score, 2)} (flag above {fmt(r.anomaly.threshold, 2)})</span>
            </>
          ) : <strong>Not run</strong>}
          {r.classifier && (
            <span className="muted small">
              Classifier: {r.classifier.prediction.replace(/_/g, ' ')} ({(r.classifier.confidence * 100).toFixed(0)}%)
            </span>
          )}
        </div>
        <div className="card stat">
          <span className="muted small">Assessment</span>
          <strong>{check.latency_ms != null ? `${check.latency_ms} ms` : '—'}</strong>
          <span className="muted small">{check.source === 'iot' ? 'Live IoT + OBD-II data' : 'Manual readings'} · {fmtTime(check.created_at)}</span>
          <span className="muted small">Models: {r.models_used.map((m) => MODEL_LABEL[m] ?? m).join(', ')}</span>
        </div>
      </div>

      <div className="fault-layout">
        <section className="card">
          <h2>Detected issues & mitigation plan</h2>
          {ok ? (
            <div className="all-clear">
              <strong>✓ No hidden fault patterns found</strong>
              <p className="muted small">The rule checks and AI models did not find any warning signs in these readings.</p>
            </div>
          ) : r.issues.map((issue) => <IssueCard key={issue.fault} issue={issue} />)}
          {r.notes.map((n) => <p key={n} className="notice info" style={{ marginTop: 10 }}>{n}</p>)}
        </section>

        <div className="fault-side">
          <section className="card">
            <h2>Longevity tips</h2>
            <ul className="tips">{r.longevity_tips.map((t) => <li key={t}>{t}</li>)}</ul>
          </section>
          <section className="card">
            <h2>Readings used</h2>
            <Readings f={check.features} />
          </section>
        </div>
      </div>

      {(r.explanations?.classifier || r.explanations?.anomaly) && (
        <section className="card" style={{ marginTop: 16 }}>
          <h2>Why this prediction (SHAP)</h2>
          <div className="grid cols-2">
            {r.explanations.classifier && (
              <ShapBars explanation={r.explanations.classifier}
                title={`Fault classifier → ${r.explanations.classifier.target.replace(/_/g, ' ')}`} />
            )}
            {r.explanations.anomaly && (
              <ShapBars explanation={r.explanations.anomaly} title="Anomaly model → anomaly score" />
            )}
          </div>
        </section>
      )}

      {r.reasoning && (
        <section className="card" style={{ marginTop: 16 }}>
          <h2>How the plan was made (expert system)</h2>
          <p className="muted small">
            {r.engine?.name ?? 'Expert system'} · {r.reasoning.length} rule{r.reasoning.length === 1 ? '' : 's'} fired,
            in order: detection → AI fusion → severity → mitigation.
          </p>
          {r.reasoning.length === 0 ? <p className="muted small">No rules fired: all readings were within normal limits.</p> : (
            <ol className="trace">
              {r.reasoning.map((t, i) => (
                <li key={i}><strong>{t.rule}</strong> <span className="muted">— {t.because}</span></li>
              ))}
            </ol>
          )}
        </section>
      )}
    </div>
  );
}
