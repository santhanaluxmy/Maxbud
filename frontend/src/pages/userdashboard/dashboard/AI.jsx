import AdvisorMessage from "./AdvisorMessage";
import MerchantSelector from "./MerchantSelector";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../../api/client";
import { apiUrl } from "../../../api/base.js";
import { getAuthSession } from "../../../services/authApi";
import { ArrowUp, Sparkles, MessageCircle, ArrowRight, ScanLine } from "lucide-react";
import "./TargetedModules.css";
import { Link } from "react-router-dom";
import GlassCard from "../../../components/common/GlassCard";
import { useSubscription } from "../../../subscriptions/SubscriptionContext";

export default function AI({ mode }) {
  const conversation = useRef(null);
  const operation = useRef(false);
  const advisorRequest = useRef({ question: "", id: "" });
  const [loading, setLoading] = useState(true);
  const { usage, refresh: refreshSubscription } = useSubscription();
  const [history, setHistory] = useState([]);
  const [question, setQuestion] = useState("");
  const [receipt, setReceipt] = useState(null);
  const [categories, setCategories] = useState([]);
  const [merchants, setMerchants] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [accountId, setAccountId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState(null);
  const load = useCallback(async () => {
    const [result, options, suggestions] = await Promise.all([api(mode === "advisor" ? "/ai/advisor" : "/accounts"), mode === "advisor" ? Promise.resolve([]) : api("/ai/categories"), mode === "advisor" ? Promise.resolve([]) : api("/ai/merchants")]);
    return { result, options, suggestions };
  }, [mode]);
  const applyData = useCallback(({ result, options, suggestions }) => {
    setCategories(options);
    setMerchants(suggestions);
    if (mode === "advisor") setHistory(result);
    else setAccounts(Array.isArray(result) ? result : result.items || []);
  }, [mode]);
  useEffect(() => { let active = true; load().then(result => { if (active) applyData(result); }).catch(e => { if (active) setError(e.message); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [load, applyData]);
  useEffect(() => { if (conversation.current) conversation.current.scrollIntoView({ block: "end" }); }, [history, busy]);
  async function run(fn) {
    if (operation.current) return;
    operation.current = true; setBusy(true); setError(""); setMessage("");
    try { await fn(); applyData(await load()); await refreshSubscription(); } catch (e) { setError(e.message); } finally { operation.current = false; setBusy(false); }
  }
  async function sendQuestion() {
    const text = question.trim();
    if (advisorRequest.current.question !== text) advisorRequest.current = { question: text, id: crypto.randomUUID() };
    await api("/ai/advisor", { method: "POST", data: { question: text, request_id: advisorRequest.current.id } });
    setQuestion("");
    advisorRequest.current = { question: "", id: "" };
  }
  return <div className={mode === "advisor" ? "advisor-page" : "scanner-page"}>
    <div className="db-page-intro"><div><h1>{mode === "advisor" ? "AI Money Advisor" : "AI Receipt Scanner"}</h1></div></div>
    {mode !== "advisor" && <p className="ai-usage-line"><ScanLine size={17}/>{usage ? `${usage.used.receipt_scans} of ${usage.limits.receipt_scans} scans used this month` : "Loading scan allowance…"}<Link to="/dashboard/upgrade">View plans</Link></p>}
    {error && <p className="db-error" role="alert">{error}</p>}{message && <p role="status">{message}</p>}
    {mode === "advisor" ? <>
      <section className="advisor-chat" aria-label="Money advisor conversation">
        <header className="advisor-header"><Link className="advisor-allowance" to="/dashboard/upgrade">{usage ? `${Math.max(0, usage.limits.advisor_messages - usage.used.advisor_messages)} messages remaining` : "Usage unavailable"}</Link></header>
        <div className="advisor-conversation" role="log" aria-label="Conversation history" aria-busy={loading || busy}>
          {loading ? <p className="advisor-loading" role="status">Loading your conversation…</p> : !history.length ? <div className="advisor-empty"><span className="advisor-empty-icon"><MessageCircle size={30}/></span><h2>Make room for a clearer plan</h2><p>Ask about your budget, spending or savings. Start with a question below, or write your own.</p><div className="advisor-suggestions">{["How can I improve my monthly budget?", "Where could I reduce my spending?", "How should I plan for a savings goal?"].map(text => <button type="button" key={text} onClick={() => setQuestion(text)}>{text}<ArrowRight size={16}/></button>)}</div></div> : [...history].reverse().map(row => <div className="advisor-exchange" key={row.id}><div className="advisor-bubble advisor-user"><span>You</span><p>{row.question}</p></div><div className="advisor-bubble advisor-assistant"><span><Sparkles size={14}/> MaxBud Advisor</span><AdvisorMessage answer={row.answer}/></div></div>)}
          {busy && <div className="advisor-bubble advisor-assistant" role="status"><span><Sparkles size={14}/> MaxBud Advisor</span><p className="advisor-thinking">Thinking about your question<span aria-hidden="true">…</span></p></div>}
          <div ref={conversation} className="advisor-end" aria-hidden="true"/>
        </div>
        <form className="advisor-composer" onSubmit={e => { e.preventDefault(); if (!question.trim() || busy) return; run(sendQuestion); }}>
          <label htmlFor="advisor-question">Your question</label><div className="advisor-input-row"><textarea id="advisor-question" required maxLength={2000} rows={2} placeholder="What would you like to understand about your money?" value={question} disabled={busy} onChange={e => setQuestion(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); if (question.trim() && !busy) e.currentTarget.form.requestSubmit(); } }}/><button type="submit" disabled={loading || busy || !question.trim() || (usage && usage.used.advisor_messages >= usage.limits.advisor_messages)} className="db-primary-btn" aria-label="Send question"><ArrowUp size={18}/><span>{busy ? "Sending…" : "Send"}</span></button></div>
          <p>Your financial totals and question are shared with the AI provider. Avoid personal identifiers. <span>Enter to send · Shift + Enter for a new line</span></p>
        </form>
      </section>
    </> : <div className="receipt-workspace">
      <ol className="receipt-steps" aria-label="Receipt workflow">{["Upload", "Scan", "Review", "Save transaction"].map((step, index) => <li key={step} className={(receipt?.status === "confirmed" ? index === 3 : receipt ? index === 2 : busy ? index === 1 : index === 0) ? "current" : ""}><span>{index + 1}</span>{step}</li>)}</ol>
      {receipt?.status === "confirmed" && <GlassCard title="Transaction saved"><p>Your receipt is linked to transaction #{receipt.transaction_id}.</p><Link className="db-primary-btn" to="/dashboard/transactions">View saved transaction</Link><Link className="db-outline-btn" to="/dashboard">View updated dashboard</Link></GlassCard>}
      <GlassCard title="Upload your receipt" subtitle="JPG or PNG, up to 5 MB. You review the details before anything is saved."><form className="db-modal-form" onSubmit={e => { e.preventDefault(); run(async () => {
        if (!file || file.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png"].includes(file.type)) throw new Error("Choose a JPG or PNG under 5 MB.");
        const data = new FormData(); data.append("file", file);
        const response = await fetch(apiUrl("/ai/receipts"), { method: "POST", headers: { Authorization: `Bearer ${getAuthSession()?.token}` }, body: data });
        const result = await response.json(); if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : "Receipt scan failed");
        setReceipt(result.status === "review" ? { ...result, data: { ...result.data, currency: result.data.currency || "LKR", category: categories.find(category => category.toLowerCase() === result.data.category?.toLowerCase()) || "" } } : result); setAccountId(""); if (result.status === "confirmed") setMessage("This receipt already has a saved transaction.");
      }); }}>
        <label>Receipt image<input required type="file" accept="image/jpeg,image/png" disabled={busy} onChange={e => { setFile(e.target.files[0]); setReceipt(null); setAccountId(""); setMessage(""); setError(""); }}/></label>
        <p className="db-note">The receipt image is sent to the AI provider. Review the result before saving.</p>
        <button disabled={busy} className="db-primary-btn">{busy ? "Scanning…" : "Scan receipt"}</button>
      </form></GlassCard>
      {receipt?.status === "review" && <GlassCard className="receipt-review"><form className="db-modal-form" onSubmit={e => { e.preventDefault(); run(async () => { const result = await api(`/ai/receipts/${receipt.id}/confirm`, { method: "POST", data: { merchant: receipt.data.merchant, date: receipt.data.date, total: receipt.data.total, currency: receipt.data.currency, category: receipt.data.category, items: receipt.data.items, account_id: Number(accountId) } }); if (result.status !== "confirmed" || !result.transaction_id) throw new Error("The receipt was not saved. Please review and try again."); setReceipt(result); setMessage("Receipt transaction saved. Your balance and budget now include this expense."); }); }}>
        <fieldset className="receipt-review-fields" disabled={busy}><legend>Review receipt</legend>
        {receipt.data.printed_total === null && <p className="db-warning">No printed grand total was found. {receipt.data.calculated_subtotal ? `Visible line-item subtotal: ${receipt.data.calculated_subtotal}. This is calculated, not the printed grand total.` : "Enter a verified total before confirming."}</p>}
        <MerchantSelector value={receipt.data.merchant || ""} suggestions={merchants} onChange={(merchant, category) => setReceipt({ ...receipt, data: { ...receipt.data, merchant, ...(category && categories.includes(category) ? { category } : {}) } })}/>
        <div className="db-two-fields">{[["date", "Receipt date"], ["total", "Reviewed transaction total"]].map(([key, label]) => <label key={key}>{label}<input required type={key === "date" ? "date" : "number"} min={key === "total" ? "0.01" : undefined} step={key === "total" ? "0.01" : undefined} value={receipt.data[key] ?? ""} onChange={e => setReceipt({ ...receipt, data: { ...receipt.data, [key]: e.target.value } })}/></label>)}</div>
        <label>Currency<select aria-label="Currency" required value={receipt.data.currency || "LKR"} onChange={e => { setReceipt({ ...receipt, data: { ...receipt.data, currency: e.target.value } }); setAccountId(""); }}>{[...new Set(["LKR", "USD", "EUR", "GBP", "INR", ...accounts.map(account => account.currency), receipt.data.currency].filter(Boolean))].map(currency => <option key={currency} value={currency}>{currency}</option>)}</select></label>
        <label>Expense category<select aria-label="Expense category" required value={receipt.data.category || ""} onChange={e => setReceipt({ ...receipt, data: { ...receipt.data, category: e.target.value } })}><option value="">Choose an existing category</option>{categories.map(value => <option key={value} value={value}>{value}</option>)}</select></label>
        {receipt.data.items.map((item, index) => <fieldset className="db-two-fields" key={index}><legend>Item {index + 1}</legend>{[["name", "Item name"], ["quantity", "Quantity"], ["unit_price", "Unit price"], ["amount", "Item amount"]].map(([key, label]) => <label key={key}>{label}<input type={key === "name" ? "text" : "number"} min={key === "name" ? undefined : "0"} step={key === "quantity" ? "0.001" : "0.01"} value={item[key] ?? ""} onChange={e => setReceipt({ ...receipt, data: { ...receipt.data, items: receipt.data.items.map((row, i) => i === index ? { ...row, [key]: e.target.value === "" ? null : e.target.value } : row) } })}/></label>)}</fieldset>)}
        <label>Account<select aria-label="Account" required value={accountId} onChange={e => setAccountId(e.target.value)}><option value="">Choose account</option>{accounts.filter(a => !a.is_archived && a.currency === receipt.data.currency).map(a => <option value={a.id} key={a.id}>{a.name}</option>)}</select></label>
        {!accounts.some(a => !a.is_archived && a.currency === receipt.data.currency) && <p className="db-note">Choose a reviewed currency matching an active personal account, or create an account first.</p>}
        </fieldset>
        <button disabled={busy || !accounts.some(account => !account.is_archived && String(account.id) === String(accountId) && account.currency === receipt.data.currency)} className="db-primary-btn">{busy ? "Saving transaction…" : "Confirm expense"}</button>
      </form></GlassCard>}
    </div>}
  </div>;
}
