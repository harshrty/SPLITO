import { Routes, Route, Navigate, Link } from "react-router-dom";
import { useAuth } from "./store/auth";
import { Brand, Avatar, Icon } from "./components/ui";
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
      <Link to="/app"><Brand /></Link>
      <span className="spacer" />
      <span className="user-pill">
        <Avatar name={user?.display_name || "?"} size={26} />
        <span className="hide-sm" style={{ fontWeight: 600, fontSize: 14 }}>{user?.display_name}</span>
      </span>
      <button className="ghost sm" onClick={logout}>
        <Icon name="logout" size={15} /><span className="hide-sm">Logout</span>
      </button>
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
