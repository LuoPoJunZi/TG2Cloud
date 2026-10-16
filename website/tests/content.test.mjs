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
  const source=await readFile(new URL('../../payload_clouddrive2/app/version.py',import.meta.url),'utf8');
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
  for(const path of ['scripts/lib/deployer_products.py','.github/CONTRIBUTING.md','.github/SECURITY.md']){
    assert.ok(template.includes(`'${path}'`));
    assert.ok(await readFile(new URL('../../'+path,import.meta.url),'utf8'));
  }
  assert.ok(guide.includes('scripts/lib/vps_resources.py'));
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
