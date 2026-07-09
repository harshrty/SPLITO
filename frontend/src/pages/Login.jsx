import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";
import { useAuth } from "../store/auth";

// Strict-ish email check: local part, single @, dotted domain with a real TLD.
const EMAIL_RE =
  /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/;

export default function Login({ initial = "register" }) {
  const [mode, setMode] = useState(initial);
  const [form, setForm] = useState({ email: "", password: "", display_name: "" });
  const [error, setError] = useState("");
  const setAuth = useAuth((s) => s.setAuth);
  const navigate = useNavigate();

  const emailValid = EMAIL_RE.test(form.email);
  const emailTouched = form.email.length > 0;
  const canSubmit =
    emailValid &&
    form.password.length >= 8 &&
    (mode === "login" || form.display_name.trim().length > 0);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!emailValid) return setError("Please enter a valid email address.");
    try {
      if (mode === "register") await client.post("/auth/register/", form);
      const { data } = await client.post("/auth/login/", {
        email: form.email,
        password: form.password,
      });
      setAuth(data.access, data.user);
      navigate("/app");
    } catch (err) {
      const d = err.response?.data;
      setError(typeof d === "object" ? Object.values(d).flat().join(" ") : String(d || "Request failed"));
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <Link to="/" className="brand center">SPLITO</Link>
        <h1>{mode === "register" ? "Create your account" : "Welcome back"}</h1>
        <p className="muted center">
          {mode === "register" ? "Start splitting expenses honestly." : "Sign in to continue."}
        </p>
        <form onSubmit={submit}>
          {mode === "register" && (
            <label>
              <span>Display name</span>
              <input
                placeholder="e.g. Aisha"
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              />
            </label>
          )}
          <label>
            <span>Email</span>
            <input
              type="email"
              placeholder="you@example.com"
              value={form.email}
              className={emailTouched && !emailValid ? "invalid" : ""}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            {emailTouched && !emailValid && <small className="field-error">Enter a valid email address</small>}
          </label>
          <label>
            <span>Password</span>
            <input
              type="password"
              placeholder="At least 8 characters"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </label>
          <button type="submit" className="big" disabled={!canSubmit}>
            {mode === "login" ? "Sign in" : "Sign up"}
          </button>
        </form>
        {error && <p className="error center">{error}</p>}
        <p className="muted center switch">
          {mode === "login" ? "New to SPLITO? " : "Already have an account? "}
          <a onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
            {mode === "login" ? "Sign up" : "Sign in"}
          </a>
        </p>
      </div>
    </div>
  );
}
