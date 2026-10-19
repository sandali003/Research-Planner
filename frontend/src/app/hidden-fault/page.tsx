'use client';

import { AppShell } from '@/components/AppShell';

// Offline evaluation of the OBD-II anomaly model
// (vehical-hidden-fault-and-mitigation/models/obd_anomaly_metadata.json)
const RESULTS = [
  { label: 'Model', value: 'One-Class SVM' },
  { label: 'ROC-AUC', value: '0.946' },
  { label: 'Faults caught', value: '31 / 37' },
  { label: 'False alarms', value: '5.9%' },
];

export default function HiddenFaultPage() {
  return (
    <AppShell>
      <main className="container">
        <div className="page-head">
          <h1>Hidden Fault & Mitigation</h1>
          <p className="muted">
            Finds faults that are not obvious from single readings and gives clear next steps.
          </p>
        </div>

        <p className="notice info">
          This component runs as a Streamlit prototype. Live results on this page will be added
          once it is connected to the backend.
        </p>

        <div className="grid cols-2" style={{ marginTop: 16 }}>
          <section className="card">
            <h2>How it works</h2>
            <ol className="steps">
              <li><strong>Rule check</strong> — Toyota threshold rules for vibration, idle speed, lugging and overheating.</li>
              <li><strong>AI anomaly check</strong> — a model trained only on healthy engines flags unusual patterns.</li>
              <li><strong>Hidden fault</strong> — unusual pattern with no rule triggered = possible hidden fault.</li>
              <li><strong>Mitigation</strong> — severity, immediate actions and longevity tips in plain language.</li>
            </ol>
          </section>

          <section className="card">
            <h2>Offline evaluation</h2>
            <div className="grid cols-2 mini-stats">
              {RESULTS.map((r) => (
                <div key={r.label}>
                  <span className="muted small">{r.label}</span>
                  <strong>{r.value}</strong>
                </div>
              ))}
            </div>
            <p className="muted small" style={{ marginTop: 12 }}>
              Real OBD-II readings from 60 Toyota vehicles; fault labels from threshold rules.
            </p>
          </section>
        </div>
      </main>
    </AppShell>
  );
}
