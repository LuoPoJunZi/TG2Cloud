import test from 'node:test';
import assert from 'node:assert/strict';
import {renderMarkdown,inline,safeUrl,slugify} from '../scripts/markdown.mjs';
test('escapes HTML and code',()=>{
  assert.match(renderMarkdown('<script>alert(1)</script>').html,/&lt;script&gt;/);
  assert.match(inline('`<编号>`'),/<code>&lt;编号&gt;<\/code>/);
});
test('blocks dangerous URL schemes',()=>{
  assert.equal(safeUrl('javascript:alert(1)'),'#');
  assert.equal(safeUrl('//evil.example/path'),'#');
  assert.equal(safeUrl('data:text/html,x'),'#');
  assert.equal(safeUrl('/guide/quick-start/'),'/guide/quick-start/');
});
test('headings have predictable unique IDs',()=>{
  const out=renderMarkdown('# Test\n\n## TG2Cloud v1.0.2\n\n## 同名\n\n## 同名');
  assert.deepEqual(out.headings.map(h=>h.id),['test','tg2cloud-v1-0-2','同名','同名-1']);
  assert.equal(slugify('WebDAV 验收'),'webdav-验收');
});
test('renders supported lists, tables and links',()=>{
  const out=renderMarkdown('# Test\n\n1. First\n2. Second\n\n| A | B |\n| --- | --- |\n| `x` | [OK](/faq/) |');
  assert.match(out.html,/<ol>/);assert.match(out.html,/<table>/);
  assert.match(out.html,/<a href="\/faq\/">OK<\/a>/);
});
test('callouts and fenced code',()=>{
  const out=renderMarkdown('# Test\n\n:::warning 小心\n内容 **重点**。\n:::\n\n```bash\nprintf "<x>"\n```');
  assert.match(out.html,/callout warning/);assert.match(out.html,/<strong>重点<\/strong>/);
  assert.match(out.html,/printf &quot;&lt;x&gt;&quot;/);
});
test('rejects unclosed blocks',()=>{
  assert.throws(()=>renderMarkdown('```js\nx'),/Unclosed/);
  assert.throws(()=>renderMarkdown(':::tip\nx'),/Unclosed/);
});
test('raw image markup is not executed',()=>{
  assert.match(renderMarkdown('<img src=x onerror=alert(1)>').html,/&lt;img/);
  assert.match(inline('![demo](/images/demo.png)'),/<img loading="lazy"/);
});
