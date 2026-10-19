'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { AppShell } from '@/components/AppShell';
import { api } from '@/lib/api';
import type { Vehicle } from '@/lib/types';

type Status = 'Live' | 'Prototype' | 'Coming soon';

const COMPONENT_CARDS: { title: string; text: string; href?: string; status: Status }[] = [
  {
    title: 'Vehicle Health',
    text: 'Overall health score from IoT sensor and OBD-II readings, with explainable factors.',
    href: '/vehicles',
    status: 'Live',
  },
  {
    title: 'Hidden Fault & Mitigation',
    text: 'Rules + AI anomaly detection to find hidden faults and suggest what to do next.',
    href: '/hidden-fault',
    status: 'Prototype',
  },
  {
    title: 'Age & Mileage Deterioration',
    text: 'Vehicle deterioration adjusted for the age and mileage of the vehicle.',
    href: '/deterioration',
    status: 'Coming soon',
  },
  {
    title: 'Component 4',
    text: 'Reserved for the next research component.',
    status: 'Coming soon',
  },
];

const STATUS_CLASS: Record<Status, string> = {
  Live: 'status-live',
  Prototype: 'status-proto',
  'Coming soon': 'status-soon',
};

function vehicleName(v: Vehicle) {
  return [v.make, v.model].filter(Boolean).join(' ') || `Vehicle #${v.id}`;
}

function DashboardView() {
  const [vehicles, setVehicles] = useState<Vehicle[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.vehicles().then(setVehicles).catch((e: Error) => setError(e.message));
  }, []);

  return (
    <main className="container">
      <div className="page-head">
        <h1>Dashboard</h1>
        <p className="muted">Vehicle health, hidden faults and deterioration in one place.</p>
      </div>

      {error && <p className="error" role="alert">{error}</p>}

      <div className="grid cols-3 stat-row">
        <div className="card stat">
          <span className="muted small">Vehicles</span>
          <strong>{vehicles === null ? '…' : vehicles.length}</strong>
        </div>
        <div className="card stat">
          <span className="muted small">Data sources</span>
          <strong>OBD-II + IoT</strong>
        </div>
        <div className="card stat">
          <span className="muted small">Components</span>
          <strong>4</strong>
        </div>
      </div>

      <h2 className="section-title">Components</h2>
      <div className="grid cols-2">
        {COMPONENT_CARDS.map((c) => {
          const body = (
            <>
              <div className="row spread">
                <h3>{c.title}</h3>
                <span className={`status ${STATUS_CLASS[c.status]}`}>{c.status}</span>
              </div>
              <p className="muted small">{c.text}</p>
              {c.href && <span className="card-link">Open →</span>}
            </>
          );
          return c.href
            ? <Link key={c.title} href={c.href} className="card component-card">{body}</Link>
            : <div key={c.title} className="card component-card disabled">{body}</div>;
        })}
      </div>

      <h2 className="section-title">Your vehicles</h2>
      <section className="card">
        {vehicles === null ? <p className="muted">Loading…</p>
          : vehicles.length === 0 ? (
            <p className="muted">No vehicles yet. <Link href="/vehicles">Add your first vehicle →</Link></p>
          ) : (
            <table>
              <thead><tr><th>Vehicle</th><th>Year</th><th /></tr></thead>
              <tbody>
                {vehicles.slice(0, 5).map((v) => (
                  <tr key={v.id}>
                    <td>{vehicleName(v)}</td>
                    <td>{v.year ?? '—'}</td>
                    <td><Link href={`/vehicles/${v.id}`}>View health →</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </section>
    </main>
  );
}

export default function DashboardPage() {
  return <AppShell><DashboardView /></AppShell>;
}
