import assert from 'node:assert/strict';
import { test } from 'node:test';
import { advisorText } from '../src/pages/userdashboard/dashboard/advisorText.js';
test('advisor unwraps JSON and preserves multilingual text', () => {
  assert.equal(advisorText('{"answer":"## Budget\\n\\n- Save LKR 5000\\n- சேமிப்பு திட்டம்"}'),'## Budget\n\n- Save LKR 5,000.00\n- சேமிப்பு திட்டம்');
  assert.equal(advisorText('```json\n{"response":{"content":"Vanakkam! LKR 1250.5"}}\n```'),'Vanakkam! LKR 1,250.50');
  assert.match(advisorText({summary:'Review budget',recommendations:['Track food']}),/Track food/);
});
test('malformed structured replies do not become raw object text', () => {
  for (const value of ['{broken JSON',{},[]]) assert.match(advisorText(value),/could not be displayed/);
  assert.equal(advisorText('<img src=x onerror=alert(1)>'),'<img src=x onerror=alert(1)>');
});
