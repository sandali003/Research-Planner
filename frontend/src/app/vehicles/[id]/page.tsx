'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { FactorBars } from '@/components/FactorBars';
import { ScoreGauge } from '@/components/ScoreGauge';
import { Sparkline } from '@/components/Sparkline';
import { ApiError, api } from '@/lib/api';
import { AppShell } from '@/components/AppShell';
import { CONDITION_COLOR, fmt, fmtTime, vibrationSeries } from '@/lib/format';
import type { AssessmentListItem, AssessmentRow, LatestReadings, ManualAssessmentInputs } from '@/lib/types';

const POLL_MS = 3000;

type ManualKey = Exclude<keyof ManualAssessmentInputs, 'dtc_codes'>;
const MANUAL_FIELDS: { key: ManualKey; label: string; step: string; placeholder: string; required: boolean }[] = [
  { key: 'ds18b20_temp_c', label: 'Engine temperature (°C)', step: '0.1', placeholder: '90', required: true },
  { key: 'battery_voltage_v', label: 'Battery voltage (V)', step: '0.01', placeholder: '14.1', required: true },
  { key: 'vibration_rms_g', label: 'Vibration RMS (g)', step: '0.001', placeholder: '0.03', required: true },
  { key: 'vibration_peak_g', label: 'Vibration peak (g)', step: '0.001', placeholder: '0.15', required: true },
  { key: 'engine_rpm', label: 'Engine RPM (OBD-II)', step: '1', placeholder: '1800', required: false },
  { key: 'engine_load_pct', label: 'Engine load % (OBD-II)', step: '0.1', placeholder: '40', required: false },
];

function VehicleView({ id }: { id: number }) {
  const [readings, setReadings] = useState<LatestReadings | null>(null);
  const [latest, setLatest] = useState<AssessmentRow | null>(null);
  const [history, setHistory] = useState<AssessmentListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<'assess' | 'manual' | 'session' | 'device' | null>(null);
  const [mode, setMode] = useState<'iot' | 'manual'>('iot');
  const [manual, setManual] = useState<Record<string, string>>({});
  const [dtc, setDtc] = useState('');
  const [windowSec, setWindowSec] = useState(30);
  const [sessionCondition, setSessionCondition] = useState<'idle' | 'driving'>('idle');
  const [newKey, setNewKey] = useState<string | null>(null);

  const refreshAssessments = useCallback(async () => {
    const [l, h] = await Promise.all([api.latestAssessment(id), api.assessments(id)]);
    setLatest(l);
    setHistory(h);
  }, [id]);

  useEffect(() => {
    refreshAssessments().catch((e: Error) => setError(e.message));
  }, [refreshAssessments]);

  // Poll live readings; pause while the tab is hidden.
  useEffect(() => {
    let stop = false;
    const tick = () => {
      if (document.hidden) return;
      api.latestReadings(id, 60).then((r) => { if (!stop) setReadings(r); }).catch(() => undefined);
    };
    tick();
    const t = setInterval(tick, POLL_MS);
    return () => { stop = true; clearInterval(t); };
  }, [id]);

  async function guarded(kind: NonNullable<typeof busy>, fn: () => Promise<void>) {
    setBusy(kind);
    setError(null);
    try {
      await fn();
    } catch (err) {
      if (err instanceof ApiError && (err.status === 400 || err.status === 422) && kind === 'manual') {
        setError(`Please check the readings: ${err.message}`);
      } else if (err instanceof ApiError && err.status === 422) {
        setError('Not enough recent sensor data. Make sure the ESP32 is streaming, or increase the window.');
      } else if (err instanceof ApiError && err.status === 503) {
        setError('The AI scoring service is unavailable. Start the ML service and try again.');
      } else {
        setError(err instanceof Error ? err.message : 'Something went wrong');
      }
    } finally {
      setBusy(null);
    }
  }

  function runManual(e: FormEvent) {
    e.preventDefault();
    const inputs: Record<string, unknown> = {};
    for (const f of MANUAL_FIELDS) {
      if (manual[f.key]?.trim()) inputs[f.key] = Number(manual[f.key]);
    }
    const codes = dtc.split(/[\s,;]+/).filter(Boolean).map((c) => c.toUpperCase());
    if (codes.length) inputs.dtc_codes = codes;
    guarded('manual', async () => {
      await api.manualAssess(id, inputs as unknown as ManualAssessmentInputs);
      await refreshAssessments();
    });
  }

  const session = readings?.session ?? null;
  const live = session && !session.ended_at;
  const sensor = readings?.sensor ?? [];
  const obd = readings?.obd ?? [];
  const lastObd = obd.at(-1);
  const result = latest?.result;

  return (
    <>
      <main className="container">
        <p><Link href="/vehicles">← Vehicles</Link></p>
        <h1 style={{ margin: 0 }}>Vehicle #{id} health</h1>

        <section className="card run-card" style={{ marginTop: 16 }}>
          <div className="auth-toggle run-toggle" role="tablist">
            <button type="button" role="tab" aria-selected={mode === 'iot'} className={mode === 'iot' ? 'active' : ''}
              onClick={() => setMode('iot')}>Live IoT data</button>
            <button type="button" role="tab" aria-selected={mode === 'manual'} className={mode === 'manual' ? 'active' : ''}
              onClick={() => setMode('manual')}>Manual readings</button>
          </div>

          {mode === 'iot' ? (
            <div className="row run-row">
              <p className="muted small" style={{ flex: 1, margin: 0 }}>
                Uses the OBD-II and external sensor readings streamed by the vehicle&apos;s ESP32 during the selected window.
              </p>
              <label htmlFor="win" className="inline-label">
                Window
                <select id="win" value={windowSec} onChange={(e) => setWindowSec(Number(e.target.value))}>
                  {[10, 30, 60, 120, 300].map((s) => <option key={s} value={s}>{s}s</option>)}
                </select>
              </label>
              <button className="primary" disabled={busy !== null}
                onClick={() => guarded('assess', async () => { await api.assess(id, windowSec); await refreshAssessments(); })}>
                {busy === 'assess' ? 'Assessing…' : 'Run assessment'}
              </button>
            </div>
          ) : (
            <form onSubmit={runManual}>
              <p className="muted small">
                Enter the external sensor readings (required) and OBD-II data (optional). Empty OBD-II fields are not penalised.
              </p>
              <div className="manual-grid">
                {MANUAL_FIELDS.map((f) => (
                  <div key={f.key}>
                    <label htmlFor={f.key}>{f.label}{f.required && ' *'}</label>
                    <input id={f.key} type="number" step={f.step} placeholder={f.placeholder} required={f.required}
                      value={manual[f.key] ?? ''} onChange={(e) => setManual({ ...manual, [f.key]: e.target.value })} />
                  </div>
                ))}
                <div>
                  <label htmlFor="dtc">OBD-II fault codes</label>
                  <input id="dtc" placeholder="P0300, P0562" value={dtc} onChange={(e) => setDtc(e.target.value)} />
                </div>
              </div>
              <button className="primary" style={{ marginTop: 16 }} disabled={busy !== null}>
                {busy === 'manual' ? 'Assessing…' : 'Get prediction'}
              </button>
            </form>
          )}
        </section>
        {error && <p className="error" role="alert">{error}</p>}

        <div className="grid cols-3" style={{ marginTop: 16 }}>
          <section className="card">
            <h2>Overall health</h2>
            {result ? (
              <>
                <ScoreGauge score={result.overall} condition={result.condition} />
                <p className="muted small" style={{ textAlign: 'center' }}>
                  {latest && fmtTime(latest.created_at)}{latest?.latency_ms != null && ` · ${latest.latency_ms} ms`}
                </p>
              </>
            ) : <p className="muted">No assessment yet. Stream some data or enter readings manually, then run an assessment.</p>}
          </section>

          <section className="card" style={{ gridColumn: 'span 2' }}>
            <h2>Why this score? (explainable AI)</h2>
            {result ? (
              <>
                <FactorBars factors={result.factors} />
                <p className="explain" style={{ marginTop: 16 }}>{result.explanation}</p>
              </>
            ) : <p className="muted">Explanations appear after the first assessment.</p>}
          </section>
        </div>

        <div className="grid cols-2" style={{ marginTop: 16 }}>
          <section className="card">
            <div className="row spread">
              <h2 style={{ margin: 0 }}>Live sensors</h2>
              <span className="small" style={{ color: live ? 'var(--good)' : 'var(--muted)' }}>
                {live ? `● session #${session.id} (${session.condition})` : '○ no active session'}
              </span>
            </div>
            <div className="grid" style={{ marginTop: 12 }}>
              <Sparkline title="Engine temperature" unit="°C" values={sensor.map((s) => s.temp_c)} color="var(--poor)" />
              <Sparkline title="Battery voltage" unit="V" values={sensor.map((s) => s.voltage_v)} color="var(--accent)" digits={2} />
              <Sparkline title="Vibration (gravity removed)" unit="g" values={vibrationSeries(sensor)} color="#9333ea" digits={3} />
            </div>
          </section>

          <section className="card">
            <h2>OBD-II &amp; session control</h2>
            {lastObd ? (
              <table>
                <tbody>
                  <tr><th>RPM</th><td>{fmt(lastObd.rpm, 0)}</td></tr>
                  <tr><th>Engine load</th><td>{fmt(lastObd.engine_load)} %</td></tr>
                  <tr><th>Coolant</th><td>{fmt(lastObd.coolant_temp)} °C</td></tr>
                  <tr><th>Fault codes</th><td>{lastObd.dtc_codes.length ? lastObd.dtc_codes.join(', ') : 'None'}</td></tr>
                </tbody>
              </table>
            ) : <p className="muted small">No OBD-II data received yet.</p>}

            <div className="row" style={{ marginTop: 16 }}>
              <select style={{ width: 'auto' }} value={sessionCondition} onChange={(e) => setSessionCondition(e.target.value as 'idle' | 'driving')}>
                <option value="idle">Idle</option>
                <option value="driving">Driving</option>
              </select>
              <button disabled={busy !== null}
                onClick={() => guarded('session', async () => { await api.startSession(id, sessionCondition); })}>
                Start new session
              </button>
              {live && (
                <button disabled={busy !== null}
                  onClick={() => guarded('session', async () => { await api.stopSession(session.id); })}>
                  Stop session
                </button>
              )}
            </div>

            <div style={{ marginTop: 16 }}>
              <button disabled={busy !== null}
                onClick={() => guarded('device', async () => { setNewKey((await api.createDevice(id, 'esp32')).api_key); })}>
                Register ESP32 device
              </button>
              {newKey && (
                <p className="notice" style={{ marginTop: 10 }}>
                  Device key (copy now — it won&apos;t be shown again):<br /><code style={{ wordBreak: 'break-all' }}>{newKey}</code>
                </p>
              )}
            </div>
          </section>
        </div>

        <section className="card" style={{ marginTop: 16 }}>
          <h2>Assessment history</h2>
          {history.length === 0 ? <p className="muted">None yet.</p> : (
            <table>
              <thead><tr><th>When</th><th>Source</th><th>Score</th><th>Condition</th><th>Latency</th></tr></thead>
              <tbody>
                {history.map((a) => (
                  <tr key={a.id}>
                    <td>{fmtTime(a.created_at)}</td>
                    <td>{a.session_id == null ? 'Manual' : 'IoT'}</td>
                    <td>{fmt(a.overall_score)}</td>
                    <td><span className="pill" style={{ background: CONDITION_COLOR[a.condition] }}>{a.condition}</span></td>
                    <td>{a.latency_ms != null ? `${a.latency_ms} ms` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      </main>
    </>
  );
}

export default function VehiclePage({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  return <AppShell>{Number.isInteger(id) && id > 0 ? <VehicleView id={id} /> : <p className="container">Invalid vehicle id.</p>}</AppShell>;
}
