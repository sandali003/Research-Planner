import { fmt } from '@/lib/format';

interface Props {
  title: string;
  unit: string;
  values: (number | null)[];
  color: string;
  digits?: number;
}

export function Sparkline({ title, unit, values, color, digits = 1 }: Props) {
  const pts = values.map((v, i) => ({ v, i })).filter((p): p is { v: number; i: number } => p.v != null);
  const last = pts.at(-1)?.v ?? null;
  const W = 300;
  const H = 70;

  let path = '';
  if (pts.length > 1) {
    const min = Math.min(...pts.map((p) => p.v));
    const max = Math.max(...pts.map((p) => p.v));
    const span = max - min || 1;
    const n = Math.max(values.length - 1, 1);
    path = pts.map((p, k) => `${k ? 'L' : 'M'}${(p.i / n) * W},${H - 6 - ((p.v - min) / span) * (H - 12)}`).join(' ');
  }

  return (
    <div>
      <div className="row spread">
        <span className="muted small">{title}</span>
        <strong>{fmt(last, digits)} <span className="muted small">{unit}</span></strong>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" aria-label={`${title} trend`}>
        {path ? <path d={path} fill="none" stroke={color} strokeWidth="2" vectorEffect="non-scaling-stroke" />
          : <text x="8" y={H / 2} fill="var(--muted)" fontSize="12">No data yet</text>}
      </svg>
    </div>
  );
}
