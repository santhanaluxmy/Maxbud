import "./RegisterPage.css";

import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import {
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
  UserRound,
} from "lucide-react";

import logo from "../../assets/images/maxbud-logo.png";
import financeHero from "../../assets/images/maxbud2.png";
import { authDestination, pendingInvitation } from "../../services/familyInvitation";

import {
  registerUser,
  googleLogin,
  saveAuthSession,
} from "../../services/authApi";

export default function RegisterPage() {
  const navigate = useNavigate();

  const googleConfigured = Boolean(
    import.meta.env.VITE_GOOGLE_CLIENT_ID
  );

  const [values, setValues] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
  });

  const [showPassword, setShowPassword] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [fieldErrors, setFieldErrors] = useState({});
  const [loading, setLoading] = useState(false);

  function change(e) {
    const { name, value } = e.target;

    setValues((previous) => ({
      ...previous,
      [name]: value,
    }));

    setFeedback("");
    setFieldErrors(previous => ({ ...previous, [name]: "" }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFeedback("");

    const fullName = values.name.trim();
    const cleanEmail = values.email.trim().toLowerCase();
    const password = values.password;

    const errors = {};
    if (!cleanEmail) errors.email = "Please enter your email address.";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(cleanEmail)) errors.email = "Please enter a valid email address.";
    if (fullName.length < 2 || fullName.length > 100) errors.name = "Full name must contain 2–100 characters.";
    if (!(password.length >= 8 && password.length <= 128 && /[A-Z]/.test(password) && /[a-z]/.test(password) && /[0-9]/.test(password) && /[^A-Za-z0-9]/.test(password))) errors.password = "Use 8–128 characters with uppercase, lowercase, a number and a symbol.";
    if (password !== values.confirmPassword) errors.confirmPassword = "Passwords do not match.";
    setFieldErrors(errors);
    if (Object.keys(errors).length) return;

    setLoading(true);

    try {
      const result = await registerUser({
        full_name: fullName,
        email: cleanEmail,
        password,
        confirm_password: values.confirmPassword,
      });

      if (!result.access_token) {
        throw new Error(
          "Registration succeeded, but no authentication token was received."
        );
      }

      saveAuthSession(result, false);

      navigate(authDestination(result), {
        replace: true,
      });
    } catch (error) {
      if (error.message === "Email already registered") setFieldErrors({ email: error.message });
      else setFeedback(error.message || "Unable to create account. Please try again.");
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
      // Backend will create or find the Google user.
      const result = await googleLogin(
        credentialResponse.credential
      );

      if (!result.access_token) {
        throw new Error(
          "Authentication token not received."
        );
      }

      saveAuthSession(result, false);

      navigate(
        authDestination(result),
        { replace: true }
      );
    } catch (error) {
      setFeedback(
        error.message ||
          "Google registration could not be completed."
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
            src={financeHero}
            alt="MaxBud savings illustration"
          />

          <h2>Start your financial journey.</h2>

          <p>
            Build better habits and take control of your money.
          </p>
        </div>

        {/* Right side register card */}
        <div className="auth-panel">
          <div className="auth-card">

            <Link to="/" className="auth-brand" aria-label="MaxBud home">
              <img
                src={logo}
                className="auth-logo"
                alt="MaxBud logo"
              />
            </Link>

            <h1>Create your account</h1>

            <p>
              Let's start your journey with MaxBud.
            </p>
            {pendingInvitation() && <p role="status">Create your own account using the invited email. Your household invitation will be waiting after registration.</p>}

            <form onSubmit={handleSubmit} noValidate>

              {/* Full Name */}
              <label>
                Full Name

                <span className="auth-input">
                  <UserRound size={18} />

                  <input
                    type="text"
                    aria-label="Full Name"
                    aria-invalid={Boolean(fieldErrors.name)}
                    aria-describedby={fieldErrors.name ? "name-error" : undefined}
                    name="name"
                    placeholder="Enter your full name"
                    autoComplete="name"
                    value={values.name}
                    onChange={change}
                    maxLength={100}
                    disabled={loading}
                  />
                </span>
                {fieldErrors.name && <span id="name-error" className="auth-field-error" role="alert">{fieldErrors.name}</span>}
              </label>

              {/* Email */}
              <label>
                Email Address

                <span className="auth-input">
                  <Mail size={18} />

                  <input
                    type="email"
                    aria-label="Email Address"
                    aria-invalid={Boolean(fieldErrors.email)}
                    aria-describedby={fieldErrors.email ? "email-error" : undefined}
                    name="email"
                    placeholder="you@example.com"
                    autoComplete="email"
                    value={values.email}
                    onChange={change}
                    disabled={loading}
                  />
                </span>
                {fieldErrors.email && <span id="email-error" className="auth-field-error" role="alert">{fieldErrors.email}</span>}
              </label>

              {/* Password */}
              <label>
                Password

                <span className="auth-input">
                  <LockKeyhole size={18} />

                  <input
                    type={showPassword ? "text" : "password"}
                    aria-label="Password"
                    aria-invalid={Boolean(fieldErrors.password)}
                    aria-describedby={fieldErrors.password ? "password-error" : undefined}
                    name="password"
                    placeholder="Create a strong password"
                    autoComplete="new-password"
                    value={values.password}
                    onChange={change}
                    maxLength={128}
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

              {/* Confirm Password */}
              <label>
                Confirm Password

                <span className="auth-input">
                  <LockKeyhole size={18} />

                  <input
                    type={showPassword ? "text" : "password"}
                    aria-label="Confirm Password"
                    aria-invalid={Boolean(fieldErrors.confirmPassword)}
                    aria-describedby={fieldErrors.confirmPassword ? "confirmPassword-error" : undefined}
                    name="confirmPassword"
                    placeholder="Confirm password"
                    autoComplete="new-password"
                    value={values.confirmPassword}
                    onChange={change}
                    maxLength={128}
                    disabled={loading}
                  />
                </span>
                {fieldErrors.confirmPassword && <span id="confirmPassword-error" className="auth-field-error" role="alert">{fieldErrors.confirmPassword}</span>}
              </label>

              {feedback && <div className="auth-feedback" role="alert">{feedback}</div>}

              <button
                type="submit"
                className="max-btn aqua auth-submit"
                disabled={loading}
              >
                {loading
                  ? "Creating Account..."
                  : "Create Account"}

                {!loading && <span>→</span>}
              </button>
            </form>

            {/* OR Divider */}
            <div className="google-divider">
              <span>or continue with</span>
            </div>

            {/* Google Register */}
            <div className="google-login-area">
              {googleConfigured ? (
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() =>
                    setFeedback(
                      "Google sign-up was cancelled or failed."
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
              Already have an account?{" "}
              <Link to="/login">
                Sign In
              </Link>
            </p>

          </div>
        </div>
      </div>
    </div>
  );
}
