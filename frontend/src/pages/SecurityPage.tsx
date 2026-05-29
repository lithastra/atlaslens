import { useEffect, useState } from 'react';
import { useFilters } from '../context/FilterContext';
import {
  getSummary, getEvents,
  type Summary, type EventItem,
} from '../api/client';
import KpiCard from '../components/KpiCard';

const PRODUCT_COLORS: Record<string, string> = {
  jira: '#2f6fed', confluence: '#00857a', bitbucket: '#5b4cc4', jsm: '#d9730d',
};
const SEV_CLASS: Record<string, string> = { high: 'high', medium: 'med', low: 'low' };

type Tab = 'perm' | 'auth' | 'sensitive';

const TAB_OPERATIONS: Record<Tab, string[]> = {
  perm: ['permission_changed', 'group_membership_changed'],
  auth: ['login', 'login_failed'],
  sensitive: ['space_exported', 'repository_deleted', 'global_config_changed', 'user_deactivated', 'user_created'],
};

export default function SecurityPage() {
  const { toParams } = useFilters();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [tab, setTab] = useState<Tab>('perm');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const base = toParams();
    const params = { ...base, pipeline: 'audit' };
    setLoading(true);
    getSummary(params).then(setSummary).finally(() => setLoading(false));
  }, [toParams]);

  useEffect(() => {
    const base = toParams();
    const ops = TAB_OPERATIONS[tab];
    const params = { ...base, pipeline: 'audit', operation: ops, limit: '50', sort: 'occurred_at_desc' };
    getEvents(params).then((r) => setEvents(r.items));
  }, [toParams, tab]);

  if (loading) return <div className="empty">Loading...</div>;
  if (!summary) return <div className="empty">No data available.</div>;

  const permGroupCount = (summary.by_severity['high'] ?? 0);
  const signInCount = summary.by_category['security'] ?? 0;

  return (
    <>
      <div className="banner">
        <span style={{ fontSize: 18 }}>!</span>
        <div>
          Some sign-in events on Cloud require an <b>Atlassian Guard</b> licence.
          Where a class is unavailable it is shown as a gap rather than hidden silently.
          Bitbucket Cloud audit logs also require Guard and are unavailable.
        </div>
      </div>

      <div className="grid kpis">
        <KpiCard label="Security events" value={summary.total_events.toLocaleString()} accent="#c0563b" />
        <KpiCard label="Permission / group changes" value={permGroupCount.toLocaleString()} accent="#d14343" />
        <KpiCard label="Sign-ins" value={signInCount.toLocaleString()} subtitle="Guard gap: partial" />
        <KpiCard label="High-severity ops" value={(summary.by_severity['high'] ?? 0).toLocaleString()} accent="#d14343" />
      </div>

      <div className="tabbar" style={{ marginTop: 16 }}>
        <button className={tab === 'perm' ? 'active' : ''} onClick={() => setTab('perm')}>
          Permission & group changes
        </button>
        <button className={tab === 'auth' ? 'active' : ''} onClick={() => setTab('auth')}>
          Sign-ins
        </button>
        <button className={tab === 'sensitive' ? 'active' : ''} onClick={() => setTab('sensitive')}>
          Sensitive operations
        </button>
      </div>

      {tab === 'auth' && (
        <div className="banner" style={{ background: '#fff7e8', borderColor: '#f4dfa8', color: '#7a5b00' }}>
          <span style={{ fontSize: 18 }}>!</span>
          <div>
            Cloud sign-in / authentication events require <b>Atlassian Guard</b> (not licensed).
            Only product-level audit data is available. Some sign-in records may be missing.
          </div>
        </div>
      )}

      <div className="card">
        <div className="scrollbox" style={{ maxHeight: 520 }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>When</th>
                <th>Actor</th>
                <th>Product</th>
                <th>Operation</th>
                <th>Severity</th>
                <th>Object</th>
                {tab === 'perm' && <th>Detail</th>}
                <th>IP</th>
              </tr>
            </thead>
            <tbody>
              {events.length === 0 && (
                <tr>
                  <td colSpan={tab === 'perm' ? 8 : 7} className="empty">
                    No events found for this category.
                  </td>
                </tr>
              )}
              {events.map((e) => (
                <tr key={e.id}>
                  <td className="muted" style={{ whiteSpace: 'nowrap', fontSize: 12 }}>
                    {new Date(e.occurred_at).toLocaleString()}
                  </td>
                  <td>{e.actor_display_name || e.actor_raw}</td>
                  <td>
                    <span className="pdot" style={{ background: PRODUCT_COLORS[e.product] ?? '#999' }} />{' '}
                    {e.product}
                  </td>
                  <td><span className="op">{e.operation}</span></td>
                  <td>
                    <span className={`sev ${SEV_CLASS[e.severity] ?? 'low'}`}>{e.severity}</span>
                  </td>
                  <td>{e.object_ref?.name ?? ''}</td>
                  {tab === 'perm' && (
                    <td className="muted" style={{ fontSize: 12 }}>
                      {e.context ? `${e.context['from'] ?? ''} -> ${e.context['to'] ?? ''}` : ''}
                    </td>
                  )}
                  <td className="muted" style={{ fontSize: 12 }}>{e.source_ip ?? ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
