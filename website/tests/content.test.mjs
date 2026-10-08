import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const read=path=>readFile(new URL('../'+path,import.meta.url),'utf8');
const config=JSON.parse(await read('site.config.json'));

test('documented version and verification date are valid',()=>{
  assert.match(config.version,/^\d+\.\d+\.\d+$/);
  assert.match(config.verifiedAt,/^\d{4}-\d{2}-\d{2}$/);
  assert.equal(new Date(config.verifiedAt).toISOString().slice(0,10),config.verifiedAt);
});

test('download assets and source checkout match the documented release',async()=>{
  const download=await read('docs/download.md');
  const links=[...download.matchAll(/\]\((https:\/\/[^\s)]+\/releases\/download\/[^\s)]+)\)/g)].map(match=>match[1]);
  const expected=[
    'TG2Cloud-CloudDrive2-Deployer.exe',
    'TG2Cloud-OpenList-Deployer.exe',
    'SHA256SUMS.txt'
  ].map(name=>`${config.repo}/releases/download/v${config.version}/${name}`);
  assert.deepEqual(links.sort(),expected.sort());
  assert.ok(download.includes(`${config.repo}/releases/tag/v${config.version}`));
  assert.ok(download.includes(`**TG2Cloud v${config.version}**`));
  for(const path of ['docs/download.md','docs/reference/development.md']){
    const content=await read(path);
    assert.deepEqual([...content.matchAll(/^git checkout (\S+)\r?$/gm)].map(match=>match[1]),[`v${config.version}`]);
  }
});

test('latest changelog entry matches the documented release',async()=>{
  const changelog=await read('docs/changelog.md');
  const latest=changelog.match(/^## TG2Cloud v(\d+\.\d+\.\d+)\r?$/m);
  assert.equal(latest?.[1],config.version);
  assert.ok(changelog.includes(`${config.repo}/releases/tag/v${config.version}`));
});

test('content source metadata matches the site configuration',async()=>{
  for(const path of ['README.md','THIRD_PARTY_NOTICES.md']){
    const content=await read(path);
    assert.ok(content.includes(`TG2Cloud v${config.version}`),path);
    assert.ok(content.includes(config.verifiedAt),path);
  }
  const sources=await read('docs/reference/sources.md');
  assert.ok(sources.includes(`**v${config.version}**`));
  assert.ok(sources.includes(`${config.repo}/releases/tag/v${config.version}`));
  const [year,month,day]=config.verifiedAt.split('-').map(Number);
  assert.ok(sources.includes(`**${year} 年 ${month} 月 ${day} 日**`));
});
