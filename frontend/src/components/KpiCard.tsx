interface KpiCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  accent: string;
}

export default function KpiCard({ label, value, subtitle, accent }: KpiCardProps) {
  return (
    <div className="card kpi">
      <div className="k-acc" style={{ background: accent }} />
      <div className="k-label">{label}</div>
      <div className="k-val">{value}</div>
      {subtitle && <div className="k-sub">{subtitle}</div>}
    </div>
  );
}
