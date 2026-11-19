import { useCallback, useEffect, useRef, useState } from "react";
import { Mail, Send } from "lucide-react";
import { api } from "../../../api/client";
import { invitationDate } from "../../../services/familyInvitation";
import GlassCard from "../../../components/common/GlassCard";
import FamilyConfirmDialog from "./FamilyConfirmDialog";

const deliveryLabels = { submitted: "Submitted to mail server", not_configured: "Email not sent", failed: "Email not sent", unconfirmed: "Submission not confirmed", unknown: "Not recorded" };
const statusLabels = { pending: "Pending acceptance", accepted: "Accepted", revoked: "Revoked", expired: "Expired", rejected: "Declined" };

export default function FamilyInvitations({ family, onChanged }) {
  const [email, setEmail] = useState("");
  const [rows, setRows] = useState([]);
  const [created, setCreated] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [revoke, setRevoke] = useState(null);
  const busy = useRef(false);
  const generation = useRef(0);
  const load = useCallback(signal => {
    const request = ++generation.current;
    return api("/family/invitations", { signal }).then(result => {
      if (!signal?.aborted && request === generation.current) { setRows(result); setLoadError(""); }
    }).catch(error => { if (!signal?.aborted && request === generation.current) setLoadError(error.message); })
      .finally(() => { if (!signal?.aborted && request === generation.current) setLoading(false); });
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    const refresh = () => { if (document.visibilityState === "visible" && !busy.current) load(controller.signal); };
    const interval = window.setInterval(refresh, 5000);
    window.addEventListener("focus", refresh);
    return () => { controller.abort(); window.clearInterval(interval); window.removeEventListener("focus", refresh); };
  }, [load]);
  async function create(event) {
    event.preventDefault();
    if (busy.current) return;
    busy.current = true; setSaving(true); setError(""); setCreated(null);
    try {
      const result = await api("/family/invitations", { method: "POST", data: { email: email.trim().toLowerCase(), can_view_shared: true, can_add_shared: true } });
      if (result.delivery_status !== "submitted") throw new Error(result.delivery || "Email submission was not confirmed. Please check the pending invitation before retrying.");
      setCreated({ ...result, email: email.trim().toLowerCase() }); setEmail("");
      await load(); onChanged();
    } catch (error) { setError(error.message); await load(); onChanged(); }
    finally { busy.current = false; setSaving(false); }
  }
  async function resend(row) {
    if (busy.current) return;
    busy.current = true; setSaving(true); setError(""); setCreated(null);
    try {
      const result = await api(`/family/invitations/${row.id}/resend`, { method: "POST" });
      if (result.delivery_status !== "submitted") throw new Error("Email submission was not confirmed. Please check with the recipient before retrying.");
      setCreated({ ...result, email: row.email });
      await load(); onChanged();
    } catch (error) { setError(error.message); await load(); onChanged(); }
    finally { busy.current = false; setSaving(false); }
  }
  const pending = rows.filter(row => row.status === "pending");
  const history = rows.filter(row => row.status !== "pending");
  return <div className="family-invitations">
    <GlassCard title="Invite someone to your household" subtitle={`1 owner + ${Math.max(0, family.max_members - 1)} members (${family.max_members} people total). Everyone uses their own MaxBud account.`}>
      <form className="family-form family-invite-form" onSubmit={create}>
        <label htmlFor="family-invite-email">Invited email<input id="family-invite-email" required type="email" maxLength={254} autoComplete="email" placeholder="name@example.com" disabled={saving} value={email} onChange={event => setEmail(event.target.value)}/></label>
        <button className="db-primary-btn" disabled={saving || !family.can_edit_shared || family.available_slots === 0}><Send size={18}/>{saving ? "Sending…" : "Send Invitation"}</button>
      </form>
      <p className="family-invite-help">The invitee can view shared reports and add shared records. You can change these permissions after they join. Invitations expire after seven days.</p>
      {family.available_slots === 0 && <p role="status" className="family-invite-warning">All household spaces are filled or reserved by pending invitations. Revoke an unused invitation to free a space.</p>}
      {(error || loadError) && <p role="alert" className="family-invite-warning">{error || loadError}</p>}
      {created && <p className="family-invite-delivery submitted" role="status"><Mail size={18}/><span>Invitation email sent to <strong>{created.email}</strong>. They can open the email, sign in or register, and accept your invitation.</span></p>}
    </GlassCard>
    <GlassCard title="Pending invitations" subtitle="These people have not accepted yet. Each invitation reserves one household space. Resending replaces the previous link.">
      {loading ? <p role="status">Loading invitations…</p> : !pending.length ? <div className="family-invite-empty"><Mail size={24}/><p>No pending invitations.</p><small>Send an invitation above to welcome someone to your household.</small></div> : <InvitationTable rows={pending} onRevoke={setRevoke} onResend={resend} busy={saving} canResend={family.can_edit_shared}/>}
      {history.length > 0 && <details className="family-invitation-history"><summary>Invitation history ({history.length})</summary><p>Accepted, declined, expired and revoked invitations are kept here for your reference.</p><InvitationTable rows={history}/></details>}
    </GlassCard>

    {revoke && <FamilyConfirmDialog title="Revoke invitation?" confirmLabel="Revoke Invitation" onClose={() => setRevoke(null)} onConfirm={async () => {
      await api(`/family/invitations/${revoke.id}`, { method: "DELETE" });
      if (created?.id === revoke.id) setCreated(null);
      await load(); onChanged();
    }}><p>The invitation for <strong>{revoke.email}</strong> will stop working and its reserved space will become available. Existing members and financial records are unaffected.</p></FamilyConfirmDialog>}
  </div>;
}

function InvitationTable({ rows, onRevoke, onResend, busy = false, canResend = false }) {
  return <div className="family-invite-table-wrap"><table className="family-invite-table"><thead><tr><th>Invited person</th><th>Invitation</th><th>Email submission</th>{onRevoke && <th>Action</th>}</tr></thead><tbody>{rows.map(row => <tr key={row.id}>
    <td data-label="Invited person"><strong>{row.email}</strong><small>Expires {invitationDate(row.expires_at)}</small></td>
    <td data-label="Invitation"><span className={`family-invite-badge ${row.status}`}>{statusLabels[row.status] || row.status}</span></td>
    <td data-label="Email submission"><span>{deliveryLabels[row.delivery_status] || "Not recorded"}</span>{row.email_submitted_at && <small>{invitationDate(row.email_submitted_at)}</small>}</td>
    {onRevoke && <td data-label="Action"><div className="family-invite-actions">{onResend && <button className="db-outline-btn" disabled={busy || !canResend} aria-label={`Resend invitation to ${row.email}`} onClick={() => onResend(row)}>Resend Invitation</button>}<button className="db-outline-btn" disabled={busy} aria-label={`Revoke invitation for ${row.email}`} onClick={() => onRevoke(row)}>Revoke</button></div></td>}
  </tr>)}</tbody></table></div>;
}
