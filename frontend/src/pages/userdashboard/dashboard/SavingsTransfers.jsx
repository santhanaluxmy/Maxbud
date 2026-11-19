import { useEffect, useRef, useState } from "react";
import { api, money } from "../../../api/client";

export default function SavingsTransfers({ search, onChanged }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [more, setMore] = useState(false);
  const [error, setError] = useState("");
  const [reversing, setReversing] = useState(null);
  const pending = useRef(false);

  useEffect(() => {
    let active = true;
    api("/goals/transfers?limit=100").then(items => {
      if (active) { setRows(items); setMore(items.length === 100); }
    }).catch(err => { if (active) setError(err.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  async function reverse(row) {
    if (pending.current || !window.confirm(`Return ${money(row.amount, row.currency)} from ${row.goal_name} to ${row.source_account_name}?`)) return;
    pending.current = true;
    setReversing(row.id);
    setError("");
    try {
      await api(`/goals/${row.goal_id}/contributions/${row.contribution_id}/reverse`, { method: "POST" });
      setRows(previous => previous.map(item => item.id === row.id ? { ...item, status: "reversed", reversed_at: new Date().toISOString() } : item));
      await onChanged();
    } catch (err) { setError(err.message); }
    finally { pending.current = false; setReversing(null); }
  }

  async function loadMore() {
    if (pending.current) return;
    pending.current = true;
    setLoading(true);
    setError("");
    try {
      const items = await api(`/goals/transfers?limit=100&offset=${rows.length}`);
      setRows(previous => [...previous, ...items.filter(item => !previous.some(row => row.id === item.id))]);
      setMore(items.length === 100);
    } catch (err) { setError(err.message); }
    finally { pending.current = false; setLoading(false); }
  }

  const shown = rows.filter(row => `${row.txn_date} ${row.source_account_name} ${row.goal_name} ${row.amount} ${row.status}`.toLowerCase().includes(search.toLowerCase()));
  return <>
    {error && <p className="db-error" role="alert">{error}</p>}
    {loading && <p role="status">Loading savings transfers…</p>}
    <div className="db-table-wrap">
      <table className="db-table" aria-label="Savings transfers">
        <thead><tr><th>Date</th><th>Source account</th><th>Destination goal</th><th>Amount</th><th>Status</th><th>Action</th></tr></thead>
        <tbody>{shown.map(row => <tr key={row.id}>
          <td>{row.txn_date}</td><td>{row.source_account_name}</td><td>{row.goal_name}</td>
          <td>{money(row.amount, row.currency)}</td>
          <td>{row.status === "reversed" ? `Reversed ${row.reversed_at?.slice(0, 10) || ""}` : "Transferred"}</td>
          <td>{row.status !== "reversed" && <button type="button" className="db-outline-btn" disabled={reversing !== null || loading} onClick={() => reverse(row)}>{reversing === row.id ? "Reversing…" : "Reverse"}</button>}</td>
        </tr>)}</tbody>
      </table>
    </div>
    {!loading && !shown.length && <p className="db-note">No savings transfers found.</p>}
    {more && <button type="button" className="db-outline-btn" disabled={loading || reversing !== null} onClick={loadMore}>Load more transfers</button>}
  </>;
}
