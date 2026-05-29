import { useEffect, useState } from 'react';
import { useFilters } from '../context/FilterContext';
import { getItems, getFilters, type WorkItem } from '../api/client';

const PRODUCT_COLORS: Record<string, string> = {
  jira: '#2f6fed', confluence: '#00857a', bitbucket: '#5b4cc4', jsm: '#d9730d',
};

const SORT_OPTIONS = [
  { value: 'updated_desc', label: 'Updated -- newest first' },
  { value: 'updated_asc', label: 'Updated -- oldest first' },
  { value: 'name', label: 'Name A-Z' },
];

export default function WorkItemsPage() {
  const { toParams } = useFilters();
  const [users, setUsers] = useState<{ id: string; name: string }[]>([]);
  const [selectedUser, setSelectedUser] = useState('');
  const [sort, setSort] = useState('updated_desc');
  const [items, setItems] = useState<WorkItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getFilters().then((f) => setUsers(f.users)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedUser) {
      setItems([]);
      setTotal(0);
      return;
    }
    const params = toParams();
    setLoading(true);
    getItems({ ...params, actor: selectedUser, sort, limit: '100' })
      .then((r) => {
        setItems(r.items);
        setTotal(r.total);
      })
      .finally(() => setLoading(false));
  }, [toParams, selectedUser, sort]);

  return (
    <>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="pad" style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <label className="muted" style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
              Individual
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
          <div>
            <label className="muted" style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', display: 'block', marginBottom: 4 }}>
              Sort by
            </label>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              style={{ height: 34, border: '1px solid #e3e8f0', borderRadius: 8, padding: '0 8px' }}
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div style={{ flex: 1 }} />
          {selectedUser && (
            <div className="muted" style={{ fontSize: 13 }}>
              {total} items
            </div>
          )}
        </div>
      </div>

      {!selectedUser && <div className="empty">Select a user above to view their work items.</div>}

      {selectedUser && loading && <div className="empty">Loading...</div>}

      {selectedUser && !loading && (
        <div className="card">
          <div className="pad spread">
            <div>
              <div className="ctitle">Items created or updated by this person</div>
              <div className="csub">
                Jira & JSM tickets, Bitbucket pull requests, Confluence pages -- respects the product & date filters and global search
              </div>
            </div>
            <span className="pill">{total}</span>
          </div>
          <div className="scrollbox" style={{ maxHeight: 560 }}>
            <table className="tbl">
              <thead>
                <tr><th>Item</th><th>Type</th><th>Role</th><th>Updated</th></tr>
              </thead>
              <tbody>
                {items.length === 0 && (
                  <tr><td colSpan={4} className="empty">No work items found.</td></tr>
                )}
                {items.map((item) => (
                  <tr key={`${item.object_id}-${item.product}`}>
                    <td style={{ fontWeight: 600 }}>{item.name}</td>
                    <td>
                      <span className="pdot" style={{ background: PRODUCT_COLORS[item.product] ?? '#999' }} />{' '}
                      {item.object_type.replace(/_/g, ' ')} ({item.product})
                    </td>
                    <td>
                      <span className="pill" style={{
                        background: item.role === 'created' ? '#dff2e6' : '#eaf1fd',
                        color: item.role === 'created' ? '#1d7a45' : '#1f3864',
                      }}>
                        {item.role}
                      </span>
                    </td>
                    <td className="muted" style={{ whiteSpace: 'nowrap', fontSize: 12 }}>
                      {new Date(item.updated_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
