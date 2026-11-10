import { Routes, Route, Navigate } from "react-router-dom";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import OnboardingPage from "./pages/OnboardingPage";
import UserDashboard from "./pages/UserDashboard";
import { getAuthSession } from "./services/authApi";

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
    <Route path="/dashboard" element={<ProtectedRoute needsOnboarding><UserDashboard/></ProtectedRoute>}/>
    <Route path="*" element={<Navigate to="/" replace/>}/>
  </Routes>;
}