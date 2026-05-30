import { useEffect, useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useFilters } from '../context/FilterContext';
import { getFilters, type FilterOptions } from '../api/client';

const PRODUCTS = [
  { id: 'jira', name: 'Jira', color: '#2f6fed' },
  { id: 'confluence', name: 'Confluence', color: '#00857a' },
  { id: 'bitbucket', name: 'Bitbucket', color: '#5b4cc4' },
  { id: 'jsm', name: 'JSM', color: '#d9730d' },
] as const;

const NAV_ITEMS = [
  { to: '/', label: 'Overview', color: 'var(--brand)', end: true },
  { to: '/productivity', label: 'Productivity', color: 'var(--jira)' },
  { to: '/security', label: 'Security & Forensics', color: 'var(--security)' },
  { to: '/timeline', label: 'User Timeline', color: 'var(--bitbucket)' },
  { to: '/workitems', label: 'Work Items', color: '#8a5cf6' },
  { to: '/reports', label: 'Reports & Export', color: 'var(--jsm)' },
  { to: '/health', label: 'Connector Health', color: 'var(--confluence)' },
] as const;

const DEPLOYMENTS = [
  { value: '', label: 'All' },
  { value: 'cloud', label: 'Cloud' },
  { value: 'datacenter', label: 'Data Center' },
] as const;

const PRESETS = ['7', '30', '90', ''] as const;
const PRESET_LABELS: Record<string, string> = { '7': '7d', '30': '30d', '90': '90d', '': 'All' };

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase();
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { filters, setFilter, resetFilters } = useFilters();
  const [filterOpts, setFilterOpts] = useState<FilterOptions>({ users: [], operations: [], groups: [] });

  useEffect(() => {
    getFilters().then(setFilterOpts).catch(() => {});
  }, []);

  const toggleProduct = (id: string) => {
    const current = filters.products;
    if (current.includes(id)) {
      if (current.length > 1) {
        setFilter('products', current.filter((p) => p !== id));
      }
    } else {
      setFilter('products', [...current, id]);
    }
  };

  const setPreset = (preset: string) => {
    setFilter('preset', preset);
    setFilter('year', '');
    setFilter('month', '');
    setFilter('day', '');
  };

  const setDatePart = (key: 'year' | 'month' | 'day', value: string) => {
    setFilter(key, value);
    setFilter('preset', '');
  };

  return (
    <>
      <header className="topbar">
        <div className="logo">
          <span className="mark">A</span> AtlasLens
        </div>

        <div className="seg">
          {DEPLOYMENTS.map((d) => (
            <button
              key={d.value}
              className={filters.deployment === d.value ? 'active' : ''}
              onClick={() => setFilter('deployment', d.value)}
            >
              {d.label}
            </button>
          ))}
        </div>

        <div className="search">
          <span className="ic">{'⚒'}</span>
          <input
            type="text"
            placeholder="Search actors, objects, operations..."
            value={filters.q}
            onChange={(e) => setFilter('q', e.target.value)}
          />
        </div>

        <div style={{ flex: 1 }} />

        <button
          className="btn sm"
          style={{ background: 'rgba(255,255,255,.14)', border: 'none', color: '#fff' }}
        >
          {'↡'} Export
        </button>

        <div className="avatar" title={user?.username ?? ''} onClick={logout} style={{ cursor: 'pointer' }}>
          {user ? initials(user.username) : '?'}
        </div>
      </header>

      <div className="shell">
        <aside className="side">
          <nav>
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  'navitem' + (isActive ? ' active' : '')
                }
              >
                <span className="dot" style={{ color: item.color }} />
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="sidehead">Filters</div>

          <div className="filter">
            <label className="flabel">Products</label>
            <div className="chips">
              {PRODUCTS.map((p) => {
                const on = filters.products.includes(p.id);
                return (
                  <span
                    key={p.id}
                    className={'chip' + (on ? ' on' : ' off')}
                    onClick={() => toggleProduct(p.id)}
                  >
                    <span className="sw" style={{ background: p.color }} />
                    {p.name}
                  </span>
                );
              })}
            </div>
          </div>

          <div className="filter">
            <label className="flabel">Date -- year / month / day</label>
            <div className="drill">
              <select
                value={filters.year}
                onChange={(e) => setDatePart('year', e.target.value)}
              >
                <option value="">Any year</option>
                <option value="2026">2026</option>
                <option value="2025">2025</option>
              </select>
              <select
                value={filters.month}
                onChange={(e) => setDatePart('month', e.target.value)}
              >
                <option value="">Any month</option>
                {MONTHS.map((m, i) => (
                  <option key={m} value={String(i + 1)}>
                    {m}
                  </option>
                ))}
              </select>
              <select
                value={filters.day}
                onChange={(e) => setDatePart('day', e.target.value)}
              >
                <option value="">Any day</option>
                {Array.from({ length: 31 }, (_, i) => (
                  <option key={i + 1} value={String(i + 1)}>
                    {i + 1}
                  </option>
                ))}
              </select>
            </div>
            <div className="chips" style={{ marginTop: 8 }}>
              {PRESETS.map((p) => (
                <span
                  key={p || 'all'}
                  className={'chip' + (filters.preset === p ? ' on' : '')}
                  onClick={() => setPreset(p)}
                >
                  {PRESET_LABELS[p]}
                </span>
              ))}
            </div>
          </div>

          <div className="filter">
            <label className="flabel">User</label>
            <select
              value={filters.user}
              onChange={(e) => setFilter('user', e.target.value)}
            >
              <option value="">All users</option>
              {filterOpts.users.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </select>
          </div>

          {filterOpts.groups.length > 0 && (
            <div className="filter">
              <label className="flabel">Group / team</label>
              <select
                value={filters.group}
                onChange={(e) => setFilter('group', e.target.value)}
              >
                <option value="">All groups</option>
                {filterOpts.groups.map((g) => (
                  <option key={g.id} value={g.id}>{g.name}</option>
                ))}
              </select>
            </div>
          )}

          <div className="filter">
            <label className="flabel">Operation</label>
            <select
              value={filters.operation}
              onChange={(e) => setFilter('operation', e.target.value)}
            >
              <option value="">All operations</option>
              {filterOpts.operations.map((op) => (
                <option key={op} value={op}>{op.replace(/_/g, ' ')}</option>
              ))}
            </select>
          </div>

          <div className="filter">
            <label className="flabel">Category</label>
            <select
              value={filters.category}
              onChange={(e) => setFilter('category', e.target.value)}
            >
              <option value="">All categories</option>
              <option value="security">Security / admin</option>
              <option value="content">Activity / content</option>
            </select>
          </div>

          <button
            className="btn block"
            style={{ marginTop: 6 }}
            onClick={resetFilters}
          >
            Reset filters
          </button>
        </aside>

        <main className="content">
          <Outlet />
        </main>
      </div>
    </>
  );
}
