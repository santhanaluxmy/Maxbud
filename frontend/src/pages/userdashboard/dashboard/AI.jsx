import AdvisorMessage from "./AdvisorMessage";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../../api/client";
import { getAuthSession } from "../../../services/authApi";
import { ArrowUp, Sparkles, MessageCircle, ArrowRight, ScanLine } from "lucide-react";
import { Link } from "react-router-dom";
import GlassCard from "../../../components/common/GlassCard";

export default function AI({ mode }) {
  const conversation = useRef(null);
  const advisorRequest = useRef({ question: "", id: "" });
  const [loading, setLoading] = useState(true);
  const [usage, setUsage] = useState(null);
  const [history, setHistory] = useState([]);
  const [question, setQuestion] = useState("");
  const [receipt, setReceipt] = useState(null);
  const [categories, setCategories] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [accountId, setAccountId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState(null);
  const load = useCallback(async () => {
    const [meter, result, options] = await Promise.all([api("/ai/usage"), api(mode === "advisor" ? "/ai/advisor" : "/accounts"), mode === "advisor" ? Promise.resolve([]) : api("/ai/categories")]);
    return { meter, result, options };
  }, [mode]);
  const applyData = useCallback(({ meter, result, options }) => {
    setCategories(options);
    setUsage(meter);
    if (mode === "advisor") setHistory(result);
    else setAccounts(result.items || []);
  }, [mode]);
  useEffect(() => { let active = true; load().then(result => { if (active) applyData(result); }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [load, applyData]);
  useEffect(() => { if (conversation.current) conversation.current.scrollTop = conversation.current.scrollHeight; }, [history, busy]);
  async function run(fn) {
    setBusy(true); setError(""); setMessage("");
    try { await fn(); applyData(await load()); } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function sendQuestion() {
    const text = question.trim();
    if (advisorRequest.current.question !== text) advisorRequest.current = { question: text, id: crypto.randomUUID() };
    await api("/ai/advisor", { method: "POST", data: { question: text, request_id: advisorRequest.current.id } });
    setQuestion("");
    advisorRequest.current = { question: "", id: "" };
  }
  return <>
    <div className="db-page-intro"><div><span className="db-page-subtitle">MAXBUD SMART TOOLS</span><h1>{mode === "advisor" ? "AI Money Advisor" : "AI Receipt Scanner"}</h1><p>{mode === "advisor" ? "A thoughtful space for your everyday money questions." : "Less typing. More clarity. Review every detail before saving."}</p></div></div>
    {mode !== "advisor" && <p className="ai-usage-line"><ScanLine size={17}/>{usage ? `${usage.used.receipt_scans} of ${usage.limits.receipt_scans} scans used this month` : "Loading scan allowance…"}<Link to="/dashboard/upgrade">View plans</Link></p>}
    {error && <p className="db-error" role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {mode === "advisor" ? <>
      <section className="advisor-chat" aria-label="Money advisor conversation">
        <header className="advisor-header"><span className="db-icon-pill"><Sparkles size={21}/></span><div><h2>Your money, in perspective</h2><p>Guidance based on your recorded financial summary</p></div><Link className="advisor-allowance" to="/dashboard/upgrade">{usage ? `${Math.max(0, usage.limits.advisor_messages - usage.used.advisor_messages)} messages remaining` : "Usage unavailable"}</Link></header>
        <div className="advisor-conversation" ref={conversation} role="log" aria-label="Conversation history" aria-busy={loading || busy}>
          {loading ? <p className="advisor-loading" role="status">Loading your conversation…</p> : !history.length ? <div className="advisor-empty"><span className="advisor-empty-icon"><MessageCircle size={30}/></span><h2>Make room for a clearer plan</h2><p>Ask about your budget, spending or savings. Start with a question below, or write your own.</p><div className="advisor-suggestions">{["How can I improve my monthly budget?", "Where could I reduce my spending?", "How should I plan for a savings goal?"].map(text => <button type="button" key={text} onClick={() => setQuestion(text)}>{text}<ArrowRight size={16}/></button>)}</div></div> : [...history].reverse().map(row => <div className="advisor-exchange" key={row.id}><div className="advisor-bubble advisor-user"><span>You</span><p>{row.question}</p></div><div className="advisor-bubble advisor-assistant"><span><Sparkles size={14}/> MaxBud Advisor</span><AdvisorMessage answer={row.answer}/></div></div>)}
          {busy && <div className="advisor-bubble advisor-assistant" role="status"><span><Sparkles size={14}/> MaxBud Advisor</span><p className="advisor-thinking">Thinking about your question<span aria-hidden="true">…</span></p></div>}
        </div>
        <form className="advisor-composer" onSubmit={e => { e.preventDefault(); if (!question.trim() || busy) return; run(sendQuestion); }}>
          <label htmlFor="advisor-question">Your question</label><div className="advisor-input-row"><textarea id="advisor-question" required maxLength={2000} rows={2} placeholder="What would you like to understand about your money?" value={question} disabled={busy} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); if (question.trim() && !busy) e.currentTarget.form.requestSubmit(); } }}/><button type="submit" disabled={loading || busy || !question.trim() || (usage && usage.used.advisor_messages >= usage.limits.advisor_messages)} className="db-primary-btn" aria-label="Send question"><ArrowUp size={18}/><span>{busy ? "Sending…" : "Send"}</span></button></div>
          <p>Your financial totals and question are shared with the AI provider. Avoid personal identifiers. <span>Enter to send · Shift + Enter for a new line</span></p>
        </form>
      </section>
    </> : <>
      <GlassCard><form className="db-modal-form" onSubmit={e => { e.preventDefault(); run(async () => {
        if (!file || file.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png"].includes(file.type)) throw new Error("Choose a JPG or PNG under 5 MB.");
        const data = new FormData(); data.append("file", file);
        const response = await fetch(`${(import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "")}/ai/receipts`, { method: "POST", headers: { Authorization: `Bearer ${getAuthSession()?.token}` }, body: data });
        const result = await response.json(); if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Receipt scan failed");
        setReceipt(result); if (result.status === "confirmed") setMessage("This receipt already has a saved transaction.");
      }); }}>
        <label>Receipt image<input required type="file" accept="image/jpeg,image/png" onChange={e => setFile(e.target.files[0])}/></label>
        <p className="db-note">The receipt image is sent to the AI provider. Review the result before saving.</p>
        <button disabled={busy} className="db-primary-btn">{busy ? "Scanning…" : "Scan receipt"}</button>
      </form></GlassCard>
      {receipt?.status === "review" && <GlassCard><form className="db-modal-form" onSubmit={e => { e.preventDefault(); run(async () => { const result = await api(`/ai/receipts/${receipt.id}/confirm`, { method: "POST", data: { ...receipt.data, account_id: Number(accountId) } }); setReceipt(result); setMessage("Receipt transaction saved."); }); }}>
        <h3>Review receipt</h3>
        {receipt.data.printed_total === null && <p className="db-warning">No printed grand total was found. {receipt.data.calculated_subtotal ? `Visible line-item subtotal: ${receipt.data.calculated_subtotal}. This is calculated, not the printed grand total.` : "Enter a verified total before confirming."}</p>}
        {["merchant", "date", "total", "currency"].map(key => <label key={key}>{key === "total" ? "Reviewed transaction total" : key}<input required type={key === "date" ? "date" : key === "total" ? "number" : "text"} min={key === "total" ? "0.01" : undefined} step={key === "total" ? "0.01" : undefined} value={receipt.data[key] ?? ""} onChange={e => setReceipt({ ...receipt, data: { ...receipt.data, [key]: e.target.value } })}/></label>)}
        <label>Expense category<select aria-label="Expense category" required value={receipt.data.category || ""} onChange={e => setReceipt({ ...receipt, data: { ...receipt.data, category: e.target.value } })}><option value="">Choose an existing category</option>{categories.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
        {receipt.data.items.map((item, index) => <fieldset className="db-two-fields" key={index}><legend>Item {index + 1}</legend>{[["name", "Item name"], ["quantity", "Quantity"], ["unit_price", "Unit price"], ["amount", "Item amount"]].map(([key, label]) => <label key={key}>{label}<input type={key === "name" ? "text" : "number"} min={key === "name" ? undefined : "0"} step={key === "quantity" ? "0.001" : "0.01"} value={item[key] ?? ""} onChange={e => setReceipt({ ...receipt, data: { ...receipt.data, items: receipt.data.items.map((row, i) => i === index ? { ...row, [key]: e.target.value === "" ? null : e.target.value } : row) } })}/></label>)}</fieldset>)}
        <label>Account<select aria-label="Account" required value={accountId} onChange={e => setAccountId(e.target.value)}><option value="">Choose account</option>{accounts.filter(a => !a.is_archived).map(a => <option value={a.id} key={a.id}>{a.name}</option>)}</select></label>
        <button disabled={busy} className="db-primary-btn">Confirm expense</button>
      </form></GlassCard>}
    </>}
  </>;
}
