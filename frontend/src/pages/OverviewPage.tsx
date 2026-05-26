import { useEffect, useState, useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
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
const CAT_COLORS: Record<string, string> = { security: '#c0563b', content: '#2f6fed' };

export default function OverviewPage() {
  const { toParams } = useFilters();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [timeseries, setTimeseries] = useState<TimeseriesBucket[]>([]);
  const [topActors, setTopActors] = useState<TopItem[]>([]);
  const [recent, setRecent] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const params = toParams();
    setLoading(true);
    Promise.all([
      getSummary(params),
      getTimeseries({ ...params, granularity: 'day', group_by: 'category' }),
      getTop({ ...params, field: 'actor', limit: '8' }),
      getEvents({ ...params, limit: '20', sort: 'occurred_at_desc' }),
    ])
      .then(([s, ts, ta, ev]) => {
        setSummary(s);
        setTimeseries(ts);
        setTopActors(ta);
        setRecent(ev.items);
      })
      .finally(() => setLoading(false));
  }, [toParams]);

  const chartData = useMemo(() => {
    const map = new Map<string, { bucket: string; security: number; content: number }>();
    for (const b of timeseries) {
      if (!map.has(b.bucket)) map.set(b.bucket, { bucket: b.bucket, security: 0, content: 0 });
      const row = map.get(b.bucket)!;
      if (b.group === 'security') row.security += b.count;
      else row.content += b.count;
    }
    return Array.from(map.values()).sort((a, b) => a.bucket.localeCompare(b.bucket));
  }, [timeseries]);

  const donutData = useMemo(() => {
    if (!summary) return [];
    return Object.entries(summary.by_product).map(([name, value]) => ({ name, value }));
  }, [summary]);

  if (loading) return <div className="empty">Loading...</div>;
  if (!summary) return <div className="empty">No data available.</div>;

  const activityCount = summary.by_category['content'] ?? 0;
  const sensitiveCount = summary.by_severity['high'] ?? 0;

  return (
    <>
      <div className="grid kpis">
        <KpiCard label="Total events" value={summary.total_events.toLocaleString()} />
        <KpiCard label="Active users" value={summary.unique_actors.toLocaleString()} />
        <KpiCard label="Activity events" value={activityCount.toLocaleString()} accent="#2f6fed" />
        <KpiCard label="Sensitive ops" value={sensitiveCount.toLocaleString()} accent="#d14343" />
      </div>

      <div className="grid twocol" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="pad spread">
            <div>
              <div className="ctitle">Event volume over time</div>
              <div className="csub">All events in scope, by category</div>
            </div>
          </div>
          <div className="pad" style={{ paddingTop: 0 }}>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={chartData}>
                <XAxis dataKey="bucket" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="content" stackId="a" fill={CAT_COLORS.content} name="Activity" />
                <Bar dataKey="security" stackId="a" fill={CAT_COLORS.security} name="Security" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="pad">
            <div className="ctitle">Activity by product</div>
            <div className="csub">Share of events in scope</div>
          </div>
          <div className="pad" style={{ paddingTop: 0 }}>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={donutData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                >
                  {donutData.map((d) => (
                    <Cell key={d.name} fill={PRODUCT_COLORS[d.name] ?? '#999'} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, fontSize: 12, color: '#5a6678' }}>
              {donutData.map((d) => (
                <span key={d.name} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <i style={{ width: 10, height: 10, borderRadius: 3, display: 'inline-block', background: PRODUCT_COLORS[d.name] ?? '#999' }} />
                  {d.name} ({d.value})
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid twocol" style={{ marginTop: 16 }}>
        <div className="card">
          <div className="pad spread">
            <div className="ctitle">Recent events</div>
            <span className="pill">{recent.length}</span>
          </div>
          <div className="scrollbox">
            <table className="tbl">
              <thead>
                <tr><th>When</th><th>Actor</th><th>Product</th><th>Operation</th><th>Object</th></tr>
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
                    <td>{e.actor_raw}</td>
                    <td>
                      <span className="pdot" style={{ background: PRODUCT_COLORS[e.product] ?? '#999' }} />{' '}
                      {e.product}
                    </td>
                    <td><span className="op">{e.operation}</span></td>
                    <td>{e.object_ref?.name ?? ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="pad">
            <div className="ctitle">Top contributors</div>
            <div className="csub">By events in scope</div>
          </div>
          <div className="pad" style={{ paddingTop: 4 }}>
            <HBar
              items={topActors.map((a) => ({
                label: a.key,
                value: a.count,
                color: '#2f6fed',
              }))}
            />
            {topActors.length === 0 && <div className="empty">No data.</div>}
          </div>
        </div>
      </div>
    </>
  );
}
