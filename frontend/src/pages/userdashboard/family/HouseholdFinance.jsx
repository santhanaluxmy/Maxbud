import { useCallback, useEffect, useRef, useState } from "react";
import { api, money } from "../../../api/client";
import { getAuthSession } from "../../../services/authApi";
import GlassCard from "../../../components/common/GlassCard";
import Modal from "../../../components/common/Modal";

export default function HouseholdFinance({ family, section = "overview" }) {
  const owner = family.role === "owner";
  const canEdit = family.can_edit_shared && family.can_add_shared;
  const me = getAuthSession()?.user?.id;
  const [data, setData] = useState(null), [error, setError] = useState("");
  const [modal, setModal] = useState(null), [form, setForm] = useState({});
  const [busy, setBusy] = useState(false), [revision, setRevision] = useState(0);
  const [notice, setNotice] = useState("");
  const saving = useRef(false);
  const load = useCallback(async () => {
    const endpoints = { activity: "/family/activity", wallets: "/family/wallets", expenses: "/family/expenses", debts: "/family/reimbursements", accounts: "/accounts", participants: "/family/participants", report: "/dashboard?scope=family", income: "/family/income" };
    const needed = { activity: ["activity"], overview: ["report"], reports: ["report"], budgets: ["report"], wallets: ["wallets", "accounts"], expenses: ["wallets", "accounts", "participants", "expenses"], income: ["wallets", "income"], reimbursements: ["debts", "accounts"], bills: ["wallets", "report"] }[section] || [];
    const result = { activity: [], wallets: [], expenses: [], debts: [], accounts: [], participants: [], income: [], report: {} };
    await Promise.all(needed.map(async key => { const value = await api(endpoints[key]); result[key] = key === "accounts" ? value.items || [] : value; }));
    return result;
  }, [section]);
  useEffect(() => {
    if (!family.can_view_shared) return;
    let active = true;
    load().then(value => { if (active) { setData(value); setError(""); } }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [family.can_view_shared, family.id, revision, load]);
  function open(kind, row = null) {
    setError(""); setNotice(""); setModal({ kind, row });
    setForm({ name: row?.name || "", category: row?.category || (kind === "income" ? "Household income" : "Food"), amount: row?.remaining || "", account_id: "", description: "", txn_date: new Date().toLocaleDateString("en-CA"), due_date: new Date().toLocaleDateString("en-CA"), recurrence: "monthly", monthly_limit: row?.limit || "", split_mode: "none", splits: {}, request_id: crypto.randomUUID() });
  }
  async function run(fn) {
    if (saving.current) return;
    saving.current = true; setBusy(true); setError(""); setNotice("");
    try { await fn(); setModal(null); setNotice("Shared record saved. Updated balances and history are shown below."); setRevision(value => value + 1); } catch (e) { setError(e.message); } finally { saving.current = false; setBusy(false); }
  }
  async function submit(event) {
    event.preventDefault();
    if (modal.kind === "expense" && form.split_mode !== "none" && !Object.values(form.splits).some(value => value.selected)) {
      setError("Choose at least one split participant, or select no personal reimbursement split.");
      return;
    }
    const row = modal.row;
    await run(async () => {
      if (modal.kind === "wallet" || modal.kind === "walletEdit") return api(row ? `/family/wallets/${row.id}` : "/family/wallets", { method: row ? "PATCH" : "POST", data: { name: form.name } });
      if (modal.kind === "fund") return api(`/family/wallets/${row.id}/contribute`, { method: "POST", data: { account_id: Number(form.account_id), amount: form.amount, request_id: form.request_id } });
      if (modal.kind === "settle") return api(`/family/reimbursements/${row.share_id}/settle`, { method: "POST", data: { account_id: Number(form.account_id), amount: form.amount, request_id: form.request_id } });
      if (modal.kind === "income") return api("/family/income", { method: "POST", data: { account_id: Number(form.account_id), category: form.category, amount: form.amount, description: form.description, txn_date: form.txn_date, request_id: form.request_id } });
      if (modal.kind === "budget") return api(row ? `/family/budgets/${row.id}` : "/family/budgets", { method: row ? "PUT" : "POST", data: { category: form.category, monthly_limit: form.monthly_limit } });
      if (modal.kind === "bill") return api("/family/bills", { method: "POST", data: { name: form.name, category: form.category, amount: form.amount, account_id: Number(form.account_id), due_date: form.due_date, recurrence: form.recurrence } });
      const splits = form.split_mode === "none" ? [] : Object.entries(form.splits).filter(([, value]) => value.selected).map(([id, value]) => ({ user_id: Number(id), value: form.split_mode === "equal" ? null : value.amount }));
      return api("/family/expenses", { method: "POST", data: { account_id: Number(form.account_id), category: form.category, amount: form.amount, description: form.description, txn_date: form.txn_date, split_mode: form.split_mode === "none" ? "equal" : form.split_mode, splits, request_id: form.request_id } });
    });
  }
  const change = key => event => setForm({ ...form, [key]: event.target.value });
  const accountOptions = (shared = false) => <><option value="">Choose payment account</option>{data?.accounts.filter(a => !a.is_archived && a.currency === "LKR").map(a => <option key={a.id} value={a.id}>Personal: {a.name}</option>)}{shared && data?.wallets.filter(a => !a.is_archived).map(a => <option key={a.id} value={a.id}>Shared: {a.name}</option>)}</>;
  if (!family.can_view_shared) return <GlassCard title="Shared household finances"><p>The owner has not granted your account access to shared reports. Your personal records remain private.</p></GlassCard>;
  return <>
    {notice && <p className="family-feedback" role="status">{notice}</p>}
    {error && !modal && <p className="family-feedback" role="alert">{error} <button className="db-outline-btn" onClick={() => setRevision(value => value + 1)}>Retry shared data</button></p>}
    {!canEdit && <p className="db-warning">Shared history is available. Shared editing requires an active Family Pack, no more than five household users, and permission from the owner.</p>}
    {!data ? <p role="status">{error ? "Shared data could not load." : "Loading shared finances…"}</p> : <>
      {["overview", "reports"].includes(section) && <GlassCard title="Household this month" subtitle="Only explicitly shared income and expenses; private accounts stay private.">
        <dl className="family-overview">{[["Shared income", data.report.monthly_income], ["Shared expenses", data.report.monthly_expenses], ["Income minus expenses", data.report.monthly_net_cash_flow], ["Shared wallet balance", data.report.total_balance]].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{money(value)}</dd></div>)}</dl>
        <p className="db-note">Personal contributions to wallets are transfers, not household income.</p>
      </GlassCard>}
      {section === "wallets" && <GlassCard title="Shared wallets" subtitle="Contributions are transfers, never new income." action={owner && <button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => open("wallet")}>New shared wallet</button>}>
        {!data.wallets.length && <p>{owner ? "Create a shared wallet before recording common income or wallet contributions." : "Ask the owner to create a shared wallet. You can then contribute from your own personal account."}</p>}{!owner && <p className="db-note">The owner creates and manages wallets. You can contribute when shared editing is enabled.</p>}<div className="family-shared-goals">{data.wallets.map(wallet => <article className="family-shared-goal" key={wallet.id}><h3>{wallet.name}</h3><strong>{money(wallet.balance, "LKR")}</strong><p>{wallet.is_archived ? "Archived; balance and history preserved." : "Available shared wallet balance"}</p><div className="family-actions"><button className="db-primary-btn" disabled={!canEdit || busy || wallet.is_archived} onClick={() => open("fund", wallet)}>Contribute to wallet</button>{owner && <details><summary>Manage wallet</summary><div className="family-actions"><button className="db-outline-btn" disabled={!canEdit || busy} onClick={() => open("walletEdit", wallet)}>Rename</button><button className="db-outline-btn" disabled={!canEdit || busy} onClick={() => run(() => api(`/family/wallets/${wallet.id}/archive`, { method: "POST", data: { archived: !wallet.is_archived } }))}>{wallet.is_archived ? "Restore" : "Archive"}</button></div></details>}</div></article>)}</div>
      </GlassCard>}
      {section === "budgets" && <GlassCard title="Shared monthly budgets" subtitle="Separate from every member’s personal budgets." action={owner && <button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => open("budget")}>New shared budget</button>}>
        {!data.report.budgets.length && <p>{owner ? "Create a category limit to track household spending." : "The owner has not created a shared budget yet. Ask them to set the household limits."}</p>}{!owner && <p className="db-note">The owner manages budget limits. Your shared expenses update spending automatically.</p>}{data.report.budgets.map(budget => <article className="family-shared-goal" key={budget.id}><h3>{budget.category}</h3><p>{money(budget.spent)} of {money(budget.limit)} · {budget.status}</p><p>Remaining: {money(budget.remaining)}</p><progress aria-label={`${budget.category} shared budget`} value={budget.used_percent} max="100"/>{owner && <details><summary>Manage budget limit</summary><div className="family-actions"><button className="db-outline-btn" disabled={!canEdit || busy} onClick={() => open("budget", budget)}>Edit budget</button><button className="db-outline-btn" disabled={!canEdit || busy} onClick={() => { if (window.confirm("Remove this shared budget definition? Expense history is preserved.")) run(() => api(`/family/budgets/${budget.id}`, { method: "DELETE" })); }}>Delete budget</button></div></details>}</article>)}
      </GlassCard>}
      {section === "income" && <GlassCard title="Shared income" subtitle="Record common earnings in a household wallet, separately from private salaries." action={<button className="db-primary-btn" disabled={!canEdit || busy || !data.wallets.some(wallet => !wallet.is_archived)} onClick={() => open("income")}>Add shared income</button>}>
        {!data.income.length && <p>No shared income yet.</p>}{!data.wallets.some(wallet => !wallet.is_archived) && <p className="db-note">{owner ? "Create or restore a shared wallet in Shared wallets to receive income." : "Ask the owner to create or restore a shared wallet to receive income."}</p>}
        <div className="family-table-wrap"><table className="family-table"><thead><tr><th>Date</th><th>Shared note</th><th>Recorded by</th><th>Amount</th></tr></thead><tbody>{data.income.map(income => <tr key={income.id}><td>{income.date}</td><td>{income.description || income.category}</td><td>{income.recorded_by_name}</td><td>{money(income.amount)}</td></tr>)}</tbody></table></div>
      </GlassCard>}
      {section === "expenses" && <GlassCard title="Shared expenses" subtitle="Only records deliberately entered as shared appear here." action={<button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => open("expense")}>Add shared expense</button>}>
        {!data.expenses.length && <p>No shared expenses yet.</p>}<div className="family-table-wrap"><table className="family-table"><thead><tr><th>Date</th><th>Shared note</th><th>Paid by</th><th>Source</th><th>Amount</th></tr></thead><tbody>{data.expenses.map(expense => <tr key={expense.id}><td>{expense.date}</td><td>{expense.description || expense.category}</td><td>{expense.payer_name}</td><td>{expense.source === "shared_wallet" ? "Household wallet" : "Member’s personal funds"}</td><td>{money(expense.amount)}</td></tr>)}</tbody></table></div>
      </GlassCard>}
      {section === "reimbursements" && <GlassCard title="Reimbursements" subtitle="Settlements move money between accounts; they do not duplicate the original expense.">
        {!data.debts.length && <p>No split expenses or reimbursement balances.</p>}{data.debts.map(debt => <article className="family-shared-goal" key={debt.share_id}><p>Expense #{debt.expense_id}</p><p><strong>{debt.debtor}</strong> owes <strong>{debt.creditor}</strong></p><p>Agreed share: {money(debt.amount)} · Settled: {money(debt.settled)} · Outstanding: {money(debt.remaining)}</p>{debt.debtor_id === me && Number(debt.remaining) > 0 && <button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => open("settle", debt)}>Record partial or full settlement</button>}</article>)}
      </GlassCard>}
      {section === "bills" && <GlassCard title="Household bills" subtitle="The owner defines bills; authorized members can record payment from the assigned shared wallet." action={owner && <button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => open("bill")}>New household bill</button>}>
        {!data.report.upcoming_bills.length && <p>No upcoming shared bills.</p>}{data.report.upcoming_bills.map(bill => <article className="family-shared-goal" key={bill.id}><h3>{bill.name}</h3><p>{bill.due_date} · {money(bill.amount)}</p><button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => run(() => api(`/family/bills/${bill.id}/pay`, { method: "POST", data: { due_date: bill.due_date } }))}>Mark household bill paid</button></article>)}
      </GlassCard>}
      {section === "activity" && <GlassCard title="Shared financial activity" subtitle="Latest 100 recorded shared events. Transfers and goal allocations are not new income or expenses.">
        {!data.activity.length ? <p>No shared activity yet. Recorded household transactions and contributions will appear here.</p> : <div className="family-table-wrap"><table className="family-table"><thead><tr><th>Date</th><th>Member</th><th>Activity</th><th>Details</th><th>Amount</th></tr></thead><tbody>{data.activity.map(row => <tr key={row.key}><td>{row.date.slice(0,10)}</td><td>{row.member}</td><td>{row.kind}</td><td>{row.description}</td><td>{money(row.amount)}</td></tr>)}</tbody></table></div>}
      </GlassCard>}
      {section === "reports" && <>
        <GlassCard title="Member contributions" subtitle="Wallet funding and reimbursements are transfers. Goal contributions are allocations, not new income.">
          <p>Wallet funding this month: {money(data.report.monthly_wallet_funding)}. Wallet net movement: {money(data.report.monthly_wallet_net_movement)}.</p>
          <div className="family-table-wrap"><table className="family-table"><thead><tr><th>Member</th><th>Shared income (month)</th><th>Expenses paid (month)</th><th>Wallet funding (month)</th><th>Goal allocations (all time)</th></tr></thead><tbody>{data.report.member_summaries.map(member => <tr key={member.user_id}><td>{member.full_name}</td><td>{money(member.income)}</td><td>{money(member.expenses)}</td><td>{money(member.wallet_funding)}</td><td>{money(member.shared_goal_contributions)}</td></tr>)}</tbody></table></div>
        </GlassCard>
        <GlassCard title="Shared income and spending trend" subtitle="Monthly shared totals only. Private salaries and account balances never appear here.">
          <div className="family-table-wrap"><table className="family-table"><thead><tr><th>Month</th><th>Income</th><th>Expenses</th><th>Wallet funding (transfer)</th></tr></thead><tbody>{data.report.six_month_trend.map(row => <tr key={row.month}><td>{row.month}</td><td>{money(row.income)}</td><td>{money(row.expenses)}</td><td>{money(row.wallet_funding)}</td></tr>)}</tbody></table></div>
          <p className="db-note">A dated shared running-balance ledger is not yet available. Use Shared income, Shared expenses and Reimbursements for the available details.</p>
        </GlassCard>
      </>}
    </>}
    {modal && <Modal title={{ wallet: "New shared wallet", walletEdit: "Rename shared wallet", fund: "Contribute to shared wallet", expense: "Record shared expense", income: "Record shared income", budget: "Shared monthly budget", bill: "Household bill", settle: "Record reimbursement" }[modal.kind]} onClose={() => { if (!busy) setModal(null); }}><form className="family-form" onSubmit={submit}>
      {["wallet", "walletEdit", "bill"].includes(modal.kind) && <label>Name<input required maxLength={120} value={form.name} onChange={change("name")}/></label>}
      {["expense", "income", "budget", "bill"].includes(modal.kind) && <label>Category<input required maxLength={60} value={form.category} onChange={change("category")}/></label>}
      {modal.kind === "budget" && <label>Monthly limit (LKR)<input required type="number" min="0" step="0.01" value={form.monthly_limit} onChange={change("monthly_limit")}/></label>}
      {["fund", "expense", "income", "bill", "settle"].includes(modal.kind) && <><label>Amount (LKR)<input required type="number" min="0.01" max={modal.kind === "settle" ? modal.row.remaining : undefined} step="0.01" value={form.amount} onChange={change("amount")}/></label><label>{modal.kind === "income" ? "Income wallet" : "Payment account"}<select aria-label={modal.kind === "income" ? "Income wallet" : "Payment account"} required value={form.account_id} onChange={change("account_id")}>{["bill", "income"].includes(modal.kind) ? <><option value="">Choose shared wallet</option>{data?.wallets.filter(a => !a.is_archived).map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</> : accountOptions(modal.kind === "expense" && form.split_mode === "none")}</select></label></>}
      {modal.kind === "income" && <><label>Shared note<input maxLength={255} value={form.description} onChange={change("description")}/></label><label>Income date<input required type="date" value={form.txn_date} onChange={change("txn_date")}/></label></>}
      {modal.kind === "expense" && <><p>Paid by you. Personal account details are not shown to other members.</p><label>Shared note<input maxLength={255} value={form.description} onChange={change("description")}/></label><label>Expense date<input required type="date" value={form.txn_date} onChange={change("txn_date")}/></label><label>Agreed split<select aria-label="Agreed split" value={form.split_mode} onChange={event => setForm({ ...form, split_mode: event.target.value, account_id: "" })}><option value="none">No personal reimbursement split</option><option value="equal">Equal split</option><option value="custom">Custom amounts</option><option value="percentage">Percentages</option></select></label>{form.split_mode !== "none" && <><p>Use a personal payment account for splits. Custom amounts must total the expense; percentages must total 100.</p>{data.participants.map(person => <div key={person.id}><label><input type="checkbox" checked={!!form.splits[person.id]?.selected} onChange={event => setForm({ ...form, splits: { ...form.splits, [person.id]: { amount: form.splits[person.id]?.amount || "", selected: event.target.checked } } })}/>{person.full_name}</label>{form.splits[person.id]?.selected && form.split_mode !== "equal" && <label>{person.full_name} {form.split_mode === "percentage" ? "percentage" : "amount"}<input required type="number" min="0" step={form.split_mode === "percentage" ? "0.0001" : "0.01"} value={form.splits[person.id].amount} onChange={event => setForm({ ...form, splits: { ...form.splits, [person.id]: { ...form.splits[person.id], amount: event.target.value } } })}/></label>}</div>)}</>}</>}
      {modal.kind === "bill" && <><label>Due date<input required type="date" value={form.due_date} onChange={change("due_date")}/></label><label>Repeat<select aria-label="Repeat" value={form.recurrence} onChange={change("recurrence")}>{["none", "weekly", "monthly", "yearly"].map(value => <option key={value}>{value}</option>)}</select></label></>}
      {["fund", "settle"].includes(modal.kind) && !data.accounts.some(a => !a.is_archived && a.currency === "LKR") && <p role="status">Create an active LKR account in Personal Finance before funding or reimbursing.</p>}
      {error && <p role="alert">{error}</p>}<div className="family-actions"><button type="button" className="db-outline-btn" disabled={busy} onClick={() => setModal(null)}>Cancel</button><button className="db-primary-btn" disabled={busy}>{busy ? "Saving…" : "Save shared record"}</button></div>
    </form></Modal>}
  </>;
}
