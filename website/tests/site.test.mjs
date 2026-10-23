import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {renderMarkdown,slugify} from '../scripts/markdown.mjs';
import {renderPage} from '../src/templates.mjs';

const read=path=>readFile(new URL('../'+path,import.meta.url),'utf8');
const config=JSON.parse(await read('site.config.json'));
const aliases=JSON.parse(await read('src/legacy-anchors.json'));
const hashes={css:'test',js:'test',init:'test'};

test('Linux walkthroughs do not direct users through retired desktop controls',async()=>{
  for(const path of ['guide/quick-start','deploy/ssh','deploy/clouddrive2','deploy/openlist']){
    const article=await read('docs/'+path+'.md');
    assert.doesNotMatch(article,/点击[“「](?:测试 SSH|一键部署基础环境)|下载 `TG2Cloud-.*Deployer\.exe`|右侧日常管理区/,path);
  }
  const install=await read('docs/guide/quick-start.md');
  for(const entry of ['install.sh','install-lan.sh'])assert.ok(install.includes('/main/'+entry));
  assert.ok(install.includes('11. WebDAV 验收'));
  const editions=await read('docs/guide/editions.md');
  assert.ok(editions.includes('实例快照与隔离预检'));
  assert.doesNotMatch(editions,/\| 部署器文件 \||\| 手动业务安全备份界面 \| 无/);
});

test('task settings and backup instructions use the current management menu',async()=>{
  const cases=[['deploy/telegram','5. Bot 用户管理'],['usage/commands','5. Bot 用户管理'],
    ['usage/first-transfer','8. 文件分类设置'],['operations/backup','13. 数据备份管理']];
  for(const [path,label] of cases){
    const article=await read('docs/'+path+'.md');
    assert.ok(article.includes(label),path);
    assert.doesNotMatch(article,/`tg2cloud` → (?:10 → 5|14 → 1|7 → 创建共享代理备份)/,path);
  }
  const backup=await read('docs/operations/backup.md');
  assert.ok(backup.includes('两版都支持实例快照'));
  assert.ok(backup.includes('不等于生产恢复')||backup.includes('不等于实际服务恢复')||backup.includes('不等于完整服务恢复'));
  assert.doesNotMatch(backup,/CloudDrive2 仍没有手动业务|须后续发布并更新/);
});

test('article source links identify the actual website article and existing project reference',async()=>{
  for(const page of config.navigation.flatMap(group=>group.items)){
    const article=await read('docs/'+page.slug+'.md');
    const rendered=renderMarkdown(article);
    const html=renderPage({config,page,body:rendered.html,headings:rendered.headings,hashes});
    assert.ok(html.includes(`class="article-source" href="${config.repo}/blob/main/website/docs/${page.slug}.md"`),page.slug);
    const reference=html.match(/class="reference-source" href="[^"]+\/blob\/main\/([^"]+)"/);
    assert.ok(reference,page.slug);
    assert.ok(await readFile(new URL('../../'+reference[1],import.meta.url)),page.slug+': reference exists');
    assert.ok(html.includes('class="mobile-toc"'),page.slug+': mobile section navigation');
  }
});

test('version menu uses real changelog sections instead of hard-coded early releases',async()=>{
  const versionHistory=renderMarkdown(await read('docs/changelog.md')).headings
    .filter(heading=>heading.level===2&&/^TG2Cloud v\d+\.\d+\.\d+$/.test(heading.title))
    .map(heading=>({version:heading.title.slice('TG2Cloud v'.length),id:heading.id}));
  const html=renderPage({config:{...config,versionHistory},page:{title:'首页',slug:''},home:true,hashes});
  const menu=html.match(/<details class="version-menu">([\s\S]*?)<\/details>/)?.[1];
  assert.ok(menu);
  for(const row of versionHistory.filter(row=>row.version!==config.version).slice(0,3)){
    assert.ok(menu.includes(`/changelog/#${encodeURIComponent(row.id)}`),row.version);
  }
  assert.ok(menu.includes('完整版本记录'));
  assert.ok(menu.includes('非文档快照'));
  assert.ok(versionHistory.length>=23,'do not remove historical versions to simplify the menu');
});

test('all retired section anchors still locate real headings without polluting the table of contents',async()=>{
  let count=0;
  for(const [slug,legacyAnchors] of Object.entries(aliases)){
    const article=await read('docs/'+slug+'.md');
    const before=renderMarkdown(article);
    const after=renderMarkdown(article,{legacyAnchors});
    assert.deepEqual(after.headings,before.headings,slug+': only current headings in TOC/search');
    const ids=[...after.html.matchAll(/\bid="([^"]+)"/g)].map(match=>match[1]);
    assert.equal(ids.length,new Set(ids).size,slug+': unique identifiers');
    for(const [alias,title] of Object.entries(legacyAnchors)){
      assert.ok(ids.includes(alias),slug+': '+alias);
      assert.ok(before.headings.some(heading=>heading.id===slugify(title)),slug+': valid target');
      count++;
    }
  }
  assert.ok(count>=40,'preserve bookmarks across rewritten installation and maintenance guides');
});

test('legacy anchors cannot inject markup or silently reference missing sections',()=>{
  assert.throws(()=>renderMarkdown('# Title',{legacyAnchors:{'bad" onclick="x':'Title'}}),/Invalid legacy anchor/);
  assert.throws(()=>renderMarkdown('# Title',{legacyAnchors:{old:'Absent'}}),/Missing legacy anchor target/);
  const native=renderMarkdown('# Title\n\n## Old',{legacyAnchors:{old:'Title'}});
  assert.equal([...native.html.matchAll(/id="old"/g)].length,1,'existing section wins over alias');
});

test('confirmed production origin and error pages retain navigation and local search',()=>{
  assert.equal(config.siteUrl,'https://tg2cloud.pages.dev');
  const page=renderPage({config,page:{title:'未找到',slug:''},notFound:true,hashes});
  assert.ok(page.includes('<meta name="robots" content="noindex">'));
  assert.ok(page.includes('href="/">返回文档首页'));
  assert.match(page,/<button[^>]*data-open-search>搜索文档<\/button>/);
  assert.ok(page.includes('https://tg2cloud.pages.dev/404.html'));
});
