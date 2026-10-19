'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { AppShell } from '@/components/AppShell';
import { FaultReport, SeverityPill, type FaultCheckView } from '@/components/FaultReport';
import { api } from '@/lib/api';
import { fmtTime } from '@/lib/format';
import type { FaultCheck, FaultCheckListItem, FaultCheckRow, FaultInputs, Vehicle } from '@/lib/types';

const WINDOWS = [30, 60, 120];

const MANUAL_FIELDS: { key: keyof FaultInputs; label: string; step: string; placeholder: string }[] = [
  { key: 'engine_rpm', label: 'Engine RPM', step: '1', placeholder: '1800' },
  { key: 'engine_load_pct', label: 'Engine load (%)', step: '0.1', placeholder: '45' },
  { key: 'coolant_temp_c', label: 'Coolant temp (°C)', step: '0.1', placeholder: '88' },
  { key: 'battery_voltage_v', label: 'Battery voltage (V)', step: '0.01', placeholder: '14.1' },
  { key: 'vibration_x_g', label: 'Vibration X (g)', step: '0.01', placeholder: '0.05' },
  { key: 'vibration_y_g', label: 'Vibration Y (g)', step: '0.01', placeholder: '0.05' },
  { key: 'vibration_z_g', label: 'Vibration Z (g)', step: '0.01', placeholder: '0.05' },
];

const fromNew = (c: FaultCheck): FaultCheckView => ({
  id: c.id, source: c.source, created_at: c.created_at, latency_ms: c.latency_ms, features: c.features, result: c,
});
const fromRow = (c: FaultCheckRow): FaultCheckView => ({
  id: c.id, source: c.source, created_at: c.created_at, latency_ms: c.latency_ms, features: c.features, result: c.result,
});

const vehicleName = (v: Vehicle) => [v.make, v.model].filter(Boolean).join(' ') || `Vehicle #${v.id}`;

function HiddenFaultView() {
  const [vehicles, setVehicles] = useState<Vehicle[] | null>(null);
  const [vehicleId, setVehicleId] = useState<number | null>(null);
  const [check, setCheck] = useState<FaultCheckView | null>(null);
  const [history, setHistory] = useState<FaultCheckListItem[]>([]);
  const [mode, setMode] = useState<'iot' | 'manual'>('iot');
  const [windowSeconds, setWindowSeconds] = useState(60);
  const [manual, setManual] = useState<Record<string, string>>({});
  const [dtc, setDtc] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.vehicles().then((list) => {
      setVehicles(list);
      if (list.length) setVehicleId(list[0].id);
    }).catch((e: Error) => setError(e.message));
  }, []);

  const loadVehicle = useCallback(async (id: number) => {
    setError(null);
    try {
      const [latest, list] = await Promise.all([api.latestFaultCheck(id), api.faultChecks(id)]);
      setCheck(latest ? fromRow(latest) : null);
      setHistory(list);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load results');
    }
  }, []);

  useEffect(() => { if (vehicleId) loadVehicle(vehicleId); }, [vehicleId, loadVehicle]);

  async function run(fn: () => Promise<FaultCheck>) {
    if (!vehicleId) return;
    setBusy(true);
    setError(null);
    try {
      setCheck(fromNew(await fn()));
      setHistory(await api.faultChecks(vehicleId));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Check failed');
    } finally {
      setBusy(false);
    }
  }

  function runManual(e: FormEvent) {
    e.preventDefault();
    const inputs: FaultInputs = {};
    for (const f of MANUAL_FIELDS) {
      if (manual[f.key]?.trim()) (inputs as Record<string, number>)[f.key] = Number(manual[f.key]);
    }
    const codes = dtc.split(/[\s,]+/).filter(Boolean).map((c) => c.toUpperCase());
    if (codes.length) inputs.dtc_codes = codes;
    run(() => api.manualFaultCheck(vehicleId!, inputs));
  }

  async function openCheck(id: number) {
    if (!vehicleId) return;
    try {
      setCheck(fromRow(await api.faultCheckById(vehicleId, id)));
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load check');
    }
  }

  return (
    <main className="container">
      <div className="page-head row spread">
        <div>
          <h1>Hidden Fault & Mitigation</h1>
          <p className="muted">Predict hidden faults early and get a clear plan to fix them and keep your vehicle healthy.</p>
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

      {error && <p className="error" role="alert">{error}</p>}

      {vehicles === null ? <p className="muted">Loading…</p> : vehicles.length === 0 ? (
        <section className="card empty-state">
          <h2>No vehicles yet</h2>
          <p className="muted">Add a vehicle first, then run a hidden fault check. <Link href="/vehicles">Add vehicle →</Link></p>
        </section>
      ) : (
        <>
          <section className="card run-card">
            <div className="auth-toggle run-toggle" role="tablist">
              <button type="button" role="tab" aria-selected={mode === 'iot'} className={mode === 'iot' ? 'active' : ''}
                onClick={() => setMode('iot')}>Live IoT data</button>
              <button type="button" role="tab" aria-selected={mode === 'manual'} className={mode === 'manual' ? 'active' : ''}
                onClick={() => setMode('manual')}>Manual readings</button>
            </div>

            {mode === 'iot' ? (
              <div className="row run-row">
                <p className="muted small" style={{ flex: 1, margin: 0 }}>
                  Uses the latest OBD-II and IoT sensor readings (vibration, temperature, battery voltage) sent by the vehicle&apos;s device.
                </p>
                <label className="inline-label">
                  Data window
                  <select value={windowSeconds} onChange={(e) => setWindowSeconds(Number(e.target.value))}>
                    {WINDOWS.map((w) => <option key={w} value={w}>Last {w} s</option>)}
                  </select>
                </label>
                <button className="primary" disabled={busy} onClick={() => run(() => api.faultCheck(vehicleId!, windowSeconds))}>
                  {busy ? 'Checking…' : 'Run hidden fault check'}
                </button>
              </div>
            ) : (
              <form onSubmit={runManual}>
                <p className="muted small">Fill in the readings you have. Leave a field empty if it is not available.</p>
                <div className="manual-grid">
                  {MANUAL_FIELDS.map((f) => (
                    <div key={f.key}>
                      <label htmlFor={f.key}>{f.label}</label>
                      <input id={f.key} type="number" step={f.step} placeholder={f.placeholder}
                        value={manual[f.key] ?? ''} onChange={(e) => setManual({ ...manual, [f.key]: e.target.value })} />
                    </div>
                  ))}
                  <div>
                    <label htmlFor="dtc">Trouble codes (optional)</label>
                    <input id="dtc" placeholder="P0301, P0171" value={dtc} onChange={(e) => setDtc(e.target.value)} />
                  </div>
                </div>
                <button className="primary" style={{ marginTop: 16 }} disabled={busy}>
                  {busy ? 'Checking…' : 'Run hidden fault check'}
                </button>
              </form>
            )}
          </section>

          {check ? <FaultReport check={check} /> : (
            <section className="card empty-state" style={{ marginTop: 16 }}>
              <h2>No checks yet</h2>
              <p className="muted">Run a hidden fault check to see predicted faults and a mitigation plan.</p>
            </section>
          )}

          <h2 className="section-title">Check history</h2>
          <section className="card">
            {history.length === 0 ? <p className="muted">No checks yet.</p> : (
              <table>
                <thead><tr><th>Time</th><th>Data</th><th>Result</th><th>Severity</th><th>Latency</th><th /></tr></thead>
                <tbody>
                  {history.map((h) => (
                    <tr key={h.id} className={check?.id === h.id ? 'selected' : undefined}>
                      <td>{fmtTime(h.created_at)}</td>
                      <td>{h.source === 'iot' ? 'IoT' : 'Manual'}</td>
                      <td>{h.primary_fault === 'Normal' ? 'No fault' : h.primary_fault.replace(/_/g, ' ')}</td>
                      <td><SeverityPill severity={h.severity} /></td>
                      <td>{h.latency_ms != null ? `${h.latency_ms} ms` : '—'}</td>
                      <td><button type="button" className="link-btn" onClick={() => openCheck(h.id)}>View</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </main>
  );
}

export default function HiddenFaultPage() {
  return <AppShell><HiddenFaultView /></AppShell>;
}
