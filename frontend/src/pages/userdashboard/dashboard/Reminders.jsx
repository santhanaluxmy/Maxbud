import { useEffect, useState } from "react";
import { api, money } from "../../../api/client";
import GlassCard from "../../../components/common/GlassCard";
import Modal from "../../../components/common/Modal";

const fresh = () => ({ name: "", category: "Rent", amount: "", account_id: "", due_date: new Date().toLocaleDateString("en-CA"), recurrence: "monthly" });
export default function Reminders() {
  const [rows, setRows] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  async function load() {
    const [bills, accs] = await Promise.all([api("/reminders"), api("/accounts")]);
    setRows(bills); setAccounts(Array.isArray(accs) ? accs : accs.items || []);
  }
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api("/reminders", { signal: controller.signal }), api("/accounts", { signal: controller.signal })]).then(([bills, accs]) => { if (!controller.signal.aborted) { setRows(bills); setAccounts(Array.isArray(accs) ? accs : accs.items || []); } }).catch(e => { if (!controller.signal.aborted) setError(e.message); }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);
  async function action(fn) {
    setBusy(true); setError("");
    try { await fn(); await load(); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <>
    <div className="db-page-intro"><div><h1>Reminders</h1></div></div>
    <div className="db-section-actions"><button className="db-primary-btn" onClick={() => setForm(fresh())}>New reminder</button></div>
    {error && <p className="db-error" role="alert">{error}</p>}
    {loading && <p role="status">Loading reminders…</p>}
    {!loading && !rows.length && <GlassCard>No upcoming payments. Add a bill reminder to get started.</GlassCard>}
    <div className="db-goals-grid">{rows.map(row => <GlassCard key={row.id}>
      <h3>{row.name}</h3><strong>{money(row.amount, accounts.find(account => account.id === row.account_id)?.currency || "LKR")}</strong>
      <p>{row.due_date < new Date().toLocaleDateString("en-CA") ? "Overdue" : "Upcoming"}: {row.due_date} · {row.recurrence}</p>
      <div className="db-row-actions">
        <button disabled={busy} onClick={() => setForm(row)}>Edit</button>
        <button disabled={busy} onClick={() => action(() => api(`/reminders/${row.id}/pay`, { method: "POST", data: { due_date: row.due_date } }))}>Mark paid</button>
        <button disabled={busy} onClick={() => { if (window.confirm("Archive this reminder? Payment history will be preserved.")) action(() => api(`/reminders/${row.id}`, { method: "DELETE" })); }}>Delete</button>
      </div>
    </GlassCard>)}</div>
    {form && <Modal title={form.id ? "Edit reminder" : "New reminder"} onClose={() => setForm(null)}>
      <form className="db-modal-form" onSubmit={e => { e.preventDefault(); action(async () => { await api(form.id ? `/reminders/${form.id}` : "/reminders", { method: form.id ? "PUT" : "POST", data: { ...form, account_id: Number(form.account_id) } }); setForm(null); }); }}>
        <label>Name<input required maxLength={120} value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}/></label>
        <label>Category<input required list="bill-categories" value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}/></label>
        <datalist id="bill-categories">{["Rent", "Electricity", "Water", "Loan", "Subscription", "Other"].map(x => <option key={x} value={x}/>)}</datalist>
        <label>Amount<input required type="number" min="0.01" step="0.01" value={form.amount} onChange={e => setForm({ ...form, amount: e.target.value })}/></label>
        <label>Account<select aria-label="Account" required value={form.account_id} onChange={e => setForm({ ...form, account_id: e.target.value })}><option value="">Choose account</option>{accounts.filter(a => !a.is_archived).map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        <label>Due date<input required type="date" value={form.due_date} onChange={e => setForm({ ...form, due_date: e.target.value })}/></label>
        <label>Repeat<select aria-label="Repeat" value={form.recurrence} onChange={e => setForm({ ...form, recurrence: e.target.value })}>{["none", "weekly", "monthly", "yearly"].map(x => <option key={x}>{x}</option>)}</select></label>
        {error && <p role="alert" className="db-error">{error}</p>}
        <button disabled={busy} className="db-primary-btn">{busy ? "Saving…" : "Save reminder"}</button>
      </form>
    </Modal>}
  </>;
}
