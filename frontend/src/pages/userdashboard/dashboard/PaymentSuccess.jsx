import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../../api/client";
import GlassCard from "../../../components/common/GlassCard";
import { useSubscription } from "../../../subscriptions/SubscriptionContext";
import { verifiedCheckoutDestination } from "../../../subscriptions/checkoutNavigation";
import "./Subscription.css";

export default function PaymentSuccess() {
  const { refresh } = useSubscription();
  const navigate = useNavigate();
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState({ status: "loading", plan: null, error: "" });
  useEffect(() => {
    const controller = new AbortController();
    let timer;
    let timeout;
    const deadline = Date.now() + 60000;
    function returnToSubscription(reason, message = "") {
      window.clearTimeout(timer);
      window.clearTimeout(timeout);
      controller.abort();
      navigate(`/dashboard/upgrade?checkout=${reason}`, { replace: true, state: { verificationError: message } });
    }
    timeout = window.setTimeout(() => returnToSubscription("pending"), 60000);
    async function check() {
      try {
        const result = await api("/billing/stripe/reconcile", { method: "POST", signal: controller.signal });
        if (controller.signal.aborted) return;
        const destination = verifiedCheckoutDestination(result);
        if (destination) {
          window.clearTimeout(timeout);
          setState({ status: "active", plan: result.subscription.plan, error: "" });
          // Paid verification must not wait on unrelated usage requests.
          refresh().catch(() => {});
          navigate(destination, { replace: true });
          return;
        }
        if (["canceled", "failed"].includes(result.activation)) { returnToSubscription(result.activation); return; }
        if (result.activation === "active") { returnToSubscription("error"); return; }
        if (Date.now() < deadline) {
          setState({ status: "loading", plan: null, error: "" });
          timer = window.setTimeout(check, 3000);
        } else returnToSubscription("pending");
      } catch (e) {
        if (!controller.signal.aborted) returnToSubscription("error", e.message);
      }
    }
    check();
    return () => { controller.abort(); window.clearTimeout(timer); window.clearTimeout(timeout); };
  }, [attempt, refresh, navigate]);
  const active = state.status === "active";
  return <section className="subscription-confirmation" aria-busy={state.status === "loading"}>
    <GlassCard><span className="db-page-subtitle">YOUR MAXBUD MEMBERSHIP</span>
      <h1>{active ? state.plan === "family_pack" ? "Family Pack Active" : "Premium Active" : state.status === "loading" ? "Activating your subscription…" : state.status === "canceled" ? "Checkout expired" : "Confirmation pending"}</h1>
      <p role="status" aria-live="polite">{active ? "Your subscription is verified and your features are ready. Your existing usage and financial history are preserved." : state.status === "loading" ? "We’re checking your payment securely. This can take a moment." : state.status === "canceled" ? "This checkout was not completed. You can choose a plan and try again." : "We could not confirm an active paid subscription yet. If you completed payment, please check again. Do not make another payment."}</p>
      {state.error && <p className="db-error" role="alert">{state.error}</p>}
      <div className="subscription-confirmation-actions">{active ? <Link className="db-primary-btn" to={state.plan === "family_pack" ? "/dashboard/family" : "/dashboard"}>Continue</Link> : state.status !== "loading" && <button className="db-primary-btn" onClick={() => { setState({ status: "loading", plan: null, error: "" }); setAttempt(value => value + 1); }}>Check again</button>}<Link className="db-outline-btn" to="/dashboard/upgrade">View subscription</Link></div>
    </GlassCard>
  </section>;
}
