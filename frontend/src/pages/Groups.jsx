import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import client from "../api/client";

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
    <div className="card">
      <h2>Your groups</h2>
      <div className="row">
        <input placeholder="New group name" value={name} onChange={(e) => setName(e.target.value)} />
        <button disabled={!name} onClick={() => create.mutate()}>Create</button>
      </div>
      {isLoading ? (
        <p className="muted">Loading…</p>
      ) : (
        <ul className="list">
          {groups.map((g) => (
            <li key={g.id}>
              <Link to={`/groups/${g.id}`}>{g.name}</Link>
              <span className="muted"> · {g.base_currency}</span>
            </li>
          ))}
          {groups.length === 0 && <p className="muted">No groups yet — create one.</p>}
        </ul>
      )}
    </div>
  );
}
