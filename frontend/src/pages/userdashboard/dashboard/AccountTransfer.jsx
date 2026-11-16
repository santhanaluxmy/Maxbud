import { useState } from "react";
import { api, money } from "../../../api/client";
import Modal from "../../../components/common/Modal";

export default function AccountTransfer({ accounts, onClose, onSaved }) {
  const active = accounts.filter(account => !account.is_archived);
  const [form, setForm] = useState(() => ({
    from_account_id: String(active[0]?.id || ""),
    to_account_id: String(active[1]?.id || ""),
    amount: "",
    txn_date: new Date().toLocaleDateString("en-CA"),
    description: "",
    client_request_id: crypto.randomUUID(),
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const source = active.find(account => String(account.id) === form.from_account_id);
  const destinations = active.filter(account => String(account.id) !== form.from_account_id && account.currency === source?.currency);

  async function save(event) {
    event.preventDefault();
    if (saving) return;
    setSaving(true);
    setError("");
    try {
      await api("/transfers", {
        method: "POST",
        data: { ...form, from_account_id: Number(form.from_account_id), to_account_id: Number(form.to_account_id) },
      });
      await onSaved();
    } catch (failure) {
      setError(failure.message);
    } finally {
      setSaving(false);
    }
  }

  return <Modal title="Transfer between accounts" onClose={() => { if (!saving) onClose(); }}>
    <form className="db-modal-form" onSubmit={save}>
      <p className="db-note">Move money between your tracked accounts. Transfers do not count as income or expenses.</p>
      <label>From account<select aria-label="From account" required disabled={saving} value={form.from_account_id} onChange={event => {
        const next = active.find(account => String(account.id) === event.target.value);
        const destination = active.find(account => account.id !== next.id && account.currency === next.currency);
        setForm({ ...form, from_account_id: event.target.value, to_account_id: String(destination?.id || "") });
      }}>{active.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label>
      <label>To account<select aria-label="To account" required disabled={saving} value={form.to_account_id} onChange={event => setForm({ ...form, to_account_id: event.target.value })}>
        <option value="">Choose another account</option>{destinations.map(account => <option key={account.id} value={account.id}>{account.name}</option>)}
      </select></label>
      {source && <p className="db-note">Available in {source.name}: {money(source.current_balance, source.currency)}</p>}
      <label>Transfer amount ({source?.currency || "LKR"})<input required disabled={saving} type="number" min="0.01" step="0.01" value={form.amount} onChange={event => setForm({ ...form, amount: event.target.value })}/></label>
      <label>Transfer date<input required disabled={saving} type="date" value={form.txn_date} onChange={event => setForm({ ...form, txn_date: event.target.value })}/></label>
      <label>Note (optional)<input disabled={saving} maxLength={255} value={form.description} onChange={event => setForm({ ...form, description: event.target.value })}/></label>
      {error && <p className="db-error" role="alert">{error}</p>}
      {!destinations.length && <p className="db-note">Add another active account in the same currency to transfer money.</p>}
      <button className="db-primary-btn db-modal-submit" disabled={saving || !destinations.length}>{saving ? "Transferring…" : "Transfer money"}</button>
    </form>
  </Modal>;
}
