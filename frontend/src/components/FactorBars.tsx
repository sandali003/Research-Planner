import type { Factor } from '@/lib/types';

/** SHAP-style diverging bars: negative impact (lowers score) grows left in red, positive grows right in green. */
export function FactorBars({ factors }: { factors: Factor[] }) {
  const max = Math.max(1, ...factors.map((f) => Math.abs(f.impact)));

  return (
    <div>
      {factors.map((f) => {
        const widthPct = (Math.abs(f.impact) / max) * 50;
        const negative = f.impact < 0;
        return (
          <div key={f.component}>
            <div className="bar-row">
              <span>{f.label}</span>
              <div className="bar-track" role="img" aria-label={`${f.label} ${negative ? 'lowers' : 'raises'} the score by ${Math.abs(f.impact).toFixed(1)} points`}>
                <div className="bar-mid" />
                <div className="bar-fill" style={{
                  width: `${widthPct}%`,
                  left: negative ? `${50 - widthPct}%` : '50%',
                  background: negative ? 'var(--critical)' : 'var(--good)',
                }} />
              </div>
              <span style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                {f.impact > 0 ? '+' : ''}{f.impact.toFixed(1)}
              </span>
            </div>
            <div className="muted small" style={{ marginLeft: 160, marginTop: -6 }}>
              {f.status} · score {f.score.toFixed(0)} — {f.reason}
            </div>
          </div>
        );
      })}
    </div>
  );
}
