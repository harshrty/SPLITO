import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import client from "../api/client";
import { useAuth } from "../store/auth";
import { Brand, Icon } from "../components/ui";

// Strict-ish email check: local part, single @, dotted domain with a real TLD.
const EMAIL_RE =
  /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$/;

export default function Login({ initial = "register" }) {
  const [mode, setMode] = useState(initial);
  const [form, setForm] = useState({ email: "", password: "", display_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const setAuth = useAuth((s) => s.setAuth);
  const navigate = useNavigate();

  const emailValid = EMAIL_RE.test(form.email);
  const emailTouched = form.email.length > 0;
  const canSubmit =
    !busy &&
    emailValid &&
    form.password.length >= 8 &&
    (mode === "login" || form.display_name.trim().length > 0);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!emailValid) return setError("Please enter a valid email address.");
    setBusy(true);
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
    } finally {
      setBusy(false);
    }
  };

  const isReg = mode === "register";

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="brand-wrap">
          <Link to="/"><Brand /></Link>
        </div>
        <h1>{isReg ? "Create your account" : "Welcome back"}</h1>
        <p className="sub">
          {isReg ? "Start splitting expenses honestly." : "Sign in to continue to your groups."}
        </p>
        <form onSubmit={submit}>
          {isReg && (
            <label className="field">
              Display name
              <input
                placeholder="e.g. Aisha"
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
              />
            </label>
          )}
          <label className="field">
            Email
            <input
              type="email"
              placeholder="you@example.com"
              value={form.email}
              className={emailTouched && !emailValid ? "invalid" : ""}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
            />
            {emailTouched && !emailValid && <small className="field-error">Enter a valid email address</small>}
          </label>
          <label className="field">
            Password
            <input
              type="password"
              placeholder="At least 8 characters"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
            />
          </label>
          <button type="submit" className="big" disabled={!canSubmit}>
            {busy ? <span className="spinner" style={{ borderTopColor: "#fff", borderColor: "rgba(255,255,255,.4)" }} /> : <Icon name={isReg ? "sparkles" : "arrowRight"} size={17} />}
            {isReg ? "Create account" : "Sign in"}
          </button>
        </form>
        {error && (
          <div className="alert err" style={{ marginTop: 16 }}>
            <Icon name="alert" size={18} /><span>{error}</span>
          </div>
        )}
        <p className="switch">
          {isReg ? "Already have an account? " : "New to SPLITO? "}
          <a onClick={() => { setMode(isReg ? "login" : "register"); setError(""); }}>
            {isReg ? "Sign in" : "Create one free"}
          </a>
        </p>
      </div>
    </div>
  );
}
