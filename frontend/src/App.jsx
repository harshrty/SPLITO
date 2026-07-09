import { Routes, Route, Navigate, Link } from "react-router-dom";
import { useAuth } from "./store/auth";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Groups from "./pages/Groups";
import GroupDetail from "./pages/GroupDetail";
import ImportWizard from "./pages/ImportWizard";

function Private({ children }) {
  const token = useAuth((s) => s.token);
  return token ? children : <Navigate to="/login" replace />;
}

function Nav() {
  const { user, token, logout } = useAuth();
  if (!token) return null;
  return (
    <nav className="nav">
      <Link to="/app" className="brand">SPLITO</Link>
      <span className="spacer" />
      <span className="muted">{user?.display_name}</span>
      <button className="ghost" onClick={logout}>Logout</button>
    </nav>
  );
}

export default function App() {
  return (
    <>
      <Nav />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/signup" element={<Login initial="register" />} />
        <Route path="/login" element={<Login initial="login" />} />
        <Route path="/app" element={<Private><div className="container"><Groups /></div></Private>} />
        <Route path="/groups/:id" element={<Private><div className="container"><GroupDetail /></div></Private>} />
        <Route path="/groups/:id/import" element={<Private><div className="container"><ImportWizard /></div></Private>} />
      </Routes>
    </>
  );
}
