import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Plus, Trash2, Wallet, ShieldCheck, CheckCircle2, UserRound, Landmark, PiggyBank, Target } from "lucide-react";
import { api } from "../api/client";
import { getAuthSession } from "../services/authApi";
import logo from "../assets/images/maxbud-logo.png";
import "./onboarding.css";

const steps = ["About you", "Income", "Accounts", "Budgets", "Goals"];
const paths = ["about-you", "income", "accounts", "budgets", "goals"];
const categories = ["Food", "Transport", "Shopping", "Health", "Entertainment", "Other"];
const icons = [UserRound, Wallet, Landmark, PiggyBank, Target];

const blankIncome = () => ({ name: "Salary", amount: "", frequency: "monthly" });
const blankAccount = () => ({ name: "Cash Wallet", kind: "cash", opening_balance: "0" });
const blankGoal = () => ({ name: "", target_amount: "", saved_amount: "0", target_date: "" });

export default function OnboardingPage() {
  const navigate = useNavigate();
  const session = getAuthSession();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [form, setForm] = useState({
    full_name: session?.user?.full_name || "",
    currency: "LKR",
    sources: [blankIncome()],
    accounts: [blankAccount()],
    budgets: categories.map((category) => ({ category, monthly_limit: "0" })),
    goals: [blankGoal()],
  });

  useEffect(() => {
    let active = true;
    api("/onboarding/status").then((status) => {
      if (!active) return;
      if (status.onboarding_completed) {
        for (const storage of [localStorage, sessionStorage]) {
          const saved = storage.getItem("maxbud_auth");
          if (saved) { const parsed = JSON.parse(saved); parsed.onboarding_completed = true; storage.setItem("maxbud_auth", JSON.stringify(parsed)); }
        }
        navigate("/dashboard", { replace: true });
      } else setStep(Math.max(1, Math.min(5, status.current_step || 1)));
    }).catch((err) => { if (active) setError(err.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [navigate]);

  const update = (key, value) => setForm((prev) => ({ ...prev, [key]: value }));
  const updateItem = (key, index, name, value) => setForm((prev) => ({ ...prev, [key]: prev[key].map((item, i) => i === index ? { ...item, [name]: value } : item) }));
  const addItem = (key, create) => update(key, [...form[key], create()]);
  const removeItem = (key, index) => update(key, form[key].filter((_, i) => i !== index));

  async function next(event) {
    event.preventDefault();
    setError(""); setSaving(true);
    let payload;
    if (step === 1) payload = { full_name: form.full_name.trim(), currency: form.currency };
    if (step === 2) payload = { sources: form.sources.map((item) => ({ ...item, amount: String(item.amount) })) };
    if (step === 3) payload = { accounts: form.accounts.map((item) => ({ ...item, opening_balance: String(item.opening_balance) })) };
    if (step === 4) payload = { budgets: form.budgets.map((item) => ({ ...item, monthly_limit: String(item.monthly_limit) })) };
    if (step === 5) payload = { goals: form.goals.filter((item) => item.name.trim()).map(({ target_date, ...item }) => ({ ...item, ...(target_date ? { target_date } : {}) })) };
    try {
      await api(`/onboarding/${paths[step - 1]}`, { method: "POST", data: payload });
      if (step === 5) {
        for (const store of [localStorage, sessionStorage]) {
          const saved = store.getItem("maxbud_auth");
          if (saved) { const parsed = JSON.parse(saved); parsed.onboarding_completed = true; store.setItem("maxbud_auth", JSON.stringify(parsed)); }
        }
        navigate("/dashboard", { replace: true });
      } else setStep((current) => current + 1);
    } catch (err) {
      setError(err.message);
      if (err.status === 409) {
        try { const current = await api("/onboarding/status"); if (current.current_step) setStep(current.current_step); } catch { /* keep original error */ }
      }
    } finally { setSaving(false); }
  }

  if (loading) return <div className="ob-center">Loading your financial setup…</div>;
  const ActiveIcon = icons[step - 1];
  return (
    <div className="ob-page">
      <div className="ob-shell">
        <aside className="ob-aside glass-ui">
          <img src={logo} alt="MaxBud" className="ob-logo" />
          <div className="ob-aside-art"><PiggyBank size={100} strokeWidth={1.1} /><span className="ob-bubble bubble-one"/><span className="ob-bubble bubble-two"/></div>
          <h2>Money management, made simple.</h2>
          <p>Five short steps to make MaxBud yours. Your information stays with your account.</p>
          <div className="ob-side-progress">{steps.map((item, i) => <div key={item} className={`ob-side-step ${i + 1 === step ? "is-active" : ""} ${i + 1 < step ? "is-done" : ""}`}><span>{i + 1 < step ? <CheckCircle2 size={16} /> : String(i + 1).padStart(2, "0")}</span>{item}</div>)}</div>
        </aside>
        <main className="ob-main glass-ui">
          <div className="ob-topline"><span>ACCOUNT SETUP</span><strong>Step {step} of 5</strong></div>
          <div className="ob-progress"><span style={{ width: `${(step / 5) * 100}%` }}/></div>
          <div className="ob-title-icon"><ActiveIcon size={24} /></div>
          <h1>{["Tell us about yourself", "Your income sources", "Where do you keep money?", "Set monthly spending limits", "Make a savings goal"][step - 1]}</h1>
          <p className="ob-subtitle">{["Let's personalize your dashboard.", "Add salary and any other earnings.", "These are tracked accounts. No bank connection is needed.", "Adjust category budgets to suit your lifestyle.", "Choose something worth saving for. You can add more later."][step - 1]}</p>
          <form onSubmit={next} className="ob-form">
            {step === 1 && <div className="ob-form-grid"><label>Full name<input required minLength={2} maxLength={150} value={form.full_name} onChange={(e) => update("full_name", e.target.value)} /></label><label>Currency<select value={form.currency} onChange={(e) => update("currency", e.target.value)}><option value="LKR">LKR — Sri Lankan Rupee</option><option value="USD">USD — US Dollar</option><option value="EUR">EUR — Euro</option></select></label></div>}
            {step === 2 && <>{form.sources.map((item, i) => <div className="ob-inline-row" key={i}><label>Income name<input required value={item.name} maxLength={120} onChange={(e) => updateItem("sources", i, "name", e.target.value)} /></label><label>Amount<input required type="number" min="0.01" step="0.01" value={item.amount} onChange={(e) => updateItem("sources", i, "amount", e.target.value)} placeholder="80000" /></label><label>Frequency<select value={item.frequency} onChange={(e) => updateItem("sources", i, "frequency", e.target.value)}><option value="monthly">Monthly</option><option value="weekly">Weekly</option><option value="yearly">Yearly</option></select></label>{form.sources.length > 1 && <button className="ob-remove" type="button" aria-label="Remove income" onClick={() => removeItem("sources", i)}><Trash2 size={17}/></button>}</div>)}<button type="button" className="ob-text-button" onClick={() => addItem("sources", blankIncome)}><Plus size={16}/> Add income source</button></>}
            {step === 3 && <>{form.accounts.map((item, i) => <div className="ob-inline-row" key={i}><label>Account name<input required value={item.name} onChange={(e) => updateItem("accounts", i, "name", e.target.value)} /></label><label>Type<select value={item.kind} onChange={(e) => updateItem("accounts", i, "kind", e.target.value)}><option value="cash">Cash</option><option value="bank">Bank</option><option value="wallet">Wallet</option><option value="other">Other</option></select></label><label>Opening balance<input required type="number" min="0" step="0.01" value={item.opening_balance} onChange={(e) => updateItem("accounts", i, "opening_balance", e.target.value)} /></label>{form.accounts.length > 1 && <button type="button" className="ob-remove" aria-label="Remove account" onClick={() => removeItem("accounts", i)}><Trash2 size={17}/></button>}</div>)}<button type="button" className="ob-text-button" onClick={() => addItem("accounts", blankAccount)}><Plus size={16}/> Add account</button></>}
            {step === 4 && <div className="ob-budget-grid">{form.budgets.map((item, i) => <label key={item.category}>{item.category}<input type="number" min="0" step="0.01" value={item.monthly_limit} onChange={(e) => updateItem("budgets", i, "monthly_limit", e.target.value)}/></label>)}</div>}
            {step === 5 && <>{form.goals.map((item, i) => <div className="ob-goal-fields" key={i}><label>Goal name<input value={item.name} onChange={(e) => updateItem("goals", i, "name", e.target.value)} placeholder="New laptop" /></label><label>Target amount<input type="number" min="0.01" step="0.01" value={item.target_amount} onChange={(e) => updateItem("goals", i, "target_amount", e.target.value)} placeholder="150000" /></label><label>Already saved<input type="number" min="0" step="0.01" value={item.saved_amount} onChange={(e) => updateItem("goals", i, "saved_amount", e.target.value)} /></label><label>Target date (optional)<input type="date" value={item.target_date} onChange={(e) => updateItem("goals", i, "target_date", e.target.value)} /></label>{form.goals.length > 1 && <button type="button" className="ob-remove" onClick={() => removeItem("goals", i)}><Trash2 size={17} /></button>}</div>)}<button type="button" className="ob-text-button" onClick={() => addItem("goals", blankGoal)}><Plus size={16}/> Add goal</button><p className="ob-hint">You can leave the goal name blank to finish without a goal.</p></>}
            {error && <p role="alert" className="ob-error">{error}</p>}
            <div className="ob-actions"><span className="ob-safe"><ShieldCheck size={16}/> Saved to your MaxBud account</span><button type="submit" className="ob-next" disabled={saving}>{saving ? "Saving…" : step === 5 ? "Open my dashboard" : "Save & Continue"}<ArrowRight size={18}/></button></div>
          </form>
        </main>
      </div>
    </div>
  );
}