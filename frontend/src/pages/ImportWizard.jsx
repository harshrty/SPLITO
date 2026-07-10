import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import client from "../api/client";
import { Icon, Badge, EmptyState } from "../components/ui";

function Stepper({ step }) {
  const steps = ["Upload", "People", "Review", "Done"];
  return (
    <div className="row" style={{ gap: 0, marginBottom: 22 }}>
      {steps.map((s, i) => {
        const state = i < step ? "done" : i === step ? "active" : "todo";
        return (
          <div key={s} className="row" style={{ gap: 0, flex: i < steps.length - 1 ? 1 : "0 0 auto" }}>
            <div className="row" style={{ gap: 8 }}>
              <span style={{
                width: 26, height: 26, borderRadius: "50%", display: "grid", placeItems: "center",
                fontSize: 13, fontWeight: 700,
                background: state === "todo" ? "var(--surface-3)" : "var(--brand)",
                color: state === "todo" ? "var(--text-3)" : "#fff",
              }}>
                {state === "done" ? <Icon name="check" size={14} /> : i + 1}
              </span>
              <span style={{ fontWeight: 600, fontSize: 14, color: state === "todo" ? "var(--text-3)" : "var(--text)" }}>{s}</span>
            </div>
            {i < steps.length - 1 && (
              <div style={{ flex: 1, height: 2, margin: "0 12px", background: i < step ? "var(--brand)" : "var(--border)" }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function ImportWizard() {
  const { id } = useParams();
  const [file, setFile] = useState(null);
  const [roster, setRoster] = useState(null);   // { candidates, suggested_start_date, existing_people }
  const [draft, setDraft] = useState([]);        // editable candidate rows
  const [startDate, setStartDate] = useState("");
  const [batch, setBatch] = useState(null);
  const [report, setReport] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const today = new Date().toISOString().slice(0, 10);

  // Step 0 → scan the sheet for people (persists nothing)
  const scan = async () => {
    setError(""); setResult(null); setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await client.post(`/groups/${id}/import/scan-roster/`, fd);
      // everyone already exists → skip the People step entirely
      if (data.candidates.length && data.candidates.every((c) => c.already_exists)) {
        await ingest();
        return;
      }
      setRoster(data);
      setStartDate(data.suggested_start_date || today);
      setDraft(data.candidates.map((c) => ({ ...c, include: !c.already_exists })));
    } catch (e) { setError(JSON.stringify(e.response?.data || "scan failed")); }
    finally { setBusy(false); }
  };

  // ingest + run detectors against the (now populated) roster
  const ingest = async () => {
    const fd = new FormData();
    fd.append("file", file);
    const { data } = await client.post(`/groups/${id}/import/`, fd);
    setBatch(data.batch_id);
    setReport(data.report);
  };

  // Step 1 → create the confirmed roster, then ingest
  const applyAndIngest = async () => {
    setError(""); setBusy(true);
    try {
      const people = draft.filter((d) => d.include).map((d) => ({
        canonical: d.canonical, is_guest: d.is_guest, aliases: d.variants,
      }));
      if (people.length) {
        await client.post(`/groups/${id}/import/apply-roster/`, { start_date: startDate, people });
      }
      await ingest();
    } catch (e) { setError(JSON.stringify(e.response?.data || "could not create roster")); }
    finally { setBusy(false); }
  };

  const updRow = (i, patch) => setDraft((d) => d.map((row, j) => (j === i ? { ...row, ...patch } : row)));

  const resolve = async (anomalyId, status) => {
    await client.post(`/import/anomalies/${anomalyId}/resolve/`, { status });
    setReport((r) => r.map((a) => (a.id === anomalyId ? { ...a, status } : a)));
  };

  const commit = async () => {
    setError(""); setBusy(true);
    try {
      const { data } = await client.post(`/import/${batch}/commit/`);
      setResult(data);
    } catch (e) {
      const detail = e.response?.data?.detail;
      setError(e.response?.status === 409 ? (detail || "Resolve all blocking anomalies first.") : JSON.stringify(e.response?.data));
    } finally { setBusy(false); }
  };

  const pendingBlocks = report.filter((a) => a.severity === "block" && a.status === "pending").length;
  const blocks = report.filter((a) => a.severity === "block").length;
  const includedCount = draft.filter((d) => d.include).length;
  const step = result ? 3 : batch ? 2 : roster ? 1 : 0;

  return (
    <div className="stack gap-lg">
      <div className="section-head">
        <div className="row" style={{ gap: 14 }}>
          <Link to={`/groups/${id}`} className="btn ghost sm icon-btn" title="Back to group"><Icon name="arrowLeft" size={16} /></Link>
          <div>
            <h1>Import spreadsheet</h1>
            <p className="sub">Scan → confirm people → review → commit. Nothing enters the ledger until you commit.</p>
          </div>
        </div>
      </div>

      <div className="card pad-lg">
        <Stepper step={step} />

        {step === 0 && (
          <div className="stack gap">
            <div className="alert info">
              <Icon name="info" size={18} />
              <span>Upload <code>expenses_export</code> (.xlsx or .csv). We first scan it for the people involved so the group's roster is set up before anything is imported.</span>
            </div>
            <label className="field">Spreadsheet file
              <input type="file" accept=".xlsx,.csv" onChange={(e) => setFile(e.target.files[0])} />
            </label>
            <div>
              <button disabled={!file || busy} onClick={scan}>
                {busy ? <span className="spinner" style={{ borderTopColor: "#fff", borderColor: "rgba(255,255,255,.4)" }} /> : <Icon name="users" size={16} />}
                Scan for people
              </button>
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="stack gap">
            <div className="row between wrap" style={{ gap: 12 }}>
              <div className="row" style={{ gap: 10 }}>
                <h3>Confirm the people</h3>
                <Badge tone="neutral">{draft.length} found</Badge>
                <Badge tone="pos">{includedCount} to add</Badge>
              </div>
              <button disabled={busy} onClick={applyAndIngest}>
                {busy ? <span className="spinner" style={{ borderTopColor: "#fff", borderColor: "rgba(255,255,255,.4)" }} /> : <Icon name="check" size={16} />}
                Create roster &amp; scan expenses
              </button>
            </div>
            <div className="alert info">
              <Icon name="sparkles" size={18} />
              <span>We pulled these names from the sheet and merged obvious spelling variants. Tick <b>Guest</b> for one-off people, untick anyone who shouldn't be added, and set the date everyone joined. Extra spellings become aliases automatically.</span>
            </div>
            <label className="field" style={{ maxWidth: 240 }}>Everyone joined on
              <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            </label>

            <div className="table-wrap">
              <table>
                <thead><tr><th>Add</th><th>Person</th><th>Guest</th><th>Spellings in file</th><th className="num">Rows</th></tr></thead>
                <tbody>
                  {draft.map((d, i) => (
                    <tr key={i} style={{ opacity: d.include ? 1 : 0.5 }}>
                      <td>
                        <input type="checkbox" checked={d.include} disabled={d.already_exists}
                          onChange={(e) => updRow(i, { include: e.target.checked })} />
                      </td>
                      <td>
                        <input value={d.canonical} onChange={(e) => updRow(i, { canonical: e.target.value })}
                          style={{ minWidth: 130, padding: "4px 8px" }} disabled={d.person_known} />
                        {d.already_exists
                          ? <span className="faint" style={{ fontSize: 11, marginLeft: 6 }}>already in group</span>
                          : d.person_known
                            ? <span className="faint" style={{ fontSize: 11, marginLeft: 6 }}>known · links new spelling</span>
                            : null}
                      </td>
                      <td>
                        <input type="checkbox" checked={d.is_guest} disabled={d.person_known}
                          onChange={(e) => updRow(i, { is_guest: e.target.checked })} />
                      </td>
                      <td>
                        <span className="row wrap" style={{ gap: 4 }}>
                          {d.variants.map((v) => <code key={v} style={{ fontSize: 11 }}>{v}</code>)}
                        </span>
                      </td>
                      <td className="num mono faint">{d.occurrences}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted" style={{ fontSize: 13 }}>
              Note: the sheet has no join/leave history — everyone gets the date above. You can refine individual leave dates
              (e.g. someone who moved out) on the group page afterwards.
            </p>
          </div>
        )}

        {step === 2 && (
          <div className="stack gap">
            <div className="row between wrap" style={{ gap: 12 }}>
              <div className="row" style={{ gap: 10 }}>
                <h3>Import report</h3>
                <Badge tone="neutral">{report.length} anomalies</Badge>
                {blocks > 0 && <Badge tone={pendingBlocks > 0 ? "neg" : "pos"}>{blocks} blocking</Badge>}
              </div>
              <button className="success" disabled={pendingBlocks > 0 || busy} onClick={commit}
                title={pendingBlocks ? `${pendingBlocks} blocking anomalies pending` : ""}>
                <Icon name="check" size={16} /> Commit import
                {pendingBlocks > 0 ? ` (${pendingBlocks} pending)` : ""}
              </button>
            </div>

            {pendingBlocks > 0 && (
              <div className="alert warn">
                <Icon name="alert" size={18} />
                <span>{pendingBlocks} blocking {pendingBlocks === 1 ? "anomaly" : "anomalies"} must be resolved before you can commit.</span>
              </div>
            )}

            {report.length === 0 ? (
              <EmptyState icon="checkCircle" title="Clean file">No anomalies detected — you can commit safely.</EmptyState>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Row</th><th>Type</th><th>Severity</th><th>Detail</th><th>Status</th><th>Action</th></tr></thead>
                  <tbody>
                    {report.map((a) => (
                      <tr key={a.id} className={a.severity === "block" && a.status === "pending" ? "block-row" : ""}>
                        <td className="mono faint">{a.row_number}</td>
                        <td><code>{a.anomaly_type}</code></td>
                        <td><Badge tone={a.severity === "block" ? "neg" : "warn"} dot>{a.severity}</Badge></td>
                        <td>{a.detail}</td>
                        <td>
                          {a.status === "pending"
                            ? <Badge tone="neutral">pending</Badge>
                            : <Badge tone={a.status === "approved" ? "pos" : "neutral"}>{a.status}</Badge>}
                        </td>
                        <td>
                          {a.status === "pending" ? (
                            <div className="row" style={{ gap: 6 }}>
                              <button className="success sm" onClick={() => resolve(a.id, "approved")}><Icon name="check" size={14} /> Approve</button>
                              <button className="subtle sm" onClick={() => resolve(a.id, "rejected")}><Icon name="x" size={14} /> Reject</button>
                            </div>
                          ) : <span className="faint">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {step === 3 && result && (
          <div className="stack gap">
            <div className="row" style={{ gap: 12 }}>
              <span className="stat-icon" style={{ background: "var(--pos-bg)", color: "var(--pos)", width: 44, height: 44 }}>
                <Icon name="checkCircle" size={22} />
              </span>
              <div>
                <h3>Import committed</h3>
                <p className="muted">Your ledger has been updated.</p>
              </div>
            </div>
            <div className="stats" style={{ margin: 0 }}>
              <div className="stat"><div className="stat-label">Expenses created</div><div className="stat-value">{result.created}</div></div>
              <div className="stat"><div className="stat-label">Settlements</div><div className="stat-value">{result.settlements}</div></div>
              <div className="stat"><div className="stat-label">Duplicates voided</div><div className="stat-value">{result.voided}</div></div>
              <div className="stat"><div className="stat-label">Rows skipped</div><div className="stat-value">{result.skipped.length}</div></div>
            </div>
            {result.skipped.length > 0 && (
              <details className="card" style={{ boxShadow: "none", background: "var(--surface-2)" }}>
                <summary style={{ cursor: "pointer", fontWeight: 600 }}>Skipped rows ({result.skipped.length})</summary>
                <ul className="list divided" style={{ marginTop: 10 }}>
                  {result.skipped.map((s, i) => <li key={i}><span className="mono faint">row {s.row}</span> {s.reason}</li>)}
                </ul>
              </details>
            )}
            <div>
              <Link to={`/groups/${id}`}><button><Icon name="scale" size={16} /> View balances</button></Link>
            </div>
          </div>
        )}

        {error && <div className="alert err" style={{ marginTop: 16 }}><Icon name="alert" size={18} /><span>{error}</span></div>}
      </div>
    </div>
  );
}
