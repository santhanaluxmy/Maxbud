import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { createServer } from 'vite';

test('advisor presents structured multilingual replies as safe readable HTML', async () => {
  const server = await createServer({ server: { middlewareMode: true, watch: null }, appType: 'custom' });
  try {
    const { default: AdvisorMessage } = await server.ssrLoadModule('/src/pages/userdashboard/dashboard/AdvisorMessage.jsx');
    const render = answer => renderToStaticMarkup(createElement(AdvisorMessage, { answer }));
    const html = render(JSON.stringify({ answer: '## Your plan\n\n- Save **LKR 5000**\n- சேமிப்பு திட்டம்\n\n<img src=x onerror=alert(1)>' }));
    assert.match(html, /<h3>Your plan<\/h3>/);
    assert.equal((html.match(/<li>/g) || []).length, 2);
    assert.match(html, /<strong>LKR 5,000.00<\/strong>/);
    assert.match(html, /சேமிப்பு திட்டம்/);
    assert.match(html, /&lt;img/);
    assert.doesNotMatch(html, /<img|<script/);
    assert.doesNotMatch(html, /&quot;answer&quot;/);
    const table = render('| Category | Amount |\n| --- | --- |\n| Food | LKR 1250 |');
    assert.match(table, /<li>/);
    assert.match(table, /Category: Food/);
    assert.match(table, /LKR 1,250.00/);
    assert.match(render('{invalid JSON'), /could not be displayed/);
  } finally { await server.close(); }
});
