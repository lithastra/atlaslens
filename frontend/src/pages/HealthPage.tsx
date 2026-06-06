import { useCallback, useEffect, useState } from 'react';
import {
  getSyncStatus,
  triggerSync,
  type ConnectorStatus,
  type SyncStatus,
} from '../api/client';

function relativeTime(iso: string | null): string {
  if (!iso) return '--';
  const diff = Date.now() - new Date(iso).getTime();
  const secs = Math.floor(diff / 1000);
  if (secs < 60) return secs < 5 ? 'just now' : `${secs}s ago`;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

const STATE_STYLES: Record<string, { text: string; color: string }> = {
  running: { text: 'Running', color: '#2f6fed' },
  pending: { text: 'Queued', color: '#8a8f98' },
  done: { text: 'Done', color: '#1f9d57' },
  ok: { text: 'OK', color: '#1f9d57' },
  error: { text: 'Error', color: '#d14343' },
  cancelled: { text: 'Cancelled', color: '#b06a00' },
  idle: { text: 'Idle', color: '#8a8f98' },
};

function StateBadge({ c }: { c: ConnectorStatus }) {
  const s = STATE_STYLES[c.state] ?? STATE_STYLES.idle;
  const showCount =
    (c.state === 'done' || c.state === 'running') && c.count != null;
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: s.color, fontWeight: 600, fontSize: 12 }}>
      {c.state === 'running' && <span className="spin" aria-hidden>⟳</span>}
      {c.state === 'pending' && <span aria-hidden>…</span>}
      {s.text}
      {showCount ? ` (${c.count})` : ''}
    </span>
  );
}

export default function HealthPage() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);

  const refresh = useCallback(
    () =>
      getSyncStatus()
        .then(setStatus)
        .catch(() => {
          /* keep last good status */
        })
        .finally(() => setLoading(false)),
    [],
  );

  useEffect(() => {
    refresh();
    // Poll so the progress + "last sync" column stay live.
    const id = window.setInterval(refresh, 2500);
    return () => clearInterval(id);
  }, [refresh]);

  const onSyncNow = async () => {
    setStarting(true);
    setSyncMsg(null);
    try {
      await triggerSync();
      setSyncMsg('Sync started — any in-progress sync was replaced.');
      await refresh(); // reflect the new run immediately
    } catch {
      setSyncMsg('Failed to start sync.');
    } finally {
      setStarting(false);
    }
  };

  if (loading) return <div className="empty">Loading...</div>;

  const connectors = status?.connectors ?? [];
  const running = status?.running ?? false;
  const doneCount = connectors.filter(
    (c) => c.state === 'done' || c.state === 'ok',
  ).length;

  return (
    <>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 12,
          marginBottom: 14,
        }}
      >
        <div className="muted" style={{ fontSize: 13 }}>
          One connector per <b style={{ color: 'var(--text-h)' }}>product x deployment</b>.
          Each pulls incrementally from its last high-water mark and respects source rate limits.
        </div>
        <button className="btn sm" onClick={onSyncNow} disabled={starting}>
          {starting ? 'Starting…' : running ? '↻ Restart sync' : '↻ Sync now'}
        </button>
      </div>

      {running && (
        <div
          className="card"
          style={{
            marginBottom: 12,
            padding: '10px 14px',
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            borderLeft: '3px solid #2f6fed',
          }}
        >
          <span className="spin" aria-hidden style={{ color: '#2f6fed' }}>⟳</span>
          <span style={{ fontWeight: 600 }}>Sync in progress</span>
          <span className="muted" style={{ fontSize: 12 }}>
            {doneCount}/{connectors.length} connectors done
            {status?.started_at ? ` · started ${relativeTime(status.started_at)}` : ''}
          </span>
        </div>
      )}

      {syncMsg && (
        <div className="muted" style={{ marginBottom: 12, fontSize: 12 }}>
          {syncMsg}
        </div>
      )}

      <div className="card">
        <table className="tbl">
          <thead>
            <tr>
              <th>Connector</th>
              <th>Deployment</th>
              <th>Progress</th>
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
            {connectors.map((c) => (
              <tr key={c.connector}>
                <td style={{ fontWeight: 600 }}>{c.connector}</td>
                <td>{c.deployment}</td>
                <td><StateBadge c={c} /></td>
                <td className="muted" style={{ fontSize: 12 }}>{relativeTime(c.last_success_at)}</td>
                <td className="muted" style={{ fontSize: 11, fontFamily: 'monospace', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.cursor ?? '--'}
                </td>
                <td style={{ fontSize: 12, color: c.last_error ? '#d14343' : undefined, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.last_error ?? '--'}
                </td>
                <td className="muted" style={{ fontSize: 12 }}>{c.note ?? ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
