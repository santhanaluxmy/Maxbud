import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, money } from "../../../api/client";
import GlassCard from "../../../components/common/GlassCard";
import { planLabels, useSubscription } from "../../../subscriptions/SubscriptionContext";
import "./Subscription.css";

const date = value => new Date(value.endsWith("Z") ? value : value + "Z").toLocaleDateString();

export default function Upgrade() {
  const { subscription: data, usage, error: loadError, refresh } = useSubscription();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const operation = useRef(false);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  useEffect(() => {
    if (params.get("checkout") === "returned") navigate("/dashboard/payment-success", { replace: true });
  }, [params, navigate]);
  async function run(action, fn) {
    if (operation.current) return;
    operation.current = true; setBusy(action); setError("");
    try { await fn(); } catch (e) { setError(e.message); } finally { operation.current = false; setBusy(""); }
  }
  const paid = data?.source === "stripe_test" && ["premium_individual", "family_pack"].includes(data.plan);
  const hasSubscription = data?.stripe_subscription_exists;
  return <>
    <div className="db-page-intro"><div><span className="db-page-subtitle">YOUR MAXBUD MEMBERSHIP</span><h1>Subscription</h1><p>Personal tools for you. Shared tools for your household.</p></div></div>
    {data?.catalog.stripe_test_enabled && <p className="db-note" role="note">Test mode · No real money is charged.</p>}
    {params.get("checkout") === "canceled" && <p className="db-warning" role="status">Checkout was canceled. Your plan has not changed. You can return to checkout when you’re ready.</p>}
    {(error || loadError) && <p className="db-error" role="alert">{error || loadError}</p>}
    {!data ? <GlassCard><p role="status">{loadError ? "Membership could not load." : "Loading membership…"}</p>{loadError && <button className="db-outline-btn" disabled={!!busy} onClick={() => run("refresh", refresh)}>Try again</button>}</GlassCard> : <>
      <GlassCard className="subscription-status"><div><span className="db-page-subtitle">CURRENT PLAN</span><h2>{planLabels[data.plan] || data.plan}</h2><p>Status: {data.billing_status.replaceAll("_", " ")}</p>
        {data.plan === "trial" && data.trial_ends_at && <p>{data.trial_days_remaining} days remaining · Trial ends {date(data.trial_ends_at)}</p>}
        {paid && <p>{money(data.catalog.plans.find(p => p.id === data.plan)?.prices.monthly)} / month</p>}
        {paid && data.expires_at && <p>{data.cancel_at_period_end ? "Access until" : "Renews"} {date(data.expires_at)}</p>}
        {data.cancel_at_period_end && paid && <p>Renewal canceled. Your paid features remain available until the date above.</p>}
        {data.test_access && <p className="db-warning">Temporary test access · No payment received.</p>}
        {data.billing_portal_available && <button className="db-outline-btn" disabled={!!busy} onClick={() => run("portal", async () => { const result = await api("/billing/stripe/portal", { method: "POST" }); window.location.assign(result.url); })}>{busy === "portal" ? "Opening…" : "Manage Subscription"}</button>}
        {hasSubscription && !data.billing_portal_available && <p className="db-note">Subscription management is temporarily unavailable. You can check your plan again below.</p>}
      </div>{usage && <div className="subscription-meters">{[["receipt_scans", "Receipt scans"], ["advisor_messages", "AI Advisor messages"]].map(([key, label]) => <div key={key}><span>{label}<strong>{usage.used[key]} / {usage.limits[key]}</strong></span><progress aria-label={`${label} monthly usage`} value={usage.used[key]} max={Math.max(1, usage.limits[key])}/></div>)}<p>{data.limits.active_goals} active savings goals allowed</p></div>}</GlassCard>
      <p className="db-note">Monthly billing in LKR. Cancel renewal through Manage Subscription.</p>
      <div className="subscription-plans">{data.catalog.plans.map(plan => {
        const current = data.plan === plan.id;
        return <GlassCard key={plan.id} className={`subscription-plan ${plan.id === "family_pack" ? "subscription-featured" : ""}`}><h2>{plan.name}</h2>
          <p className="subscription-price">{money(plan.prices.monthly, data.catalog.currency)}<small>{plan.id === "trial" ? "3 calendar months for new registrations" : "per month"}</small></p>
          <ul><li>{plan.limits.receipt_scans} receipt scans / month</li><li>{plan.limits.advisor_messages} AI Advisor messages / month</li><li>{plan.limits.active_goals} active savings goals</li><li>{plan.id === "family_pack" ? `Owner + up to ${plan.limits.family_members - 1} invited members; permitted shared accounts, income, expenses, budgets, goals and reports` : "Personal finance; household management is not included"}</li>{plan.id === "family_pack" && <li>Members keep their own personal plans and AI allowances.</li>}</ul>
          {current ? <button className="db-outline-btn" disabled>Current Plan</button> : plan.id !== "trial" && (!hasSubscription ? data.catalog.checkout_available[plan.id] ? <button className="db-primary-btn" disabled={!!busy} onClick={() => run(plan.id, async () => { const result = await api("/billing/stripe/checkout", { method: "POST", data: { plan: plan.id, billing_cycle: "monthly", request_id: crypto.randomUUID() } }); window.location.assign(result.url); })}>{busy === plan.id ? "Opening checkout…" : plan.id === "family_pack" ? "Choose Family Pack" : "Upgrade to Premium"}</button> : <p className="db-note">Subscriptions are temporarily unavailable.</p> : <p className="db-note">Plan switching is currently unavailable. Your existing subscription continues on its current plan.</p>)}
        </GlassCard>;
      })}</div>
      {data.catalog.stripe_test_enabled && <Link className="db-outline-btn" to="/dashboard/payment-success">{data.checkout_pending ? "Check payment confirmation" : "Refresh subscription status"}</Link>}
      {!data.can_edit && <p className="db-warning">Your personal access period has ended. History and export remain available; subscribe to add or edit financial records.</p>}
      {data.sponsored_by && data.plan !== "family_pack" && <p className="db-note">Your household sponsor provides permitted shared tools. Your personal plan and AI limits remain independent.</p>}
    </>}
  </>;
}
