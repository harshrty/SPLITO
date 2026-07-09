import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../api/client";
import { rupees } from "../lib/money";

export default function GroupDetail() {
  const { id } = useParams();
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["balances", id] });
    qc.invalidateQueries({ queryKey: ["expenses", id] });
  };

  const people = useQuery({ queryKey: ["people", id], queryFn: () => client.get(`/groups/${id}/people/`).then((r) => r.data) });
  const expenses = useQuery({ queryKey: ["expenses", id], queryFn: () => client.get(`/groups/${id}/expenses/`).then((r) => r.data) });
  const balances = useQuery({ queryKey: ["balances", id], queryFn: () => client.get(`/groups/${id}/balances/`).then((r) => r.data) });
  const simplified = useQuery({ queryKey: ["simplified", id], queryFn: () => client.get(`/groups/${id}/balances/simplified/`).then((r) => r.data) });

  const nameOf = (pid) => people.data?.find((p) => p.id === pid)?.canonical_name || `#${pid}`;

  const [pname, setPname] = useState("");
  const addPerson = useMutation({
    mutationFn: () => client.post(`/groups/${id}/people/`, { canonical_name: pname }),
    onSuccess: () => { setPname(""); qc.invalidateQueries({ queryKey: ["people", id] }); },
  });

  const [exp, setExp] = useState({ spent_on: "", description: "", paid_by: "", amount: "", currency: "INR", participants: [] });
  const addExpense = useMutation({
    mutationFn: () =>
      client.post(`/groups/${id}/expenses/`, {
        ...exp, paid_by: Number(exp.paid_by), split_type: "equal",
        participants: exp.participants.map(Number),
      }),
    onSuccess: () => { setExp({ spent_on: "", description: "", paid_by: "", amount: "", currency: "INR", participants: [] }); invalidate(); qc.invalidateQueries({ queryKey: ["simplified", id] }); },
  });

  const [settle, setSettle] = useState({ from_person: "", to_person: "", amount: "", settled_on: "" });
  const addSettle = useMutation({
    mutationFn: () =>
      client.post(`/groups/${id}/settlements/`, {
        from_person: Number(settle.from_person), to_person: Number(settle.to_person),
        amount_minor: Math.round(Number(settle.amount) * 100), settled_on: settle.settled_on,
      }),
    onSuccess: () => { setSettle({ from_person: "", to_person: "", amount: "", settled_on: "" }); invalidate(); qc.invalidateQueries({ queryKey: ["simplified", id] }); },
  });

  const toggle = (pid) =>
    setExp((e) => ({ ...e, participants: e.participants.includes(pid) ? e.participants.filter((x) => x !== pid) : [...e.participants, pid] }));

  return (
    <div>
      <div className="row between">
        <h2>Group #{id}</h2>
        <Link to={`/groups/${id}/import`}><button>Import CSV →</button></Link>
      </div>

      <div className="grid2">
        <div className="card">
          <h3>People</h3>
          <ul className="list">
            {people.data?.map((p) => <li key={p.id}>{p.canonical_name}{p.is_guest ? " (guest)" : ""}</li>)}
          </ul>
          <div className="row">
            <input placeholder="Add person" value={pname} onChange={(e) => setPname(e.target.value)} />
            <button disabled={!pname} onClick={() => addPerson.mutate()}>Add</button>
          </div>
        </div>

        <div className="card">
          <h3>Balances</h3>
          <table>
            <tbody>
              {balances.data?.map((b) => (
                <tr key={b.person_id}>
                  <td>{nameOf(b.person_id)}</td>
                  <td className={b.net_minor >= 0 ? "pos" : "neg"}>{rupees(b.net_minor)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <h4>Who pays whom</h4>
          <ul className="list">
            {simplified.data?.map((t, i) => (
              <li key={i}>{nameOf(t.from_person_id)} → {nameOf(t.to_person_id)}: <b>{rupees(t.amount_minor)}</b></li>
            ))}
            {simplified.data?.length === 0 && <li className="muted">All settled up.</li>}
          </ul>
        </div>
      </div>

      <div className="card">
        <h3>Add expense (equal split)</h3>
        <div className="row wrap">
          <input type="date" value={exp.spent_on} onChange={(e) => setExp({ ...exp, spent_on: e.target.value })} />
          <input placeholder="Description" value={exp.description} onChange={(e) => setExp({ ...exp, description: e.target.value })} />
          <input placeholder="Amount" value={exp.amount} onChange={(e) => setExp({ ...exp, amount: e.target.value })} />
          <select value={exp.currency} onChange={(e) => setExp({ ...exp, currency: e.target.value })}>
            <option>INR</option><option>USD</option>
          </select>
          <select value={exp.paid_by} onChange={(e) => setExp({ ...exp, paid_by: e.target.value })}>
            <option value="">paid by…</option>
            {people.data?.map((p) => <option key={p.id} value={p.id}>{p.canonical_name}</option>)}
          </select>
        </div>
        <div className="row wrap">
          {people.data?.map((p) => (
            <label key={p.id} className="chip">
              <input type="checkbox" checked={exp.participants.includes(p.id)} onChange={() => toggle(p.id)} /> {p.canonical_name}
            </label>
          ))}
        </div>
        <button disabled={!exp.paid_by || !exp.amount || exp.participants.length === 0} onClick={() => addExpense.mutate()}>Add expense</button>
        {addExpense.isError && <p className="error">{JSON.stringify(addExpense.error.response?.data)}</p>}
      </div>

      <div className="card">
        <h3>Expenses</h3>
        <table>
          <thead><tr><th>Date</th><th>Description</th><th>Paid by</th><th>Amount</th><th>Split</th></tr></thead>
          <tbody>
            {expenses.data?.map((e) => (
              <tr key={e.id} className={e.status === "void" ? "muted" : ""}>
                <td>{e.spent_on}</td><td>{e.description}</td><td>{nameOf(e.paid_by)}</td>
                <td>{rupees(e.amount_base_minor)}{e.original_currency !== "INR" ? ` (${e.original_currency})` : ""}</td>
                <td>{e.split_type}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Record a settlement</h3>
        <div className="row wrap">
          <select value={settle.from_person} onChange={(e) => setSettle({ ...settle, from_person: e.target.value })}>
            <option value="">from…</option>{people.data?.map((p) => <option key={p.id} value={p.id}>{p.canonical_name}</option>)}
          </select>
          <select value={settle.to_person} onChange={(e) => setSettle({ ...settle, to_person: e.target.value })}>
            <option value="">to…</option>{people.data?.map((p) => <option key={p.id} value={p.id}>{p.canonical_name}</option>)}
          </select>
          <input placeholder="Amount ₹" value={settle.amount} onChange={(e) => setSettle({ ...settle, amount: e.target.value })} />
          <input type="date" value={settle.settled_on} onChange={(e) => setSettle({ ...settle, settled_on: e.target.value })} />
          <button disabled={!settle.from_person || !settle.to_person || !settle.amount} onClick={() => addSettle.mutate()}>Settle</button>
        </div>
      </div>
    </div>
  );
}
