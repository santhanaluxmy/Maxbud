import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import HouseholdFinance from "./HouseholdFinance";
import { Plus, Users } from "lucide-react";
import { api, money } from "../../../api/client";
import GlassCard from "../../../components/common/GlassCard";
import EmptyState from "../../../components/common/EmptyState";
import Loading from "../../../components/common/Loading";
import Modal from "../../../components/common/Modal";
import "../dashboard/Dashboard.css";
import "./FamilyPage.css";

const blank = { full_name: "", email: "", password: "", confirm_password: "" };

export default function FamilyPage() {
  const [subscription, setSubscription] = useState(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteToken, setInviteToken] = useState(() => sessionStorage.getItem("maxbud_invitation") || "");
  const [inviteLink, setInviteLink] = useState("");
  const [invitations, setInvitations] = useState([]);
  const [householdName, setHouseholdName] = useState("");
  const [sharedGoals, setSharedGoals] = useState([]);
  const [goalError, setGoalError] = useState("");
  const [goalsLoading, setGoalsLoading] = useState(true);
  const [goalModal, setGoalModal] = useState(null);
  const [goalForm, setGoalForm] = useState({ name: "", target_amount: "", target_date: "", amount: "" });
  const [goalSaving, setGoalSaving] = useState(false);
  const goalRequest = useRef("");
  const goalBusy = useRef(false);
  const [family, setFamily] = useState(null);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(blank);
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState(0);
  const busy = useRef(false);
  const dialog = useRef(null);
  const opener = useRef(null);
  const owner = family?.role === "owner";
  const canEditShared = family?.can_edit_shared && family?.can_add_shared;

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api("/family", { signal: controller.signal }), api("/family/members", { signal: controller.signal })])
      .then(([info, list]) => { if (!controller.signal.aborted) { setFamily(info); setMembers(list); setError(""); } })
      .catch((err) => { if (!controller.signal.aborted) { setFamily(null); setMembers([]); setError(err.status === 404 ? "" : err.message); } })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision]);

  useEffect(() => {
    if (!family || !family.can_view_shared) return;
    const controller = new AbortController();
    api("/goals?scope=family", { signal: controller.signal }).then(goals => { if (!controller.signal.aborted) { setSharedGoals(goals); setGoalError(""); } }).catch(error => { if (!controller.signal.aborted) setGoalError(error.message); }).finally(() => { if (!controller.signal.aborted) setGoalsLoading(false); });
    return () => controller.abort();
  }, [family, revision]);

  function openGoal(kind, goal = null) {
    goalRequest.current = crypto.randomUUID();
    setGoalError(""); setGoalModal({ kind, goal });
    setGoalForm({ name: goal?.name || "", target_amount: goal?.target_amount || "", target_date: goal?.target_date || "", amount: "" });
  }
  async function saveGoal(event) {
    event.preventDefault();
    if (goalBusy.current) return;
    goalBusy.current = true; setGoalSaving(true); setGoalError("");
    try {
      const goal = goalModal.goal;
      if (goalModal.kind === "contribute") await api(`/goals/${goal.id}/contribute`, { method: "POST", data: { amount: goalForm.amount, request_id: goalRequest.current } });
      else await api(goal ? `/goals/${goal.id}` : "/goals?scope=family", { method: goal ? "PUT" : "POST", data: { name: goalForm.name.trim(), target_amount: goalForm.target_amount, saved_amount: goal?.saved_amount || "0", target_date: goalForm.target_date || null } });
      setGoalModal(null); setRevision(value => value + 1);
    } catch (error) { setGoalError(error.message); }
    finally { goalBusy.current = false; setGoalSaving(false); }
  }
  async function changeGoalStatus(goal) {
    if (goalBusy.current) return;
    goalBusy.current = true; setGoalSaving(true); setGoalError("");
    try { await api(`/goals/${goal.id}`, { method: "PATCH", data: { status: goal.status === "archived" ? "active" : "archived" } }); setRevision(value => value + 1); }
    catch (error) { setGoalError(error.message); }
    finally { goalBusy.current = false; setGoalSaving(false); }
  }

  useEffect(() => {
    if (!modal) return;
    const previous = document.activeElement;
    const node = dialog.current.closest('[role="dialog"]');
    const elements = () => [...node.querySelectorAll("input, button")].filter((item) => !item.disabled);
    elements()[0]?.focus();
    function keydown(event) {
      if (event.key === "Escape" && !busy.current) setModal(null);
      if (event.key === "Tab") {
        const items = elements(), first = items[0], last = items.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    }
    node.addEventListener("keydown", keydown);
    return () => { node.removeEventListener("keydown", keydown); (opener.current || previous)?.focus(); };
  }, [modal]);

  function open(value, event) {
    opener.current = event.currentTarget;
    setError(""); setNotice(""); setForm(blank); setModal(value);
  }

  async function submit(event) {
    event.preventDefault();
    if (busy.current) return;
    if (modal === "add" && form.password !== form.confirm_password) { setError("Passwords do not match."); return; }
    busy.current = true; setSaving(true); setError("");
    try {
      if (modal === "add") {
        await api("/family/members", { method: "POST", data: { ...form, full_name: form.full_name.trim(), email: form.email.trim().toLowerCase() } });
        setNotice("Family member added. They can sign in with their email and password.");
      } else {
        await api(`/family/members/${modal.id}`, { method: "DELETE" });
        setNotice("Membership removed. Their personal account and financial records are preserved.");
      }
      setForm(blank); setModal(null); setLoading(true); setRevision((value) => value + 1);
    } catch (err) { setError(err.message); }
    finally { busy.current = false; setSaving(false); }
  }

  const add = (event) => open("add", event);
  async function familyAction(fn) {
    if (busy.current) return false;
    busy.current = true; setSaving(true); setError(""); setNotice("");
    try { await fn(); setRevision(value => value + 1); return true; }
    catch (error) { setError(error.message); return false; }
    finally { busy.current = false; setSaving(false); }
  }
  async function updatePermissions(member, permissions) {
    setMembers(rows => rows.map(row => row.id === member.id ? { ...row, ...permissions } : row));
    const saved = await familyAction(() => api(`/family/members/${member.id}/permissions`, { method: "PATCH", data: permissions }));
    if (!saved) setMembers(rows => rows.map(row => row.id === member.id ? member : row));
  }
  useEffect(() => {
    const controller = new AbortController();
    api("/subscriptions", { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setSubscription(value); }).catch(error => { if (!controller.signal.aborted) setError(error.message); });
    return () => controller.abort();
  }, [revision]);
  useEffect(() => {
    if (!owner) return;
    let active = true;
    api("/family/invitations").then(rows => { if (active) setInvitations(rows); }).catch(error => { if (active) setError(error.message); });
    return () => { active = false; };
  }, [owner, revision]);
  return <main className="db-main family-page" aria-busy={loading}>
    <div className="db-page-intro"><div><span className="db-page-subtitle">MAXBUD / YOUR WORKSPACE</span><h1>Family Management</h1><p>Manage your household membership and keep personal finances private.</p></div>
      {owner && family.legacy_member_creation && <button type="button" className="db-primary-btn" disabled={loading || family.available_slots === 0} onClick={add}><Plus size={17}/>Add Member</button>}
    </div>
    {!loading && !family && <p className="db-note">Getting started: choose Family Pack → create a household → invite by email and share the secure link → plan shared finances together.</p>}
    {error && <div className="family-feedback" role="alert">{error} <button type="button" onClick={() => { setLoading(true); setRevision((value) => value + 1); }}>Retry</button> <Link to="/login">Sign in</Link></div>}
    {notice && <p className="family-feedback" role="status">{notice}</p>}
    {subscription?.test_access && <p className="db-warning" role="note">TEST ACCESS — no payment. Temporary Family Pack access ends {new Date(subscription.test_access_expires_at + "Z").toLocaleString()}.</p>}
    {loading ? <Loading>Loading family membership…</Loading> : family && <>
      <GlassCard title={family.name} subtitle="Family overview"><dl className="family-overview">
        {[["Plan", ({ family_pack: "Family Pack", premium: "Legacy Premium", free: "Legacy Free", read_only: "Read-only history" }[family.plan] || family.plan)], ["Owner", family.owner_name], ["Active members", family.total_active_members], ["Maximum members", family.max_members], ["Available slots", family.available_slots], ["Currency", family.currency]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>{owner && family.can_edit_shared && family.available_slots === 0 && <p role="status">No invitation spaces available ({family.max_members} users including the owner; pending invitations reserve spaces).</p>}</GlassCard>
      <GlassCard title={owner ? "Family members" : "Your membership"} subtitle={owner ? "Each member signs in to their own personal account." : "You manage your personal finances independently. Shared access is controlled by the owner."}>
        {owner && family.legacy_member_creation && members.length <= 1 && <><EmptyState icon={Users} title="No family members yet." text="Add a member to help your household budget together."/><button type="button" className="db-primary-btn" onClick={add} disabled={family.available_slots === 0}>Add Member</button></>}
        <div className="family-table-wrap"><table className="family-table"><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Joined</th>{owner && <><th>Shared permissions</th><th>Action</th></>}</tr></thead><tbody>{members.map((member) => <tr key={member.id}><td>{member.full_name}</td><td>{member.email}</td><td>{member.role === "owner" ? "Owner" : "Member"}</td><td>{member.is_active ? "Active" : "Inactive"}</td><td>{member.joined_at ? new Date(member.joined_at).toLocaleDateString() : "Not recorded"}</td>{owner && <td>{member.role !== "owner" && <><label><input type="checkbox" aria-label={`Allow shared reports for ${member.full_name}`} checked={member.can_view_shared} disabled={saving} onChange={event => updatePermissions(member, { can_view_shared: event.target.checked, can_add_shared: event.target.checked && member.can_add_shared })}/> Reports</label><label><input type="checkbox" aria-label={`Allow shared editing for ${member.full_name}`} checked={member.can_add_shared} disabled={saving || !member.can_view_shared} onChange={event => updatePermissions(member, { can_view_shared: member.can_view_shared, can_add_shared: event.target.checked })}/> Shared editing</label></>}</td>}{owner && <td>{member.role !== "owner" && <button type="button" className="db-secondary-btn" onClick={(event) => open(member, event)} aria-label={`Remove ${member.full_name}`}>Remove</button>}</td>}</tr>)}</tbody></table></div>
      </GlassCard>
    </>}
    {!loading && <GlassCard title="Join a household" subtitle="Sign in with the invited email. An invitation never changes your own subscription.">{inviteToken ? <form className="family-form" onSubmit={event => { event.preventDefault(); familyAction(async () => { await api("/family/invitations/respond", { method: "POST", data: { token: inviteToken, accept: true } }); sessionStorage.removeItem("maxbud_invitation"); setInviteToken(""); setNotice("Invitation accepted. Personal finances remain private."); }); }}><p>Your secure invitation is ready. Accept to join using the email the owner invited. Your personal accounts stay private.</p><div className="family-actions"><button className="db-primary-btn" disabled={saving}>Accept invitation</button><button type="button" className="db-outline-btn" disabled={saving || inviteToken.length < 32} onClick={() => familyAction(async () => { await api("/family/invitations/respond", { method: "POST", data: { token: inviteToken, accept: false } }); sessionStorage.removeItem("maxbud_invitation"); setInviteToken(""); setNotice("Invitation rejected."); })}>Reject invitation</button></div></form> : <p>To join a household, open the secure invitation link shared by its owner and sign in with the invited email. You do not need to enter a code.</p>}</GlassCard>}
    {!loading && !family && <GlassCard title="Your household"><p>New personal trials do not include household creation. An active Family Pack can sponsor a household; invited members do not need to buy another Family Pack.</p>{subscription?.plan === "family_pack" && subscription.billing_plan === "family_pack" ? <form className="family-form" onSubmit={event => { event.preventDefault(); familyAction(() => api("/family", { method: "POST", data: { name: householdName } })); }}><label>Household name<input required minLength={2} maxLength={100} value={householdName} onChange={event => setHouseholdName(event.target.value)}/></label><button className="db-primary-btn" disabled={saving}>Create household</button></form> : <Link className="db-outline-btn" to="/dashboard/upgrade">View Family Pack</Link>}</GlassCard>}
    {family && owner && <GlassCard title="Invite a member by email" subtitle="Invite up to five additional people. Links expire after seven days; no email is sent automatically."><form className="family-form" onSubmit={event => { event.preventDefault(); familyAction(async () => { const result = await api("/family/invitations", { method: "POST", data: { email: inviteEmail, can_view_shared: true, can_add_shared: true } }); setInviteLink(`${window.location.origin}/dashboard/family#invite=${encodeURIComponent(result.token)}`); setInviteEmail(""); }); }}><label>Invited email<input required type="email" value={inviteEmail} onChange={event => setInviteEmail(event.target.value)}/></label><p>The invited member can view shared reports and add shared expenses. You can change these permissions afterward.</p><button className="db-primary-btn" disabled={saving || !family.can_edit_shared || family.available_slots === 0}>Create secure invitation</button></form>{inviteLink && <><label>Invitation link<input readOnly aria-label="Invitation link" value={inviteLink} onFocus={event => event.target.select()}/></label><button className="db-outline-btn" onClick={async () => { try { await navigator.clipboard.writeText(inviteLink); setNotice("Invitation link copied. Share it privately with the invited person."); } catch { setNotice("Select the invitation link above to copy and share it privately."); } }}>Copy invitation link</button></>}{invitations.length > 0 && <div className="family-table-wrap"><table className="family-table"><thead><tr><th>Invited email</th><th>Status</th><th>Action</th></tr></thead><tbody>{invitations.map(invitation => <tr key={invitation.id}><td>{invitation.email}</td><td>{invitation.status}</td><td>{invitation.status === "pending" && <button disabled={saving} onClick={() => familyAction(() => api(`/family/invitations/${invitation.id}`, { method: "DELETE" }))}>Revoke invitation</button>}</td></tr>)}</tbody></table></div>}</GlassCard>}
    {family && !owner && <button className="db-outline-btn" disabled={saving} onClick={() => { if (window.confirm("Leave this household? Your personal history and recorded contributions will be preserved.")) familyAction(() => api("/family/leave", { method: "POST" })); }}>Leave household</button>}
    {family && owner && family.total_active_members === 1 && <button className="db-outline-btn" disabled={saving} onClick={() => { if (window.confirm("Close this empty household? The server rejects this if shared financial records exist.")) familyAction(() => api("/family/close", { method: "POST" })); }}>Close empty household</button>}
    {family && !family.can_edit_shared && <GlassCard title={family.plan === "family_pack" ? "Family member limit exceeded" : "Family Pack required"}>{family.plan === "family_pack" && <p>Remove extra memberships to return to six people including the owner. Financial history is preserved.</p>}<p>Free and Premium cover personal finances. An active Family Pack unlocks shared income, expenses and budgets for the owner and up to five invited members. Existing history is preserved.</p>{owner && <Link className="db-primary-btn" to="/dashboard/upgrade">View Family Pack</Link>}</GlassCard>}
    {family && !loading && <>
      {family.can_view_shared && <GlassCard title="Family finances" subtitle="Household aggregates stay separate from personal records."><div className="family-actions"><Link className="db-outline-btn" to="/dashboard?scope=family">View family financial report</Link><Link className="db-outline-btn" to="/dashboard/upgrade">Family subscription</Link></div><p className="db-note">Only explicitly shared records appear in household reports. Private salaries and account details are never pooled. Historical shared contributions remain in the ledger.</p></GlassCard>}
      <HouseholdFinance family={family}/>
      {family.can_view_shared && <GlassCard title="Shared savings goals" subtitle="Work toward a household goal together. Contributions are allocations, not new income." action={owner && <button type="button" className="db-primary-btn" disabled={!canEditShared} onClick={() => openGoal("create")}>New shared goal</button>}>
        {goalError && !goalModal && <p className="family-feedback" role="alert">{goalError}</p>}
        {goalsLoading ? <Loading>Loading shared goals…</Loading> : !sharedGoals.length ? <EmptyState title="A shared goal starts here" text={owner ? "Create a goal for your family to contribute toward." : "Your family owner can create a shared savings goal."}/> : <div className="family-shared-goals">{sharedGoals.map(goal => <article className="family-shared-goal" key={goal.id}>
          <div className="family-goal-heading"><h3>{goal.name}</h3><span className="db-pill">{goal.status}</span></div>
          <div className="family-goal-numbers"><div><small>Saved together</small><strong>{money(goal.saved_amount,"LKR")}</strong></div><div><small>Target</small><strong>{money(goal.target_amount,"LKR")}</strong></div><div><small>Remaining</small><strong>{money(goal.remaining_amount,"LKR")}</strong></div></div>
          <progress aria-label={`${goal.name} shared progress`} value={goal.progress} max={100}/><p>{Math.round(goal.progress)}% complete{goal.target_date ? ` · Target: ${goal.target_date}` : ""}</p>
          <ul className="family-contributors">{goal.contributions.map(member => <li key={member.user_id}><span className={`family-member-dot tone-${member.user_id % 3}`}/><span>{member.full_name}{!member.is_active_member && " (former or inactive member)"}</span><strong>{money(member.amount,"LKR")}</strong></li>)}</ul>
          <div className="family-actions">{goal.status === "active" && <button type="button" className="db-primary-btn" disabled={goalSaving || !canEditShared} onClick={() => openGoal("contribute",goal)} aria-label={`Contribute to ${goal.name}`}>Contribute</button>}{owner && <><button type="button" className="db-outline-btn" disabled={goalSaving || !canEditShared} onClick={() => openGoal("edit",goal)} aria-label={`Edit ${goal.name}`}>Edit</button><button type="button" className="db-outline-btn" disabled={goalSaving || !canEditShared} onClick={() => changeGoalStatus(goal)} aria-label={`${goal.status === "archived" ? "Restore" : "Archive"} ${goal.name}`}>{goal.status === "archived" ? "Restore" : "Archive"}</button></>}</div>
          <details className="family-goal-history"><summary>Contribution history ({goal.history.length})</summary><div className="family-table-wrap"><table className="family-table"><thead><tr><th>Member</th><th>Date</th><th>Amount</th><th>Status</th></tr></thead><tbody>{goal.history.map(entry => <tr key={entry.id}><td>{entry.full_name}</td><td>{entry.recorded_on}</td><td>{money(entry.amount,"LKR")}</td><td>{entry.reversed ? "Reversed" : "Recorded"}</td></tr>)}</tbody></table></div></details>
        </article>)}</div>}
      </GlassCard>}
    </>}
    {goalModal && <Modal title={goalModal.kind === "contribute" ? `Contribute to ${goalModal.goal.name}` : goalModal.kind === "edit" ? "Edit shared goal" : "New shared savings goal"} onClose={() => { if (!goalBusy.current) setGoalModal(null); }}><form className="family-form" onSubmit={saveGoal}>
      {goalModal.kind === "contribute" ? <><label>Contribution amount (LKR)<input required type="number" min="0.01" step="0.01" max={goalModal.goal.remaining_amount} value={goalForm.amount} disabled={goalSaving} onChange={event => setGoalForm({ ...goalForm, amount: event.target.value })}/></label><p>This records your allocation in the shared ledger. It does not move account funds or create income.</p></> : <><label>Goal name<input required minLength={1} maxLength={120} disabled={goalSaving} value={goalForm.name} onChange={event => setGoalForm({ ...goalForm, name: event.target.value })}/></label><label>Target amount (LKR)<input required type="number" min={goalModal.goal?.saved_amount || "0.01"} max="9999999999.99" step="0.01" disabled={goalSaving} value={goalForm.target_amount} onChange={event => setGoalForm({ ...goalForm, target_amount: event.target.value })}/></label><label>Target date (optional)<input type="date" disabled={goalSaving} value={goalForm.target_date} onChange={event => setGoalForm({ ...goalForm, target_date: event.target.value })}/></label><p>Saved amounts come only from recorded member contributions.</p></>}
      {goalError && <p role="alert">{goalError}</p>}<div className="family-actions"><button type="button" className="db-outline-btn" disabled={goalSaving} onClick={() => setGoalModal(null)}>Cancel</button><button className="db-primary-btn" disabled={goalSaving}>{goalSaving ? "Saving…" : goalModal.kind === "contribute" ? "Record contribution" : "Save shared goal"}</button></div>
    </form></Modal>}
    {modal && <Modal title={modal === "add" ? "Add family member" : "Remove family member"} onClose={() => { if (!busy.current) { setModal(null); setForm(blank); } }}><div ref={dialog}>
      <form className="family-form" onSubmit={submit}>
        {modal === "add" ? <>{[["full_name", "Full Name", "text"], ["email", "Email Address", "email"], ["password", "Password", "password"], ["confirm_password", "Confirm Password", "password"]].map(([key, label, type]) => <label key={key} htmlFor={`family-${key}`}>{label}<input id={`family-${key}`} name={key} type={type} value={form[key]} onChange={(event) => setForm({ ...form, [key]: event.target.value })} required disabled={saving} minLength={key === "full_name" ? 2 : type === "password" ? 8 : undefined} maxLength={key === "full_name" ? 100 : key === "email" ? 254 : 128} autoComplete={type === "password" ? "new-password" : "off"} pattern={key === "password" ? "(?=.*[A-Z])(?=.*[a-z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,128}" : undefined}/></label>)}<p>Use 8–128 characters with uppercase, lowercase, a number and a symbol.</p></> : <p>Remove <strong>{modal.full_name}</strong> from the family? Their personal account and financial records will be preserved. Family access ends immediately.</p>}
        {error && <p role="alert">{error}</p>}
        <div className="family-actions"><button className="db-secondary-btn" type="button" disabled={saving} onClick={() => { setModal(null); setForm(blank); }}>Cancel</button><button className="db-primary-btn" type="submit" disabled={saving}>{saving ? "Saving…" : modal === "add" ? "Add Member" : "Remove Member"}</button></div>
      </form>
    </div></Modal>}
  </main>;
}
