import { useEffect, useState } from 'react';
import { getSyncStatus, type ConnectorStatus } from '../api/client';

function relativeTime(iso: string | null): string {
  if (!iso) return '--';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function statusLabel(status: ConnectorStatus): { text: string; cls: string } {
  if (status.last_error) return { text: 'Error', cls: 'status-err' };
  if (status.last_success_at) return { text: 'OK', cls: 'status-ok' };
  return { text: 'Pending', cls: 'status-warn' };
}

export default function HealthPage() {
  const [connectors, setConnectors] = useState<ConnectorStatus[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getSyncStatus()
      .then(setConnectors)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="empty">Loading...</div>;

  return (
    <>
      <div className="muted" style={{ marginBottom: 14, fontSize: 13 }}>
        One connector per <b style={{ color: 'var(--text-h)' }}>product x deployment</b>.
        Each pulls incrementally from its last high-water mark and respects source rate limits.
      </div>

      <div className="card">
        <table className="tbl">
          <thead>
            <tr>
              <th>Connector</th>
              <th>Deployment</th>
              <th>Status</th>
              <th>Last sync</th>
              <th>Cursor</th>
              <th>Error</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {connectors.length === 0 && (
              <tr><td colSpan={7} className="empty">No connectors configured.</td></tr>
            )}
            {connectors.map((c) => {
              const st = statusLabel(c);
              return (
                <tr key={c.connector}>
                  <td style={{ fontWeight: 600 }}>{c.connector}</td>
                  <td>{c.deployment}</td>
                  <td><span className={st.cls}>{st.text}</span></td>
                  <td className="muted" style={{ fontSize: 12 }}>{relativeTime(c.last_success_at)}</td>
                  <td className="muted" style={{ fontSize: 11, fontFamily: 'monospace', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {c.cursor ?? '--'}
                  </td>
                  <td style={{ fontSize: 12, color: c.last_error ? '#d14343' : undefined, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {c.last_error ?? '--'}
                  </td>
                  <td className="muted" style={{ fontSize: 12 }}>{c.note ?? ''}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
