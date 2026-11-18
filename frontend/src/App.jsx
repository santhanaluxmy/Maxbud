import { useEffect, useState } from "react";
import { api } from "./api/client";
import { Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/landingpage/LandingPage";
import PasswordRecovery from "./pages/login/PasswordRecovery";
import LoginPage from "./pages/login/LoginPage";
import RegisterPage from "./pages/register/RegisterPage";
import OnboardingPage from "./pages/onboarding/Onboarding";
import Dashboard from "./pages/userdashboard/dashboard/Dashboard";
import DashboardLayout from "./pages/userdashboard/layout/DashboardLayout";
import { getAuthSession } from "./services/authApi";
import FamilyPage from "./pages/userdashboard/family/FamilyPage";
import Notifications from "./pages/userdashboard/dashboard/Notifications";
import Upgrade from "./pages/userdashboard/dashboard/Upgrade";
import PaymentSuccess from "./pages/userdashboard/dashboard/PaymentSuccess";
import SubscriptionProvider from "./subscriptions/SubscriptionProvider";
import Admin from "./pages/userdashboard/dashboard/Admin";
import AI from "./pages/userdashboard/dashboard/AI";
import Settings from "./pages/userdashboard/dashboard/Settings";
import Reminders from "./pages/userdashboard/dashboard/Reminders";
import "./pages/userdashboard/dashboard/Dashboard.css";

// Invitation tokens use a URL fragment so they are not sent in server access logs.
if (window.location.hash.startsWith("#invite=")) {
  sessionStorage.setItem("maxbud_invitation", decodeURIComponent(window.location.hash.slice(8)));
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}

function AdminRoute() {
  const [state, setState] = useState("loading");
  useEffect(() => { let active = true; api("/auth/me").then(user => { if (active) setState(user.role === "admin" ? "allowed" : "denied"); }).catch(() => { if (active) setState("denied"); }); const expiry = window.setInterval(() => { if (!getAuthSession()?.token) window.location.assign("/login"); }, 1000); return () => { active = false; window.clearInterval(expiry); }; }, []);
  if (state === "loading") return <p role="status">Checking platform permission…</p>;
  return state === "allowed" ? <Admin/> : <p role="alert">Platform administrator access is required.</p>;
}

function ProtectedRoute({ children, needsOnboarding = false }) {
  const session = getAuthSession();
  if (!session?.token) return <Navigate to="/login" replace />;
  if (needsOnboarding && !session.onboarding_completed && session.user?.role !== "admin") return <Navigate to="/onboarding" replace />;
  return children;
}

export default function App() {
  return <Routes>
    <Route path="/" element={<LandingPage/>}/>
    <Route path="/login" element={<LoginPage/>}/>
    <Route path="/forgot-password" element={<PasswordRecovery/>}/>
    <Route path="/register" element={<RegisterPage/>}/>
    <Route path="/onboarding" element={<ProtectedRoute><OnboardingPage/></ProtectedRoute>}/>
    <Route path="/dashboard" element={<ProtectedRoute needsOnboarding><SubscriptionProvider><DashboardLayout/></SubscriptionProvider></ProtectedRoute>}>
      <Route index element={<Dashboard/>}/>
      <Route path="admin" element={<main className="db-main"><AdminRoute/></main>}/>
      <Route path="notifications" element={<main className="db-main"><Notifications/></main>}/>
      <Route path="upgrade" element={<main className="db-main"><Upgrade/></main>}/>
      <Route path="payment-success" element={<main className="db-main"><PaymentSuccess/></main>}/>
      <Route path="ai-scan" element={<main className="db-main"><AI mode="scan"/></main>}/>
      <Route path="ai-advisor" element={<main className="db-main"><AI mode="advisor"/></main>}/>
      <Route path="settings" element={<main className="db-main"><Settings/></main>}/>
      <Route path="reminders" element={<main className="db-main"><Reminders/></main>}/>
      <Route path="family" element={<FamilyPage/>}/>
      <Route path="family/:section" element={<FamilyPage/>}/>
      {["accounts", "transactions", "budgets", "goals", "reports"].map((path) => <Route key={path} path={path} element={<Dashboard/>}/>)}
    </Route>
    <Route path="*" element={<Navigate to="/" replace/>}/>
    <Route path="transactions" element={<Navigate to="/dashboard/transactions" replace/>} />
  </Routes>;
}
