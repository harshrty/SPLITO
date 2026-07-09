import { Link, Navigate } from "react-router-dom";
import { useAuth } from "../store/auth";
import { Brand, Icon } from "../components/ui";

const FEATURES = [
  { icon: "scale", title: "One number per person", body: 'Net "who pays whom", simplified to the fewest transfers.' },
  { icon: "receipt", title: "No magic numbers", body: "Every rupee traces back to a real expense and split." },
  { icon: "globe", title: "INR + USD", body: "Date-effective, snapshotted currency conversions." },
  { icon: "shield", title: "Safe import", body: "Detect → review → approve → commit. Never guesses silently." },
];

export default function Landing() {
  const token = useAuth((s) => s.token);
  if (token) return <Navigate to="/app" replace />;

  return (
    <div className="landing">
      <header className="landing-nav">
        <Brand />
        <div className="row">
          <Link to="/login"><button className="ghost">Sign in</button></Link>
          <Link to="/signup"><button>Sign up</button></Link>
        </div>
      </header>

      <section className="hero">
        <span className="eyebrow"><Icon name="sparkles" size={15} /> Shared expenses, done honestly</span>
        <h1>Split fairly.<br /><span className="grad">Settle with confidence.</span></h1>
        <p className="lead">
          Split rent, trips and groceries across a household whose members change over time —
          with mixed currencies, an auditable trail, and a messy-spreadsheet importer that never
          guesses silently.
        </p>
        <div className="row cta">
          <Link to="/signup"><button className="big">Get started <Icon name="arrowRight" size={17} /></button></Link>
          <Link to="/login"><button className="big ghost">Sign in</button></Link>
        </div>
      </section>

      <section className="features">
        {FEATURES.map((f) => (
          <div className="feature" key={f.title}>
            <div className="feature-icon"><Icon name={f.icon} size={20} /></div>
            <b>{f.title}</b>
            <span>{f.body}</span>
          </div>
        ))}
      </section>
    </div>
  );
}
