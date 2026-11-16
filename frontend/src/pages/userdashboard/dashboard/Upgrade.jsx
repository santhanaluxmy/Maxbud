import { useCallback, useEffect, useState } from "react";
import { api, money } from "../../../api/client";
import GlassCard from "../../../components/common/GlassCard";
import Modal from "../../../components/common/Modal";

const labels = { trial: "Free Trial", premium_individual: "Premium Individual", family_pack: "Family Pack", free: "Legacy Free", premium: "Legacy Premium", read_only: "Read-only history" };
export default function Upgrade() {
  const [data, setData] = useState(null), [usage, setUsage] = useState(null);
  const [error, setError] = useState(""), [message, setMessage] = useState("");
  const [cycle, setCycle] = useState("monthly"), [checkout, setCheckout] = useState(null), [busy, setBusy] = useState(false);
  const load = useCallback(() => Promise.all([api("/subscriptions"), api("/ai/usage")]), []);
  useEffect(() => { let active = true; load().then(([state, meter]) => { if (active) { setData(state); setUsage(meter); } }).catch(e => { if (active) setError(e.message); }); return () => { active = false; }; }, [load]);
  async function run(fn) {
    setBusy(true); setError(""); setMessage("");
    try { await fn(); const [state, meter] = await load(); setData(state); setUsage(meter); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <>
    <div className="db-page-intro"><div><span className="db-page-subtitle">YOUR MAXBUD MEMBERSHIP</span><h1>Subscription</h1><p>Personal tools for you. Shared tools for your household.</p></div></div>
    <p className="db-warning" role="note">Demo Payment — No real money will be charged.</p>
    {error && <p className="db-error" role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {!data ? <GlassCard><p role="status">{error ? "Membership could not load." : "Loading membership…"}</p><button className="db-outline-btn" onClick={() => run(async () => {})}>Retry</button></GlassCard> : <>
      <GlassCard className="subscription-status"><div><span className="db-page-subtitle">CURRENT ACCESS</span><h2>{labels[data.plan] || data.plan}</h2><p>{data.status}{data.source === "demo" ? " · SIMULATED / DEMO" : ""}</p>
        {data.trial_ends_at && data.plan === "trial" && <p>{data.trial_days_remaining} days remaining · Ends {new Date(data.trial_ends_at + "Z").toLocaleDateString()}</p>}
        {data.expires_at && data.plan !== "trial" && <p>Current period ends {new Date(data.expires_at + "Z").toLocaleDateString()}</p>}
        {data.sponsored_by && <p>Your household sponsors this access. Your own subscription has not been canceled.</p>}
        {!data.can_edit && <p>History and export remain available. Select a plan to resume financial editing.</p>}
        {data.cancel_at_period_end && <p>Cancellation scheduled. Access continues until period end.</p>}
        {data.pending_plan && <p>Next checkout selection: {labels[data.pending_plan]}. No automatic renewal charge.</p>}
      </div>{usage && <div className="subscription-meters">{[["receipt_scans", "Receipt scans"], ["advisor_messages", "Advisor messages"]].map(([key, label]) => <div key={key}><span>{label}<strong>{usage.used[key]} / {usage.limits[key]}</strong></span><progress aria-label={`${label} monthly usage`} value={usage.used[key]} max={Math.max(1, usage.limits[key])}/></div>)}</div>}</GlassCard>
      <label>Billing period <select aria-label="Billing period" value={cycle} onChange={e => setCycle(e.target.value)}><option value="monthly">Monthly</option><option value="yearly">Yearly</option></select></label>
      <div className="subscription-plans">{data.catalog.plans.map(plan => <GlassCard key={plan.id} className={`subscription-plan ${plan.id === "family_pack" ? "subscription-featured" : ""}`}><h2>{plan.name}</h2>
        <p className="subscription-price">{plan.id === "trial" ? "LKR 0" : plan.prices[cycle] === null ? "Price not configured" : money(plan.prices[cycle], data.catalog.currency)}<small>{plan.id === "trial" ? "3 calendar months for new registrations" : `per ${cycle === "monthly" ? "month" : "year"} · configurable demo price`}</small></p>
        <ul><li>{plan.limits.receipt_scans} receipt scans / month</li><li>{plan.limits.advisor_messages} advisor messages / month</li><li>{plan.limits.active_goals} active goals</li><li>{plan.id === "family_pack" ? `Owner + up to ${plan.limits.family_members - 1} invited people; shared income, expenses and budgets` : "Personal finance only; no shared household budget"}</li>{plan.id === "trial" && <li>Household management is not included.</li>}</ul>
        {plan.id !== "trial" && <><button className="db-primary-btn" disabled={busy || !data.catalog.demo_enabled} onClick={() => run(async () => { setCheckout(await api("/subscriptions/checkout", { method: "POST", data: { plan: plan.id, billing_cycle: cycle, request_id: crypto.randomUUID() } })); })}>{data.catalog.demo_enabled ? data.billing_plan === plan.id ? "Simulate renewal" : "Open demo checkout" : "Demo checkout disabled"}</button>
          {data.source === "demo" && data.billing_plan !== plan.id && <button className="db-outline-btn" disabled={busy} onClick={() => run(async () => { const result = await api("/subscriptions/schedule", { method: "POST", data: { plan: plan.id, billing_cycle: cycle } }); setMessage(result.message); })}>Schedule next plan</button>}</>}
      </GlassCard>)}</div>
      {data.source === "demo" && <button className="db-outline-btn" disabled={busy || data.cancel_at_period_end} onClick={() => run(async () => { await api("/subscriptions/cancel", { method: "POST" }); setMessage("Cancellation scheduled. Your existing period remains available."); })}>Cancel at period end</button>}
      <p className="db-note">Prices are configurable and provisional. No real payment gateway is connected. A failed simulation never activates a new plan. New registrations receive one persisted three-calendar-month personal trial.</p>
    </>}
    {checkout && <Modal title="Demo Checkout" onClose={() => { if (!busy) setCheckout(null); }}><p className="db-warning">Demo Payment — No real money will be charged.</p><p>{labels[checkout.plan]} · {checkout.billing_cycle}</p><p>{checkout.amount === null ? "No configured price. Simulation only; this is not real revenue." : `Simulated amount: ${money(checkout.amount)}`}</p><div className="family-actions">{[["success", "Simulate Successful Payment"], ["failure", "Simulate Failed Payment"]].map(([outcome, label]) => <button key={outcome} className={outcome === "success" ? "db-primary-btn" : "db-outline-btn"} disabled={busy} onClick={() => run(async () => { const result = await api(`/subscriptions/checkout/${checkout.id}/simulate`, { method: "POST", data: { outcome } }); setMessage(result.checkout_status === "succeeded" ? "Demo subscription activated. No real payment occurred." : "Simulation failed. No new entitlement was granted."); setCheckout(null); })}>{label}</button>)}</div>{error && <p role="alert">{error}</p>}</Modal>}
  </>;
}
