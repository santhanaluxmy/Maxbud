import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../../api/client";
import GlassCard from "../../../components/common/GlassCard";
export default function Notifications() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => { api("/notifications").then(setRows).catch(e => setError(e.message)); }, []);
  async function read(row) {
    try { await api("/notifications/read", { method: "POST", data: { key: row.key } }); setRows(rows.map(x => x.key === row.key ? { ...x, read: true } : x)); } catch (e) { setError(e.message); }
  }
  return <><div className="db-page-intro"><div><span className="db-page-subtitle">YOUR LATEST UPDATES</span><h1>Notifications</h1><p>Important moments in your budget, bills and goals.</p></div></div>{error && <p className="db-error" role="alert">{error}</p>}{!rows.length && !error && <p>No current alerts.</p>}{rows.map(row => <GlassCard key={row.key}><p>{row.message}</p><Link to={row.path}>View</Link>{!row.read && <button className="db-outline-btn" onClick={() => read(row)}>Mark read</button>}{row.read && <span>Read</span>}</GlassCard>)}</>;
}
