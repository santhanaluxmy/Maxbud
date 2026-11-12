import Modal from "../../../components/common/Modal";
import Loading from "../../../components/common/Loading";
import EmptyState from "../../../components/common/EmptyState";
import GlassCard from "../../../components/common/GlassCard";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  ArrowUpRight, ArrowDownRight, ArrowRight, Plus, Wallet,   ReceiptText, PieChart, Target, LineChart, LogOut, Bell,   ScanLine, Sparkles, Users, TrendingUp, TrendingDown,
  Check, ShieldCheck, RefreshCw, Filter, Trash2, Pencil,
  PiggyBank, Landmark, Info, } from "lucide-react";
import { api, money, logout } from "../../../api/client";
import { getAuthSession } from "../../../services/authApi";
import { navigation, dashboardPath } from "../layout/navigation";
import "./Dashboard.css";

const tones = ["aqua", "pink", "cream"];
const today = () => new Date().toLocaleDateString("en-CA");
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function IconPill({ icon: Icon, tone = "aqua" }) { return <span className={`db-icon-pill ${tone}`}><Icon size={19}/></span>; }
function Progress({ value, className = "" }) { return <div className={`db-progress ${className}`}><span style={{ width: `${Math.min(100, Math.max(0, value))}%` }}/></div>; }
function MetricCard({ title, value, icon, tone, note, prominent = false }) {
  return <div className={`db-metric glass-card ${prominent ? "db-metric-prominent" : ""}`}>
    <div className="db-metric-top"><IconPill icon={icon} tone={tone}/><ArrowUpRight size={16} className="db-metric-corner"/></div>
    <span className="db-metric-label">{title}</span><strong>{value}</strong><small>{note}</small>
  </div>;
}

function TrendGraph({ rows, currency = "LKR" }) {
  const points = useMemo(() => {
    const data = Array.isArray(rows) ? rows.slice(-6) : [];
    const max = Math.max(1, ...data.flatMap((r) => [Number(r.income) || 0, Number(r.expenses) || 0]));
    const width = 640, height = 202, padX = 23, padY = 22;
    const calc = (key) => data.map((r, i) => ({ x: padX + (i / Math.max(1, data.length - 1)) * (width - padX * 2), y: height - padY - ((Number(r[key]) || 0) / max) * (height - padY * 2) }));
    return { data, income: calc("income"), expenses: calc("expenses"), max };
  }, [rows]);
  const path = (items) => items.map((p, i) => `${i ? "L" : "M"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  if (points.data.length === 0) return <EmptyState icon={LineChart} title="Chart appears here" text="Add a transaction to see monthly trends."/>;
  return <div className="db-trend">
    <div className="db-chart-legend"><span><i className="aqua-dot"/>Income</span><span><i className="pink-dot"/>Expenses</span></div>
    <svg viewBox="0 0 640 220" preserveAspectRatio="none" className="db-chart-svg" aria-label={`Six-month income and expense trend in ${currency}`} role="img">
      <defs><linearGradient id="db-chart-income" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#B1E5E6" stopOpacity=".52"/><stop offset="100%" stopColor="#B1E5E6" stopOpacity="0"/></linearGradient></defs>
      {[30, 75, 120, 165].map((y) => <line key={y} x1="0" x2="640" y1={y} y2={y} stroke="currentColor" strokeOpacity=".10" strokeDasharray="4 6"/>) }
      {points.income.length > 1 && <path d={`${path(points.income)} L ${points.income.at(-1).x} 202 L ${points.income[0].x} 202 Z`} fill="url(#db-chart-income)"/>}
      <path d={path(points.income)} fill="none" stroke="#76bdbe" strokeWidth="4.2" strokeLinecap="round" strokeLinejoin="round" className="db-draw-line"/>
      <path d={path(points.expenses)} fill="none" stroke="#ee929c" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" className="db-draw-line"/>
      {points.income.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r="4.5" fill="#B1E5E6" stroke="#fff" strokeWidth="2"/>) }
      {points.expenses.map((p, i) => <circle key={i} cx={p.x} cy={p.y} r="4" fill="#F7ADAD" stroke="#fff" strokeWidth="2"/>) }
    </svg>
    <div className="db-trend-labels">{points.data.map((r, i) => <span key={r.month || i}>{r.month ? MONTHS[Number(r.month.split("-")[1]) - 1] || r.month : "—"}</span>)}</div>
  </div>;
}
function Donut({ data, currency }) {
  const positive = data.filter((d) => Number(d.amount) > 0);
  const total = positive.reduce((sum, d) => sum + Number(d.amount), 0);
  if (total <= 0) return <EmptyState icon={PieChart} title="No expenses recorded" text="Add expenses to see the category breakdown."/>;
  const stops = positive.reduce((acc, d, i) => {
    const end = acc.angle + Number(d.amount) / total * 360;
    return { angle: end, stops: [...acc.stops, `${["#B1E5E6", "#F7ADAD", "#EEEAD7", "#88c8c9", "#e994a0", "#d7cfb1"][i % 6]} ${acc.angle}deg ${end}deg`] };
  }, { angle: 0, stops: [] }).stops;
  return <div className="db-donut-block"><div className="db-donut" style={{ background: `conic-gradient(${stops.join(",")})` }}><div><span>Total spent</span><strong>{money(total, currency)}</strong></div></div><div className="db-category-legend">{positive.slice(0, 6).map((item, i) => <div key={item.category}><i style={{ background: ["#B1E5E6", "#F7ADAD", "#EEEAD7", "#88c8c9", "#e994a0", "#d7cfb1"][i] }}/><span>{item.category}</span><strong>{Math.round(Number(item.amount) / total * 100)}%</strong></div>)}</div></div>;
}
function TransactionRows({ data, currency, onEdit, onDelete, compact = false }) {
  if (!data?.length) return <EmptyState icon={ReceiptText} title="No transactions yet" text="Your recorded income and expenses will appear here."/>;
  return <div className="db-table-wrap"><table className="db-table"><thead><tr><th>Transaction</th><th>Date</th><th>Category</th><th>Amount</th>{!compact && <th>Actions</th>}</tr></thead><tbody>{data.map((txn) => <tr key={txn.id}><td><div className="db-table-identity"><span className={`db-mini-icon ${txn.kind === "income" ? "aqua" : "pink"}`}>{txn.kind === "income" ? <ArrowDownRight size={17}/> : <ArrowUpRight size={17}/>}</span><span><b>{txn.description || (txn.kind === "income" ? "Income" : "Expense")}</b><small>{txn.kind === "income" ? "Money in" : "Money out"}</small></span></div></td><td>{txn.txn_date || txn.date || "—"}</td><td><span className="db-table-tag">{txn.category}</span></td><td className={txn.kind === "income" ? "db-income" : "db-expense"}>{txn.kind === "income" ? "+" : "−"}{money(txn.amount, currency)}</td>{!compact && <td><div className="db-row-actions"><button aria-label="Edit transaction" title="Edit" onClick={() => onEdit(txn)}><Pencil size={15}/></button><button aria-label="Delete transaction" title="Delete" onClick={() => onDelete(txn)}><Trash2 size={15}/></button></div></td>}</tr>)}</tbody></table></div>;
}
const freshTransaction = (kind, accountId) => ({ account_id: String(accountId || ""), kind, category: kind === "income" ? "Salary" : "Food", amount: "", description: "", txn_date: today() });


export default function Dashboard() {
  const navigate = useNavigate();
  const session = getAuthSession();
  const person = session?.user || {};
  const { pathname } = useLocation();
  const tab = navigation.find((item) => dashboardPath(item.id) === pathname.replace(/\/$/, ""))?.id || "overview";
  const [data, setData] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [featureError, setFeatureError] = useState("");
  const [modal, setModal] = useState(null);
  const [editId, setEditId] = useState(null);
  const [form, setForm] = useState(freshTransaction("expense", ""));
  const [accountForm, setAccountForm] = useState({ name: "", kind: "cash", opening_balance: "0" });
  const [budgetForm, setBudgetForm] = useState({ category: "Food", monthly_limit: "0" });
  const [goalForm, setGoalForm] = useState({ name: "", target_amount: "", saved_amount: "0", target_date: "" });
  const [contribution, setContribution] = useState({ id: null, amount: "" });
  const [saving, setSaving] = useState(false);
  const [filter, setFilter] = useState("all");

  async function refresh() {
    setLoading(true); setError(""); setFeatureError("");
    const [summary, txns, accs] = await Promise.allSettled([api("/dashboard"), api("/transactions?limit=100"), api("/accounts")]);
    if (summary.status === "fulfilled") setData(summary.value);
    else setError(summary.reason.message || "Dashboard could not load.");
    if (txns.status === "fulfilled") setTransactions(Array.isArray(txns.value) ? txns.value : []);
    else setFeatureError(txns.reason.message || "Transactions could not load.");
    if (accs.status === "fulfilled") setAccounts(Array.isArray(accs.value) ? accs.value : accs.value?.items || []);
    else setFeatureError((prev) => [prev, "Accounts require GET /accounts in your backend."].filter(Boolean).join(" "));
    setLoading(false);
  }
  useEffect(() => {
    let active = true;
    Promise.allSettled([api("/dashboard"), api("/transactions?limit=100"), api("/accounts")])
      .then(([summary, txns, accs]) => {
        if (!active) return;
        if (summary.status === "fulfilled") setData(summary.value);
        else setError(summary.reason.message || "Dashboard could not load.");
        if (txns.status === "fulfilled") setTransactions(Array.isArray(txns.value) ? txns.value : []);
        else setFeatureError(txns.reason.message || "Transactions could not load.");
        if (accs.status === "fulfilled") setAccounts(Array.isArray(accs.value) ? accs.value : accs.value?.items || []);
        else setFeatureError((prev) => [prev, "Accounts require GET /accounts in your backend."].filter(Boolean).join(" "));
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const currency = data?.currency || person.currency || "LKR";
  const budgets = Array.isArray(data?.budgets) ? data.budgets : [];
  const goals = Array.isArray(data?.goals) ? data.goals : [];
  const spending = Array.isArray(data?.spending_by_category) ? data.spending_by_category : [];
  const trend = Array.isArray(data?.six_month_trend) ? data.six_month_trend : [];
  const shownTransactions = filter === "all" ? transactions : transactions.filter((t) => t.kind === filter);
  const title = navigation.find((item) => item.id === tab)?.label || "Overview";
  const firstName = person.full_name?.trim().split(" ")[0] || "there";

  function goTab(name) { navigate(dashboardPath(name)); setError(""); }
  function startTransaction(kind = "expense", existing = null) {
    setEditId(existing?.id || null);
    setForm(existing ? { account_id: String(existing.account_id || accounts[0]?.id || ""), kind: existing.kind, category: existing.category || "Other", amount: String(existing.amount), description: existing.description || "", txn_date: existing.txn_date || existing.date || today() } : freshTransaction(kind, accounts[0]?.id));
    setModal("transaction"); setError("");
  }
  async function saveTransaction(e) {
    e.preventDefault(); setSaving(true); setError("");
    try {
      await api(editId ? `/transactions/${editId}` : "/transactions", { method: editId ? "PUT" : "POST", data: { ...form, account_id: Number(form.account_id), amount: String(form.amount) } });
      setModal(null); await refresh();
    } catch (err) { setError(err.message); } finally { setSaving(false); }
  }
  async function deleteTransaction(txn) {
    if (!window.confirm("Delete this transaction?")) return;
    try { await api(`/transactions/${txn.id}`, { method: "DELETE" }); await refresh(); }
    catch (err) { setError(err.message); }
  }
  async function submitSimple(e, path, payload) {
    e.preventDefault(); setSaving(true); setError("");
    try { await api(path, { method: "POST", data: payload }); setModal(null); await refresh(); }
    catch (err) { setError(err.message); } finally { setSaving(false); }
  }
  function signOut() { logout(); navigate("/login", { replace: true }); }

  const actionButton = (label, action, icon = Plus) => { const Icon = icon; return <button type="button" className="db-primary-btn" onClick={action}><Icon size={17}/>{label}</button>; };
  const tabsWithButtons = ["overview", "transactions"].includes(tab);

  return <>
      <main className="db-main">
        <div className="db-page-intro"><div><span className="db-page-subtitle">{tab === "overview" ? "YOUR FINANCIAL OVERVIEW" : "MAXBUD / YOUR WORKSPACE"}</span><h1>{tab === "overview" ? `Welcome back, ${firstName} 👋` : title}</h1><p>{tab === "overview" ? "Here's your money at a glance. You're in control." : "A clearer view of your money, one step at a time."}</p></div>{tabsWithButtons && <div className="db-intro-actions"><button type="button" className="db-outline-btn" onClick={refresh}><RefreshCw size={17}/>Refresh</button>{actionButton("Add transaction", () => startTransaction("expense"))}</div>}</div>
        {error && <div className="db-error" role="alert"><Info size={19}/>{error}</div>}
        {featureError && <div className="db-warning" role="status"><Info size={18}/>{featureError}</div>}
        {loading && !data ? <Loading/> : null}

        {tab === "overview" && <>
          <div className="db-hero glass-card"><div className="db-hero-glow"/><div className="db-hero-copy"><div className="db-hero-kicker"><span className="db-live-dot"/> YOUR MONEY, SIMPLIFIED</div><p>Estimated safe to spend</p><strong>{data?.safe_to_spend_estimate != null ? money(data.safe_to_spend_estimate, currency) : "Not available yet"}</strong><small>{data?.safe_to_spend_note || "Add your income, expenses and budgets to understand what is available. Future bills are not included."}</small><div className="db-hero-actions"><button onClick={() => startTransaction("expense")}><Plus size={17}/> Add expense</button><button onClick={() => goTab("reports")}>Explore insights <ArrowRight size={17}/></button></div></div><div className="db-hero-visual"><div className="db-orbit orbit-one"/><div className="db-orbit orbit-two"/><div className="db-hero-credit glass-card"><span>MONTHLY CASH FLOW <TrendingUp size={18}/></span><strong>{money((Number(data?.monthly_income) || 0) - (Number(data?.monthly_expenses) || 0), currency)}</strong><div className="db-hero-bars">{[37, 62, 49, 78, 58, 87, 67, 94, 73].map((height, i) => <i key={i} style={{ height: `${height}%` }}/>)}</div></div></div></div>
          <div className="db-metric-grid"><MetricCard title="Total balance" value={money(data?.total_balance, currency)} icon={Wallet} tone="aqua" note="Across tracked accounts" prominent/><MetricCard title="Monthly income" value={money(data?.monthly_income, currency)} icon={ArrowDownRight} tone="aqua" note="Income recorded this month"/><MetricCard title="Monthly expenses" value={money(data?.monthly_expenses, currency)} icon={ArrowUpRight} tone="pink" note="Expenses recorded this month"/><MetricCard title="Remaining budget" value={money(data?.remaining_budget, currency)} icon={PieChart} tone="cream" note="Category budgets this month"/></div>
          <div className="db-analytics-grid"><GlassCard title="Income & expenses" subtitle="Your last six months" action={<button className="db-small-link" onClick={() => goTab("reports")}>View report <ArrowRight size={15}/></button>}><TrendGraph rows={trend} currency={currency}/></GlassCard><GlassCard title="Spending breakdown" subtitle="Where your money went this month"><Donut data={spending} currency={currency}/></GlassCard></div>
          <div className="db-bottom-grid"><GlassCard title="Recent transactions" subtitle="Your latest activity" action={<button className="db-small-link" onClick={() => goTab("transactions")}>See all <ArrowRight size={15}/></button>}><TransactionRows data={transactions.slice(0, 5)} currency={currency} compact/></GlassCard><GlassCard title="Savings goals" subtitle="Little steps, big dreams" action={<button className="db-small-link" onClick={() => goTab("goals")}>See goals <ArrowRight size={15}/></button>}>{goals.length ? goals.slice(0, 3).map((goal) => { const percent = Number(goal.target) > 0 ? Number(goal.saved) / Number(goal.target) * 100 : 0; return <div className="db-goal-line" key={goal.id}><div><strong>{goal.name}</strong><span>{Math.round(percent)}%</span></div><Progress value={percent}/><small>{money(goal.saved, currency)} of {money(goal.target, currency)}</small></div>; }) : <EmptyState icon={Target} title="Your goals start here" text="Set a goal to watch your savings progress."/>}</GlassCard></div>
        </>}

        {tab === "transactions" && <GlassCard title="Transaction history" subtitle={`${shownTransactions.length} recorded transactions`} action={actionButton("Add transaction", () => startTransaction("expense"))}><div className="db-filterbar"><Filter size={17}/>{["all", "income", "expense"].map((item) => <button className={filter === item ? "active" : ""} onClick={() => setFilter(item)} key={item}>{item === "all" ? "All" : item === "income" ? "Income" : "Expenses"}</button>)}</div><TransactionRows data={shownTransactions} currency={currency} onEdit={(txn) => startTransaction("expense", txn)} onDelete={deleteTransaction}/></GlassCard>}

        {tab === "accounts" && <><div className="db-section-actions">{actionButton("Add account", () => { setAccountForm({ name: "", kind: "cash", opening_balance: "0" }); setModal("account"); })}</div><div className="db-accounts-grid">{accounts.map((account, i) => <article className="db-account-card glass-card" key={account.id}><div className="db-account-top"><IconPill icon={account.kind === "bank" ? Landmark : Wallet} tone={tones[i % 3]}/><span>{account.kind.toUpperCase()}</span></div><h3>{account.name}</h3><p>Current tracked balance</p><strong>{money(account.current_balance ?? account.balance ?? account.opening_balance, account.currency || currency)}</strong><small>Account #{account.id} · Used for recording transactions</small></article>)}</div>{accounts.length === 0 && <GlassCard><EmptyState icon={Wallet} title="No accounts available" text="Add a cash or bank account to begin recording transactions."/></GlassCard>}<p className="db-note"><ShieldCheck size={16}/> MaxBud tracks accounts manually; it does not connect to banks or move actual money.</p></>}

        {tab === "budgets" && <><div className="db-section-actions">{actionButton("New budget", () => { setBudgetForm({ category: "", monthly_limit: "0" }); setModal("budget"); })}</div><div className="db-budget-grid">{budgets.map((budget, i) => { const limit = Number(budget.limit) || 0, spent = Number(budget.spent) || 0, percent = limit > 0 ? spent / limit * 100 : 0; return <article className="db-budget-card glass-card" key={budget.category}><div className="db-budget-head"><IconPill icon={PieChart} tone={tones[i % 3]}/><span className={percent > 100 ? "db-pill pink" : "db-pill"}>{percent > 100 ? "Over budget" : "On track"}</span></div><h3>{budget.category}</h3><div className="db-budget-values"><strong>{money(spent, currency)}</strong><span>of {money(limit, currency)}</span></div><Progress value={percent}/><p>{Math.round(percent)}% used · {money(limit - spent, currency)} remaining</p></article>; })}</div>{budgets.length === 0 && <GlassCard><EmptyState icon={PieChart} title="No budgets yet" text="Create a budget to set a monthly spending limit."/></GlassCard>}</>}

        {tab === "goals" && <><div className="db-section-actions">{actionButton("New goal", () => { setGoalForm({ name: "", target_amount: "", saved_amount: "0", target_date: "" }); setModal("goal"); })}</div><div className="db-goals-grid">{goals.map((goal, i) => { const percent = Number(goal.target) ? Number(goal.saved) / Number(goal.target) * 100 : 0; return <article className="db-goal-card glass-card" key={goal.id}><div className="db-goal-card-top"><IconPill icon={Target} tone={tones[i % 3]}/><span className="db-pill">{goal.status}</span></div><h3>{goal.name}</h3><p>Saved so far</p><strong>{money(goal.saved, currency)}</strong><span className="db-target">Target: {money(goal.target, currency)}</span><Progress value={percent}/><div className="db-goal-foot"><span>{Math.round(percent)}% complete</span><button onClick={() => { setContribution({ id: goal.id, amount: "" }); setModal("contribute"); }}>Contribute <Plus size={15}/></button></div></article>; })}</div>{goals.length === 0 && <GlassCard><EmptyState icon={Target} title="No active goals yet" text="Create a goal to start tracking your savings."/></GlassCard>}<p className="db-note"><Info size={16}/> Contributions update your goal allocation. They do not transfer money between actual accounts.</p></>}

        {tab === "reports" && <><div className="db-metric-grid"><MetricCard title="Total balance" value={money(data?.total_balance, currency)} icon={Wallet} tone="aqua" note="Current tracked balance"/><MetricCard title="Monthly income" value={money(data?.monthly_income, currency)} icon={TrendingUp} tone="aqua" note="Recorded income"/><MetricCard title="Monthly expenses" value={money(data?.monthly_expenses, currency)} icon={TrendingDown} tone="pink" note="Recorded expenses"/><MetricCard title="Allocated savings" value={money(data?.total_savings_allocated, currency)} icon={PiggyBank} tone="cream" note="Savings-goal allocations"/></div><div className="db-analytics-grid"><GlassCard title="Six-month overview" subtitle="Income versus expenses"><TrendGraph rows={trend} currency={currency}/></GlassCard><GlassCard title="Expense categories" subtitle="Current month"><Donut data={spending} currency={currency}/></GlassCard></div><p className="db-note"><Info size={16}/> Advanced forecasts, PDF/Excel exports and AI insights are planned Premium features, not enabled in this version.</p></>}

        {["scan", "advisor", "family"].includes(tab) && <GlassCard className="db-feature-preview"><div className="db-preview-icon">{tab === "family" ? <Users size={34}/> : tab === "scan" ? <ScanLine size={34}/> : <Sparkles size={34}/>}</div><span className="db-pill">{tab === "family" ? "Planned Premium feature" : "Coming soon"}</span><h2>{tab === "scan" ? "AI receipt scanning" : tab === "advisor" ? "Your AI money coach" : "Budget together as a family"}</h2><p>{tab === "scan" ? "Scan a bill, review AI-extracted details and confirm before saving. Planned: 5 scans/month on Free and up to 100 on Premium." : tab === "advisor" ? "Ask questions about your budget with privacy-conscious summaries. Planned: 10 messages/month on Free and up to 200 on Premium." : "Premium will allow an owner to invite members and share a unified family budget. The current build is personal budgeting only."}</p><button className="db-primary-btn" onClick={() => goTab("overview")}><ArrowRight size={17}/> Back to Overview</button></GlassCard>}

        {tab === "reminders" && <GlassCard title="Reminders"><EmptyState icon={Bell} title="Reminders are coming soon" text="The current backend does not expose a reminders API."/></GlassCard>}

        {tab === "settings" && <GlassCard title="Account information" subtitle="Your current MaxBud profile"><div className="db-settings-row"><span>Full name</span><strong>{person.full_name || "—"}</strong></div><div className="db-settings-row"><span>Email</span><strong>{person.email || "—"}</strong></div><div className="db-settings-row"><span>Currency</span><strong>{currency}</strong></div><div className="db-settings-row"><span>Current plan</span><strong>Free (premium plans not activated)</strong></div><div className="db-settings-row"><span>Security</span><strong>JWT authenticated session</strong></div><button className="db-outline-btn" onClick={signOut}><LogOut size={17}/> Sign out</button></GlassCard>}
      </main>

    {modal === "transaction" && <Modal title={editId ? "Edit transaction" : "Add transaction"} onClose={() => { setModal(null); setError(""); }}><form className="db-modal-form" onSubmit={saveTransaction}>
      <div className="db-kind-picker">{["expense", "income"].map((kind) => <button type="button" className={form.kind === kind ? "active" : ""} onClick={() => setForm((prev) => ({ ...prev, kind, category: kind === "income" ? "Salary" : "Food" }))} key={kind}>{kind === "expense" ? <ArrowUpRight size={16}/> : <ArrowDownRight size={16}/>} {kind === "expense" ? "Expense" : "Income"}</button>)}</div>
      {accounts.length === 0 && <p className="db-warning">Create an account in My Accounts before recording a transaction.</p>}
      <label>Account<select required value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })}><option value="">Select account</option>{accounts.map((account) => <option key={account.id} value={account.id}>{account.name} · {account.currency || currency}</option>)}</select></label>
      <div className="db-two-fields"><label>Amount ({currency})<input required min="0.01" step="0.01" type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} placeholder="2500.00" /></label><label>Date<input required type="date" value={form.txn_date} onChange={(e) => setForm({ ...form, txn_date: e.target.value })}/></label></div>
      <label>Category<input required maxLength={60} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} list="db-categories"/><datalist id="db-categories">{["Food", "Transport", "Shopping", "Health", "Entertainment", "Other", "Salary", "Freelance"].map((c) => <option key={c} value={c}/>)}</datalist></label>
      <label>Note (optional)<input maxLength={255} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="What was this for?"/></label>
      {error && <p className="db-error" role="alert">{error}</p>}
      <button className="db-primary-btn db-modal-submit" type="submit" disabled={saving || !accounts.length}>{saving ? "Saving…" : editId ? "Save changes" : "Save transaction"}<Check size={17}/></button>
    </form></Modal>}

    {modal === "account" && <Modal title="Add a tracked account" onClose={() => setModal(null)}><form className="db-modal-form" onSubmit={(e) => submitSimple(e, "/accounts", { ...accountForm, opening_balance: String(accountForm.opening_balance) })}><label>Account name<input required maxLength={120} value={accountForm.name} onChange={(e) => setAccountForm({ ...accountForm, name: e.target.value })} placeholder="My cash wallet"/></label><label>Account type<select value={accountForm.kind} onChange={(e) => setAccountForm({ ...accountForm, kind: e.target.value })}><option value="cash">Cash</option><option value="bank">Bank</option><option value="wallet">Wallet</option><option value="other">Other</option></select></label><label>Opening balance ({currency})<input required min="0" step="0.01" type="number" value={accountForm.opening_balance} onChange={(e) => setAccountForm({ ...accountForm, opening_balance: e.target.value })}/></label>{error && <p className="db-error">{error}</p>}<button className="db-primary-btn db-modal-submit" type="submit" disabled={saving}>{saving ? "Saving…" : "Create account"}</button></form></Modal>}

    {modal === "budget" && <Modal title="Create a monthly budget" onClose={() => setModal(null)}><form className="db-modal-form" onSubmit={(e) => submitSimple(e, "/budgets", { ...budgetForm, monthly_limit: String(budgetForm.monthly_limit) })}><label>Category<input required maxLength={60} value={budgetForm.category} onChange={(e) => setBudgetForm({ ...budgetForm, category: e.target.value })} list="db-budget-categories"/><datalist id="db-budget-categories">{["Food", "Transport", "Shopping", "Health", "Entertainment", "Other"].map((v) => <option key={v} value={v}/>)}</datalist></label><label>Monthly limit ({currency})<input type="number" required min="0" step="0.01" value={budgetForm.monthly_limit} onChange={(e) => setBudgetForm({ ...budgetForm, monthly_limit: e.target.value })}/></label>{error && <p className="db-error">{error}</p>}<button className="db-primary-btn db-modal-submit" disabled={saving}>{saving ? "Saving…" : "Create budget"}</button></form></Modal>}

    {modal === "goal" && <Modal title="Create a savings goal" onClose={() => setModal(null)}><form className="db-modal-form" onSubmit={(e) => { const { target_date, ...fields } = goalForm; submitSimple(e, "/goals", { ...fields, ...(target_date ? { target_date } : {}) }); }}><label>Goal name<input maxLength={120} required value={goalForm.name} onChange={(e) => setGoalForm({ ...goalForm, name: e.target.value })} placeholder="Emergency fund"/></label><div className="db-two-fields"><label>Target amount ({currency})<input required min="0.01" step="0.01" type="number" value={goalForm.target_amount} onChange={(e) => setGoalForm({ ...goalForm, target_amount: e.target.value })}/></label><label>Already saved<input min="0" step="0.01" type="number" value={goalForm.saved_amount} onChange={(e) => setGoalForm({ ...goalForm, saved_amount: e.target.value })}/></label></div><label>Target date (optional)<input type="date" value={goalForm.target_date} onChange={(e) => setGoalForm({ ...goalForm, target_date: e.target.value })}/></label>{error && <p className="db-error">{error}</p>}<button className="db-primary-btn db-modal-submit" disabled={saving}>{saving ? "Saving…" : "Create goal"}</button></form></Modal>}

    {modal === "contribute" && <Modal title="Add to savings goal" onClose={() => setModal(null)}><form className="db-modal-form" onSubmit={(e) => submitSimple(e, `/goals/${contribution.id}/contribute`, { amount: String(contribution.amount) })}><label>Contribution amount ({currency})<input required type="number" min="0.01" step="0.01" value={contribution.amount} onChange={(e) => setContribution({ ...contribution, amount: e.target.value })}/></label><p className="db-note">This tracks your goal allocation; it does not move money from an account.</p>{error && <p className="db-error">{error}</p>}<button className="db-primary-btn db-modal-submit" disabled={saving}>{saving ? "Saving…" : "Add contribution"}</button></form></Modal>}
  </>;
}