import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import logo from "../../assets/images/maxbud-logo.png";
import "./LoginPage.css";

export default function PasswordRecovery() {
  const [step, setStep] = useState(0), [busy, setBusy] = useState(false);
  const [email, setEmail] = useState(""), [code, setCode] = useState("");
  const [challenge, setChallenge] = useState(""), [proof, setProof] = useState("");
  const [password, setPassword] = useState(""), [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState(""), [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError("");
    try {
      if (step === 0) {
        const result = await api("/auth/recovery/request", { method: "POST", data: { email } });
        setChallenge(result.challenge_id); setMessage(result.message); setStep(1);
      } else if (step === 1) {
        const result = await api("/auth/recovery/verify", { method: "POST", data: { challenge_id: challenge, code } });
        setProof(result.reset_token); setMessage(""); setStep(2);
      } else {
        if (password !== confirmation) throw new Error("Passwords do not match.");
        await api("/auth/recovery/reset", { method: "POST", data: { challenge_id: challenge, reset_token: proof, password, confirm_password: confirmation } });
        setPassword(""); setConfirmation(""); setProof(""); setCode(""); setMessage("Password updated. Sign in with your new password."); setStep(3);
      }
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  }
  return <main className="auth-page recovery-page"><section className="auth-card">
    <Link to="/" className="auth-brand" aria-label="MaxBud home"><img className="auth-logo" src={logo} alt="MaxBud logo"/></Link>
    <h1>{["Forgot password?", "Check your email", "Create a new password", "You’re ready to sign in"][step]}</h1>
    <p>{["We’ll send a short-lived recovery code to your registered email.", "Enter the six-digit code. It expires in 10 minutes.", "Use 8–128 characters with uppercase, lowercase, a number and a symbol.", "All previous sessions have ended for your security."][step]}</p>
    {message && <p role="status">{message}</p>}{error && <p role="alert" className="auth-feedback">{error}</p>}
    {step < 3 && <form onSubmit={submit}>
      {step === 0 && <label>Email address<span className="auth-input"><input required type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} disabled={busy}/></span></label>}
      {step === 1 && <label>Recovery code<span className="auth-input"><input required inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" value={code} onChange={e => setCode(e.target.value)} disabled={busy}/></span></label>}
      {step === 2 && <>{[["New password", password, setPassword], ["Confirm password", confirmation, setConfirmation]].map(([label, value, change]) => <label key={label}>{label}<span className="auth-input"><input required type="password" minLength={8} maxLength={128} autoComplete="new-password" value={value} onChange={e => change(e.target.value)} disabled={busy}/></span></label>)}</>}
      <button className="max-btn aqua auth-submit" disabled={busy}>{busy ? "Please wait…" : ["Send recovery code", "Verify code", "Save new password"][step]}</button>
    </form>}
    {step === 1 && <button className="auth-recovery-link" disabled={busy} onClick={() => { setStep(0); setCode(""); setMessage(""); setError(""); }}>Request a new code</button>}
    <p className="auth-switch"><Link to="/login">Back to sign in</Link></p>
  </section></main>;
}
