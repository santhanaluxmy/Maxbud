import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowDownToLine, ArrowUpFromLine, ArrowRight, BarChart3, Bus, Coins,
  Ellipsis, GraduationCap, HeartPulse, House, Info, List, PieChart as PieIcon,
  RefreshCw, ShoppingBag, Target, Utensils, Wallet, Users,
} from "lucide-react";
import {
  Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { api } from "../../../api/client";
import EmptyState from "../../../components/common/EmptyState";
import Loading from "../../../components/common/Loading";
import piggyBank from "../../../assets/images/maxbud2.png";
import "./DashboardOverview.css";

const palette = ["#96d9d3", "#f7b7b7", "#e8dfbf", "#bfe7df", "#f5cdcb", "#78bab5"];
const number = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) ? Number(value) : null;
const titleCase = (value) => String(value || "Other").replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
const formatAmount = (value) => number(value)?.toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? "Unavailable";
const formatMoney = (value, currency) => number(value) === null ? "Unavailable" : `${currency} ${formatAmount(value)}`;
function formatDate(value) {
  if (!value) return "—";
  const date = new Date(`${value}T12:00:00`);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}
function categoryIcon(category) {
  const name = String(category || "").toLowerCase();
  if (/food|grocer|dining/.test(name)) return Utensils;
  if (/transport|fuel/.test(name)) return Bus;
  if (/rent|bill/.test(name)) return House;
  if (/shop/.test(name)) return ShoppingBag;
  if (/health/.test(name)) return HeartPulse;
  return Ellipsis;
}
function Panel({ icon: Icon, title, subtitle, action, className = "", children }) {
  return <section className={`ov-panel ${className}`} aria-label={title}>
    <header className="ov-panel-heading"><Icon size={25} strokeWidth={1.7} aria-hidden="true"/><div><h2>{title}</h2><p>{subtitle}</p></div>{action}</header>
    {children}
  </section>;
}
function Metric({ title, value, icon: Icon, tone, note, children, help }) {
  return <section className={`ov-metric ov-${tone}`} aria-label={title}>
    <span className="ov-metric-icon"><Icon size={27} strokeWidth={1.7}/></span>
    <div className="ov-metric-body"><span className="ov-metric-label">{title}{help && <span className="ov-help" tabIndex={0} aria-label={help} title={help}><Info size={14}/></span>}</span><strong>{value}</strong><small>{note}</small>{children}</div>
  </section>;
}
function CashFlow({ rows, currency, loading, available, shared = false }) {
  const data = rows.slice(-6).map((row) => ({
    month: row.month,
    label: /^\d{4}-\d{2}$/.test(row.month) ? new Date(`${row.month}-15T12:00:00`).toLocaleDateString("en-GB", { month: "short" }) : row.month,
    income: number(row.income), expenses: number(row.expenses),
  }));
  const hasActivity = data.some((row) => row.income > 0 || row.expenses > 0);
  return <Panel icon={BarChart3} title={shared ? "Shared Funding vs Spending" : "Income vs Expenses"} subtitle="Your cash flow over the last 6 months." action={<span className="ov-range">Last 6 Months</span>}>
    {loading ? <Loading>Loading your cash flow…</Loading> : !available ? <EmptyState icon={BarChart3} title="Cash flow unavailable" text="Retry loading your dashboard to see your chart."/> : !hasActivity ? <EmptyState icon={BarChart3} title="Your cash flow starts here" text="Record income and expenses to see your six-month overview."/> : <>
      <div className="ov-legend"><span><i style={{ background: palette[0] }}/>Income</span><span><i style={{ background: palette[1] }}/>Expenses</span></div>
      <div className="ov-bar-chart" role="img" aria-label={`Monthly income versus expenses in ${currency}. ${data.map((r) => `${r.label}: income ${formatAmount(r.income)}, expenses ${formatAmount(r.expenses)}`).join("; ")}`}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <BarChart data={data} margin={{ top: 8, right: 0, left: 0, bottom: 0 }} barGap={5} accessibilityLayer>
            <CartesianGrid stroke="#d9ddcf" strokeDasharray="3 3" vertical={false}/>
            <XAxis dataKey="label" axisLine={{ stroke: "#d2d8ce" }} tickLine={false} tick={{ fill: "#244d50", fontSize: 11 }} dy={5}/>
            <YAxis width={67} axisLine={false} tickLine={false} tick={{ fill: "#426264", fontSize: 10 }} tickFormatter={(value) => `${currency} ${Math.abs(value) >= 1000 ? `${+(value / 1000).toFixed(1)}K` : value}`}/>
            <Tooltip cursor={{ fill: "rgba(177,229,230,.16)" }} formatter={(value, name) => [formatMoney(value, currency), name]} contentStyle={{ borderRadius: 12, border: "1px solid #b1e5e6", background: "#fcfaf3", fontSize: 12 }}/>
            <Bar dataKey="income" name={shared ? "Wallet funding (transfers)" : "Income"} fill={palette[0]} radius={[4, 4, 0, 0]} maxBarSize={34}/>
            <Bar dataKey="expenses" name={shared ? "Shared spending" : "Expenses"} fill={palette[1]} radius={[4, 4, 0, 0]} maxBarSize={34}/>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>}
  </Panel>;
}
function Spending({ rows, currency, loading, available }) {
  const data = rows.filter((row) => number(row.amount) > 0).map((row) => ({ ...row, amount: number(row.amount) }));
  const total = data.reduce((sum, row) => sum + row.amount, 0);
  return <Panel icon={PieIcon} title="Spending by Category" subtitle="This month's expenses breakdown.">
    {loading ? <Loading>Loading your categories…</Loading> : !available ? <EmptyState icon={PieIcon} title="Category spending unavailable" text="Retry loading your dashboard to see your spending."/> : total <= 0 ? <EmptyState icon={PieIcon} title="No expenses this month" text="Your recorded expenses will appear here by category."/> : <div className="ov-spending">
      <div className="ov-donut" role="img" aria-label={`Total category spending ${formatMoney(total, currency)}`}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <PieChart accessibilityLayer><Pie data={data} dataKey="amount" nameKey="category" innerRadius="65%" outerRadius="96%" startAngle={90} endAngle={-270} stroke="none" paddingAngle={0}>{data.map((row, index) => <Cell key={row.category} fill={palette[index % palette.length]}/>)}</Pie><Tooltip formatter={(value) => formatMoney(value, currency)} contentStyle={{ borderRadius: 12, border: "1px solid #b1e5e6", background: "#fcfaf3", fontSize: 12 }}/></PieChart>
        </ResponsiveContainer>
        <div className="ov-donut-center"><span>{currency}</span><strong>{formatAmount(total)}</strong><small>Total</small></div>
      </div>
      <ul className="ov-categories">{data.map((row, index) => { const Icon = categoryIcon(row.category); return <li key={row.category} title={formatMoney(row.amount, currency)}><Icon size={19} style={{ color: ["#448e88", "#b96770", "#8d8061"][index % 3] }}/><span>{titleCase(row.category)}</span><strong>{Math.round(row.amount / total * 100)}%</strong></li>; })}</ul>
    </div>}
  </Panel>;
}
function RecentTransactions({ rows, accounts, currency, loading, available }) {
  return <Panel className="ov-transactions" icon={List} title="Recent Transactions" subtitle="Your latest income and expenses." action={<Link className="ov-link" to="/dashboard/transactions">View All <ArrowRight size={15}/></Link>}>
    {loading ? <Loading>Loading your recent transactions…</Loading> : !available ? <EmptyState title="Recent transactions unavailable" text="Retry loading your dashboard to see your activity."/> : !rows.length ? <EmptyState title="No transactions yet" text="Record your first income or expense to get started."/> : <div className="ov-table-scroll"><table className="ov-table"><thead><tr><th>Date</th><th>Merchant / Note</th><th>Category</th><th>Account</th><th>Amount</th></tr></thead><tbody>{rows.slice(0, 5).map((row) => {
      const incoming = row.kind === "income";
      const Icon = incoming ? Wallet : categoryIcon(row.category);
      return <tr key={row.id}><td>{formatDate(row.date || row.txn_date)}</td><td><span className="ov-merchant"><span className={`ov-txn-icon ${incoming ? "ov-incoming" : "ov-outgoing"}`}><Icon size={16}/></span><span title={row.description}>{row.description || (incoming ? "Income" : "Expense")}</span></span></td><td><span className={`ov-category ${incoming ? "ov-incoming" : "ov-outgoing"}`}>{titleCase(row.category)}</span></td><td>{accounts.find((account) => account.id === row.account_id)?.name || `Account #${row.account_id}`}</td><td className={incoming ? "ov-income" : "ov-expense"}>{incoming ? "+" : "−"} {formatMoney(row.amount, currency)}</td></tr>;
    })}</tbody></table></div>}
  </Panel>;
}
function GoalProgress({ goals, currency, loading, available }) {
  const [selectedId, setSelectedId] = useState("");
  const goal = goals.find((item) => String(item.id) === selectedId) || goals[0];
  const target = number(goal?.target), saved = number(goal?.saved);
  const percent = target > 0 && saved !== null ? Math.max(0, Math.min(100, saved / target * 100)) : null;
  return <Panel icon={Target} title="Savings Goal Progress" subtitle="Keep going! Every contribution counts." action={<Link className="ov-link" to="/dashboard/goals">View Goals <ArrowRight size={15}/></Link>}>
    {loading ? <Loading>Loading your savings goals…</Loading> : !available ? <EmptyState icon={Target} title="Savings goals unavailable" text="Retry loading your dashboard to see your goals."/> : !goal ? <EmptyState icon={Target} title="Something worth saving for" text="Create a savings goal to follow your progress here."/> : <>
      {goals.length > 1 && <label className="ov-goal-select">Goal<select value={String(goal.id)} onChange={(event) => setSelectedId(event.target.value)}>{goals.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      <article className="ov-goal"><div className="ov-goal-top"><span className="ov-goal-icon"><GraduationCap size={32} strokeWidth={1.5}/></span><div><h3>{goal.name}</h3><p>Target: <strong>{formatMoney(target, currency)}</strong></p></div>{percent !== null && <strong className="ov-goal-percent">{Math.round(percent)}%</strong>}</div>
        {percent !== null && <div className="ov-progress" role="progressbar" aria-label={`${goal.name} savings progress`} aria-valuenow={Math.round(percent)} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${percent}%` }}/></div>}
        <div className="ov-goal-values"><div><span>Saved</span><strong>{formatMoney(saved, currency)}</strong></div><div><span>Remaining</span><strong>{formatMoney(target !== null && saved !== null ? Math.max(0, target - saved) : null, currency)}</strong></div></div>
      </article>
    </>}
  </Panel>;
}

export default function DashboardOverview({ person }) {
  const [billState, setBillState] = useState({ rows: [], loading: true, error: "" });
  const [data, setData] = useState(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const scope = searchParams.get("scope") === "family" ? "family" : "me";
  const setScope = value => setSearchParams(previous => { const next = new URLSearchParams(previous); next.set("scope", value); return next; }, { replace: true });
  const [canViewFamily, setCanViewFamily] = useState(false);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [accountError, setAccountError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError(null);
      setAccountError("");
      const [summary, accountList] = await Promise.allSettled([api(`/dashboard?scope=${scope}`, { signal: controller.signal }), api("/accounts", { signal: controller.signal })]);
      if (controller.signal.aborted) return;
      if (summary.status === "fulfilled" && summary.value && typeof summary.value === "object") { setData(summary.value); setCanViewFamily(summary.value.can_view_family === true); }
      else { setData(null); setError(summary.reason || new Error("The dashboard returned an empty response. Please retry.")); }
      if (accountList.status === "fulfilled") setAccounts(Array.isArray(accountList.value) ? accountList.value : accountList.value?.items || []);
      else { setAccounts([]); setAccountError(accountList.reason?.status === 401 ? "Your session has expired. Sign in again to load account names." : `Account names could not load. ${accountList.reason?.message || "Please retry."}`); }
      setLoading(false);
    }
    load();
    return () => controller.abort();
  }, [revision, scope]);

  useEffect(() => {
    if (scope !== "me") return;
    const controller = new AbortController();
    api("/reminders", { signal: controller.signal }).then(rows => { if (!controller.signal.aborted) setBillState({ rows, loading: false, error: "" }); }).catch(error => { if (!controller.signal.aborted) setBillState({ rows: [], loading: false, error: error.message }); });
    return () => controller.abort();
  }, [scope, revision]);

  const firstName = person?.full_name?.trim().split(" ")[0] || "there";
  const currency = data?.currency || person?.currency || "LKR";
  const rows = (key) => Array.isArray(data?.[key]) ? data[key] : [];
  const safe = number(data?.safe_to_spend_estimate), balance = number(data?.total_balance);
  const safePercent = safe !== null && balance > 0 ? Math.max(0, Math.min(100, safe / balance * 100)) : null;
  const available = !loading && data !== null;
  const value = (key) => loading ? "—" : formatMoney(data?.[key], currency);

  return <main className="ov-main" aria-busy={loading}>
    <section className="ov-welcome"><div><span className="ov-eyebrow">YOUR FINANCIAL OVERVIEW</span><h1>Welcome back, {firstName} <span className="ov-wave" role="img" aria-label="hello">👋</span></h1><p>Track, plan and grow your money with MaxBud.</p></div><img className="ov-piggy" src={piggyBank} alt="Piggy bank with coins and a growing savings chart"/><button className="ov-refresh" type="button" onClick={() => setRevision((value) => value + 1)} disabled={loading} aria-label="Refresh dashboard" title="Refresh dashboard"><RefreshCw size={17}/></button></section>
    {canViewFamily && <label className="ov-goal-select">Dashboard scope<select aria-label="Dashboard scope" value={scope} onChange={(event) => { setData(null); setLoading(true); setScope(event.target.value); }}><option value="me">My Finances</option><option value="family">Family Finances</option></select></label>}
    {scope === "family" && <p role="status">Only explicitly shared household records are shown. Private salaries, accounts and transactions remain private.</p>}
    {error && <div className="ov-notice ov-notice-error" role="alert"><Info size={19}/><div><strong>{error.status === 401 ? "Your session has expired." : "We couldn't load your dashboard."}</strong><p>{error.message}</p></div>{error.status === 401 ? <Link to="/login">Sign in again <ArrowRight size={16}/></Link> : <button type="button" onClick={() => setRevision((value) => value + 1)}>Retry</button>}</div>}
    {accountError && !error && <div className="ov-notice" role="status"><Info size={18}/><span>{accountError} Account IDs are shown in the meantime.</span>{accountError.includes("expired") && <Link to="/login">Sign in again</Link>}</div>}
    <div className="ov-metrics">
      <Metric title="Safe to Spend" value={value("safe_to_spend_estimate")} icon={Coins} tone="mint" help={data?.safe_to_spend_note || "An estimate after reserving remaining budgets. Upcoming bills and loans are excluded."} note={safePercent !== null && available ? `${Math.round(safePercent)}% of tracked balance` : "Estimated after budget reserves"}>
        {safePercent !== null && available && <div className="ov-safe-progress" role="progressbar" aria-label="Safe to spend as a share of tracked balance" aria-valuenow={Math.round(safePercent)} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${safePercent}%` }}/></div>}
      </Metric>

      <Metric title={scope === "family" ? "Wallet Funding (Transfers)" : "Income (This Month)"} value={value(scope === "family" ? "monthly_wallet_funding" : "monthly_income")} icon={ArrowDownToLine} tone="cream" note={loading ? "Loading recorded income…" : "Actual recorded income"}/>
      <Metric title={scope === "family" ? "Shared Spending (This Month)" : "Expenses (This Month)"} value={value("monthly_expenses")} icon={ArrowUpFromLine} tone="pink" note={loading ? "Loading recorded expenses…" : "Actual recorded expenses"}/>
      <Metric title={scope === "family" ? "Shared Wallet Balance" : "Total Balance"} value={value("total_balance")} icon={Wallet} tone="aqua" note={loading ? "Loading your balance…" : "Across your tracked accounts"}/>

    </div>
    {scope === "me" && <div className="ov-grid ov-commitments">
      <Panel icon={PieIcon} title="Budget Progress" subtitle="Keep your monthly plan in view." action={<Link className="ov-link" to="/dashboard/budgets">View budgets <ArrowRight size={15}/></Link>}>
        {loading ? <Loading>Loading budgets…</Loading> : !available ? <p>Budget progress is unavailable.</p> : !rows("budgets").length ? <EmptyState icon={PieIcon} title="Give your spending a plan" text="Create a category budget to follow your progress here."/> : <div className="ov-budget-list">{rows("budgets").slice(0,4).map(budget => <div key={budget.category}><div><strong>{titleCase(budget.category)}</strong><span>{formatMoney(budget.spent,currency)} <small>of {formatMoney(budget.limit,currency)}</small></span></div><progress aria-label={`${budget.category} budget used`} value={Math.max(0,number(budget.used_percent) || 0)} max={100} className={budget.used_percent >= 80 ? "ov-budget-warning" : ""}/></div>)}</div>}
      </Panel>
      <Panel icon={House} title="Upcoming Bills" subtitle="Your next payments, including anything overdue." action={<Link className="ov-link" to="/dashboard/reminders">View bills <ArrowRight size={15}/></Link>}>
        {billState.loading ? <Loading>Loading payments…</Loading> : billState.error ? <p role="status">{billState.error}</p> : !billState.rows.length ? <EmptyState icon={House} title="Nothing due right now" text="Add a reminder to keep upcoming payments in sight."/> : <ul className="ov-bill-list">{billState.rows.slice(0,4).map(bill => <li key={bill.id}><span className="db-icon-pill"><House size={16}/></span><div><strong>{bill.name}</strong><small>{formatDate(bill.due_date)}</small></div><strong>{formatMoney(bill.amount,currency)}</strong></li>)}</ul>}
      </Panel>
    </div>}
    <div className="ov-grid ov-chart-grid"><CashFlow shared={scope === "family"} rows={scope === "family" ? rows("six_month_trend").map(row => ({ ...row, income: row.wallet_funding || "0.00" })) : rows("six_month_trend")} currency={currency} loading={loading} available={available}/><Spending rows={rows("spending_by_category")} currency={currency} loading={loading} available={available}/></div>
    {scope === "me" ? <div className="ov-grid ov-bottom-grid"><RecentTransactions rows={rows("recent_transactions")} accounts={accounts} currency={currency} loading={loading} available={available}/><GoalProgress goals={rows("goals")} currency={currency} loading={loading} available={available}/></div> : <Panel icon={PieIcon} title="Family budget overview" subtitle="Combined monthly budgets across active family members.">
      {loading ? <Loading>Loading family budgets…</Loading> : !available ? <p>Family budgets unavailable.</p> : !rows("budgets").length ? <p>No family budgets yet.</p> : <div className="ov-table-scroll"><table className="ov-table"><thead><tr><th>Category</th><th>Budget</th><th>Spent</th><th>Remaining</th></tr></thead><tbody>{rows("budgets").map((budget) => <tr key={budget.category}><td>{titleCase(budget.category)}</td><td>{formatMoney(budget.limit, currency)}</td><td>{formatMoney(budget.spent, currency)}</td><td>{formatMoney(budget.remaining, currency)}</td></tr>)}</tbody></table></div>}
    </Panel>}
    {scope === "family" && <>
      <Panel icon={Users} title="Household contribution summary" subtitle="Wallet funding is a transfer, not income. Private salaries are not included.">
        {!available ? <p>{loading ? "Loading shared report…" : "Shared report unavailable."}</p> : <><p className="db-note">{data.family_population}</p><p>Wallet net cash flow this month: {formatMoney(data.monthly_net_cash_flow,currency)}. Personal payments and reimbursements are tracked separately.</p><div className="ov-table-scroll"><table className="ov-table"><thead><tr><th>Member</th><th>Wallet funding (month)</th><th>Shared expenses paid (month)</th><th>Goal allocations (all time)</th></tr></thead><tbody>{rows("member_summaries").map(member => <tr key={member.user_id}><td><span className={`family-member-dot tone-${member.user_id % 3}`}/>{member.full_name}</td><td>{formatMoney(member.wallet_funding,currency)}</td><td>{formatMoney(member.expenses,currency)}</td><td>{formatMoney(member.shared_goal_contributions,currency)}</td></tr>)}</tbody><tfoot><tr><th>Household</th><td>{formatMoney(data.monthly_wallet_funding,currency)}</td><td>{formatMoney(data.monthly_expenses,currency)}</td><td>{formatMoney(data.total_savings_allocated,currency)}</td></tr></tfoot></table></div></>}
      </Panel>
      <div className="ov-grid family-report-grid">
        <Panel icon={Target} title="Shared savings" subtitle="Contribution history is retained when membership changes." action={<Link className="ov-link" to="/dashboard/family">Manage goals <ArrowRight size={15}/></Link>}>
          {!rows("shared_goals").length ? <p>No shared savings goals yet.</p> : <ul className="ov-bill-list">{rows("shared_goals").map(goal => <li key={goal.id}><div><strong>{goal.name}</strong><small>{goal.status} · {Math.round(goal.progress)}% complete</small></div><strong>{formatMoney(goal.saved_amount,currency)}</strong></li>)}</ul>}
        </Panel>
        <Panel icon={House} title="Household bills" subtitle="Combined payments by category and due date; personal bill details remain private.">
          {!rows("upcoming_bills").length ? <p>No upcoming household bills recorded.</p> : <ul className="ov-bill-list">{rows("upcoming_bills").map(bill => <li key={`${bill.category}-${bill.due_date}`}><div><strong>{titleCase(bill.category)}</strong><small>{formatDate(bill.due_date)} · {bill.bill_count} payment{bill.bill_count === 1 ? "" : "s"}</small></div><strong>{formatMoney(bill.amount,currency)}</strong></li>)}</ul>}
        </Panel>
      </div>
      <Panel icon={Users} title="Outstanding reimbursements" subtitle="These balances are debts between members, not new expenses.">{!rows("reimbursements").length ? <p>No reimbursements recorded.</p> : <ul className="ov-bill-list">{rows("reimbursements").map(debt => <li key={debt.share_id}><div><strong>{debt.debtor} owes {debt.creditor}</strong><small>Expense #{debt.expense_id}</small></div><strong>{formatMoney(debt.remaining,currency)}</strong></li>)}</ul>}</Panel>
    </>}
  </main>;
}
