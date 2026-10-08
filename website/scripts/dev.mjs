import {spawn} from 'node:child_process';
import {watch} from 'node:fs';
import {fileURLToPath} from 'node:url';
const cwd=fileURLToPath(new URL('../',import.meta.url));
let building=false,queued=false,timer;
async function build(){
  if(building){queued=true;return;}
  building=true;
  await new Promise(resolve=>{
    const p=spawn(process.execPath,['scripts/build.mjs'],{cwd,stdio:'inherit'});
    p.on('exit',code=>{if(code)console.error('Build failed; fix the error and save to retry.');resolve();});
  });
  building=false;
  if(queued){queued=false;await build();}
}
await build();
const preview=spawn(process.execPath,['scripts/serve.mjs'],{cwd,stdio:'inherit'});
for(const path of ['docs','src','public','scripts','site.config.json']){
  watch(new URL('../'+path,import.meta.url),{recursive:path!=='site.config.json'},()=>{
    clearTimeout(timer);timer=setTimeout(build,180);
  });
}
function stop(){preview.kill();process.exit();}
process.on('SIGINT',stop);process.on('SIGTERM',stop);
console.log('Watching Markdown, templates, assets and site config. Refresh your browser after a rebuild.');
