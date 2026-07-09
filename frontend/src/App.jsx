import { Routes, Route, Navigate, Link } from "react-router-dom";
import { useAuth } from "./store/auth";
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
      <Link to="/" className="brand">SPLITO</Link>
      <span className="spacer" />
      <span className="muted">{user?.display_name}</span>
      <button onClick={logout}>Logout</button>
    </nav>
  );
}

export default function App() {
  return (
    <>
      <Nav />
      <main className="container">
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Private><Groups /></Private>} />
          <Route path="/groups/:id" element={<Private><GroupDetail /></Private>} />
          <Route path="/groups/:id/import" element={<Private><ImportWizard /></Private>} />
        </Routes>
      </main>
    </>
  );
}
