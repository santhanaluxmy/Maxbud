import { useState } from "react";
import { api } from "../../../api/client";
import { getAuthSession } from "../../../services/authApi";
import { Link } from "react-router-dom";
import GlassCard from "../../../components/common/GlassCard";
export default function Settings() {
  const [name, setName] = useState(getAuthSession()?.user?.full_name || "");
  const [passwords, setPasswords] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function save(e, path, data) {
    e.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const result = await api(path, { method: "PUT", data });
      if (path.endsWith("profile")) {
        for (const storage of [localStorage, sessionStorage]) {
          const raw = storage.getItem("maxbud_auth");
          if (raw) { const session = JSON.parse(raw); session.user = result; storage.setItem("maxbud_auth", JSON.stringify(session)); }
        }
      } else setPasswords({ current_password: "", new_password: "", confirm_password: "" });
      setMessage("Changes saved.");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <>
    <div className="db-page-intro"><div><span className="db-page-subtitle">YOUR ACCOUNT</span><h1>Account settings</h1><p>Keep your profile and sign-in details up to date.</p></div></div><p><Link to="/dashboard/upgrade">View subscription and plan limits</Link></p>
    <button className="db-outline-btn" disabled={busy} onClick={async () => {
      setBusy(true); setError("");
      try { const data = await api("/settings/export"); const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })); const link = document.createElement("a"); link.href = url; link.download = `maxbud-export-${new Date().toLocaleDateString("en-CA")}.json`; link.click(); URL.revokeObjectURL(url); setMessage("Your export was downloaded."); } catch (error) { setError(error.message); } finally { setBusy(false); }
    }}>Export my records</button>
    {message && <p role="status">{message}</p>}{error && <p className="db-error" role="alert">{error}</p>}
    <div className="db-settings-grid"><GlassCard><form className="db-modal-form" onSubmit={e => save(e, "/settings/profile", { full_name: name })}>
      <label>Full name<input required minLength={2} maxLength={100} value={name} onChange={e => setName(e.target.value)}/></label>
      <p>{getAuthSession()?.user?.email}</p><button disabled={busy} className="db-primary-btn">Save profile</button>
    </form></GlassCard>
    <GlassCard><form className="db-modal-form" onSubmit={e => save(e, "/settings/password", passwords)}>
      <h3>Change password</h3>{Object.keys(passwords).map(key => <label key={key}>{key.replaceAll("_", " ")}<input required type="password" autoComplete={key === "current_password" ? "current-password" : "new-password"} minLength={key === "current_password" ? 1 : 8} maxLength={128} value={passwords[key]} onChange={e => setPasswords({ ...passwords, [key]: e.target.value })}/></label>)}
      <button disabled={busy} className="db-primary-btn">Update password</button>
    </form></GlassCard></div>
  </>;
}
