import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';

const read=path=>readFile(new URL('../'+path,import.meta.url),'utf8');
const config=JSON.parse(await read('site.config.json'));

test('documented version and verification date are valid',()=>{
  assert.match(config.version,/^\d+\.\d+\.\d+$/);
  assert.match(config.publishedVersion,/^\d+\.\d+\.\d+$/);
  assert.ok(['released','unreleased'].includes(config.releaseStatus));
  const source=config.version.split('.').map(Number);
  const published=config.publishedVersion.split('.').map(Number);
  const difference=source.map((part,index)=>part-published[index]).find(part=>part!==0)||0;
  assert.ok(config.releaseStatus==='released'?difference===0:difference>0);
  assert.match(config.verifiedAt,/^\d{4}-\d{2}-\d{2}$/);
  assert.equal(new Date(config.verifiedAt).toISOString().slice(0,10),config.verifiedAt);
});

test('package and shared product versions match the documented source',async()=>{
  const pkg=JSON.parse(await read('package.json'));
  const lock=JSON.parse(await read('package-lock.json'));
  const source=await readFile(new URL('../../src/tg2cloud/version.py',import.meta.url),'utf8');
  assert.deepEqual([...source.matchAll(/^VERSION\s*=\s*"([^"]+)"\r?$/gm)].map(match=>match[1]),[config.version]);
  assert.equal(pkg.version,config.version);
  assert.equal(lock.version,config.version);
  assert.equal(lock.packages[''].version,config.version);
});

test('downloads point to published assets and source checkout respects release status',async()=>{
  const download=await read('docs/download.md');
  const links=[...download.matchAll(/\]\((https:\/\/[^\s)]+\/releases\/download\/[^\s)]+)\)/g)].map(match=>match[1]);
  const expected=[
    'TG2Cloud-CloudDrive2-Deployer.exe',
    'TG2Cloud-OpenList-Deployer.exe',
    'SHA256SUMS.txt'
  ].map(name=>`${config.repo}/releases/download/v1.2.1/${name}`);
  const [major,minor]=config.publishedVersion.split('.').map(Number);
  if(major>1 || (major===1 && minor>=3)){
    expected.push(...[`TG2Cloud-v${config.publishedVersion}-source.tar.gz`,'SHA256SUMS.txt']
      .map(name=>`${config.repo}/releases/download/v${config.publishedVersion}/${name}`));
  }
  assert.deepEqual(links.sort(),expected.sort());
  assert.ok(download.includes(`${config.repo}/releases/tag/v${config.publishedVersion}`));
  assert.ok(download.includes(`**TG2Cloud v${config.version}**`));
  if(config.releaseStatus==='unreleased'){
    assert.ok(download.includes('待发布'));
    assert.ok(!download.includes(`${config.repo}/releases/tag/v${config.version}`));
    assert.ok(!download.includes(`${config.repo}/releases/download/v${config.version}/`));
  }
  for(const path of ['docs/download.md','docs/reference/development.md']){
    const content=await read(path);
    const checkout=path==='docs/download.md'?'v1.2.1':(config.releaseStatus==='released'?`v${config.version}`:'main');
    const sections=content.split('## 恢复 v1.2.1 历史部署器构建');
    assert.deepEqual([...sections[0].matchAll(/^git checkout (\S+)\r?$/gm)].map(match=>match[1]),[checkout]);
    if(path==='docs/reference/development.md'){
      assert.equal(sections.length,2);
      assert.deepEqual([...sections[1].matchAll(/^git checkout (\S+)\r?$/gm)].map(match=>match[1]),['v1.2.1']);
      assert.ok(sections[0].includes('git switch main'));
      assert.ok(!sections[0].includes('requirements-build.txt'));
    }
  }
});

test('developer source links follow the public script-only layout',async()=>{
  const template=await read('src/templates.mjs');
  const guide=await read('docs/reference/development.md');
  for(const path of ['src/tg2cloud/deployment/profiles.py','.github/CONTRIBUTING.md','.github/SECURITY.md']){
    assert.ok(template.includes(`'${path}'`));
    assert.ok(await readFile(new URL('../../'+path,import.meta.url),'utf8'));
  }
  assert.ok(guide.includes('src/tg2cloud/deployment/resources.py'));
  assert.ok(!guide.includes('legacy/desktop/'));
});

test('latest changelog entry matches source version without claiming an unpublished release',async()=>{
  const changelog=await read('docs/changelog.md');
  const latest=changelog.match(/^## TG2Cloud v(\d+\.\d+\.\d+)\r?$/m);
  assert.equal(latest?.[1],config.version);
  assert.ok(changelog.includes(`${config.repo}/releases/tag/v${config.publishedVersion}`));
  if(config.releaseStatus==='unreleased'){
    const current=changelog.split(/^## /m)[1];
    assert.ok(current.includes('待发布'));
    assert.ok(current.includes(`${config.repo}/blob/main/CHANGELOG.md`));
    assert.ok(!changelog.includes(`${config.repo}/releases/tag/v${config.version}`));
  }
});

test('management menu matches source labels and keeps old-version boundaries',async()=>{
  const source=await readFile(new URL('../../src/tg2cloud/cli/management.py',import.meta.url),'utf8');
  const items=source.match(/MENU_ITEMS = \(([\s\S]*?)\r?\n\)/)?.[1];
  assert.ok(items);
  const entries=[...items.matchAll(/\((\d+), "([^"]+)"\)/g)].map(match=>[match[1],match[2]]);
  assert.deepEqual(entries.map(([number])=>number),[...Array.from({length:14},(_,index)=>String(index+1)),'0']);
  const article=await read('docs/operations/maintenance.md');
  const guide=await readFile(new URL('../../docs/OPERATIONS.md',import.meta.url),'utf8');
  for(const [number,label] of entries){
    assert.ok(article.includes(`${(number+'.').padEnd(3)} ${label}`),label);
    assert.ok(guide.includes(`| ${number} | ${label} |`),label);
  }
  for(const text of ['v1.4.4 菜单','旧版 v1.4.3','更新文档不会更新 VPS','tg2cloud naming-preview']){
    assert.ok(article.includes(text),text);
  }
  assert.ok(!entries.some(([,label])=>label.includes('命名预览')));
});

test('installation feedback distinguishes evidence from manual acceptance',async()=>{
  const update=await read('docs/operations/update.md');
  for(const text of ['v1.4.4','旧 v1.4.3 工具不包含新增反馈','[信息]','[提醒]','[待核对]','[错误]','20 秒',
                    'WebDAV 写入与大小复验：未执行','实际 Telegram 转存：待人工验收',
                    '公网访问：待外部网络验收','原命令退出码','用户中断时不追加读取']){
    assert.ok(update.includes(text),text);
  }
  const guide=await readFile(new URL('../../docs/OPERATIONS.md',import.meta.url),'utf8');
  for(const text of ['v1.4.4','显式参数模式的 `TG2CLOUD_*` 标记保持原样',
                    '不持久化原日志','不新增生产数据库字段','不因就绪未确认自动重启或回退']){
    assert.ok(guide.includes(text),text);
  }
  const faq=await read('docs/faq.md');
  assert.ok(faq.includes('旧工具须显式升级后使用'));
});

test('content source metadata matches the site configuration',async()=>{
  for(const path of ['README.md','THIRD_PARTY_NOTICES.md']){
    const content=await read(path);
    assert.ok(content.includes(`TG2Cloud v${config.version}`),path);
    assert.ok(content.includes(config.verifiedAt),path);
  }
  const sources=await read('docs/reference/sources.md');
  assert.ok(sources.includes(`**v${config.version}**`));
  assert.ok(sources.includes(`${config.repo}/releases/tag/v${config.publishedVersion}`));
  if(config.releaseStatus==='unreleased'){
    assert.ok(sources.includes('待发布'));
    assert.ok(!sources.includes(`${config.repo}/releases/tag/v${config.version}`));
  }
  const [year,month,day]=config.verifiedAt.split('-').map(Number);
  assert.ok(sources.includes(`**${year} 年 ${month} 月 ${day} 日**`));
});

test('VPS one-line entry is consistent with the root user guide',async()=>{
  const command='bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/install.sh)';
  const download=await read('docs/download.md');
  const guide=await readFile(new URL('../../docs/VPS-INSTALL.md',import.meta.url),'utf8');
  const readme=await readFile(new URL('../../README.md',import.meta.url),'utf8');
  const english=await readFile(new URL('../../README_EN.md',import.meta.url),'utf8');
  for(const content of [download,guide,readme,english])assert.ok(content.includes(command));
  assert.ok(download.includes('只读预检'));
  assert.ok(download.includes('OpenList 脚本实机验收暂缓'));
});

test('independent LAN and uninstall entries agree with root guides',async()=>{
  const download=await read('docs/download.md');
  const readme=await readFile(new URL('../../README.md',import.meta.url),'utf8');
  const english=await readFile(new URL('../../README_EN.md',import.meta.url),'utf8');
  for(const [script,guide] of [['install-lan.sh','LAN-INSTALL.md'],['uninstall.sh','UNINSTALL.md']]){
    const command=`bash <(curl -fsSL https://raw.githubusercontent.com/LuoPoJunZi/TG2Cloud/main/${script})`;
    const source=await readFile(new URL(`../../docs/${guide}`,import.meta.url),'utf8');
    for(const content of [download,readme,english,source])assert.ok(content.includes(command),script);
  }
  assert.ok(download.includes('卸载不是升级步骤'));
  assert.ok(download.includes('完整清理增强仍待新的实机验收'));
  assert.ok(download.includes('v1.2.0 Tag'));
  assert.ok(download.includes('--keep-data'));
  assert.ok(download.includes('不等于把 VPS 恢复到安装前'));
  const uninstallCommands=download.match(/^bash .*\/uninstall\.sh\).*$/gm)||[];
  assert.ok(uninstallCommands.length>0);
  assert.ok(uninstallCommands.every(command=>command.includes('--check')));
});

test('website brand copies match the canonical repository assets byte for byte',async()=>{
  const pairs=[
    ['tg2cloud.ico','favicon.ico'],
    ...['tg2cloud-icon.svg','tg2cloud-icon-32.png','tg2cloud-icon-64.png','tg2cloud-icon-256.png']
      .map(name=>[name,`assets/${name}`])
  ];
  const digest=buffer=>createHash('sha256').update(buffer).digest('hex');
  for(const [canonical,copy] of pairs){
    const original=await readFile(new URL(`../../assets/brand/${canonical}`,import.meta.url));
    const website=await readFile(new URL(`../public/${copy}`,import.meta.url));
    assert.equal(digest(website),digest(original),`${copy} must be copied unchanged from assets/brand/${canonical}`);
  }
});

test('v1.3.0 acceptance separates checked migration, user feedback and untested scenarios',async()=>{
  const path='docs/development/V130-ACCEPTANCE.md';
  const record=await readFile(new URL('../../'+path,import.meta.url),'utf8');
  for(const text of ['2026-10-17','旧测试候选','人工核对','用户确认','OpenList 脚本实机验收暂缓',
    '不提供强制覆盖参数','回退故障注入','下载目录为空','WebDAV 大小校验不等于内容哈希校验']){
    assert.ok(record.includes(text),text);
  }
  const index=await readFile(new URL('../../docs/README.md',import.meta.url),'utf8');
  assert.ok(index.includes('(development/V130-ACCEPTANCE.md)'));
  const notes=await readFile(new URL('../../RELEASE_NOTES.md',import.meta.url),'utf8');
  assert.ok(notes.includes(path),'release notes retain the historical acceptance link');
  for(const name of ['docs/download.md','docs/operations/update.md','docs/changelog.md','docs/reference/sources.md']){
    assert.ok((await read(name)).includes(`${config.repo}/blob/main/${path}`),name);
  }
});

test('v1.4.3 log review keeps user evidence, warnings and unverified scopes separate',async()=>{
  const path='docs/development/V143-ACCEPTANCE.md';
  const record=await readFile(new URL('../../'+path,import.meta.url),'utf8');
  for(const value of ['证据来源：用户提供的升级日志','没有独立登录','v1.4.2 → v1.4.3',
    'TG2CLOUD_DATABASE_BACKUP=OK','TG2CLOUD_CODE=OK','TG2CLOUD_BOT_HEALTH=healthy',
    'TG2CLOUD_RESULT=SUCCESS','Running pip as the','ca-certificates.crt','SYS_UID_MAX',
    '50GB','尚未确认与仍需验收','独立 SQL 查询'])assert.ok(record.includes(value),value);
  assert.doesNotMatch(record,/root@|\b(?:\d{1,3}\.){3}\d{1,3}\b/,'do not publish raw host prompts or IP addresses');
  for(const name of ['CHANGELOG.md','RELEASE_NOTES.md',
    'docs/README.md','docs/FAQ.md','docs/VPS-INSTALL.md']){
    const content=await readFile(new URL('../../'+name,import.meta.url),'utf8');
    assert.ok(content.includes('V143-ACCEPTANCE.md'),name);
  }
  for(const name of ['docs/operations/update.md','docs/faq.md','docs/download.md',
    'docs/changelog.md','docs/reference/sources.md']){
    assert.ok((await read(name)).includes(`${config.repo}/blob/main/${path}`),name);
  }
});

test('v1.4.4 dual-architecture acceptance keeps upgrade evidence separate from unrun business checks',async()=>{
  const path='docs/development/V144-ACCEPTANCE.md';
  const record=await readFile(new URL('../../'+path,import.meta.url),'utf8');
  for(const value of ['2026-10-23','证据来源：用户提供的两份升级日志','两份升级测试验收已通过',
    '没有独立登录','Ubuntu 26.04.1 LTS','Debian GNU/Linux 13','linux/arm64','linux/amd64',
    'v1.4.3 → v1.4.4','TG2CLOUD_CONFIG=PRESERVED','TG2CLOUD_DATABASE_BACKUP=OK',
    'TG2CLOUD_CODE=OK','TG2CLOUD_VERSION=1.4.4','TG2CLOUD_BOT_HEALTH=healthy',
    'TG2CLOUD_RESULT=SUCCESS','最近业务就绪观察','原 .env 保留：通过','50GB','[提醒]','CACHED',
    'WebDAV 写入与大小复验：未执行','实际 Telegram 转存：待人工验收','公网访问：待外部网络验收',
    '独立 SQL 查询','OpenList','不修改 v1.4.4 Tag'])assert.ok(record.includes(value),value);
  assert.doesNotMatch(record,/root@|\b(?:\d{1,3}\.){3}\d{1,3}\b|config-[A-Za-z0-9]{8,}\.tar\.gz/,
    'do not publish raw host prompts, IP addresses or private backup names');
  for(const name of ['README.md','README_EN.md','CHANGELOG.md','RELEASE_NOTES.md','docs/README.md',
    'docs/VPS-INSTALL.md','docs/OPERATIONS.md','docs/FAQ.md','docs/ARCHITECTURES.md',
    'docs/development/DOMAIN-HTTPS-ACCEPTANCE.md']){
    const content=await readFile(new URL('../../'+name,import.meta.url),'utf8');
    assert.ok(content.includes('V144-ACCEPTANCE.md'),name);
  }
  for(const name of ['docs/operations/update.md','docs/faq.md','docs/download.md',
    'docs/changelog.md','docs/reference/sources.md']){
    assert.ok((await read(name)).includes(`${config.repo}/blob/main/${path}`),name);
  }
  assert.ok((await read('README.md')).includes('../'+path));
  assert.ok((await read('THIRD_PARTY_NOTICES.md')).includes(`${config.repo}/blob/main/${path}`));
});

test('current helper identity in installation docs matches every public entry',async()=>{
  const guide=await readFile(new URL('../../docs/VPS-INSTALL.md',import.meta.url),'utf8');
  const removal=await readFile(new URL('../../docs/UNINSTALL.md',import.meta.url),'utf8');
  const english=await readFile(new URL('../../README_EN.md',import.meta.url),'utf8');
  const chinese=await readFile(new URL('../../README.md',import.meta.url),'utf8');
  const development=await read('docs/reference/development.md');
  const pins=[];
  for(const name of ['install.sh','install-lan.sh','uninstall.sh']){
    const entry=await readFile(new URL('../../'+name,import.meta.url),'utf8');
    const matches=[...entry.matchAll(/^installer_commit\s*=\s*"([0-9a-f]{40})"\r?$/gm)];
    assert.equal(matches.length,1,name);
    pins.push(matches[0][1]);
  }
  assert.equal(new Set(pins).size,1);
  // Exact helper identities belong in the full guides. Landing pages must link
  // to both guides instead of copying internal commit details into the overview.
  for(const [name,content] of [['VPS guide',guide],['uninstall',removal],['website development',development]]){
    assert.ok(content.includes('`'+pins[0]+'`'),name);
  }
  for(const [name,content] of [['English README',english],['Chinese README',chinese]]){
    for(const guide of ['VPS-INSTALL.md','UNINSTALL.md']){
      assert.ok(content.includes('](docs/'+guide+')'),name+': '+guide);
    }
  }
  const recovery=await readFile(new URL('../../docs/RECOVERY.md',import.meta.url),'utf8');
  assert.ok(!guide.includes('新布局尚未发布'));
  assert.ok(!development.includes('新布局只完成本地候选准备'));
  assert.ok(!recovery.includes('尚未进入 v1.3.0 Release'));
});

test('root READMEs use topic navigation while the documentation index retains acceptance history',async()=>{
  const index=await readFile(new URL('../../docs/README.md',import.meta.url),'utf8');
  for(const version of ['130','133','141','142','143','144']){
    assert.ok(index.includes(`(development/V${version}-ACCEPTANCE.md)`),version+': historical record remains discoverable');
  }
  for(const [name,heading] of [['README.md','## 使用文档'],['README_EN.md','## Documentation']]){
    const content=await readFile(new URL('../../'+name,import.meta.url),'utf8');
    const start=content.indexOf(heading);
    assert.ok(start>=0,name+': documentation section');
    const section=content.slice(start+heading.length).split(/\r?\n## /)[0];
    for(const target of ['docs/README.md','RELEASE_NOTES.md','docs/FEATURE-ENHANCEMENTS.md',
      'docs/DOCKER-NGINX.md','docs/development/MAINTENANCE-IMPROVEMENTS.md',
      'docs/development/V144-ACCEPTANCE.md']){
      assert.ok(section.includes('('+target+')'),name+': topic link '+target);
    }
    const paragraphs=section.split(/\r?\n\s*\r?\n/).map(block=>block.trim())
      .filter(block=>block&&!block.startsWith('|'));
    assert.equal(paragraphs.length,1,name+': documentation section has one introduction followed by topic navigation');
    assert.doesNotMatch(content,/2026-10-23/,name+': dated upgrade evidence belongs in the linked records');
  }
});

test('root READMEs keep repository-first documentation and the original attribution layout',async()=>{
  const base='https://tg2cloud.pages.dev/';
  for(const name of ['README.md','README_EN.md']){
    const content=await readFile(new URL('../../'+name,import.meta.url),'utf8');
    assert.ok(content.includes(base),name+': documentation home');
    assert.ok(content.includes('href="docs/README.md"'),name+': repository index');
    assert.ok(content.includes('assets/brand/tg2cloud-logo.svg'),name+': canonical brand');
    assert.ok(content.includes('https://github.com/whyhhh20/TG115'),name+': upstream credit');
    for(const target of ['LICENSE','.github/CONTRIBUTING.md','.github/SECURITY.md',
      'docs/VPS-INSTALL.md','docs/LAN-INSTALL.md','docs/填写信息清单.md','docs/OPERATIONS.md',
      'docs/RECOVERY.md','docs/UNINSTALL.md','docs/MIGRATION_FROM_TG115.md',
      'docs/development/REPOSITORY.md','docs/development/LINUX-REFACTOR.md','CHANGELOG.md','RELEASE_NOTES.md']){
      assert.ok(content.includes('('+target+')'),name+': direct repository link '+target);
    }
    const attribution=name==='README.md'?'## 致谢与项目来源':'## Acknowledgements and Project Origin';
    const license=name==='README.md'?'## 许可证与免责声明':'## License and Disclaimer';
    const credits=content.slice(content.indexOf(attribution),content.indexOf(license));
    assert.ok(content.includes(attribution),name+': attribution heading');
    assert.ok(content.includes(license),name+': separate license section');
    assert.match(credits,/<table>[\s\S]*<\/table>/,name+': author table');
    assert.equal([...credits.matchAll(/<td align="center" width="50%">/g)].length,2,name+': two author columns');
    for(const author of ['LuoPoJunZi','whyhhh20']){
      assert.ok(credits.includes(`src="https://github.com/${author}.png?size=96" width="72"`),name+': original author avatar');
    }
    const links=[...content.matchAll(/\]\(([^)]+)\)|\b(?:href|src)="([^"]+)"/g)]
      .map(match=>match[1]||match[2]);
    for(const href of links){
      assert.ok(!href.startsWith('website/'),name+': do not link website source files as user guides');
      if(href.startsWith(base)){
        assert.equal(href,base,name+': article navigation must open repository documents');
      }else if(!/^(?:https?:|#)/.test(href)){
        assert.ok(await readFile(new URL('../../'+href,import.meta.url)),name+': missing local link '+href);
      }
    }
    const removal=content.match(/^bash .*\/uninstall\.sh\).*$/gm)||[];
    assert.ok(removal.length>0,name+': removal preview');
    assert.ok(removal.every(command=>command.includes('--check')),name+': no immediate removal in the landing page');
    assert.ok(content.includes('--keep-data'),name+': data-preservation option');
  }
});
