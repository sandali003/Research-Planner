'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { AppShell } from '@/components/AppShell';
import { DeteriorationPill, DeteriorationReport, prettyComponent } from '@/components/DeteriorationReport';
import { api, ApiError } from '@/lib/api';
import { fmt, fmtTime } from '@/lib/format';
import type {
  ComponentCheck, ComponentState, DecisionKey, DeteriorationAssessment, DeteriorationContext, DeteriorationInput,
  DeteriorationListItem, FuelType, Vehicle,
} from '@/lib/types';

const DECISION_LABEL: Record<DecisionKey, string> = {
  repair_now: 'Repair now', monitor: 'Monitor', plan: 'Plan maintenance', routine: 'Routine',
};

// Components and states the Component 3 models were trained on
const COMPONENTS = ['Battery', 'Brakes', 'Cooling_System', 'Engine', 'Exhaust_System', 'Steering', 'Suspension', 'Transmission', 'Tyres'];
const STATES: ComponentState[] = ['Good', 'Fair', 'Poor', 'Critical'];
const EXAMPLE: Record<string, ComponentState> = {
  Brakes: 'Poor', Battery: 'Critical', Engine: 'Fair', Tyres: 'Good', Suspension: 'Fair', Cooling_System: 'Good',
};

const OBD_FIELDS = [
  { key: 'engine_rpm', label: 'Engine RPM', step: '1', placeholder: '2000' },
  { key: 'engine_load', label: 'Engine load (%)', step: '0.1', placeholder: '55' },
  { key: 'coolant_temp', label: 'Coolant temp (°C)', step: '0.1', placeholder: '88' },
] as const;

const vehicleName = (v: Vehicle) => [v.make, v.model].filter(Boolean).join(' ') || `Vehicle #${v.id}`;
const vehicleAge = (year: number) => Math.max(0, (Date.now() - Date.UTC(year, 6, 1)) / (365.25 * 24 * 3600 * 1000));

function errorText(e: unknown) {
  if (e instanceof ApiError && e.details && typeof e.details === 'object' && 'unknown_components' in e.details) {
    return `${e.message}: check the component names.`;
  }
  return e instanceof Error ? e.message : 'Assessment failed';
}

function DeteriorationView() {
  const [vehicles, setVehicles] = useState<Vehicle[] | null>(null);
  const [vehicleId, setVehicleId] = useState<number | null>(null);
  const [result, setResult] = useState<DeteriorationAssessment | null>(null);
  const [ctx, setCtx] = useState<DeteriorationContext | null>(null);
  const [history, setHistory] = useState<DeteriorationListItem[]>([]);

  const [odometer, setOdometer] = useState('');
  const [age, setAge] = useState('');
  const [fuel, setFuel] = useState<FuelType | ''>('');
  const [engineCc, setEngineCc] = useState('');
  const [states, setStates] = useState<Record<string, ComponentState | ''>>({});
  const [obdMode, setObdMode] = useState<'iot' | 'manual'>('iot');
  const [obd, setObd] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const vehicle = vehicles?.find((v) => v.id === vehicleId) ?? null;

  useEffect(() => {
    api.vehicles().then((list) => {
      setVehicles(list);
      if (list.length) setVehicleId(list[0].id);
    }).catch((e: Error) => setError(e.message));
  }, []);

  const show = useCallback(async (vid: number, a: DeteriorationAssessment | null) => {
    setResult(a);
    setCtx(null);
    if (a) setCtx(await api.deteriorationContext(vid, a.id).catch(() => null));
  }, []);

  const loadVehicle = useCallback(async (vid: number) => {
    setError(null);
    try {
      const [latest, list] = await Promise.all([api.latestDeterioration(vid), api.deteriorations(vid)]);
      setHistory(list);
      if (latest) setOdometer(String(latest.odometer_km));
      await show(vid, latest);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load results');
    }
  }, [show]);

  useEffect(() => {
    if (!vehicleId) return;
    setAge('');
    setOdometer('');
    loadVehicle(vehicleId);
  }, [vehicleId, loadVehicle]);

  const checks: ComponentCheck[] = COMPONENTS
    .filter((c) => states[c])
    .map((c) => ({ component: c, component_state: states[c] as ComponentState }));

  const autoAge = vehicle?.year ? vehicleAge(vehicle.year) : null;
  const ageValue = age.trim() ? Number(age) : autoAge;
  const kmPerYear = ageValue != null && Number(odometer) > 0 ? Number(odometer) / Math.max(ageValue, 1) : null;

  async function run(e: FormEvent) {
    e.preventDefault();
    if (!vehicleId) return;
    if (!checks.length) { setError('Set the state of at least one inspected component.'); return; }
    if (ageValue == null) { setError('This vehicle has no year. Enter its age in years.'); return; }

    const input: DeteriorationInput = { odometer_km: Number(odometer), components: checks };
    if (age.trim()) input.age_years = Number(age);
    if (fuel) input.fuel_type = fuel;
    if (engineCc.trim()) input.engine_cc = Number(engineCc);
    if (obdMode === 'manual') {
      const vals = OBD_FIELDS.map((f) => obd[f.key]?.trim() ?? '');
      if (vals.some((v) => !v)) { setError('Fill in all three OBD-II values, or switch to Live IoT data.'); return; }
      input.obd = { engine_rpm: Number(vals[0]), engine_load: Number(vals[1]), coolant_temp: Number(vals[2]) };
    }

    setBusy(true);
    setError(null);
    try {
      const a = await api.assessDeterioration(vehicleId, input);
      setHistory(await api.deteriorations(vehicleId));
      await show(vehicleId, a);
      document.getElementById('det-result')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  }

  async function openAssessment(id: number) {
    if (!vehicleId) return;
    try {
      await show(vehicleId, await api.deteriorationById(vehicleId, id));
      document.getElementById('det-result')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load assessment');
    }
  }

  return (
    <main className="container">
      <div className="page-head row spread">
        <div>
          <h1>Age &amp; Mileage Deterioration</h1>
          <p className="muted">Is this vehicle wearing out faster than others of the same age and mileage?</p>
        </div>
        {vehicles && vehicles.length > 0 && (
          <label className="vehicle-select">
            Vehicle
            <select value={vehicleId ?? ''} onChange={(e) => setVehicleId(Number(e.target.value))}>
              {vehicles.map((v) => <option key={v.id} value={v.id}>{vehicleName(v)}{v.year ? ` (${v.year})` : ''}</option>)}
            </select>
          </label>
        )}
      </div>

      {vehicles === null ? <p className="muted">Loading…</p> : vehicles.length === 0 ? (
        <section className="card empty-state">
          <h2>No vehicles yet</h2>
          <p className="muted">Add a vehicle first, then run a deterioration assessment. <Link href="/vehicles">Add vehicle →</Link></p>
        </section>
      ) : (
        <>
          <form className="det-form" onSubmit={run}>
            <section className="card">
              <h2><span className="det-step">1</span>Vehicle profile</h2>
              <p className="muted small">Age and mileage set the condition expected for this vehicle.</p>
              <div className="det-profile">
                <div>
                  <label htmlFor="det-odo">Odometer (km)</label>
                  <input id="det-odo" type="number" min={0} max={2000000} required placeholder="150000"
                    value={odometer} onChange={(e) => setOdometer(e.target.value)} />
                </div>
                <div>
                  <label htmlFor="det-age">Age (years)</label>
                  <input id="det-age" type="number" min={0} max={60} step={0.1}
                    placeholder={autoAge != null ? `${fmt(autoAge)} (from ${vehicle?.year})` : 'e.g. 9'}
                    value={age} onChange={(e) => setAge(e.target.value)} />
                </div>
                <div>
                  <label htmlFor="det-fuel">Fuel</label>
                  <select id="det-fuel" value={fuel} onChange={(e) => setFuel(e.target.value as FuelType | '')}>
                    <option value="">Petrol (default)</option>
                    <option value="petrol">Petrol</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="diesel">Diesel</option>
                  </select>
                </div>
                <div>
                  <label htmlFor="det-cc">Engine (cc)</label>
                  <input id="det-cc" type="number" min={600} max={5000} step={1} placeholder="e.g. 1500"
                    value={engineCc} onChange={(e) => setEngineCc(e.target.value)} />
                </div>
              </div>
              <p className="muted small det-usage">
                Model: <strong>{vehicle?.model ?? '—'}</strong>
                {kmPerYear != null && <> · Usage ≈ <strong>{Math.round(kmPerYear).toLocaleString()} km/year</strong></>}
              </p>
            </section>

            <section className="card">
              <div className="row spread">
                <h2><span className="det-step">2</span>Inspection evidence</h2>
                <button type="button" className="link-btn small" onClick={() => setStates(EXAMPLE)}>Load example</button>
              </div>
              <p className="muted small">Set each inspected component. Leave “—” for components not inspected.</p>
              <div className="det-checklist">
                {COMPONENTS.map((c) => (
                  <div key={c} className="det-check">
                    <span>{prettyComponent(c)}</span>
                    <div className="det-seg" role="radiogroup" aria-label={`${prettyComponent(c)} state`}>
                      {(['', ...STATES] as const).map((s) => (
                        <button key={s || 'none'} type="button" role="radio" aria-checked={(states[c] ?? '') === s}
                          className={`${(states[c] ?? '') === s ? 'on' : ''} ${s === 'Poor' || s === 'Critical' ? 'bad' : ''}`}
                          onClick={() => setStates({ ...states, [c]: s })}>
                          {s || '—'}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="card">
              <h2><span className="det-step">3</span>OBD-II reading</h2>
              <div className="auth-toggle run-toggle" role="tablist">
                <button type="button" role="tab" aria-selected={obdMode === 'iot'} className={obdMode === 'iot' ? 'active' : ''}
                  onClick={() => setObdMode('iot')}>Live IoT data</button>
                <button type="button" role="tab" aria-selected={obdMode === 'manual'} className={obdMode === 'manual' ? 'active' : ''}
                  onClick={() => setObdMode('manual')}>Manual reading</button>
              </div>
              {obdMode === 'iot' ? (
                <p className="muted small" style={{ margin: 0 }}>
                  Uses the vehicle device&apos;s OBD-II readings from the last 30 minutes, if there are any.
                </p>
              ) : (
                <div className="manual-grid det-obd">
                  {OBD_FIELDS.map((f) => (
                    <div key={f.key}>
                      <label htmlFor={`obd-${f.key}`}>{f.label}</label>
                      <input id={`obd-${f.key}`} type="number" step={f.step} placeholder={f.placeholder}
                        value={obd[f.key] ?? ''} onChange={(e) => setObd({ ...obd, [f.key]: e.target.value })} />
                    </div>
                  ))}
                </div>
              )}
              <p className="muted small" style={{ marginBottom: 0 }}>Supporting evidence; shown with the result.</p>
            </section>

            <div className="row spread det-run">
              <span className="muted small">{checks.length} component{checks.length === 1 ? '' : 's'} selected</span>
              <button className="primary" disabled={busy}>{busy ? 'Assessing…' : 'Run assessment'}</button>
            </div>
            {error && <p className="error" role="alert">{error}</p>}
          </form>

          <h2 className="section-title" id="det-result">Result</h2>
          {result ? <DeteriorationReport a={result} ctx={ctx} /> : (
            <section className="card empty-state">
              <h2>No assessment yet</h2>
              <p className="muted">Fill in the odometer and inspection evidence, then run an assessment.</p>
            </section>
          )}

          <h2 className="section-title">Assessment history</h2>
          <section className="card">
            {history.length === 0 ? <p className="muted" style={{ margin: 0 }}>No assessments yet.</p> : (
              <div style={{ overflowX: 'auto' }}>
                <table>
                  <thead><tr><th>Time</th><th>Odometer</th><th>Worst component</th><th>Condition age</th><th>Better-condition cars</th><th>Vs peers</th><th>Next-test risk</th><th>Decision</th><th>OBD</th><th /></tr></thead>
                  <tbody>
                    {history.map((h) => (
                      <tr key={h.id} className={result?.id === h.id ? 'selected' : undefined}>
                        <td>{fmtTime(h.created_at)}</td>
                        <td>{h.odometer_km.toLocaleString()} km</td>
                        <td>{prettyComponent(h.worst_component)}</td>
                        <td>{h.effective_age != null
                          ? `${fmt(h.effective_age)} (${h.age_gap != null && h.age_gap > 0 ? '+' : ''}${fmt(h.age_gap ?? 0)})`
                          : '—'}</td>
                        <td>{h.worse_than_pct != null ? `${h.worse_than_pct}%` : '—'}</td>
                        <td><DeteriorationPill status={h.status} /></td>
                        <td>{h.next_test_risk != null ? `${fmt(h.next_test_risk * 100, 0)}%` : '—'}</td>
                        <td>{h.decision ? DECISION_LABEL[h.decision] : '—'}</td>
                        <td>{h.obd_source === 'session' ? 'IoT' : h.obd_source === 'request' ? 'Manual' : '—'}</td>
                        <td><button type="button" className="link-btn" onClick={() => openAssessment(h.id)}>View</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}

export default function DeteriorationPage() {
  return <AppShell><DeteriorationView /></AppShell>;
}
