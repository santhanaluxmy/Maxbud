import { Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/landingpage/LandingPage";
import LoginPage from "./pages/login/LoginPage";
import RegisterPage from "./pages/register/RegisterPage";
import OnboardingPage from "./pages/onboarding/Onboarding";
import Dashboard from "./pages/userdashboard/dashboard/Dashboard";
import DashboardLayout from "./pages/userdashboard/layout/DashboardLayout";
import { getAuthSession } from "./services/authApi";
import Transaction from "./pages/userdashboard/transaction/Transaction";

function ProtectedRoute({ children, needsOnboarding = false }) {
  const session = getAuthSession();
  if (!session?.token) return <Navigate to="/login" replace />;
  if (needsOnboarding && !session.onboarding_completed) return <Navigate to="/onboarding" replace />;
  return children;
}

export default function App() {
  return <Routes>
    <Route path="/" element={<LandingPage/>}/>
    <Route path="/login" element={<LoginPage/>}/>
    <Route path="/register" element={<RegisterPage/>}/>
    <Route path="/onboarding" element={<ProtectedRoute><OnboardingPage/></ProtectedRoute>}/>
    <Route path="/dashboard" element={<ProtectedRoute needsOnboarding><DashboardLayout/></ProtectedRoute>}>
      <Route index element={<Dashboard/>}/>
      {["accounts", "transactions", "budgets", "goals", "reminders", "reports", "ai-scan", "ai-advisor", "family", "settings"].map((path) => <Route key={path} path={path} element={<Dashboard/>}/>)}
    </Route>
    <Route path="*" element={<Navigate to="/" replace/>}/>
    <Route path="transactions" element={<Transaction />} />
  </Routes>;
}