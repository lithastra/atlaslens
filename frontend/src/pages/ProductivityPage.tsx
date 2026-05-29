import { useEffect, useState, useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from 'recharts';
import { useFilters } from '../context/FilterContext';
import {
  getSummary, getTimeseries, getTop, getEvents,
  type Summary, type TimeseriesBucket, type TopItem, type EventItem,
} from '../api/client';
import KpiCard from '../components/KpiCard';
import HBar from '../components/HBar';

const PRODUCT_COLORS: Record<string, string> = {
  jira: '#2f6fed', confluence: '#00857a', bitbucket: '#5b4cc4', jsm: '#d9730d',
};

export default function ProductivityPage() {
  const { toParams } = useFilters();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesBucket[]>([]);
  const [topContrib, setTopContrib] = useState<TopItem[]>([]);
  const [topAreas, setTopAreas] = useState<TopItem[]>([]);
  const [recent, setRecent] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const base = toParams();
    const params = { ...base, pipeline: 'activity' };
    setLoading(true);
    Promise.all([
      getSummary(params),
      getTimeseries({ ...params, granularity: 'day', group_by: 'operation' }),
      getTop({ ...params, field: 'actor', limit: '8' }),
      getTop({ ...params, field: 'object', limit: '8' }),
      getEvents({ ...params, limit: '20', sort: 'occurred_at_desc' }),
    ])
      .then(([s, ts, tc, ta, ev]) => {
        setSummary(s);
        setTimeseries(ts);
        setTopContrib(tc);
        setTopAreas(ta);
        setRecent(ev.items);
      })
      .finally(() => setLoading(false));
  }, [toParams]);

  const chartData = useMemo(() => {
    const map = new Map<string, { bucket: string; created: number; updated: number }>();
    for (const b of timeseries) {
      if (!map.has(b.bucket)) map.set(b.bucket, { bucket: b.bucket, created: 0, updated: 0 });
      const row = map.get(b.bucket)!;
      const op = b.group.toLowerCase();
      if (op.includes('created') || op.includes('pushed')) row.created += b.count;
      else row.updated += b.count;
    }
    return Array.from(map.values()).sort((a, b) => a.bucket.localeCompare(b.bucket));
  }, [timeseries]);

  if (loading) return <div className="empty">Loading...</div>;
  if (!summary) return <div className="empty">No data available.</div>;

  const jiraJsm = (summary.by_product['jira'] ?? 0) + (summary.by_product['jsm'] ?? 0);
  const confEdits = summary.by_product['confluence'] ?? 0;
  const bbCount = summary.by_product['bitbucket'] ?? 0;

  return (
    <>
      <div className="grid kpis">
        <KpiCard label="Work items" value={summary.total_events.toLocaleString()} />
        <KpiCard label="Tickets & requests" value={jiraJsm.toLocaleString()} accent="#2f6fed" />
        <KpiCard label="Page edits" value={confEdits.toLocaleString()} accent="#00857a" />
        <KpiCard label="Commits & PRs" value={bbCount.toLocaleString()} accent="#5b4cc4" />
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="pad spread">
          <div>
            <div className="ctitle">Output over time -- created vs updated</div>
            <div className="csub">Tickets, pages, commits & requests produced in scope</div>
          </div>
        </div>
        <div className="pad" style={{ paddingTop: 0 }}>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData}>
              <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="created" fill="#9db8e8" name="Created" />
              <Bar dataKey="updated" fill="#2f6fed" name="Updated" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid twocol" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="pad">
            <div className="ctitle">Top contributors</div>
            <div className="csub">Work items created or updated</div>
          </div>
          <div className="pad" style={{ paddingTop: 4 }}>
            <HBar
              items={topContrib.map((a) => ({
                label: a.key,
                value: a.count,
                color: '#2f6fed',
              }))}
            />
            {topContrib.length === 0 && <div className="empty">No data.</div>}
          </div>
        </div>
        <div className="card">
          <div className="pad">
            <div className="ctitle">Most active areas</div>
            <div className="csub">Projects, spaces, repositories</div>
          </div>
          <div className="pad" style={{ paddingTop: 4 }}>
            <HBar
              items={topAreas.map((a) => ({
                label: a.key,
                value: a.count,
                color: '#00857a',
              }))}
            />
            {topAreas.length === 0 && <div className="empty">No data.</div>}
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="pad spread">
          <div className="ctitle">Recently updated tickets & pages</div>
          <span className="pill">{recent.length}</span>
        </div>
        <div className="scrollbox">
          <table className="tbl">
            <thead>
              <tr><th>When</th><th>Object</th><th>Product</th><th>Author</th><th>Change</th></tr>
            </thead>
            <tbody>
              {recent.length === 0 && (
                <tr><td colSpan={5} className="empty">No events found.</td></tr>
              )}
              {recent.map((e) => (
                <tr key={e.id}>
                  <td className="muted" style={{ whiteSpace: 'nowrap', fontSize: 12 }}>
                    {new Date(e.occurred_at).toLocaleString()}
                  </td>
                  <td>{e.object_ref?.name ?? ''}</td>
                  <td>
                    <span className="pdot" style={{ background: PRODUCT_COLORS[e.product] ?? '#999' }} />{' '}
                    {e.product}
                  </td>
                  <td>{e.actor_display_name || e.actor_raw}</td>
                  <td><span className="op">{e.operation}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
