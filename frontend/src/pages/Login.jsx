import { useState } from "react";
import { useNavigate } from "react-router-dom";
import client from "../api/client";
import { useAuth } from "../store/auth";

export default function Login() {
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ email: "", password: "", display_name: "" });
  const [error, setError] = useState("");
  const setAuth = useAuth((s) => s.setAuth);
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      if (mode === "register") {
        await client.post("/auth/register/", form);
      }
      const { data } = await client.post("/auth/login/", {
        email: form.email,
        password: form.password,
      });
      setAuth(data.access, data.user);
      navigate("/");
    } catch (err) {
      setError(JSON.stringify(err.response?.data || "request failed"));
    }
  };

  return (
    <div className="card narrow">
      <h1>SPLITO</h1>
      <p className="muted">Shared expenses, done honestly.</p>
      <form onSubmit={submit}>
        {mode === "register" && (
          <input
            placeholder="Display name"
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
          />
        )}
        <input
          placeholder="Email"
          type="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <input
          placeholder="Password"
          type="password"
          value={form.password}
          onChange={(e) => setForm({ ...form, password: e.target.value })}
        />
        <button type="submit">{mode === "login" ? "Log in" : "Register"}</button>
      </form>
      {error && <p className="error">{error}</p>}
      <p className="muted">
        {mode === "login" ? "New here?" : "Have an account?"}{" "}
        <a onClick={() => setMode(mode === "login" ? "register" : "login")}>
          {mode === "login" ? "Register" : "Log in"}
        </a>
      </p>
    </div>
  );
}
