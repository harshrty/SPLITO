import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../api/client";
import { rupees } from "../lib/money";
import { Icon, Avatar, Badge, EmptyState, Spinner } from "../components/ui";

export default function GroupDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["balances", id] });
    qc.invalidateQueries({ queryKey: ["expenses", id] });
    qc.invalidateQueries({ queryKey: ["simplified", id] });
  };

  const today = new Date().toISOString().slice(0, 10);

  const group = useQuery({ queryKey: ["group", id], queryFn: () => client.get(`/groups/${id}/`).then((r) => r.data) });
  const people = useQuery({ queryKey: ["people", id], queryFn: () => client.get(`/groups/${id}/people/`).then((r) => r.data) });
  const memberships = useQuery({ queryKey: ["memberships", id], queryFn: () => client.get(`/groups/${id}/memberships/`).then((r) => r.data) });
  const expenses = useQuery({ queryKey: ["expenses", id], queryFn: () => client.get(`/groups/${id}/expenses/`).then((r) => r.data) });
  const balances = useQuery({ queryKey: ["balances", id], queryFn: () => client.get(`/groups/${id}/balances/`).then((r) => r.data) });
  const simplified = useQuery({ queryKey: ["simplified", id], queryFn: () => client.get(`/groups/${id}/balances/simplified/`).then((r) => r.data) });

  const nameOf = (pid) => people.data?.find((p) => p.id === pid)?.canonical_name || `#${pid}`;
  const membershipOf = (pid) => memberships.data?.find((m) => m.person === pid);

  const [pname, setPname] = useState("");
  const [pjoined, setPjoined] = useState(today);
  const addPerson = useMutation({
    // A person needs a membership to bear expenses (temporal membership rule),
    // so create the Person and an open-ended Membership together.
    mutationFn: async () => {
      const { data: person } = await client.post(`/groups/${id}/people/`, { canonical_name: pname });
      await client.post(`/groups/${id}/memberships/`, { person: person.id, joined_on: pjoined || today });
      return person;
    },
    onSuccess: () => {
      setPname(""); setPjoined(today);
      qc.invalidateQueries({ queryKey: ["people", id] });
      qc.invalidateQueries({ queryKey: ["memberships", id] });
    },
  });

  const emptyExp = { spent_on: today, description: "", paid_by: "", amount: "", currency: "INR", participants: [] };
  const [exp, setExp] = useState(emptyExp);
  const addExpense = useMutation({
    mutationFn: () =>
      client.post(`/groups/${id}/expenses/`, {
        ...exp, paid_by: Number(exp.paid_by), split_type: "equal",
        participants: exp.participants.map(Number),
      }),
    onSuccess: () => { setExp(emptyExp); invalidate(); },
  });

  const emptySettle = { from_person: "", to_person: "", amount: "", settled_on: today };
  const [settle, setSettle] = useState(emptySettle);
  const addSettle = useMutation({
    mutationFn: () =>
      client.post(`/groups/${id}/settlements/`, {
        from_person: Number(settle.from_person), to_person: Number(settle.to_person),
        amount_minor: Math.round(Number(settle.amount) * 100), settled_on: settle.settled_on,
      }),
    onSuccess: () => { setSettle(emptySettle); invalidate(); },
  });

  const toggle = (pid) =>
    setExp((e) => ({ ...e, participants: e.participants.includes(pid) ? e.participants.filter((x) => x !== pid) : [...e.participants, pid] }));

  const activeExpenses = (expenses.data || []).filter((e) => e.status !== "void");
  const totalSpent = activeExpenses.reduce((s, e) => s + (e.amount_base_minor || 0), 0);
  const openTransfers = simplified.data?.length || 0;
  const settledUp = simplified.data && openTransfers === 0;

  return (
    <div className="stack gap-lg">
      <div className="section-head">
        <div className="row" style={{ gap: 14 }}>
          <Link to="/app" className="btn ghost sm icon-btn" title="All groups"><Icon name="arrowLeft" size={16} /></Link>
          <Avatar name={group.data?.name || "Group"} className="lg" />
          <div>
            <h1>{group.data?.name || `Group #${id}`}</h1>
            <p className="sub">
              {people.data?.length ?? "—"} people · base currency {group.data?.base_currency || "INR"}
            </p>
          </div>
        </div>
        <Link to={`/groups/${id}/import`}><button className="ghost"><Icon name="upload" size={16} /> Import spreadsheet</button></Link>
      </div>

      {/* stat tiles */}
      <div className="stats">
        <div className="stat">
          <div className="stat-icon"><Icon name="users" size={18} /></div>
          <div className="stat-label">People</div>
          <div className="stat-value">{people.data?.length ?? "—"}</div>
        </div>
        <div className="stat">
          <div className="stat-icon"><Icon name="receipt" size={18} /></div>
          <div className="stat-label">Expenses</div>
          <div className="stat-value">{activeExpenses.length}</div>
        </div>
        <div className="stat">
          <div className="stat-icon"><Icon name="wallet" size={18} /></div>
          <div className="stat-label">Total spent</div>
          <div className="stat-value">{rupees(totalSpent)}</div>
        </div>
        <div className={`stat ${settledUp ? "pos" : "neg"}`}>
          <div className="stat-icon"><Icon name={settledUp ? "checkCircle" : "handshake"} size={18} /></div>
          <div className="stat-label">Open transfers</div>
          <div className="stat-value">{simplified.data ? openTransfers : "—"}</div>
        </div>
      </div>

      <div className="grid2">
        {/* People */}
        <div className="card">
          <div className="card-head">
            <h3><span className="head-icon"><Icon name="users" size={18} /></span> People</h3>
          </div>
          {people.data?.length ? (
            <ul className="list divided">
              {people.data.map((p) => {
                const m = membershipOf(p.id);
                return (
                  <li key={p.id}>
                    <Avatar name={p.canonical_name} className="sm" />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 500 }}>{p.canonical_name}</div>
                      {m && (
                        <div className="faint" style={{ fontSize: 12 }}>
                          {m.left_on ? `${m.joined_on} → ${m.left_on}` : `Member since ${m.joined_on}`}
                        </div>
                      )}
                    </div>
                    {p.is_guest && <Badge tone="neutral">guest</Badge>}
                  </li>
                );
              })}
            </ul>
          ) : (
            <EmptyState icon="users" title="No people yet">Add the members of this group below.</EmptyState>
          )}
          <form className="stack gap-sm" style={{ marginTop: 14 }}
            onSubmit={(e) => { e.preventDefault(); if (pname.trim()) addPerson.mutate(); }}>
            <input placeholder="Add a person" value={pname} onChange={(e) => setPname(e.target.value)} />
            <div className="row" style={{ alignItems: "flex-end" }}>
              <label className="field" style={{ flex: 1, fontSize: 12 }}>Member since
                <input type="date" value={pjoined} onChange={(e) => setPjoined(e.target.value)} />
              </label>
              <button type="submit" disabled={!pname.trim() || addPerson.isPending}><Icon name="plus" size={16} /> Add</button>
            </div>
            {addPerson.isError && <span className="error">{JSON.stringify(addPerson.error.response?.data)}</span>}
          </form>
        </div>

        {/* Balances */}
        <div className="card">
          <div className="card-head">
            <h3><span className="head-icon"><Icon name="scale" size={18} /></span> Balances</h3>
          </div>
          {balances.data?.length ? (
            <ul className="list divided">
              {balances.data.map((b) => (
                <li key={b.person_id}>
                  <Avatar name={nameOf(b.person_id)} className="sm" />
                  <span style={{ fontWeight: 500, flex: 1 }}>{nameOf(b.person_id)}</span>
                  <span className={`mono ${b.net_minor >= 0 ? "pos" : "neg"}`}>
                    {b.net_minor >= 0 ? "gets back " : "owes "}{rupees(Math.abs(b.net_minor))}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState icon="scale" title="Nothing to balance">Add expenses to see who owes what.</EmptyState>
          )}

          <h4 style={{ margin: "20px 0 10px" }}>Who pays whom</h4>
          {settledUp ? (
            <div className="alert info"><Icon name="checkCircle" size={18} /><span>All settled up — no transfers needed.</span></div>
          ) : (
            <ul className="stack gap-sm" style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {simplified.data?.map((t, i) => (
                <li key={i} className="row" style={{ padding: "10px 12px", background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)" }}>
                  <Avatar name={nameOf(t.from_person_id)} className="sm" />
                  <span style={{ fontWeight: 500 }}>{nameOf(t.from_person_id)}</span>
                  <Icon name="arrowRight" size={15} style={{ color: "var(--text-3)" }} />
                  <Avatar name={nameOf(t.to_person_id)} className="sm" />
                  <span style={{ fontWeight: 500 }}>{nameOf(t.to_person_id)}</span>
                  <span className="spacer" />
                  <span className="mono" style={{ fontWeight: 700 }}>{rupees(t.amount_minor)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Add expense */}
      <div className="card">
        <div className="card-head">
          <h3><span className="head-icon"><Icon name="plus" size={18} /></span> Add expense</h3>
          <Badge tone="neutral">equal split</Badge>
        </div>
        <div className="row wrap" style={{ marginBottom: 14 }}>
          <label className="field" style={{ flex: "1 1 130px" }}>Date
            <input type="date" value={exp.spent_on} onChange={(e) => setExp({ ...exp, spent_on: e.target.value })} />
          </label>
          <label className="field" style={{ flex: "3 1 220px" }}>Description
            <input placeholder="e.g. Groceries" value={exp.description} onChange={(e) => setExp({ ...exp, description: e.target.value })} />
          </label>
          <label className="field" style={{ flex: "1 1 120px" }}>Amount
            <input placeholder="0.00" value={exp.amount} onChange={(e) => setExp({ ...exp, amount: e.target.value })} />
          </label>
          <label className="field" style={{ flex: "0 1 100px" }}>Currency
            <select value={exp.currency} onChange={(e) => setExp({ ...exp, currency: e.target.value })}>
              <option>INR</option><option>USD</option>
            </select>
          </label>
          <label className="field" style={{ flex: "1 1 150px" }}>Paid by
            <select value={exp.paid_by} onChange={(e) => setExp({ ...exp, paid_by: e.target.value })}>
              <option value="">Select…</option>
              {people.data?.map((p) => <option key={p.id} value={p.id}>{p.canonical_name}</option>)}
            </select>
          </label>
        </div>
        <div className="stack gap-sm">
          <span className="field" style={{ color: "var(--text-2)" }}>Split between</span>
          {people.data?.length ? (
            <div className="row wrap">
              {people.data.map((p) => {
                const on = exp.participants.includes(p.id);
                return (
                  <label key={p.id} className={`chip ${on ? "on" : ""}`}>
                    <input type="checkbox" checked={on} onChange={() => toggle(p.id)} style={{ display: "none" }} />
                    <Avatar name={p.canonical_name} className="sm" /> {p.canonical_name}
                    {on && <Icon name="check" size={14} />}
                  </label>
                );
              })}
            </div>
          ) : <span className="faint">Add people first.</span>}
        </div>
        <div className="row between" style={{ marginTop: 16 }}>
          {addExpense.isError
            ? <span className="error">{JSON.stringify(addExpense.error.response?.data)}</span>
            : <span />}
          <button disabled={!exp.paid_by || !exp.amount || exp.participants.length === 0 || addExpense.isPending}
            onClick={() => addExpense.mutate()}>
            <Icon name="plus" size={16} /> Add expense
          </button>
        </div>
      </div>

      {/* Expenses table */}
      <div className="card">
        <div className="card-head">
          <h3><span className="head-icon"><Icon name="receipt" size={18} /></span> Expenses</h3>
          <span className="faint">{activeExpenses.length} active</span>
        </div>
        {expenses.isLoading ? (
          <Spinner label="Loading expenses…" />
        ) : expenses.data?.length ? (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Date</th><th>Description</th><th>Paid by</th><th className="num">Amount</th><th>Split</th></tr></thead>
              <tbody>
                {expenses.data.map((e) => (
                  <tr key={e.id} className={e.status === "void" ? "row-void" : ""}>
                    <td className="mono faint" style={{ whiteSpace: "nowrap" }}>{e.spent_on}</td>
                    <td style={{ fontWeight: 500 }}>{e.description || <span className="faint">—</span>}</td>
                    <td>
                      <span className="row" style={{ gap: 8 }}>
                        <Avatar name={nameOf(e.paid_by)} className="sm" /> {nameOf(e.paid_by)}
                      </span>
                    </td>
                    <td className="num mono" style={{ fontWeight: 600 }}>
                      {rupees(e.amount_base_minor)}
                      {e.original_currency !== "INR" && <span className="faint"> {e.original_currency}</span>}
                    </td>
                    <td>{e.status === "void" ? <Badge tone="neg">void</Badge> : <Badge tone="neutral">{e.split_type}</Badge>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState icon="receipt" title="No expenses yet">Add an expense above or import a spreadsheet.</EmptyState>
        )}
      </div>

      {/* Settlement */}
      <div className="card">
        <div className="card-head">
          <h3><span className="head-icon"><Icon name="handshake" size={18} /></span> Record a settlement</h3>
        </div>
        <div className="row wrap">
          <label className="field" style={{ flex: "1 1 150px" }}>From
            <select value={settle.from_person} onChange={(e) => setSettle({ ...settle, from_person: e.target.value })}>
              <option value="">Select…</option>{people.data?.map((p) => <option key={p.id} value={p.id}>{p.canonical_name}</option>)}
            </select>
          </label>
          <label className="field" style={{ flex: "1 1 150px" }}>To
            <select value={settle.to_person} onChange={(e) => setSettle({ ...settle, to_person: e.target.value })}>
              <option value="">Select…</option>{people.data?.map((p) => <option key={p.id} value={p.id}>{p.canonical_name}</option>)}
            </select>
          </label>
          <label className="field" style={{ flex: "1 1 120px" }}>Amount ₹
            <input placeholder="0.00" value={settle.amount} onChange={(e) => setSettle({ ...settle, amount: e.target.value })} />
          </label>
          <label className="field" style={{ flex: "1 1 130px" }}>Date
            <input type="date" value={settle.settled_on} onChange={(e) => setSettle({ ...settle, settled_on: e.target.value })} />
          </label>
          <button style={{ alignSelf: "flex-end" }}
            disabled={!settle.from_person || !settle.to_person || !settle.amount || addSettle.isPending}
            onClick={() => addSettle.mutate()}>
            <Icon name="handshake" size={16} /> Settle
          </button>
        </div>
        {addSettle.isError && <p className="error" style={{ marginTop: 10 }}>{JSON.stringify(addSettle.error.response?.data)}</p>}
      </div>
    </div>
  );
}
