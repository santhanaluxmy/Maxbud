import { useCallback, useEffect, useState } from "react";
import { api, money } from "../../../api/client";
import { getAuthSession } from "../../../services/authApi";
import GlassCard from "../../../components/common/GlassCard";
import Modal from "../../../components/common/Modal";

export default function HouseholdFinance({ family }) {
  const owner = family.role === "owner";
  const canEdit = family.can_edit_shared && family.can_add_shared;
  const me = getAuthSession()?.user?.id;
  const [data, setData] = useState(null), [error, setError] = useState("");
  const [modal, setModal] = useState(null), [form, setForm] = useState({});
  const [busy, setBusy] = useState(false), [revision, setRevision] = useState(0);
  const load = useCallback(() => Promise.all([api("/family/wallets"), api("/family/expenses"), api("/family/reimbursements"), api("/accounts"), api("/family/participants"), api("/dashboard?scope=family")]), []);
  useEffect(() => {
    if (!family.can_view_shared) return;
    let active = true;
    load().then(([wallets, expenses, debts, accounts, participants, report]) => { if (active) { setData({ wallets, expenses, debts, accounts: accounts.items || [], participants, report }); setError(""); } }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [family.can_view_shared, family.id, revision, load]);
  function open(kind, row = null) {
    setError(""); setModal({ kind, row });
    setForm({ name: row?.name || "", category: row?.category || "Food", amount: row?.remaining || "", account_id: "", description: "", txn_date: new Date().toLocaleDateString("en-CA"), due_date: new Date().toLocaleDateString("en-CA"), recurrence: "monthly", monthly_limit: row?.limit || "", split_mode: "none", splits: {}, request_id: crypto.randomUUID() });
  }
  async function run(fn) {
    setBusy(true); setError("");
    try { await fn(); setModal(null); setRevision(value => value + 1); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function submit(event) {
    event.preventDefault();
    const row = modal.row;
    await run(async () => {
      if (modal.kind === "wallet" || modal.kind === "walletEdit") return api(row ? `/family/wallets/${row.id}` : "/family/wallets", { method: row ? "PATCH" : "POST", data: { name: form.name } });
      if (modal.kind === "fund") return api(`/family/wallets/${row.id}/contribute`, { method: "POST", data: { account_id: Number(form.account_id), amount: form.amount, request_id: form.request_id } });
      if (modal.kind === "settle") return api(`/family/reimbursements/${row.share_id}/settle`, { method: "POST", data: { account_id: Number(form.account_id), amount: form.amount, request_id: form.request_id } });
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
    {error && !modal && <p className="family-feedback" role="alert">{error}</p>}
    {!canEdit && <p className="db-warning">Shared history is available. Shared editing requires an active eligible sponsor and owner-granted permission.</p>}
    {!data ? <p role="status">{error ? "Shared data could not load." : "Loading shared finances…"}</p> : <>
      <GlassCard title="Shared wallets" subtitle="Contributions are transfers, never new income." action={owner && <button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => open("wallet")}>New shared wallet</button>}>
        {!data.wallets.length && <p>No shared wallets yet.</p>}<div className="family-shared-goals">{data.wallets.map(wallet => <article className="family-shared-goal" key={wallet.id}><h3>{wallet.name}</h3><strong>{money(wallet.balance, "LKR")}</strong><p>{wallet.is_archived ? "Archived; balance and history preserved." : "Available shared wallet balance"}</p><div className="family-actions"><button className="db-primary-btn" disabled={!canEdit || busy || wallet.is_archived} onClick={() => open("fund", wallet)}>Contribute to wallet</button>{owner && <><button className="db-outline-btn" disabled={!canEdit || busy} onClick={() => open("walletEdit", wallet)}>Rename</button><button className="db-outline-btn" disabled={!canEdit || busy} onClick={() => run(() => api(`/family/wallets/${wallet.id}/archive`, { method: "POST", data: { archived: !wallet.is_archived } }))}>{wallet.is_archived ? "Restore" : "Archive"}</button></>}</div></article>)}</div>
      </GlassCard>
      <GlassCard title="Shared monthly budgets" subtitle="Separate from every member’s personal budgets." action={owner && <button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => open("budget")}>New shared budget</button>}>
        {!data.report.budgets.length && <p>No shared budgets yet.</p>}{data.report.budgets.map(budget => <article className="family-shared-goal" key={budget.id}><h3>{budget.category}</h3><p>{money(budget.spent)} of {money(budget.limit)} · {budget.status}</p><progress aria-label={`${budget.category} shared budget`} value={budget.used_percent} max="100"/>{owner && <div className="family-actions"><button className="db-outline-btn" disabled={!canEdit || busy} onClick={() => open("budget", budget)}>Edit budget</button><button className="db-outline-btn" disabled={!canEdit || busy} onClick={() => { if (window.confirm("Remove this shared budget definition? Expense history is preserved.")) run(() => api(`/family/budgets/${budget.id}`, { method: "DELETE" })); }}>Delete budget</button></div>}</article>)}
      </GlassCard>
      <GlassCard title="Shared expenses" subtitle="Only records deliberately entered as shared appear here." action={<button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => open("expense")}>Add shared expense</button>}>
        {!data.expenses.length && <p>No shared expenses yet.</p>}<div className="family-table-wrap"><table className="family-table"><thead><tr><th>Date</th><th>Shared note</th><th>Paid by</th><th>Source</th><th>Amount</th></tr></thead><tbody>{data.expenses.map(expense => <tr key={expense.id}><td>{expense.date}</td><td>{expense.description || expense.category}</td><td>{expense.payer_name}</td><td>{expense.source === "shared_wallet" ? "Household wallet" : "Member’s personal funds"}</td><td>{money(expense.amount)}</td></tr>)}</tbody></table></div>
      </GlassCard>
      <GlassCard title="Reimbursements" subtitle="Settlements move money between accounts; they do not duplicate the original expense.">
        {!data.debts.length && <p>No split expenses or reimbursement balances.</p>}{data.debts.map(debt => <article className="family-shared-goal" key={debt.share_id}><p><strong>{debt.debtor}</strong> owes <strong>{debt.creditor}</strong></p><p>Agreed share: {money(debt.amount)} · Settled: {money(debt.settled)} · Outstanding: {money(debt.remaining)}</p>{debt.debtor_id === me && Number(debt.remaining) > 0 && <button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => open("settle", debt)}>Record partial or full settlement</button>}</article>)}
      </GlassCard>
      <GlassCard title="Household bills" action={owner && <button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => open("bill")}>New household bill</button>}>
        {!data.report.upcoming_bills.length && <p>No upcoming shared bills.</p>}{data.report.upcoming_bills.map(bill => <article className="family-shared-goal" key={bill.id}><h3>{bill.name}</h3><p>{bill.due_date} · {money(bill.amount)}</p><button className="db-primary-btn" disabled={!canEdit || busy} onClick={() => run(() => api(`/family/bills/${bill.id}/pay`, { method: "POST", data: { due_date: bill.due_date } }))}>Mark household bill paid</button></article>)}
      </GlassCard>
    </>}
    {modal && <Modal title={{ wallet: "New shared wallet", walletEdit: "Rename shared wallet", fund: "Contribute to shared wallet", expense: "Record shared expense", budget: "Shared monthly budget", bill: "Household bill", settle: "Record reimbursement" }[modal.kind]} onClose={() => { if (!busy) setModal(null); }}><form className="family-form" onSubmit={submit}>
      {["wallet", "walletEdit", "bill"].includes(modal.kind) && <label>Name<input required maxLength={120} value={form.name} onChange={change("name")}/></label>}
      {["expense", "budget", "bill"].includes(modal.kind) && <label>Category<input required maxLength={60} value={form.category} onChange={change("category")}/></label>}
      {modal.kind === "budget" && <label>Monthly limit (LKR)<input required type="number" min="0" step="0.01" value={form.monthly_limit} onChange={change("monthly_limit")}/></label>}
      {["fund", "expense", "bill", "settle"].includes(modal.kind) && <><label>Amount (LKR)<input required type="number" min="0.01" step="0.01" value={form.amount} onChange={change("amount")}/></label><label>Payment account<select aria-label="Payment account" required value={form.account_id} onChange={change("account_id")}>{modal.kind === "bill" ? <><option value="">Choose shared wallet</option>{data?.wallets.filter(a => !a.is_archived).map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</> : accountOptions(modal.kind === "expense")}</select></label></>}
      {modal.kind === "expense" && <><p>Paid by you. Personal account details are not shown to other members.</p><label>Shared note<input maxLength={255} value={form.description} onChange={change("description")}/></label><label>Expense date<input required type="date" value={form.txn_date} onChange={change("txn_date")}/></label><label>Agreed split<select aria-label="Agreed split" value={form.split_mode} onChange={change("split_mode")}><option value="none">No personal reimbursement split</option><option value="equal">Equal split</option><option value="custom">Custom amounts</option><option value="percentage">Percentages</option></select></label>{form.split_mode !== "none" && <><p>Use a personal payment account for splits. Custom amounts must total the expense; percentages must total 100.</p>{data.participants.map(person => <div key={person.id}><label><input type="checkbox" checked={!!form.splits[person.id]?.selected} onChange={event => setForm({ ...form, splits: { ...form.splits, [person.id]: { amount: form.splits[person.id]?.amount || "", selected: event.target.checked } } })}/>{person.full_name}</label>{form.splits[person.id]?.selected && form.split_mode !== "equal" && <label>{person.full_name} {form.split_mode === "percentage" ? "percentage" : "amount"}<input required type="number" min="0" step={form.split_mode === "percentage" ? "0.0001" : "0.01"} value={form.splits[person.id].amount} onChange={event => setForm({ ...form, splits: { ...form.splits, [person.id]: { ...form.splits[person.id], amount: event.target.value } } })}/></label>}</div>)}</>}</>}
      {modal.kind === "bill" && <><label>Due date<input required type="date" value={form.due_date} onChange={change("due_date")}/></label><label>Repeat<select aria-label="Repeat" value={form.recurrence} onChange={change("recurrence")}>{["none", "weekly", "monthly", "yearly"].map(value => <option key={value}>{value}</option>)}</select></label></>}
      {error && <p role="alert">{error}</p>}<div className="family-actions"><button type="button" className="db-outline-btn" disabled={busy} onClick={() => setModal(null)}>Cancel</button><button className="db-primary-btn" disabled={busy}>{busy ? "Saving…" : "Save shared record"}</button></div>
    </form></Modal>}
  </>;
}
