import { CONDITION_COLOR } from '@/lib/format';
import type { AssessmentResult } from '@/lib/types';

export function ScoreGauge({ score, condition }: { score: number; condition: AssessmentResult['condition'] }) {
  const r = 60;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, score)) / 100;
  const color = CONDITION_COLOR[condition];

  return (
    <div style={{ textAlign: 'center' }} role="img" aria-label={`Vehicle health score ${score.toFixed(0)} out of 100, ${condition}`}>
      <svg width="160" height="160" viewBox="0 0 160 160">
        <circle cx="80" cy="80" r={r} fill="none" stroke="var(--track)" strokeWidth="14" />
        <circle cx="80" cy="80" r={r} fill="none" stroke={color} strokeWidth="14" strokeLinecap="round"
          strokeDasharray={`${circ * pct} ${circ}`} transform="rotate(-90 80 80)" />
        <text x="80" y="82" textAnchor="middle" fontSize="36" fontWeight="700" fill="var(--text)">{score.toFixed(0)}</text>
        <text x="80" y="104" textAnchor="middle" fontSize="12" fill="var(--muted)">/ 100</text>
      </svg>
      <div><span className="pill" style={{ background: color }}>{condition}</span></div>
    </div>
  );
}
