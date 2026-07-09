import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../api/client";
import { Icon, Avatar, Badge, EmptyState, Spinner } from "../components/ui";

export default function Groups() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const { data: groups = [], isLoading } = useQuery({
    queryKey: ["groups"],
    queryFn: () => client.get("/groups/").then((r) => r.data),
  });
  const create = useMutation({
    mutationFn: () => client.post("/groups/", { name }),
    onSuccess: () => {
      setName("");
      qc.invalidateQueries({ queryKey: ["groups"] });
    },
  });

  return (
    <div className="stack gap-lg">
      <div className="section-head">
        <div>
          <h1>Your groups</h1>
          <p className="sub">Track shared expenses and settle up across your households and trips.</p>
        </div>
      </div>

      <div className="card">
        <div className="card-head">
          <h3><span className="head-icon"><Icon name="plus" size={18} /></span> Create a group</h3>
        </div>
        <form
          className="row"
          onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(); }}
        >
          <input placeholder="e.g. Flat 4B, Goa trip…" value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" disabled={!name.trim() || create.isPending} style={{ whiteSpace: "nowrap" }}>
            <Icon name="plus" size={16} /> Create
          </button>
        </form>
      </div>

      {isLoading ? (
        <Spinner label="Loading your groups…" />
      ) : groups.length === 0 ? (
        <div className="card">
          <EmptyState icon="users" title="No groups yet">
            Create your first group above to start splitting expenses.
          </EmptyState>
        </div>
      ) : (
        <div className="grid-groups">
          {groups.map((g) => (
            <Link key={g.id} to={`/groups/${g.id}`} className="card" style={{ display: "block", textDecoration: "none", color: "inherit" }}>
              <div className="row between" style={{ marginBottom: 16 }}>
                <Avatar name={g.name} className="lg" />
                <Icon name="chevronRight" size={18} style={{ color: "var(--text-3)" }} />
              </div>
              <h3 style={{ marginBottom: 6 }}>{g.name}</h3>
              <Badge tone="brand"><Icon name="globe" size={13} /> {g.base_currency}</Badge>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
