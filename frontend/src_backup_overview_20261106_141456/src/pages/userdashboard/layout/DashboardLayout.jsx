import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Sparkles, ArrowRight, LockKeyhole, LogOut, Menu, Bell } from "lucide-react";
import { logout } from "../../../api/client";
import { getAuthSession } from "../../../services/authApi";
import logo from "../../../assets/images/maxbud-logo.png";
import { navigation, dashboardPath } from "./navigation";
import "./DashboardLayout.css";
import "./DashboardPremium.css";

export default function DashboardLayout() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const person = getAuthSession()?.user || {};
  const firstName = person.full_name?.trim().split(" ")[0] || "there";
  const title = navigation.find((item) => dashboardPath(item.id) === pathname.replace(/\/$/, ""))?.label || "Overview";
  function goTab(id) { navigate(dashboardPath(id)); setMenuOpen(false); }
  function signOut() { logout(); navigate("/login", { replace: true }); }
  return <div className={`db-app ${collapsed ? "db-collapsed" : ""}`}>
    {menuOpen && <button type="button" aria-label="Close navigation" className="db-backdrop" onClick={() => setMenuOpen(false)}/>}
    <aside className={`db-sidebar glass-card ${menuOpen ? "open" : ""}`}>
      <Link to="/" className="db-brand" title="MaxBud home"><img src={logo} alt="MaxBud"/></Link>
      <div className="db-sidebar-group-title">YOUR WORKSPACE</div>
      <nav className="db-nav">{navigation.map(({ id, label, icon: Icon, planned, premium }) => <NavLink aria-label={label} title={label} key={id} to={dashboardPath(id)} end className={({ isActive }) => `db-nav-item ${isActive ? "selected" : ""}`} onClick={() => setMenuOpen(false)}><Icon size={19}/><span>{label}</span>{planned && <span className="db-nav-dot" title="Coming soon"/>}{premium && <LockKeyhole size={13}/>}</NavLink>)}</nav>
      <div className="db-sidebar-footer"><div className="db-plan-glass"><div className="db-plan-icon"><Sparkles size={19}/></div><strong>Your Free plan</strong><p>Core budgeting is yours. Premium AI and family features are coming soon.</p><button onClick={() => goTab("family")}>Explore Premium <ArrowRight size={15}/></button></div><button className="db-signout" onClick={signOut}><LogOut size={18}/> Sign out</button></div>
    </aside>

    <div className="db-workspace">
      <header className="db-topbar glass-card"><div className="db-topbar-left"><button type="button" aria-label="Toggle navigation" aria-expanded={menuOpen || !collapsed} className="db-hamburger" onClick={() => { if (window.matchMedia("(max-width: 990px)").matches) setMenuOpen((open) => !open); else setCollapsed((value) => !value); }}><Menu size={21}/></button><span className="db-breadcrumb">My workspace <span>/</span> <strong>{title}</strong></span></div><div className="db-topbar-right"><span className="db-date">{new Date().toLocaleDateString("en-LK", { day: "numeric", month: "short", year: "numeric" })}</span><button className="db-bell" aria-label="Reminders" title="Reminders" onClick={() => goTab("reminders")}><Bell size={19}/></button><span className="db-avatar">{firstName[0].toUpperCase()}</span><span className="db-user-name">{person.full_name || "MaxBud User"}</span></div></header>
      <Outlet/>
    </div>
  </div>;
}
