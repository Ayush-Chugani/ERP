import { useId } from 'react';

/** Tiny inline trend chart. Pure SVG, scales to its container, decorative (the value is shown as text). */
export function Sparkline({ values, color = '#3b5bdb', height = 36 }: { values: number[]; color?: string; height?: number }) {
  const id = useId();
  const w = 120;
  const pts = values.length > 1 ? values : [0, ...values, ...values];
  const lo = Math.min(...pts);
  const hi = Math.max(...pts);
  const span = hi - lo || 1;
  const step = w / (pts.length - 1);
  const y = (v: number) => height - 4 - ((v - lo) / span) * (height - 8);
  const line = pts.map((v, i) => `${i === 0 ? 'M' : 'L'}${(i * step).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const area = `${line} L${w} ${height} L0 ${height} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${height}`} width="100%" height={height} preserveAspectRatio="none" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${id})`} />
      <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
