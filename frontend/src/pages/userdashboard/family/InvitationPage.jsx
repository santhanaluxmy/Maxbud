import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CheckCircle2, Users } from "lucide-react";
import { api, logout } from "../../../api/client";
import { publicPost } from "../../../api/public";
import { getAuthSession } from "../../../services/authApi";
import { clearInvitation, invitationDate, pendingInvitation } from "../../../services/familyInvitation";
import "./FamilyPage.css";

const unavailable = {
  expired: "This invitation has expired. Ask the household owner for a new link.",
  revoked: "The owner has revoked this invitation. Ask them for a new link if you still want to join.",
  rejected: "This invitation was declined. Ask the owner for a new invitation to join.",
};

export default function InvitationPage() {
  const navigate = useNavigate();
  const token = pendingInvitation();
  const session = getAuthSession();
  const [invitation, setInvitation] = useState(null);
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    publicPost("/family/invitations/preview", { token }, { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) { setInvitation(data); setError(""); } })
      .catch(error => { if (!controller.signal.aborted) setError(error.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [token, attempt]);

  async function respond(accept) {
    if (saving) return;
    setSaving(true); setError("");
    try {
      await api("/family/invitations/respond", { method: "POST", data: { token, accept } });
      clearInvitation();
      navigate(accept ? "/dashboard/family" : session.onboarding_completed ? "/dashboard" : "/onboarding", { replace: true });
    } catch (error) { setError(error.message); }
    finally { setSaving(false); }
  }

  const available = invitation && ["pending", "accepted"].includes(invitation.status);
  const matches = session?.user?.email?.toLowerCase() === invitation?.invited_email?.toLowerCase();
  return <main className="family-invitation-page"><section className="family-invitation-card">
    <Link to="/" className="family-invite-brand">MaxBud</Link>
    <div className="family-invite-symbol"><Users size={28}/></div>
    <h1>Join your household</h1>
    <p>Your own account. A shared space for household finances.</p>
    {loading ? <p role="status">Checking your invitation…</p> : !token ? <p role="alert">This invitation link is incomplete. Open the full link shared by the household owner.</p> : <>
      {invitation && <>
        <div className="family-invite-summary"><h2>{invitation.household_name}</h2><p>Invited by {invitation.inviter_name}</p><p>For <strong>{invitation.invited_email}</strong></p><small>Expires {invitationDate(invitation.expires_at)}</small></div>
        {unavailable[invitation.status] && <p className="family-invite-warning" role="status">{unavailable[invitation.status]}</p>}
        {available && <>
          <ol className="family-invite-steps"><li>Sign in or create your own account with the invited email.</li><li>Review and accept this invitation.</li><li>Open your shared household dashboard.</li></ol>
          <p className="family-invite-privacy"><CheckCircle2 size={18}/>Your personal accounts, salary and transactions stay private. Only authorized household records are shared.</p>
          {!session?.token ? <div className="family-invite-buttons"><Link className="db-primary-btn" to="/login">Sign in to accept</Link><Link className="db-outline-btn" to="/register">Create an account</Link></div> : !matches ? <div className="family-invite-warning"><p>You are signed in as {session.user.email}. This invitation is for {invitation.invited_email}.</p><button className="db-outline-btn" onClick={() => { logout(); navigate("/login"); }}>Switch account</button></div> : <div className="family-invite-buttons"><button className="db-primary-btn" disabled={saving} onClick={() => respond(true)}>{saving ? "Saving membership…" : invitation.status === "accepted" ? "Continue to household" : "Accept Invitation"}</button>{invitation.status === "pending" && <button className="db-outline-btn" disabled={saving} onClick={() => respond(false)}>Decline invitation</button>}</div>}
        </>}
      </>}
      {error && <div className="family-invite-warning" role="alert"><p>{error}</p><button className="db-outline-btn" disabled={saving} onClick={() => { setLoading(true); setAttempt(value => value + 1); }}>Check invitation again</button></div>}
    </>}
    <Link className="family-invite-dismiss" to={session?.token ? session.onboarding_completed ? "/dashboard" : "/onboarding" : "/"} onClick={clearInvitation}>Leave invitation</Link>
  </section></main>;
}
