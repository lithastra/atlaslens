interface HBarItem {
  label: string;
  value: number;
  color?: string;
}

interface HBarProps {
  items: HBarItem[];
  max?: number;
}

export default function HBar({ items, max: maxOverride }: HBarProps) {
  if (items.length === 0) {
    return <div className="empty">No data in scope</div>;
  }

  const max = maxOverride ?? Math.max(1, ...items.map((i) => i.value));

  return (
    <div>
      {items.map((item, idx) => (
        <div className="hbar" key={idx}>
          <div className="hl">{item.label}</div>
          <div className="ht">
            <div
              className="hf"
              style={{
                width: `${((item.value / max) * 100).toFixed(1)}%`,
                background: item.color ?? 'var(--jira)',
              }}
            />
          </div>
          <div className="hv">{item.value}</div>
        </div>
      ))}
    </div>
  );
}
