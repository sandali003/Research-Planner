'use client';

import Link from 'next/link';
import { useEffect, useState, type FormEvent } from 'react';
import { AppShell } from '@/components/AppShell';
import { api } from '@/lib/api';
import { fmt, fmtTime } from '@/lib/format';
import type { BuyerType, DeteriorationAssessment, UpliftAction, ValueUplift, Vehicle } from '@/lib/types';

const vehicleName = (v: Vehicle) => [v.make, v.model].filter(Boolean).join(' ') || `Vehicle #${v.id}`;
const lkr = (v: number) => `LKR ${Math.round(v).toLocaleString()}`;
const lkrShort = (v: number) => (Math.abs(v) >= 1_000_000 ? `LKR ${fmt(v / 1_000_000, 2)}M` : lkr(v));
const signedLkr = (v: number) => `${v >= 0 ? '+' : '−'}${lkr(Math.abs(v))}`;
const pretty = (s: string) => s.replace(/_/g, ' ');

const SELL_OPTIONS = [
  { label: 'No rush', value: '' },
  { label: 'Tomorrow', value: '1' },
  { label: 'Within a week', value: '7' },
  { label: 'Within a month', value: '30' },
];

function ActionRow({ a }: { a: UpliftAction }) {
  return (
    <article className={`issue ${a.kind === 'safety' ? 'sev-high' : 'sev-none'}`}>
      <div className="row spread">
        <h3>{pretty(a.component)}</h3>
        <span className={`chip ${a.kind === 'safety' ? 'chip-target' : ''}`}>{a.kind === 'safety' ? 'Safety first' : 'Adds value'}</span>
      </div>
      <p style={{ margin: '4px 0' }}>{a.action}</p>
      <p className="muted small" style={{ margin: 0 }}>Why: {a.reason}</p>
      <div className="uplift-figures">
        <div><span>Cost</span><strong>{lkr(a.cost_lkr)}</strong><small>{lkr(a.cost_range_lkr[0])} – {lkr(a.cost_range_lkr[1])}</small></div>
        <div><span>Adds to price</span><strong>{a.kind === 'safety' ? '—' : signedLkr(a.value_gain_lkr)}</strong>
          <small>{a.kind === 'safety' ? 'not measured' : a.gain_if_done_alone_lkr != null && a.gain_if_done_alone_lkr !== a.value_gain_lkr
            ? `share of the plan · alone ${signedLkr(a.gain_if_done_alone_lkr)}` : 'estimated'}</small></div>
        <div><span>Net</span><strong className={a.net_gain_lkr >= 0 ? 'ctx-better' : 'ctx-worse'}>{signedLkr(a.net_gain_lkr)}</strong>
          <small>{a.roi != null && a.kind !== 'safety' ? `${fmt(a.roi, 1)}× return` : `${a.lead_days} day(s)`}</small></div>
      </div>
    </article>
  );
}

function UpliftReport({ r }: { r: ValueUplift }) {
  const s = r.plan_summary;
  const better = Math.round((1 - r.condition.percentile) * 100);
  return (
    <>
      <section className={`card status-card ${s.net_gain_lkr > 0 ? 'sev-none' : 'sev-low'}`}>
        <div className="row spread">
          <h2 style={{ margin: 0 }}>How to increase this {r.vehicle.model}&apos;s value</h2>
          <span className="muted small">{r.latency_ms} ms</span>
        </div>
        <p className="det-verdict">
          {r.plan.some((a) => a.kind === 'value')
            ? <>Doing the {r.plan.length} repair{r.plan.length > 1 ? 's' : ''} below for about <strong>{lkr(s.cost_lkr)}</strong> could raise
              the price by <strong>{signedLkr(s.value_gain_lkr)}</strong> ({lkr(s.value_gain_range_lkr[0])} – {lkr(s.value_gain_range_lkr[1])}),
              a net gain of <strong>{signedLkr(s.net_gain_lkr)}</strong>.</>
            : <>No repair adds more to the price than it costs in this situation{r.plan.length ? '; only the safety repairs are needed' : ''}.</>}
        </p>
        <div className="det-tiles">
          <div><span>Market value</span><strong>{lkrShort(r.market_value_lkr)}</strong><small>typical car like this (ikman.lk)</small></div>
          <div><span>This car now</span><strong>{lkrShort(r.current_value_lkr)}</strong><small>{better}% of comparable cars are in better condition</small></div>
          <div><span>After the plan</span><strong>{lkrShort(s.value_after_lkr)}</strong><small>{Math.round((1 - s.percentile_after) * 100)}% in better condition</small></div>
          <div><span>Net gain</span><strong className={s.net_gain_lkr >= 0 ? 'ctx-better' : 'ctx-worse'}>{signedLkr(s.net_gain_lkr)}</strong><small>after {lkr(s.cost_lkr)} of repairs</small></div>
        </div>
      </section>

      <div className="fault-layout" style={{ marginTop: 16 }}>
        <section className="card">
          <h2>Recommended plan</h2>
          {r.plan.length === 0
            ? <p className="muted">Nothing to do: no repair here is worth its cost for this sale.</p>
            : r.plan.map((a) => <ActionRow key={a.id} a={a} />)}
          <p className="muted small">
            Value gains are model estimates, not guaranteed prices. Repairs that only pay off together share the gain
            (Shapley values), so a repair can be worth more in the plan than alone.
          </p>
        </section>

        <div className="fault-side">
          <section className="card">
            <h2>Not worth it now</h2>
            {r.not_recommended.length === 0 ? <p className="muted small" style={{ margin: 0 }}>Every useful repair is in the plan.</p> : (
              <ul className="plain-list">
                {r.not_recommended.map((a) => (
                  <li key={a.id}><strong>{pretty(a.component)}</strong> · {lkr(a.cost_lkr)}<br />
                    <span className="muted small">{a.why_not}</span></li>
                ))}
              </ul>
            )}
          </section>
          {r.reliability_repairs.length > 0 && (
            <section className="card">
              <h2>Also fix for reliability</h2>
              <ul className="plain-list">
                {r.reliability_repairs.map((a) => (
                  <li key={a.id}><strong>{pretty(a.component)}</strong> · {lkr(a.cost_lkr)}<br /><span className="muted small">{a.reason}</span></li>
                ))}
              </ul>
            </section>
          )}
          <section className="card">
            <h2>Based on</h2>
            <table className="kv"><tbody>
              <tr><th>Vehicle</th><td>{r.vehicle.model} · {fmt(r.vehicle.age_years)} yrs · {r.vehicle.mileage_km.toLocaleString()} km</td></tr>
              <tr><th>Condition (Component 3)</th><td>{fmtTime(r.sources.deterioration_at)}</td></tr>
              <tr><th>Hidden faults (Component 2)</th><td>{r.sources.fault_check_at ? `${r.sources.fault_count} fault(s) · ${fmtTime(r.sources.fault_check_at)}` : 'No check yet'}</td></tr>
              <tr><th>Buyer</th><td>{r.inputs.buyer === 'dealer' ? 'Dealer (pays for half the gain)' : 'Private buyer'}</td></tr>
            </tbody></table>
            {r.notes.map((n) => <p key={n} className="notice info small">{n}</p>)}
          </section>
        </div>
      </div>
    </>
  );
}

export default function MaintenanceValuationPage() {
  const [vehicles, setVehicles] = useState<Vehicle[] | null>(null);
  const [vehicleId, setVehicleId] = useState<number | null>(null);
  const [deterioration, setDeterioration] = useState<DeteriorationAssessment | null | undefined>(undefined);
  const [budget, setBudget] = useState('');
  const [sellWithin, setSellWithin] = useState('');
  const [buyer, setBuyer] = useState<BuyerType>('private');
  const [result, setResult] = useState<ValueUplift | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.vehicles().then((list) => {
      setVehicles(list);
      if (list.length) setVehicleId(list[0].id);
    }).catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!vehicleId) return;
    setResult(null);
    setDeterioration(undefined);
    api.latestDeterioration(vehicleId).then(setDeterioration).catch(() => setDeterioration(null));
  }, [vehicleId]);

  const ready = Boolean(deterioration?.contextual?.available);

  async function run(e: FormEvent) {
    e.preventDefault();
    if (!vehicleId) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await api.valueUplift(vehicleId, {
        ...(budget.trim() && { budget_lkr: Number(budget) }),
        ...(sellWithin && { sell_within_days: Number(sellWithin) }),
        buyer,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not build the plan');
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <main className="container">
        <div className="page-head row spread">
          <div>
            <h1>Maintenance &amp; Valuation</h1>
            <p className="muted">Which repairs are worth doing before you sell, and how much they could add to the price.</p>
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
            <p className="muted">Add a vehicle first. <Link href="/vehicles">Add vehicle →</Link></p>
          </section>
        ) : (
          <>
            {deterioration !== undefined && !ready && (
              <section className="card empty-state">
                <h2>Run a deterioration assessment first</h2>
                <p className="muted">
                  The plan uses this vehicle&apos;s condition from Component 3 (brakes, suspension, steering, tyres or exhaust).{' '}
                  <Link href="/deterioration">Go to Deterioration →</Link>
                </p>
              </section>
            )}

            {ready && (
              <form className="card" onSubmit={run}>
                <h2>Your situation</h2>
                <p className="muted small">
                  Using the deterioration assessment of {fmtTime(deterioration!.created_at)}: {deterioration!.vehicle_model},{' '}
                  {fmt(deterioration!.age_years)} years, {deterioration!.odometer_km.toLocaleString()} km.
                </p>
                <div className="det-profile">
                  <div>
                    <label htmlFor="c4-budget">Repair budget (LKR)</label>
                    <input id="c4-budget" type="number" min={0} step={1000} placeholder="No limit"
                      value={budget} onChange={(e) => setBudget(e.target.value)} />
                  </div>
                  <div>
                    <label htmlFor="c4-sell">Selling</label>
                    <select id="c4-sell" value={sellWithin} onChange={(e) => setSellWithin(e.target.value)}>
                      {SELL_OPTIONS.map((o) => <option key={o.label} value={o.value}>{o.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="c4-buyer">Selling to</label>
                    <select id="c4-buyer" value={buyer} onChange={(e) => setBuyer(e.target.value as BuyerType)}>
                      <option value="private">Private buyer</option>
                      <option value="dealer">Dealer</option>
                    </select>
                  </div>
                </div>
                <div className="row spread det-run">
                  <span className="muted small">Hidden faults from the latest Component 2 check are included automatically.</span>
                  <button className="primary" disabled={busy}>{busy ? 'Building plan…' : 'Get my plan'}</button>
                </div>
              </form>
            )}

            {result && <div style={{ marginTop: 16 }}><UpliftReport r={result} /></div>}
          </>
        )}
      </main>
    </AppShell>
  );
}
