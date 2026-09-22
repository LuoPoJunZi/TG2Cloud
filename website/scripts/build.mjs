import {readFile,writeFile,mkdir,rm,cp} from 'node:fs/promises';
import {resolve,join,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {renderMarkdown,escapeHtml} from './markdown.mjs';
import {renderPage} from '../src/templates.mjs';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const dist=join(root,'dist');
const config=JSON.parse(await readFile(join(root,'site.config.json'),'utf8'));
const configuredUrl=(process.env.SITE_URL || config.siteUrl || '').trim();
if(configuredUrl){
  const parsed=new URL(configuredUrl);
  if(!['https:','http:'].includes(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash || parsed.pathname!=='/'){
    throw new Error('SITE_URL must be an http(s) origin, without credentials, a subpath, query or fragment.');
  }
  config.siteUrl=parsed.origin;
} else config.siteUrl='';
if(!/^\d+\.\d+\.\d+$/.test(config.version))throw new Error('Invalid documented version');

const pages=config.navigation.flatMap(group=>group.items.map(item=>({...item,group:group.title})));
if(new Set(pages.map(p=>p.slug)).size!==pages.length)throw new Error('Duplicate page route');
for(const page of pages)if(!/^[a-z0-9/-]+$/.test(page.slug)||page.slug.includes('..'))throw new Error('Invalid page slug');
await rm(dist,{recursive:true,force:true});
await mkdir(dist,{recursive:true});
await cp(join(root,'public'),dist,{recursive:true});
const hash=async path=>createHash('sha256').update(await readFile(join(dist,path))).digest('hex').slice(0,12);
const hashes={css:await hash('assets/style.css'),js:await hash('assets/app.js'),init:await hash('assets/theme-init.js')};
const searchIndex=[];
const cleanText=text=>text
 .replace(/\[([^\]]+)\]\([^)]+\)/g,'$1')
 .replace(/```[^\n]*\n/g,' ').replace(/:::[^\n]*|^[#>*-]+\s*/gm,' ')
 .replace(/[`*|]/g,' ').replace(/\s+/g,' ').trim();
for(let i=0;i<pages.length;i++){
  const page=pages[i];
  const markdown=await readFile(join(root,'docs',page.slug+'.md'),'utf8');
  const {html,headings}=renderMarkdown(markdown);
  if(headings.filter(h=>h.level===1).length!==1)throw new Error(`${page.slug}: must have one h1`);
  const lead=markdown.split('\n').find(line=>line.trim()&&!line.startsWith('#'));
  page.description=cleanText(lead || config.description).slice(0,180);
  const target=join(dist,page.slug,'index.html');
  await mkdir(dirname(target),{recursive:true});
  await writeFile(target,renderPage({config,page,body:html,headings,previous:pages[i-1],next:pages[i+1],hashes}));
  searchIndex.push({title:page.title,heading:page.group,url:`/${page.slug}/`,text:cleanText(markdown).slice(0,900)});
  // Index the entire article by h2 sections; no third-party search service.
  const sections=markdown.split(/^## /m).slice(1);
  const h2s=headings.filter(h=>h.level===2);
  sections.forEach((text,n)=>{
    const heading=h2s[n];if(!heading)return;
    searchIndex.push({title:page.title,heading:heading.title,url:`/${page.slug}/#${encodeURIComponent(heading.id)}`,text:cleanText(text)});
  });
}
await writeFile(join(dist,'index.html'),renderPage({config,page:{title:'首页',slug:''},home:true,hashes}));
await writeFile(join(dist,'404.html'),renderPage({config,page:{title:'页面未找到',slug:''},notFound:true,hashes}));
await writeFile(join(dist,'search-index.json'),JSON.stringify(searchIndex));
await writeFile(join(dist,'build-info.json'),JSON.stringify({
  site:'TG2Cloud Docs',documentedVersion:config.version,contentVerifiedAt:config.verifiedAt,
  articles:pages.length,searchRecords:searchIndex.length,siteUrl:config.siteUrl || null
},null,2));
let robots='User-agent: *\nAllow: /\n';
if(config.siteUrl){
  const urls=['/',...pages.map(p=>`/${p.slug}/`)];
  await writeFile(join(dist,'sitemap.xml'),'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+urls.map(path=>`<url><loc>${escapeHtml(config.siteUrl+path)}</loc><lastmod>${config.verifiedAt}</lastmod></url>`).join('\n')+'\n</urlset>\n');
  robots+=`Sitemap: ${config.siteUrl}/sitemap.xml\n`;
}
await writeFile(join(dist,'robots.txt'),robots);
await writeFile(join(dist,'llms.txt'),`# TG2Cloud Docs\n\nDocumented release: ${config.version}\nContent verified: ${config.verifiedAt}\nProject: ${config.repo}\n\n`+pages.map(p=>`- [${p.title}](${config.siteUrl}/${p.slug}/)`).join('\n')+'\n');
console.log(`Built ${pages.length} articles + homepage + 404, ${searchIndex.length} local search records.`);
console.log(`Output: ${dist}`);
console.log(config.siteUrl?`Canonical origin: ${config.siteUrl}`:'SITE_URL is unset: no invented canonical URL or sitemap was generated.');
