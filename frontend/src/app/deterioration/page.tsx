'use client';

import { AppShell } from '@/components/AppShell';

export default function DeteriorationPage() {
  return (
    <AppShell>
      <main className="container">
        <div className="page-head">
          <h1>Age & Mileage Deterioration</h1>
          <p className="muted">
            Vehicle deterioration adjusted for the age and mileage of the vehicle.
          </p>
        </div>

        <section className="card empty-state">
          <h2>Coming soon</h2>
          <p className="muted">This component is still being developed.</p>
        </section>
      </main>
    </AppShell>
  );
}
