import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ChevronDown, LogOut, Menu, Bell, Search, X } from "lucide-react";
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
  const [search, setSearch] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const person = getAuthSession()?.user || {};
  const firstName = person.full_name?.trim().split(" ")[0] || "there";
  const pageTitle = navigation.find((item) => dashboardPath(item.id) === pathname.replace(/\/$/, ""))?.label || "Overview";
  const results = navigation.filter((item) => `${item.label} ${item.id}`.toLowerCase().includes(search.trim().toLowerCase()));

  function goTo(path) {
    navigate(path);
    setMenuOpen(false);
    setSearchOpen(false);
    setSearch("");
  }
  function signOut() { logout(); navigate("/login", { replace: true }); }
  function toggleNavigation() {
    if (window.matchMedia("(max-width: 990px)").matches) setMenuOpen((open) => !open);
    else setCollapsed((value) => !value);
  }

  return <div className={`db-app ${collapsed ? "db-collapsed" : ""}`}>
    <a className="db-skip-link" href="#dashboard-content">Skip to content</a>
    {menuOpen && <button type="button" aria-label="Close navigation" className="db-backdrop" onClick={() => setMenuOpen(false)}/>}
    <aside id="dashboard-navigation" className={`db-sidebar ${menuOpen ? "open" : ""}`} onKeyDown={(event) => { if (event.key === "Escape") setMenuOpen(false); }}>
      <div className="db-brand-block">
        <Link to="/" className="db-brand" title="MaxBud home"><img src={logo} alt="MaxBud"/></Link>
        <p>Your Money, Your Goals</p>
        <button type="button" className="db-drawer-close" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><X size={20}/></button>
      </div>
      <nav className="db-nav" aria-label="Dashboard pages">
        {navigation.map(({ id, label, icon: Icon }) => <NavLink aria-label={label} title={label} key={id} to={dashboardPath(id)} end className={({ isActive }) => `db-nav-item ${isActive ? "selected" : ""} ${id === "settings" ? "db-nav-settings" : ""}`} onClick={() => setMenuOpen(false)}><Icon size={22} strokeWidth={1.7}/><span>{id === "accounts" ? "Accounts" : id === "scan" ? "AI Receipt Scan" : label}</span></NavLink>)}
      </nav>
      <div className="db-sidebar-footer"><button className="db-signout" aria-label="Sign out" onClick={signOut}><LogOut size={18}/><span>Sign out</span></button></div>
      <svg className="db-sidebar-art" viewBox="0 0 240 145" fill="none" aria-hidden="true"><path d="M0 60C50 95 42 133 98 109C157 73 180 93 240 125V145H0Z" fill="currentColor" opacity=".5"/><path d="M35 129C37 94 63 58 102 28" stroke="currentColor" strokeWidth="2"/><path d="M48 91C20 73 30 47 51 31C50 57 57 63 48 91ZM64 68C72 37 94 40 109 38C98 57 87 65 64 68ZM80 51C85 17 105 18 126 19C111 37 101 48 80 51ZM43 108C56 86 73 91 84 86C77 107 61 113 43 108Z" fill="currentColor"/></svg>
    </aside>
    <div className="db-workspace">
      <header className="db-topbar" aria-label={`${pageTitle} navigation`}>
        <button type="button" aria-label="Toggle navigation" aria-controls="dashboard-navigation" className="db-hamburger" onClick={toggleNavigation}><Menu size={23}/></button>
        <form className="db-search" role="search" onSubmit={(event) => { event.preventDefault(); if (results[0]) goTo(dashboardPath(results[0].id)); }} onBlur={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setSearchOpen(false); }}>
          <Search size={20} aria-hidden="true"/>
          <input type="search" aria-label="Search dashboard pages" placeholder="Search transactions, accounts, budgets…" value={search} onChange={(event) => { setSearch(event.target.value); setSearchOpen(true); }} onFocus={() => setSearchOpen(true)} onKeyDown={(event) => { if (event.key === "Escape") setSearchOpen(false); }} aria-expanded={searchOpen} aria-controls="dashboard-search-results"/>
          {searchOpen && <nav id="dashboard-search-results" className="db-search-results" aria-label="Matching dashboard pages"><small>GO TO A PAGE</small>{results.length ? results.map((item) => <Link key={item.id} to={dashboardPath(item.id)} onClick={() => { setSearchOpen(false); setSearch(""); setMenuOpen(false); }}>{item.label}</Link>) : <p>No matching pages found.</p>}</nav>}
        </form>
        <div className="db-topbar-right">
          <button type="button" className="db-bell" aria-label="Open reminders" title="Reminders" onClick={() => goTo(dashboardPath("reminders"))}><Bell size={22}/></button>
          <details className="db-profile">
            <summary aria-label={`Profile for ${person.full_name || "MaxBud User"}`}><span className="db-avatar">{firstName[0].toUpperCase()}</span><span className="db-user-name">{person.full_name || "MaxBud User"}</span><ChevronDown size={16}/></summary>
            <div className="db-profile-menu"><span>{person.email || person.full_name || "Your account"}</span><Link to={dashboardPath("settings")} onClick={(event) => event.currentTarget.closest("details").removeAttribute("open")}>Account settings</Link><button type="button" onClick={signOut}><LogOut size={16}/>Sign out</button></div>
          </details>
        </div>
      </header>
      <div id="dashboard-content" tabIndex={-1}><Outlet/></div>
    </div>
  </div>;
}
