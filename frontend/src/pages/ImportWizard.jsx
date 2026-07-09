import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import client from "../api/client";

export default function ImportWizard() {
  const { id } = useParams();
  const [file, setFile] = useState(null);
  const [batch, setBatch] = useState(null);
  const [report, setReport] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const upload = async () => {
    setError(""); setResult(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await client.post(`/groups/${id}/import/`, fd);
      setBatch(data.batch_id);
      setReport(data.report);
    } catch (e) { setError(JSON.stringify(e.response?.data || "upload failed")); }
  };

  const resolve = async (anomalyId, status) => {
    await client.post(`/import/anomalies/${anomalyId}/resolve/`, { status });
    setReport((r) => r.map((a) => (a.id === anomalyId ? { ...a, status } : a)));
  };

  const commit = async () => {
    setError("");
    try {
      const { data } = await client.post(`/import/${batch}/commit/`);
      setResult(data);
    } catch (e) {
      setError(e.response?.status === 409 ? "Resolve all BLOCK anomalies first." : JSON.stringify(e.response?.data));
    }
  };

  const pendingBlocks = report.filter((a) => a.severity === "block" && a.status === "pending").length;

  return (
    <div>
      <div className="row between">
        <h2>Import CSV — Group #{id}</h2>
        <Link to={`/groups/${id}`}><button>← Back</button></Link>
      </div>

      {!batch && (
        <div className="card">
          <p className="muted">Upload <code>expenses_export</code> (.xlsx or .csv). Nothing is imported until you review and commit.</p>
          <input type="file" accept=".xlsx,.csv" onChange={(e) => setFile(e.target.files[0])} />
          <button disabled={!file} onClick={upload}>Upload &amp; scan</button>
        </div>
      )}

      {batch && !result && (
        <div className="card">
          <div className="row between">
            <h3>Import report — {report.length} anomalies</h3>
            <button disabled={pendingBlocks > 0} onClick={commit} title={pendingBlocks ? `${pendingBlocks} blocks pending` : ""}>
              Commit {pendingBlocks > 0 ? `(${pendingBlocks} blocks pending)` : ""}
            </button>
          </div>
          <table>
            <thead><tr><th>Row</th><th>Type</th><th>Severity</th><th>Detail</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              {report.map((a) => (
                <tr key={a.id} className={a.severity === "block" ? "block-row" : ""}>
                  <td>{a.row_number}</td>
                  <td><code>{a.anomaly_type}</code></td>
                  <td><span className={a.severity === "block" ? "neg" : "warn-txt"}>{a.severity}</span></td>
                  <td>{a.detail}</td>
                  <td>{a.status}</td>
                  <td>
                    {a.status === "pending" ? (
                      <>
                        <button onClick={() => resolve(a.id, "approved")}>Approve</button>{" "}
                        <button onClick={() => resolve(a.id, "rejected")}>Reject</button>
                      </>
                    ) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {result && (
        <div className="card">
          <h3>Import committed ✓</h3>
          <ul className="list">
            <li>Expenses created: <b>{result.created}</b></li>
            <li>Settlements created: <b>{result.settlements}</b></li>
            <li>Duplicates voided: <b>{result.voided}</b></li>
            <li>Rows skipped: <b>{result.skipped.length}</b></li>
          </ul>
          {result.skipped.length > 0 && (
            <details><summary>Skipped rows</summary>
              <ul className="list">{result.skipped.map((s, i) => <li key={i}>row {s.row}: {s.reason}</li>)}</ul>
            </details>
          )}
          <Link to={`/groups/${id}`}><button>View balances →</button></Link>
        </div>
      )}

      {error && <p className="error">{error}</p>}
    </div>
  );
}
