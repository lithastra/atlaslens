import { useState } from 'react';
import { useFilters } from '../context/FilterContext';
import { exportCsv } from '../api/client';

const REPORT_TYPES = [
  'Permission & access changes',
  'Sign-in & authentication',
  'Sensitive operations',
  'Team productivity summary',
  'Full activity trail (compliance)',
];

const FORMATS = ['PDF', 'CSV', 'JSON'];

export default function ReportsPage() {
  const { toParams } = useFilters();
  const [reportType, setReportType] = useState(REPORT_TYPES[0]);
  const [formats, setFormats] = useState<Set<string>>(new Set(['PDF', 'CSV']));
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState('');

  const toggleFormat = (f: string) => {
    setFormats((prev) => {
      const next = new Set(prev);
      if (next.has(f)) next.delete(f);
      else next.add(f);
      return next;
    });
  };

  const handleGenerate = async () => {
    if (formats.size === 0) {
      setMessage('Select at least one format.');
      return;
    }
    setGenerating(true);
    setMessage('');
    try {
      const params = toParams();
      if (formats.has('CSV')) {
        const res = await exportCsv(params);
        if (res.ok) {
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'atlaslens-export.csv';
          a.click();
          URL.revokeObjectURL(url);
          setMessage('CSV export downloaded.');
        } else {
          setMessage('Export failed: ' + res.statusText);
        }
      } else {
        setMessage('Only CSV export is currently supported. PDF and JSON are planned.');
      }
    } catch (err) {
      setMessage('Export error: ' + String(err));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="grid twocol">
      <div className="card">
        <div className="pad">
          <div className="ctitle">Build & export a report</div>
          <div className="csub">Uses the filters currently in scope</div>
        </div>
        <div className="pad" style={{ paddingTop: 4 }}>
          <label className="muted" style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', display: 'block', marginBottom: 5 }}>
            Report type
          </label>
          <select
            value={reportType}
            onChange={(e) => setReportType(e.target.value)}
            style={{ width: '100%', height: 34, border: '1px solid #e3e8f0', borderRadius: 8, padding: '0 8px', marginBottom: 12 }}
          >
            {REPORT_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>

          <label className="muted" style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', display: 'block', marginBottom: 5 }}>
            Format
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
            {FORMATS.map((f) => (
              <span
                key={f}
                className={`chip ${formats.has(f) ? 'on' : ''}`}
                onClick={() => toggleFormat(f)}
                style={{ cursor: 'pointer' }}
              >
                {f}
              </span>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              className="btn primary"
              onClick={handleGenerate}
              disabled={generating}
            >
              {generating ? 'Generating...' : 'Generate now'}
            </button>
            <button className="btn">Schedule monthly...</button>
          </div>

          {message && (
            <div className="muted" style={{ marginTop: 12, fontSize: 13 }}>{message}</div>
          )}

          <div className="banner" style={{ marginTop: 16, background: '#eef6ff', borderColor: '#cfe2fb', color: '#234' }}>
            <span style={{ fontWeight: 700 }}>Integrity stamp</span>{' '}
            <div>
              Attached to compliance exports: record count, SHA-256 of the result set,
              generation time, and the exact filter criteria -- so an auditor can trust completeness.
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="pad">
          <div className="ctitle">Saved & scheduled reports</div>
        </div>
        <table className="tbl">
          <thead>
            <tr><th>Name</th><th>Schedule</th><th>Recipients</th><th>Last run</th></tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={4} className="empty">
                No saved reports yet. Generate a report or schedule one to see it here.
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
