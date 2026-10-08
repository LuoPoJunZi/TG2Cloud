// Local-only preview server. Production deployment uses static files, not this server.
import http from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import {resolve,join,extname,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../dist/',import.meta.url));
const args=process.argv.slice(2);
const flag=args.indexOf('--port');
const port=Number(flag>=0?args[flag+1]:(process.env.PORT||4173));
if(!Number.isInteger(port)||port<1||port>65535)throw new Error('Invalid port');
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml','.png':'image/png','.webp':'image/webp','.jpg':'image/jpeg','.xml':'application/xml; charset=utf-8','.txt':'text/plain; charset=utf-8'};
try{await stat(join(root,'index.html'));}catch{console.error('Build the site first: npm run build');process.exit(1);}
const server=http.createServer(async(req,res)=>{
  if(!['GET','HEAD'].includes(req.method)){res.writeHead(405,{'Allow':'GET, HEAD'});res.end();return;}
  let pathname;
  try{pathname=decodeURIComponent(new URL(req.url,'http://127.0.0.1').pathname);}catch{res.writeHead(400);res.end('Bad request');return;}
  if(pathname.includes('\0')||pathname.includes('\\')){res.writeHead(400);res.end();return;}
  let target=resolve(root,'.'+pathname);
  if(target!==resolve(root)&&!target.startsWith(resolve(root)+sep)){res.writeHead(403);res.end();return;}
  try{
    const info=await stat(target);
    if(info.isDirectory()){
      if(!pathname.endsWith('/')){
        res.writeHead(308,{Location:encodeURI(pathname+'/')});res.end();return;
      }
      target=join(target,'index.html');
    }
    const bytes=await readFile(target);
    res.writeHead(200,{'Content-Type':mime[extname(target)]||'application/octet-stream','Cache-Control':'no-cache','X-Content-Type-Options':'nosniff'});
    res.end(req.method==='HEAD'?undefined:bytes);
  }catch{
    const bytes=await readFile(join(root,'404.html'));
    res.writeHead(404,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-cache'});
    res.end(req.method==='HEAD'?undefined:bytes);
  }
});
server.on('error',error=>{console.error(error.message);process.exit(1);});
server.listen(port,'127.0.0.1',()=>console.log(`TG2Cloud Docs preview: http://127.0.0.1:${port}\nPress Ctrl+C to stop.`));
