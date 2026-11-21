import { money } from "../../../api/client";
import GlassCard from "../../../components/common/GlassCard";

export function CashFlowSummary({ data, currency, loading, error, retry }) {
  if (loading) return <section aria-label="Loading cash flow summary" aria-busy="true" className="db-metric-grid cash-summary-skeleton">{[0,1,2,3].map(i => <div className="glass-card" key={i}><span/><span/></div>)}</section>;
  if (error || !data) return <div className="db-warning" role="status">Cash flow summary is unavailable. <button className="db-outline-btn" onClick={retry}>Retry summary</button></div>;
  const metrics = [["Active account balance", data.active_tracked_balance], ["Income this month", data.monthly_income], ["Expenses this month", data.monthly_expenses], ["Net monthly cash flow", data.monthly_net_cash_flow]];
  return <section aria-label="Current cash flow summary"><div className="db-metric-grid cash-summary">{metrics.map(([label, value]) => <GlassCard key={label}><p>{label}</p><strong>{money(value, currency)}</strong></GlassCard>)}</div></section>;
}
export default function CashFlowTable({ report, currency, loading, error, retry }) {
  return <GlassCard className="cash-flow-panel" title="Monthly cash flow" subtitle={report ? `Personal account activity · ${report.month}` : "Selected calendar month"}>
    {loading ? <p role="status">Loading monthly cash flow…</p> : error || !report ? <p role="status">Monthly cash flow could not load. <button className="db-outline-btn" onClick={retry}>Retry report</button></p> : <>
      <div className="cash-flow-totals"><p>Opening balance <strong>{money(report.opening_balance,currency)}</strong></p><p>Net cash flow <strong>{money(report.net_cash_flow,currency)}</strong></p><p>Closing balance <strong>{money(report.closing_balance,currency)}</strong></p></div>
      <div className="db-table-wrap cash-flow-scroll" tabIndex={0} role="region" aria-label="Monthly category summary">
        <table className="db-table cash-flow-table">
          <caption>Category totals · {report.month}</caption>
          <thead><tr><th scope="col">Category</th><th scope="col">Type</th><th scope="col">Total Amount ({currency || "LKR"})</th></tr></thead>
          <tbody>
            {report.category_totals?.length ? report.category_totals.map(row => <tr key={`${row.kind}:${row.category}`}>
              <th scope="row">{row.category}</th>
              <td>{row.kind === "income" ? "Income" : "Expense"}</td>
              <td>{money(row.amount, currency)}</td>
            </tr>) : <tr><td colSpan={3}>No income or expenses recorded for this month.</td></tr>}
          </tbody>
          <tfoot>
            <tr><th scope="row" colSpan={2}>Total Income</th><td>{money(report.income, currency)}</td></tr>
            <tr><th scope="row" colSpan={2}>Total Expenses</th><td>{money(report.expense, currency)}</td></tr>
            <tr><th scope="row" colSpan={2}>Net Cash Flow</th><td>{money(report.net_cash_flow, currency)}</td></tr>
          </tfoot>
        </table>
      </div>
    </>}
  </GlassCard>;
}
