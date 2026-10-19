'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api } from '@/lib/api';
import { AppShell } from '@/components/AppShell';
import type { Vehicle } from '@/lib/types';

function VehiclesView() {
  const [vehicles, setVehicles] = useState<Vehicle[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ make: '', model: '', year: '', vin: '' });
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api.vehicles().then(setVehicles).catch((e: Error) => setError(e.message));
  }, []);
  useEffect(load, [load]);

  async function add(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.createVehicle({
        make: form.make || undefined,
        model: form.model || undefined,
        year: form.year ? Number(form.year) : undefined,
        vin: form.vin || undefined,
      });
      setForm({ make: '', model: '', year: '', vin: '' });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not add vehicle');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <main className="container">
        <h1>Your vehicles</h1>
        {error && <p className="error" role="alert">{error}</p>}

        <div className="grid cols-2">
          <section className="card">
            <h2>Vehicles</h2>
            {vehicles === null ? <p className="muted">Loading…</p>
              : vehicles.length === 0 ? <p className="muted">No vehicles yet — add one.</p>
              : (
                <table>
                  <thead><tr><th>Vehicle</th><th>Year</th><th /></tr></thead>
                  <tbody>
                    {vehicles.map((v) => (
                      <tr key={v.id}>
                        <td>{[v.make, v.model].filter(Boolean).join(' ') || `Vehicle #${v.id}`}</td>
                        <td>{v.year ?? '—'}</td>
                        <td><Link href={`/vehicles/${v.id}`}>Open →</Link></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
          </section>

          <form className="card" onSubmit={add}>
            <h2>Add vehicle</h2>
            <label htmlFor="make">Make</label>
            <input id="make" value={form.make} onChange={(e) => setForm({ ...form, make: e.target.value })} placeholder="Toyota" />
            <label htmlFor="model">Model</label>
            <input id="model" value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} placeholder="Corolla" />
            <label htmlFor="year">Year</label>
            <input id="year" type="number" min={1950} max={2100} value={form.year} onChange={(e) => setForm({ ...form, year: e.target.value })} />
            <label htmlFor="vin">VIN (optional)</label>
            <input id="vin" maxLength={32} value={form.vin} onChange={(e) => setForm({ ...form, vin: e.target.value })} />
            <div style={{ marginTop: 16 }}><button className="primary" disabled={busy}>{busy ? 'Adding…' : 'Add vehicle'}</button></div>
          </form>
        </div>
      </main>
    </>
  );
}

export default function VehiclesPage() {
  return <AppShell><VehiclesView /></AppShell>;
}
