import { useEffect, useState, useCallback } from 'react';
import { useFilters } from '../context/FilterContext';
import {
  exportData,
  getScheduledReports,
  createScheduledReport,
  deleteScheduledReport,
  type ScheduledReport,
} from '../api/client';

const REPORT_TYPES = [
  'Permission & access changes',
  'Sign-in & authentication',
  'Sensitive operations',
  'Team productivity summary',
  'Full activity trail (compliance)',
];

const FORMATS = ['PDF', 'CSV'] as const;
const SCHEDULES = ['daily', 'weekly', 'monthly'] as const;

export default function ReportsPage() {
  const { toParams } = useFilters();
  const [reportType, setReportType] = useState(REPORT_TYPES[0]);
  const [formats, setFormats] = useState<Set<string>>(new Set(['PDF', 'CSV']));
  const [generating, setGenerating] = useState(false);
  const [message, setMessage] = useState('');
  const [saved, setSaved] = useState<ScheduledReport[]>([]);
  const [schedule, setSchedule] = useState<string>('monthly');

  const loadSaved = useCallback(() => {
    getScheduledReports().then(setSaved).catch(() => {});
  }, []);

  useEffect(() => { loadSaved(); }, [loadSaved]);

  const toggleFormat = (f: string) => {
    setFormats((prev) => {
      const next = new Set(prev);
      if (next.has(f)) next.delete(f);
      else next.add(f);
      return next;
    });
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
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
      const downloaded: string[] = [];

      for (const fmt of ['csv', 'pdf'] as const) {
        if (!formats.has(fmt.toUpperCase())) continue;
        const res = await exportData(params, fmt);
        if (res.ok) {
          const blob = await res.blob();
          downloadBlob(blob, `atlaslens-export.${fmt}`);
          downloaded.push(fmt.toUpperCase());
        } else {
          setMessage(`${fmt.toUpperCase()} export failed: ${res.statusText}`);
          return;
        }
      }

      setMessage(`${downloaded.join(' + ')} export downloaded.`);
    } catch (err) {
      setMessage('Export error: ' + String(err));
    } finally {
      setGenerating(false);
    }
  };

  const handleSchedule = async () => {
    const fmt = formats.has('PDF') ? 'pdf' : 'csv';
    try {
      await createScheduledReport({
        name: reportType,
        schedule,
        format: fmt,
        filters: toParams(),
      });
      setMessage(`Scheduled ${schedule} report created.`);
      loadSaved();
    } catch (err) {
      setMessage('Schedule error: ' + String(err));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteScheduledReport(id);
      loadSaved();
    } catch {
      setMessage('Delete failed.');
    }
  };

  const fmtDate = (s: string | null) => {
    if (!s) return '--';
    return new Date(s).toLocaleString();
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

          <label className="muted" style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', display: 'block', marginBottom: 5 }}>
            Schedule
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
            {SCHEDULES.map((s) => (
              <span
                key={s}
                className={`chip ${schedule === s ? 'on' : ''}`}
                onClick={() => setSchedule(s)}
                style={{ cursor: 'pointer' }}
              >
                {s}
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
            <button className="btn" onClick={handleSchedule}>
              Schedule {schedule}
            </button>
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
            <tr><th>Name</th><th>Schedule</th><th>Format</th><th>Last run</th><th></th></tr>
          </thead>
          <tbody>
            {saved.length === 0 ? (
              <tr>
                <td colSpan={5} className="empty">
                  No saved reports yet. Generate a report or schedule one to see it here.
                </td>
              </tr>
            ) : (
              saved.map((r) => (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td>{r.schedule}</td>
                  <td>{r.format.toUpperCase()}</td>
                  <td>{fmtDate(r.last_run_at)}</td>
                  <td>
                    <button
                      className="btn sm"
                      style={{ padding: '2px 8px', fontSize: 11 }}
                      onClick={() => handleDelete(r.id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
