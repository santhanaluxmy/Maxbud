import "./LoginPage.css";

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import {
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
} from "lucide-react";

import logo from "../../assets/images/maxbud-logo.png";
import savingsHero from "../../assets/images/maxbud2.png";
import { authDestination, pendingInvitation } from "../../services/familyInvitation";

import {
  loginUser,
  googleLogin,
  saveAuthSession,
} from "../../services/authApi";

export default function LoginPage() {
  const navigate = useNavigate();

  const googleConfigured = Boolean(
    import.meta.env.VITE_GOOGLE_CLIENT_ID
  );

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);

  function handleAuthSuccess(result) {
    if (!result.access_token) {
      throw new Error("Authentication token not received.");
    }

    saveAuthSession(result, remember);

    navigate(authDestination(result), { replace: true });
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFeedback("");

    const cleanEmail = email.trim().toLowerCase();

    const errors = {};
    if (!cleanEmail) errors.email = "Please enter your email address.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) errors.email = "Please enter a valid email address.";
    if (!password) errors.password = "Please enter your password.";
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;

    setLoading(true);

    try {
      const result = await loginUser({
        email: cleanEmail,
        password,
      });

      handleAuthSuccess(result);
    } catch (error) {
      setFeedback(
        error.message || "Unable to sign in. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleSuccess(credentialResponse) {
    setFeedback("");

    if (!credentialResponse.credential) {
      setFeedback("Google did not return a valid credential.");
      return;
    }

    setLoading(true);

    try {
      const result = await googleLogin(
        credentialResponse.credential
      );

      handleAuthSuccess(result);
    } catch (error) {
      setFeedback(
        error.message ||
          "Google authentication could not be completed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-layout">

        {/* Left side illustration */}
        <div className="auth-visual">
          <Link to="/" className="auth-back">
            ← Back to Home
          </Link>

          <img
            src={savingsHero}
            alt="MaxBud savings illustration"
          />

          <h2>Welcome back to MaxBud!</h2>

          <p>
            Keep tracking your money and reaching your goals.
          </p>
        </div>

        {/* Right side login card */}
        <div className="auth-panel">
          <div className="auth-card">

            <Link to="/" className="auth-brand" aria-label="MaxBud home">
              <img
                src={logo}
                className="auth-logo"
                alt="MaxBud logo"
              />
            </Link>

            <h1>Welcome Back!</h1>

            <p>
              Sign in to continue managing your finances.
            </p>
            {pendingInvitation() && <p role="status">Your household invitation is saved. Sign in with the invited email to review and accept it.</p>}

            {/* Email and Password Form */}
            <form onSubmit={handleSubmit} noValidate>

              <label>
                Email Address

                <span className="auth-input">
                  <Mail size={18} />

                  <input
                    aria-label="Email Address"
                    aria-invalid={Boolean(fieldErrors.email)}
                    aria-describedby={fieldErrors.email ? "email-error" : undefined}
                    type="email"
                    placeholder="you@example.com"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      setFieldErrors(previous => ({ ...previous, email: "" }));
                      setFeedback("");
                    }}
                    autoComplete="email"
                    disabled={loading}
                  />
                </span>
                {fieldErrors.email && <span id="email-error" className="auth-field-error" role="alert">{fieldErrors.email}</span>}
              </label>

              <label>
                Password

                <span className="auth-input">
                  <LockKeyhole size={18} />

                  <input
                    aria-label="Password"
                    aria-invalid={Boolean(fieldErrors.password)}
                    aria-describedby={fieldErrors.password ? "password-error" : undefined}
                    type={showPassword ? "text" : "password"}
                    placeholder="Enter your password"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setFieldErrors(previous => ({ ...previous, password: "" }));
                      setFeedback("");
                    }}
                    autoComplete="current-password"
                    disabled={loading}
                  />

                  <button
                    type="button"
                    onClick={() =>
                      setShowPassword(!showPassword)
                    }
                    aria-label={
                      showPassword
                        ? "Hide password"
                        : "Show password"
                    }
                    disabled={loading}
                  >
                    {showPassword ? (
                      <EyeOff size={18} />
                    ) : (
                      <Eye size={18} />
                    )}
                  </button>
                </span>
                {fieldErrors.password && <span id="password-error" className="auth-field-error" role="alert">{fieldErrors.password}</span>}
              </label>

              <div className="auth-options">
                <label className="auth-check">
                  <input
                    type="checkbox"
                    checked={remember}
                    onChange={(e) =>
                      setRemember(e.target.checked)
                    }
                    disabled={loading}
                  />

                  Remember me
                </label>

                <Link to="/forgot-password" className="auth-recovery-link">Forgot password?</Link>
              </div>

              {feedback && <div className="auth-feedback" role="alert">{feedback}</div>}

              <button
                type="submit"
                className="max-btn aqua auth-submit"
                disabled={loading}
              >
                {loading ? "Signing In..." : "Sign In"}
                {!loading && <span>→</span>}
              </button>
            </form>

            {/* OR Divider */}
            <div className="google-divider">
              <span>or continue with</span>
            </div>

            {/* Google Sign In */}
            <div className="google-login-area">
              {googleConfigured ? (
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() =>
                    setFeedback(
                      "Google sign-in was cancelled or failed."
                    )
                  }
                  text="continue_with"
                  theme="outline"
                  size="large"
                  shape="rectangular"
                  width="320"
                  useOneTap={false}
                />
              ) : (
                <div className="google-setup-notice">
                  Continue with Google
                  <small>
                    Google Client ID setup required
                  </small>
                </div>
              )}
            </div>

            <p className="auth-switch">
              New to MaxBud?{" "}
              <Link to="/register">
                Create an account
              </Link>
            </p>

          </div>
        </div>
      </div>
    </div>
  );
}
