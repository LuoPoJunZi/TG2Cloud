import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

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
  ].map(name=>`${config.repo}/releases/download/v${config.publishedVersion}/${name}`);
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
    assert.deepEqual([...content.matchAll(/^git checkout (\S+)\r?$/gm)].map(match=>match[1]),[config.releaseStatus==='released'?`v${config.version}`:'main']);
  }
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
  for(const content of [download,guide,readme])assert.ok(content.includes(command));
  assert.ok(download.includes('只读预检'));
  assert.ok(download.includes('OpenList 脚本实机验收暂缓'));
});
