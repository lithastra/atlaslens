import { useEffect, useState } from 'react';
import { useFilters } from '../context/FilterContext';
import { getEvents, getFilters, getTop, type EventItem, type TopItem } from '../api/client';
import HBar from '../components/HBar';

const PRODUCT_COLORS: Record<string, string> = {
  jira: '#2f6fed', confluence: '#00857a', bitbucket: '#5b4cc4', jsm: '#d9730d',
};

export default function TimelinePage() {
  const { toParams } = useFilters();
  const [users, setUsers] = useState<{ id: string; name: string }[]>([]);
  const [selectedUser, setSelectedUser] = useState('');
  const [events, setEvents] = useState<EventItem[]>([]);
  const [byProduct, setByProduct] = useState<TopItem[]>([]);
  const [byOp, setByOp] = useState<TopItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getFilters().then((f) => setUsers(f.users)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedUser) {
      setEvents([]);
      setByProduct([]);
      setByOp([]);
      return;
    }
    const params = toParams();
    const userParams = { ...params, actor: selectedUser, limit: '100', sort: 'occurred_at_desc' };
    setLoading(true);
    Promise.all([
      getEvents(userParams),
      getTop({ ...params, actor: selectedUser, field: 'product', limit: '6' }),
      getTop({ ...params, actor: selectedUser, field: 'operation', limit: '10' }),
    ])
      .then(([ev, bp, bo]) => {
        setEvents(ev.items);
        setByProduct(bp);
        setByOp(bo);
      })
      .finally(() => setLoading(false));
  }, [toParams, selectedUser]);

  return (
    <>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="pad" style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <label className="muted" style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
              Investigate user
            </label>
            <select
              value={selectedUser}
              onChange={(e) => setSelectedUser(e.target.value)}
              style={{ height: 34, border: '1px solid #e3e8f0', borderRadius: 8, padding: '0 8px', minWidth: 220 }}
            >
              <option value="">Select a user...</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          </div>
          {selectedUser && (
            <div className="muted" style={{ fontSize: 13 }}>
              {events.length} events found
            </div>
          )}
        </div>
      </div>

      {!selectedUser && <div className="empty">Select a user above to view their activity timeline.</div>}

      {selectedUser && loading && <div className="empty">Loading...</div>}

      {selectedUser && !loading && (
        <div className="grid twocol">
          <div className="card">
            <div className="pad spread">
              <div className="ctitle">Cross-product activity timeline</div>
              <span className="pill">{events.length}</span>
            </div>
            <div className="pad" style={{ paddingTop: 0, maxHeight: 520, overflow: 'auto' }}>
              {events.length === 0 && <div className="empty">No activity found.</div>}
              <div className="feed">
                {events.map((e) => (
                  <div className="fitem" key={e.id}>
                    <div
                      className="fdot"
                      style={{ background: PRODUCT_COLORS[e.product] ?? '#999' }}
                    />
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
                      <span className="op">{e.operation}</span>
                      <span style={{ fontSize: 13 }}>{e.object_ref?.name ?? ''}</span>
                      <span className="muted" style={{ fontSize: 12 }}>
                        <span className="pdot" style={{ background: PRODUCT_COLORS[e.product] ?? '#999' }} />{' '}
                        {e.product}
                      </span>
                    </div>
                    <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
                      {new Date(e.occurred_at).toLocaleString()}
                      {e.source_ip ? ` -- ${e.source_ip}` : ''}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div className="card">
              <div className="pad"><div className="ctitle">By product</div></div>
              <div className="pad" style={{ paddingTop: 0 }}>
                <HBar
                  items={byProduct.map((p) => ({
                    label: p.key,
                    value: p.count,
                    color: PRODUCT_COLORS[p.key] ?? '#999',
                  }))}
                />
                {byProduct.length === 0 && <div className="empty">No data.</div>}
              </div>
            </div>
            <div className="card">
              <div className="pad"><div className="ctitle">By operation</div></div>
              <div className="pad" style={{ paddingTop: 0 }}>
                <HBar
                  items={byOp.map((o) => ({
                    label: o.key,
                    value: o.count,
                    color: '#5b4cc4',
                  }))}
                />
                {byOp.length === 0 && <div className="empty">No data.</div>}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
