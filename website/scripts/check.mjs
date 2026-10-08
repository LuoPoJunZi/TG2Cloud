import {readFile,readdir,stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {join,extname} from 'node:path';
const root=fileURLToPath(new URL('../dist/',import.meta.url));
async function walk(path){
  const out=[];for(const entry of await readdir(path,{withFileTypes:true})){
    const full=join(path,entry.name);if(entry.isDirectory())out.push(...await walk(full));else out.push(full);
  }return out;
}
const files=await walk(root),cache=new Map(),errors=[];
const htmlFiles=files.filter(f=>extname(f)==='.html');
for(const f of htmlFiles)cache.set(f,await readFile(f,'utf8'));
let links=0;
for(const [file,html] of cache){
  if(!html.includes('lang="zh-CN"'))errors.push(`${file}: missing language`);
  if(!html.includes('<h1'))errors.push(`${file}: missing h1`);
  const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
  if(new Set(ids).size!==ids.length)errors.push(`${file}: duplicate IDs`);
  for(const match of html.matchAll(/\b(?:href|src)="([^"]+)"/g)){
    const href=match[1].replaceAll('&amp;','&');
    if(!href.startsWith('/')&&!href.startsWith('#'))continue;
    links++;
    const u=new URL(href,'https://docs.local/'+file.slice(root.length).replaceAll('\\','/'));
    let path=decodeURIComponent(u.pathname),target=join(root,path);
    try{
      const info=await stat(target);if(info.isDirectory())target=join(target,'index.html');
      await stat(target);
      if(u.hash && extname(target)==='.html'){
        const text=cache.get(target)||await readFile(target,'utf8');
        const id=decodeURIComponent(u.hash.slice(1));
        if(!text.includes(`id="${id}"`))errors.push(`${file}: missing anchor ${href}`);
      }
    }catch{errors.push(`${file}: missing local target ${href}`);}
  }
}
const index=JSON.parse(await readFile(join(root,'search-index.json'),'utf8'));
for(const term of ['401','429','CloudDrive2','OpenList','known_hosts','LOCAL_TEMP_BUDGET_GB']){
  if(!index.some(row=>JSON.stringify(row).includes(term)))errors.push(`Search index missing ${term}`);
}
if(errors.length){console.error(errors.join('\n'));process.exit(1);}
console.log(`PASS: ${htmlFiles.length} HTML pages, ${links} local links/assets/anchors, ${index.length} search entries.`);
