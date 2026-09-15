import { useEffect, useState } from 'react'
import './App.css'

type Row = {
  row_number: number
  cleaned: Record<string, string | null>
  errors: string[]
  valid?: boolean
  imported?: boolean
}
type Report = {
  job_id?: string
  filename: string
  total_rows: number
  valid_rows?: number
  imported_rows?: number
  rejected_rows: number
  replayed?: boolean
  rows: Row[]
}
type Job = {
  id: string
  filename: string
  imported_rows: number
  rejected_rows: number
  created_at: string
}
const fields = [
  ['full_name', 'Full name', true],
  ['email', 'Email address', true],
  ['company', 'Company', false],
  ['phone', 'Phone', false],
] as const

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options)
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(
      typeof body?.detail === 'string'
        ? body.detail
        : `Request failed (${response.status}). Check that the API is running.`,
    )
  }
  return body as T
}

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [headers, setHeaders] = useState<string[]>([])
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [report, setReport] = useState<Report | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [rejectedOnly, setRejectedOnly] = useState(false)

  useEffect(() => {
    let active = true
    request<{ items: Job[] }>('/imports')
      .then(data => { if (active) setJobs(data.items) })
      .catch(err => { if (active) setError(String(err.message)) })
    return () => { active = false }
  }, [])

  async function chooseFile(selected: File | null) {
    setFile(null)
    setHeaders([])
    setMapping({})
    setReport(null)
    setError('')
    if (!selected) return
    setBusy(true)
    try {
      const data = new FormData()
      data.append('file', selected)
      const result = await request<{ headers: string[] }>('/files/inspect', {
        method: 'POST', body: data,
      })
      const aliases: Record<string, string[]> = {
        full_name: ['name', 'full_name', 'full name'],
        email: ['email', 'email address'],
        company: ['company', 'organization'],
        phone: ['phone', 'telephone'],
      }
      const guessed: Record<string, string> = {}
      for (const [field, names] of Object.entries(aliases)) {
        const match = result.headers.find(h => names.includes(h.toLowerCase()))
        if (match) guessed[field] = match
      }
      setFile(selected)
      setHeaders(result.headers)
      setMapping(guessed)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  async function run(mode: 'preview' | 'commit') {
    if (!file) return
    setBusy(true)
    setError('')
    try {
      const data = new FormData()
      data.append('file', file)
      data.append('mapping', JSON.stringify(
        Object.fromEntries(Object.entries(mapping).filter(([, value]) => value)),
      ))
      const result = await request<Report>(`/imports/${mode}`, {
        method: 'POST', body: data,
      })
      setReport(result)
      if (mode === 'commit') {
        const history = await request<{ items: Job[] }>('/imports')
        setJobs(history.items)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed.')
    } finally {
      setBusy(false)
    }
  }

  async function openReport(id: string) {
    setBusy(true)
    setError('')
    try {
      setReport(await request<Report>(`/imports/${id}`))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load report.')
    } finally {
      setBusy(false)
    }
  }

  const selected = Object.values(mapping).filter(Boolean)
  const mappingReady = Boolean(mapping.full_name && mapping.email)
    && new Set(selected).size === selected.length
  const visibleRows = (report?.rows ?? [])
    .filter(row => !rejectedOnly || row.errors.length > 0)
  const accepted = report?.imported_rows ?? report?.valid_rows ?? 0

  return (
    <main>
      <nav><strong>▣ ImportGuard</strong><span>Customer data workspace</span></nav>
      <header>
        <p className="eyebrow">CHECK FIRST. IMPORT WITH CONFIDENCE.</p>
        <h1>Clean imports.<br /><span>Clear results.</span></h1>
        <p>Map your columns, catch invalid records, and keep a report of every import.</p>
      </header>

      {error && <div className="error" role="alert">{error}</div>}
      <div className="workspace">
        <section className="card">
          <div className="section-heading"><span className="step">01</span><h2>Choose your data</h2></div>
          <label className="upload">
            <strong>{file?.name ?? 'Select a customer CSV'}</strong>
            <span>UTF-8 CSV · Up to 5 MB · 10,000 rows</span>
            <input type="file" accept=".csv" disabled={busy}
              onChange={event => void chooseFile(event.target.files?.[0] ?? null)} />
          </label>
          {headers.length > 0 && <>
            <div className="section-heading"><span className="step">02</span><h2>Match columns</h2></div>
            {fields.map(([field, label, required]) => (
              <label className="mapping" key={field}>
                <span>{label}{required ? ' *' : ''}</span>
                <select value={mapping[field] ?? ''} disabled={busy}
                  onChange={event => {
                    setMapping({ ...mapping, [field]: event.target.value })
                    setReport(null)
                  }}>
                  <option value="">{required ? 'Choose a column' : 'Skip this field'}</option>
                  {headers.map(h => <option key={h} value={h}>{h}</option>)}
                </select>
              </label>
            ))}
            <button disabled={busy || !mappingReady} onClick={() => void run('preview')}>
              {busy ? 'Working…' : 'Preview and validate'}
            </button>
          </>}
        </section>

        <section className="card history">
          <div className="section-heading"><span className="step">↺</span><h2>Recent imports</h2></div>
          <p className="muted">Saved outcomes, ready to revisit.</p>
          {jobs.length === 0 && <p>No completed imports yet.</p>}
          {jobs.map(job => (
            <button className="history-item" key={job.id} disabled={busy}
              onClick={() => void openReport(job.id)}>
              <strong>{job.filename}</strong>
              <span>{job.imported_rows} imported · {job.rejected_rows} rejected</span>
              <small>{new Date(job.created_at).toLocaleString()}</small>
            </button>
          ))}
        </section>
      </div>

      {report && <section className="card results">
        <div className="result-heading">
          <div><p className="eyebrow">{report.job_id ? 'SAVED REPORT' : 'VALIDATION PREVIEW'}</p>
            <h2>{report.filename}</h2></div>
          {report.job_id
            ? <a className="download" href={`/api/imports/${report.job_id}/rejections.csv`}>
                Download rejected rows
              </a>
            : <button disabled={busy || accepted === 0}
                onClick={() => void run('commit')}>
                {busy ? 'Importing…' : `Import ${accepted} valid rows`}
              </button>}
        </div>
        {report.replayed && <p>This file and mapping were already imported. Showing the original report.</p>}
        <div className="metrics">
          <div><strong>{report.total_rows}</strong><span>Total rows</span></div>
          <div className="good"><strong>{accepted}</strong><span>{report.job_id ? 'Imported' : 'Ready to import'}</span></div>
          <div className="bad"><strong>{report.rejected_rows}</strong><span>Rejected</span></div>
        </div>
        {!report.job_id && <p className="muted">Nothing saved yet. Final counts can change if another import adds the same customers.</p>}
        <label className="filter"><input type="checkbox" checked={rejectedOnly}
          onChange={event => setRejectedOnly(event.target.checked)} /> Show rejected rows only</label>
        <div className="table-wrap"><table>
          <thead><tr><th>Line</th><th>Name</th><th>Email</th><th>Result</th></tr></thead>
          <tbody>{visibleRows.slice(0, 100).map(row => (
            <tr key={row.row_number}>
              <td>{row.row_number}</td>
              <td>{row.cleaned.full_name ?? '—'}</td>
              <td>{row.cleaned.email ?? '—'}</td>
              <td>{row.errors.length
                ? <span className="row-error">{row.errors.join(' ')}</span>
                : <span className="badge">{report.job_id ? 'Imported' : 'Ready'}</span>}</td>
            </tr>
          ))}</tbody>
        </table></div>
        {visibleRows.length === 0 && <p>No rows match this filter.</p>}
        {visibleRows.length > 100 && <p className="muted">Showing the first 100 matching rows.</p>}
      </section>}
      <footer>ImportGuard · Existing customers are never overwritten.</footer>
    </main>
  )
}
