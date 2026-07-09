import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../store/auth";

export default function Landing() {
  const token = useAuth((s) => s.token);
  if (token) return <Navigate to="/app" replace />;

  return (
    <div className="landing">
      <header className="landing-nav">
        <span className="brand">SPLITO</span>
        <div className="row">
          <Link to="/login"><button className="ghost">Sign in</button></Link>
          <Link to="/signup"><button>Sign up</button></Link>
        </div>
      </header>

      <section className="hero">
        <h1>Shared expenses,<br /><span className="accent-text">done honestly.</span></h1>
        <p className="lead">
          Split rent, trips and groceries across a household whose members change over time —
          with mixed currencies, an auditable trail, and a messy-spreadsheet importer that never
          guesses silently.
        </p>
        <div className="row cta">
          <Link to="/signup"><button className="big">Get started — Sign up</button></Link>
          <Link to="/login"><button className="big ghost">Sign in</button></Link>
        </div>

        <div className="features">
          <div className="feature"><b>One number per person</b><span>Net "who pays whom", simplified.</span></div>
          <div className="feature"><b>No magic numbers</b><span>Every rupee traces to an expense.</span></div>
          <div className="feature"><b>INR + USD</b><span>Correct, snapshotted conversions.</span></div>
          <div className="feature"><b>Safe import</b><span>Detect → review → approve → commit.</span></div>
        </div>
      </section>
    </div>
  );
}
