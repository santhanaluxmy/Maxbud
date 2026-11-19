import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import HouseholdFinance from "./HouseholdFinance";
import { ArrowLeft, Wallet, ArrowDownLeft, Receipt, ChartPie, Target, HandCoins, ChartNoAxesCombined, Bell, Activity, Users, ArrowRight } from "lucide-react";
import { api, money } from "../../../api/client";
import GlassCard from "../../../components/common/GlassCard";
import EmptyState from "../../../components/common/EmptyState";
import Loading from "../../../components/common/Loading";
import Modal from "../../../components/common/Modal";
import "../dashboard/Dashboard.css";
import "./FamilyPage.css";
import FamilyInvitations from "./FamilyInvitations";
import FamilyMembers from "./FamilyMembers";
import FamilyConfirmDialog from "./FamilyConfirmDialog";
import { useSubscription } from "../../../subscriptions/SubscriptionContext";

const sections = {
  overview: ["Shared household", "Choose a shared task. Your personal money stays in your own workspace."],
  wallets: ["Shared wallets", "Contribute from your own account to a household wallet. Funding is a transfer, not income."],
  income: ["Shared income", "Record common earnings in a shared wallet. Keep private salaries in Personal Finance."],
  expenses: ["Shared expenses & splitting", "Record a common cost. When you pay personally, choose who shares the expense."],
  budgets: ["Shared budgets", "Follow household category limits and spending. The owner manages the limits."],
  goals: ["Shared goals", "Allocate toward a common goal and follow each member’s contribution history."],
  reimbursements: ["Reimbursements", "See split obligations and repay your own debts. Repayments are transfers, not new expenses."],
  reports: ["Shared reports", "Review shared income, spending and contributions. Private finances are excluded."],
  bills: ["Household bills", "Track common bills and record payment from the assigned shared wallet."],
  activity: ["Household activity", "Review shared transactions, wallet contributions, goal allocations and reimbursements."],
  members: ["Household membership", "View your membership. The owner manages invitations and shared permissions."],
};

const sectionIcons = { wallets: Wallet, income: ArrowDownLeft, expenses: Receipt, budgets: ChartPie, goals: Target, reimbursements: HandCoins, reports: ChartNoAxesCombined, bills: Bell, activity: Activity, members: Users };

export default function FamilyPage() {
  const { section: requestedSection = "overview" } = useParams();
  const section = Object.hasOwn(sections, requestedSection) ? requestedSection : null;
  const membershipView = section === "members" || section === "overview";
  const { subscription } = useSubscription();
  const [householdName, setHouseholdName] = useState("");
  const [closeConfirmation, setCloseConfirmation] = useState(false);
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
  const [loadedSection, setLoadedSection] = useState(null);
  const sectionLoading = loading || loadedSection !== section;
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState(null);
  const [saving, setSaving] = useState(false);
  const [revision, setRevision] = useState(0);
  const busy = useRef(false);
  const owner = family?.role === "owner";
  const canEditShared = family?.can_edit_shared && family?.can_add_shared;

  useEffect(() => {
    const controller = new AbortController();
    let fetching = false;
    function refresh() {
      if (fetching || controller.signal.aborted) return;
      fetching = true;
      Promise.all([api("/family", { signal: controller.signal }), api("/family/members", { signal: controller.signal })])
        .then(([info, list]) => { if (!controller.signal.aborted) { setFamily(info); setMembers(list); setError(""); } })
        .catch(err => { if (!controller.signal.aborted) { setFamily(null); setMembers([]); setError(err.status === 404 ? "" : err.message); } })
        .finally(() => { fetching = false; if (!controller.signal.aborted) { setLoadedSection(section); setLoading(false); } });
    }
    refresh();
    const update = () => { if (document.visibilityState === "visible" && !busy.current) refresh(); };
    const interval = membershipView ? window.setInterval(update, 5000) : null;
    if (membershipView) { window.addEventListener("focus", update); document.addEventListener("visibilitychange", update); }
    return () => { controller.abort(); window.clearInterval(interval); window.removeEventListener("focus", update); document.removeEventListener("visibilitychange", update); };
  }, [revision, section, membershipView]);

  useEffect(() => {
    if (!family || !family.can_view_shared || section !== "goals") return;
    const controller = new AbortController();
    api("/goals?scope=family", { signal: controller.signal }).then(goals => { if (!controller.signal.aborted) { setSharedGoals(goals); setGoalError(""); } }).catch(error => { if (!controller.signal.aborted) setGoalError(error.message); }).finally(() => { if (!controller.signal.aborted) setGoalsLoading(false); });
    return () => controller.abort();
  }, [family, revision, section]);

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
      setGoalModal(null); setNotice("Shared goal saved. Totals and contribution history have been updated."); setRevision(value => value + 1);
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

  function open(member) { setModal(member); }

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
  if (!section) return <main className="db-main family-page"><h1>Shared section not found</h1><Link to="/dashboard/family">Return to shared household</Link></main>;
  return <main className="db-main family-page" aria-busy={sectionLoading}>
    {section !== "overview" && <Link to="/dashboard/family" className="family-return"><ArrowLeft size={16}/>Family Overview</Link>}
    <div className="db-page-intro"><div><span className="db-page-subtitle">SHARED HOUSEHOLD</span><h1>{section === "overview" ? "Family Management" : sections[section][0]}</h1><p>{sections[section][1]}</p></div>{family && <span className="family-context"><Users size={16}/>{family.name}<small>{owner ? "Owner" : "Member"}</small></span>}
    </div>
    <div className="family-workspace">
      <div className="family-content">
    {!sectionLoading && !family && <p className="db-note">Getting started: choose Family Pack → create a household → invite by email and share the secure link → plan shared finances together.</p>}
    {error && <div className="family-feedback" role="alert">{error} <button type="button" onClick={() => { setLoading(true); setRevision((value) => value + 1); }}>Retry</button> <Link to="/login">Sign in</Link></div>}
    {notice && <p className="family-feedback" role="status">{notice}</p>}
    {subscription?.test_access && <p className="db-warning" role="note">TEST ACCESS — no payment. Temporary Family Pack access ends {new Date(subscription.test_access_expires_at + "Z").toLocaleString()}.</p>}
    {sectionLoading ? <Loading>Loading family membership…</Loading> : family && membershipView && <>
      <GlassCard title={family.name} subtitle={family.plan === "family_pack" ? `1 Owner + ${Math.max(0, family.max_members - 1)} Members (${family.max_members} total)` : "Family overview"}><dl className="family-overview">
        {[["Plan", ({ family_pack: "Family Pack", premium: "Legacy Premium", free: "Legacy Free", read_only: "Read-only history" }[family.plan] || family.plan)], ["Owner", family.owner_name], ["People in household", family.total_active_members], ["Total capacity", family.max_members], ["Available slots", family.available_slots], ["Currency", family.currency]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
      </dl>{owner && family.can_edit_shared && family.available_slots === 0 && <p role="status">No invitation spaces available ({family.max_members} users including the owner; pending invitations reserve spaces).</p>}</GlassCard>
      {section === "members" && <FamilyMembers owner={owner} members={members} saving={saving} onPermissions={updatePermissions} onRemove={open}/>}
    </>}
    {!sectionLoading && !family && <GlassCard title="Join a household" subtitle="Everyone signs in with their own account."><p>Open the full invitation link shared by the household owner. You can review and accept it after signing in with the invited email.</p></GlassCard>}
    {!sectionLoading && !family && <GlassCard title="Your household"><p>New personal trials do not include household creation. An active Family Pack can sponsor a household; invited members do not need to buy another Family Pack.</p>{subscription?.plan === "family_pack" && subscription.billing_plan === "family_pack" ? <form className="family-form" onSubmit={event => { event.preventDefault(); familyAction(() => api("/family", { method: "POST", data: { name: householdName } })); }}><label>Household name<input required minLength={2} maxLength={100} value={householdName} onChange={event => setHouseholdName(event.target.value)}/></label><button className="db-primary-btn" disabled={saving}>Create household</button></form> : <Link className="db-outline-btn" to="/dashboard/upgrade">View Family Pack</Link>}</GlassCard>}
    {family && owner && section === "members" && <FamilyInvitations family={family} onChanged={() => setRevision(value => value + 1)}/>}
    {family && !owner && section === "members" && <button className="db-outline-btn" disabled={saving} onClick={() => { if (window.confirm("Leave this household? Your personal history and recorded contributions will be preserved.")) familyAction(() => api("/family/leave", { method: "POST" })); }}>Leave household</button>}
    {family && owner && section === "members" && family.total_active_members === 1 && <div className="family-close-section"><h2>Close an empty household</h2><p>Only a household with no shared financial records can be closed. Pending invitations will be revoked. Your personal account and subscription stay active.</p><button className="db-outline-btn" disabled={saving} onClick={() => setCloseConfirmation(true)}>Close empty household</button></div>}
    {closeConfirmation && family && <FamilyConfirmDialog title="Close this household?" confirmLabel="Close household" confirmation={family.name} onClose={() => setCloseConfirmation(false)} onConfirm={async () => { await api("/family/close", { method: "POST" }); setFamily(null); setMembers([]); setNotice("The empty household is closed. Pending invitations have been revoked."); setRevision(value => value + 1); }}><p>Close <strong>{family.name}</strong>? You will need to create a household again before inviting members. Shared financial records are protected: the server will refuse to close a household that contains them.</p></FamilyConfirmDialog>}
    {family && !family.can_edit_shared && <GlassCard title={family.plan === "family_pack" ? "Family member limit exceeded" : "Family Pack required"}>{family.plan === "family_pack" && <p>Remove extra memberships to return to five people including the owner. Financial history is preserved.</p>}<p>Free and Premium cover personal finances. An active Family Pack unlocks shared income, expenses and budgets for the owner and up to four invited members. Existing history is preserved.</p>{owner && <Link className="db-primary-btn" to="/dashboard/upgrade">View Family Pack</Link>}</GlassCard>}
    {family && !sectionLoading && <>
      {section === "overview" && <GlassCard title="Your shared workspace" subtitle={owner ? "Manage household setup or choose a daily finance task." : "You have your own personal finances and a separate shared household workspace."}>
        <p>{!family.can_view_shared ? "The owner has not granted shared viewing access. Ask them to enable shared reports." : canEditShared ? "You can record shared income and expenses, fund wallets, contribute to goals and repay your own split obligations." : "You can view shared history. Editing requires an active Family Pack and the owner’s shared editing permission."}</p>
        <div className="family-task-grid">{[["wallets", "Manage Wallets", "Balances & contributions"], ["income", "Record Shared Income", "Common household earnings"], ["expenses", "Add Shared Expense", "Payments & expense splits"], ["budgets", "View Shared Budget", "Monthly spending limits"], ["goals", "Manage Goals", "Save toward something together"], ["bills", "Household Bills", "Upcoming shared payments"], ["reimbursements", "View Reimbursements", "Member balances & repayments"], ["reports", "Shared Reports", "Income, spending & contributions"], ["members", owner ? "Manage Membership" : "Your Membership", "People, invitations & access"], ["activity", "Household Activity", "Shared financial history"]].map(([key, label, description]) => { const Icon = sectionIcons[key]; return <Link className="family-task" key={key} to={`/dashboard/family/${key}`}><span className="family-task-icon"><Icon size={21}/></span><span><strong>{label}</strong><small>{description}</small></span><ArrowRight size={17}/></Link>; })}</div>
      </GlassCard>}
      {section !== "goals" && section !== "members" && <HouseholdFinance key={section} family={family} section={section}/>}
      {section === "goals" && !family.can_view_shared && <p role="status">The owner has not granted access to shared goals. Your personal goals remain available in Personal Finance.</p>}
      {section === "goals" && family.can_view_shared && !canEditShared && <p className="db-warning">You can view goals and contribution history. Contributions require an active Family Pack and the owner’s shared editing permission.</p>}
      {section === "goals" && family.can_view_shared && <GlassCard title="Shared savings goals" subtitle="Work toward a household goal together. Contributions are allocations, not new income." action={owner && <button type="button" className="db-primary-btn" disabled={!canEditShared} onClick={() => openGoal("create")}>New shared goal</button>}>
        {goalError && !goalModal && <p className="family-feedback" role="alert">{goalError} <button className="db-outline-btn" onClick={() => { setGoalsLoading(true); setRevision(value => value + 1); }}>Retry shared goals</button></p>}
        {goalsLoading ? <Loading>Loading shared goals…</Loading> : !sharedGoals.length ? <EmptyState title="A shared goal starts here" text={owner ? "Create a goal for your family to contribute toward." : "Your family owner can create a shared savings goal."}/> : <div className="family-shared-goals">{sharedGoals.map(goal => <article className="family-shared-goal" key={goal.id}>
          <div className="family-goal-heading"><h3>{goal.name}</h3><span className="db-pill">{goal.status}</span></div>
          <div className="family-goal-numbers"><div><small>Saved together</small><strong>{money(goal.saved_amount,"LKR")}</strong></div><div><small>Target</small><strong>{money(goal.target_amount,"LKR")}</strong></div><div><small>Remaining</small><strong>{money(goal.remaining_amount,"LKR")}</strong></div></div>
          <progress aria-label={`${goal.name} shared progress`} value={goal.progress} max={100}/><p>{Math.round(goal.progress)}% complete{goal.target_date ? ` · Target: ${goal.target_date}` : ""}</p>
          <ul className="family-contributors">{goal.contributions.map(member => <li key={member.user_id}><span className={`family-member-dot tone-${member.user_id % 3}`}/><span>{member.full_name}{!member.is_active_member && " (former or inactive member)"}</span><strong>{money(member.amount,"LKR")}</strong></li>)}</ul>
          <div className="family-actions">{goal.status === "active" && Number(goal.remaining_amount) > 0 && <button type="button" className="db-primary-btn" disabled={goalSaving || !canEditShared} onClick={() => openGoal("contribute",goal)} aria-label={`Contribute to ${goal.name}`}>Contribute</button>}{owner && <details><summary>Manage goal</summary><div className="family-actions"><button type="button" className="db-outline-btn" disabled={goalSaving || !canEditShared} onClick={() => openGoal("edit",goal)} aria-label={`Edit ${goal.name}`}>Edit</button><button type="button" className="db-outline-btn" disabled={goalSaving || !canEditShared} onClick={() => changeGoalStatus(goal)} aria-label={`${goal.status === "archived" ? "Restore" : "Archive"} ${goal.name}`}>{goal.status === "archived" ? "Restore" : "Archive"}</button></div></details>}</div>
          <details className="family-goal-history"><summary>Contribution history ({goal.history.length})</summary><div className="family-table-wrap"><table className="family-table"><thead><tr><th>Member</th><th>Date</th><th>Amount</th><th>Status</th></tr></thead><tbody>{goal.history.map(entry => <tr key={entry.id}><td>{entry.full_name}</td><td>{entry.recorded_on}</td><td>{money(entry.amount,"LKR")}</td><td>{entry.reversed ? "Reversed" : "Recorded"}</td></tr>)}</tbody></table></div></details>
        </article>)}</div>}
      </GlassCard>}
    </>}
    {goalModal && <Modal title={goalModal.kind === "contribute" ? `Contribute to ${goalModal.goal.name}` : goalModal.kind === "edit" ? "Edit shared goal" : "New shared savings goal"} onClose={() => { if (!goalBusy.current) setGoalModal(null); }}><form className="family-form" onSubmit={saveGoal}>
      {goalModal.kind === "contribute" ? <><label>Contribution amount (LKR)<input required type="number" min="0.01" step="0.01" max={goalModal.goal.remaining_amount} value={goalForm.amount} disabled={goalSaving} onChange={event => setGoalForm({ ...goalForm, amount: event.target.value })}/></label><p>This records your allocation in the shared ledger. It does not move account funds or create income.</p></> : <><label>Goal name<input required minLength={1} maxLength={120} disabled={goalSaving} value={goalForm.name} onChange={event => setGoalForm({ ...goalForm, name: event.target.value })}/></label><label>Target amount (LKR)<input required type="number" min={goalModal.goal?.saved_amount || "0.01"} max="9999999999.99" step="0.01" disabled={goalSaving} value={goalForm.target_amount} onChange={event => setGoalForm({ ...goalForm, target_amount: event.target.value })}/></label><label>Target date (optional)<input type="date" disabled={goalSaving} value={goalForm.target_date} onChange={event => setGoalForm({ ...goalForm, target_date: event.target.value })}/></label><p>Saved amounts come only from recorded member contributions.</p></>}
      {goalError && <p role="alert">{goalError}</p>}<div className="family-actions"><button type="button" className="db-outline-btn" disabled={goalSaving} onClick={() => setGoalModal(null)}>Cancel</button><button className="db-primary-btn" disabled={goalSaving}>{goalSaving ? "Saving…" : goalModal.kind === "contribute" ? "Record contribution" : "Save shared goal"}</button></div>
    </form></Modal>}
    {modal && <FamilyConfirmDialog title="Remove household member?" confirmLabel="Remove member" onClose={() => setModal(null)} onConfirm={async () => { await api(`/family/members/${modal.id}`, { method: "DELETE" }); setNotice("Membership removed. Their personal account and financial records are preserved."); setRevision(value => value + 1); }}><p>Remove <strong>{modal.full_name}</strong> from this household? Their access to shared records ends immediately. Their personal account and financial history are preserved.</p></FamilyConfirmDialog>}
      </div>
    </div>
  </main>;
}
