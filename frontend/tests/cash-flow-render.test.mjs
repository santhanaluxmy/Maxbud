import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

test('monthly cash flow renders category totals, balances, and empty/error states', async () => {
  const server = await createServer({ server: { middlewareMode: true, watch: null }, appType: 'custom' });
  try {
    const { default: CashFlowTable } = await server.ssrLoadModule('/src/pages/userdashboard/dashboard/CashFlow.jsx');
    const report = {
      month: '2026-11', opening_balance: '10000.00', closing_balance: '14400.00',
      income: '8000.00', expense: '3500.00', net_cash_flow: '4500.00',
      basis: 'Long accounting explanation should not appear',
      rows: [{ id: 1, description: 'Burger detail should not appear', kind: 'expense' }],
      category_totals: [
        { category: 'Salary', kind: 'income', amount: '8000.00' },
        { category: 'Food', kind: 'expense', amount: '3500.00' },
      ],
    };
    const render = props => renderToStaticMarkup(createElement(CashFlowTable, { report, currency: 'LKR', retry() {}, ...props }));
    const html = render();
    for (const label of ['Category', 'Type', 'Total Amount (LKR)', 'Opening balance', 'Closing balance', 'Total Income', 'Total Expenses', 'Net Cash Flow']) {
      assert.ok(html.includes(label), label);
    }
    assert.match(html, /Salary<\/th><td>Income<\/td><td>LKR 8,000/);
    assert.match(html, /Food<\/th><td>Expense<\/td><td>LKR 3,500/);
    assert.match(html, /Opening balance <strong>LKR 10,000/);
    assert.match(html, /Closing balance <strong>LKR 14,400/);
    assert.match(html, /Net Cash Flow<\/th><td>LKR 4,500/);
    assert.doesNotMatch(html, /Long accounting explanation|Burger detail|Running balance|Chronological|Transfer in|Transfer out/);
    assert.match(html, /Category totals · 2026-11/);

    const empty = render({ report: { ...report, category_totals: [], income: '0.00', expense: '0.00', net_cash_flow: '0.00' } });
    assert.match(empty, /No income or expenses recorded for this month/);
    assert.match(empty, /Total Income<\/th><td>LKR 0/);
    assert.match(empty, /Total Expenses<\/th><td>LKR 0/);
    assert.doesNotMatch(empty, /Opening and closing balances are the same/);
    assert.match(render({ loading: true }), /Loading monthly cash flow/);
    assert.match(render({ error: 'Unavailable' }), /Retry report/);
  } finally {
    await server.close();
  }
});
