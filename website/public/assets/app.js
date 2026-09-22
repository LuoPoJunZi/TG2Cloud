(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const root = document.documentElement;
  const themeButton = $('.theme-toggle');
  function updateThemeLabel() {
    const isDark = root.dataset.theme === 'dark';
    themeButton?.setAttribute('aria-label', isDark ? '切换浅色主题' : '切换深色主题');
    themeButton?.setAttribute('aria-pressed', String(isDark));
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', isDark ? '#111824' : '#f8faff');
  }
  updateThemeLabel();
  themeButton?.addEventListener('click', () => {
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    try { localStorage.setItem('tg2cloud-theme', root.dataset.theme); } catch {}
    updateThemeLabel();
  });
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
  systemTheme.addEventListener('change', (event) => {
    let saved; try { saved = localStorage.getItem('tg2cloud-theme'); } catch {}
    if (!saved) { root.dataset.theme = event.matches ? 'dark' : 'light'; updateThemeLabel(); }
  });

  const version = $('.version-menu');
  document.addEventListener('click', (event) => {
    if (version?.open && !version.contains(event.target)) version.open = false;
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && version?.open) {
      version.open = false; version.querySelector('summary').focus();
    }
  });

  let toastTimer;
  function toast(message) {
    const el = $('#toast'); el.textContent = message; el.classList.add('visible');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('visible'), 2200);
  }
  $$('.copy-code').forEach(button => button.addEventListener('click', async () => {
    const text = button.closest('.code-block').querySelector('code').textContent;
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else {
        const textarea = document.createElement('textarea');
        textarea.value = text; textarea.style.position = 'fixed'; textarea.style.opacity = '0';
        document.body.append(textarea); textarea.select();
        const copied = document.execCommand('copy'); textarea.remove();
        if (!copied) throw new Error('copy blocked');
      }
      button.textContent = '已复制'; toast('代码已复制');
      setTimeout(() => { button.textContent = '复制'; }, 1800);
    } catch { toast('浏览器禁止自动复制，请手动选中代码复制。'); }
  }));

  const mobileNav = $('#mobile-nav-dialog');
  const searchDialog = $('#search-dialog');
  let returnFocus;
  function openDialog(dialog, trigger) {
    if (dialog.open) return;
    returnFocus = trigger || document.activeElement;
    dialog.showModal(); document.body.classList.add('no-scroll');
  }
  function closeDialog(dialog) { if (dialog.open) dialog.close(); }
  [mobileNav,searchDialog].forEach(dialog => {
    dialog.addEventListener('close', () => {
      document.body.classList.remove('no-scroll');
      if (returnFocus instanceof HTMLElement && returnFocus.isConnected) returnFocus.focus();
    });
    dialog.addEventListener('click', event => {
      const box = dialog.getBoundingClientRect();
      if (event.target === dialog && (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom)) closeDialog(dialog);
    });
  });
  $$('.mobile-nav-toggle').forEach(button => button.addEventListener('click', () => openDialog(mobileNav,button)));
  $('[data-close-nav]').addEventListener('click', () => closeDialog(mobileNav));
  $$('#mobile-nav-dialog a').forEach(a => a.addEventListener('click', () => closeDialog(mobileNav)));

  // Search is completely local. JSON is loaded only when the dialog is first used.
  const input = $('#search-input'), results = $('#search-results'), status = $('.search-status');
  let searchData = null, searchPromise = null, activeIndex = -1;
  const defaultPaths = ['/guide/quick-start/','/deploy/clouddrive2/','/deploy/openlist/','/usage/commands/','/faq/','/operations/migration/'];
  async function loadIndex() {
    if (searchData) return searchData;
    if (!searchPromise) {
      searchPromise = fetch('/search-index.json').then(response => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      }).then(data => { searchData = data; return data; })
        .catch(error => { searchPromise = null; throw error; });
    }
    return searchPromise;
  }
  function score(item, tokens) {
    const title = item.title.toLowerCase(), heading = item.heading.toLowerCase(), text = item.text.toLowerCase();
    if (!tokens.every(token => `${title} ${heading} ${text}`.includes(token))) return 0;
    return tokens.reduce((n,t) => n + (title.includes(t)?30:0) + (heading.includes(t)?18:0) + (text.includes(t)?2:0),0);
  }
  function selectResult(index, scroll=true) {
    const links = $$('.search-result');
    if (!links.length) { activeIndex = -1; return; }
    activeIndex = (index + links.length) % links.length;
    links.forEach((link,i) => link.classList.toggle('is-selected', i === activeIndex));
    if (scroll) links[activeIndex].scrollIntoView({block:'nearest'});
  }
  function createResult(item, tokens=[]) {
    const a = document.createElement('a');
    a.className = 'search-result'; a.href = item.url; a.setAttribute('role','listitem');
    const title = document.createElement('div'); title.className='result-heading'; title.textContent=item.title;
    if (item.heading && item.heading !== item.title) {
      const span = document.createElement('span'); span.className='result-section'; span.textContent=item.heading;
      title.append(span);
    }
    const p=document.createElement('p'); p.className='result-excerpt';
    const lower=item.text.toLowerCase(); const positions=tokens.map(t=>lower.indexOf(t)).filter(n=>n>=0);
    const start=positions.length?Math.max(0,Math.min(...positions)-23):0;
    p.textContent=(start?'…':'')+item.text.slice(start,start+100)+(item.text.length>start+100?'…':'');
    a.append(title,p);
    a.addEventListener('click',()=>closeDialog(searchDialog));
    a.addEventListener('mouseenter',()=>selectResult($$('.search-result').indexOf(a),false));
    return a;
  }
  function renderResults() {
    if (!searchData) return;
    const query=input.value.trim().toLowerCase(); results.replaceChildren(); activeIndex=-1;
    if (!query) {
      status.textContent='常用入口';
      defaultPaths.forEach(path=>{
        const item=searchData.find(row=>row.url===path);
        if (item) results.append(createResult(item));
      });
      selectResult(0,false); return;
    }
    const tokens=query.split(/\s+/).filter(Boolean).slice(0,8);
    const candidates=searchData.map(item=>({item,score:score(item,tokens)})).filter(row=>row.score>0).sort((a,b)=>b.score-a.score);
    const countPerPage=new Map();
    const matches=candidates.filter(({item})=>{
      const base=item.url.split('#')[0],n=countPerPage.get(base)||0;
      if(n>=2)return false; countPerPage.set(base,n+1);return true;
    });
    status.textContent=matches.length?`找到 ${matches.length} 条相关内容${matches.length>20?'，显示前 20 条':''}`:'未找到相关内容';
    if (!matches.length) {
      const p=document.createElement('p');p.className='search-empty';p.textContent='试试“WebDAV”“401”“SSH”“预算”，或减少关键词。';results.append(p);return;
    }
    matches.slice(0,20).forEach(({item})=>results.append(createResult(item,tokens)));
    selectResult(0,false);
  }
  async function openSearch(trigger) {
    if (mobileNav.open) closeDialog(mobileNav);
    openDialog(searchDialog,trigger);
    input.focus();
    status.textContent=searchData?'常用入口':'正在加载本地索引…';
    try { await loadIndex(); if (searchDialog.open) renderResults(); }
    catch { status.textContent='搜索索引加载失败，请刷新后重试。'; results.replaceChildren(); }
  }
  $$('[data-open-search]').forEach(button=>button.addEventListener('click',()=>openSearch(button)));
  $('[data-close-search]').addEventListener('click',()=>closeDialog(searchDialog));
  input.addEventListener('input',renderResults);
  searchDialog.addEventListener('keydown',event=>{
    if(event.key==='ArrowDown'){event.preventDefault();selectResult(activeIndex+1);}
    if(event.key==='ArrowUp'){event.preventDefault();selectResult(activeIndex-1);}
    if(event.key==='Enter' && event.target===input){
      const item=$$('.search-result')[activeIndex];if(item){event.preventDefault();item.click();}
    }
  });
  document.addEventListener('keydown',event=>{
    const editable = event.target instanceof HTMLElement && (event.target.matches('input,textarea,select') || event.target.isContentEditable);
    if((event.ctrlKey||event.metaKey) && event.key.toLowerCase()==='k'){
      event.preventDefault();searchDialog.open?closeDialog(searchDialog):openSearch(document.activeElement);
    } else if(event.key==='/' && !editable && !searchDialog.open && !mobileNav.open) {
      event.preventDefault();openSearch(document.activeElement);
    }
  });

  const tocLinks=$$('.toc nav a'), headings=$$('.prose h2,.prose h3');
  if(tocLinks.length && 'IntersectionObserver' in window) {
    const observer=new IntersectionObserver(entries=>{
      const visible=entries.filter(entry=>entry.isIntersecting);
      if(!visible.length)return;
      const id=visible[0].target.id;
      tocLinks.forEach(link=>link.classList.toggle('selected',decodeURIComponent(link.hash.slice(1))===id));
    },{rootMargin:'-105px 0px -65% 0px',threshold:0});
    headings.forEach(heading=>observer.observe(heading));
  }
  const topButton=$('.back-to-top');
  window.addEventListener('scroll',()=>{topButton.hidden=window.scrollY<500;},{passive:true});
  topButton.addEventListener('click',()=>window.scrollTo({top:0,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}));

  // Keep the current sidebar entry within view on each static page navigation.
  const sidebar=$('.sidebar'),current=$('.sidebar a.current');
  if(sidebar && current){
    const relative=current.getBoundingClientRect().top-sidebar.getBoundingClientRect().top;
    if(relative>sidebar.clientHeight-90)sidebar.scrollTop=relative-sidebar.clientHeight/2;
  }
})();
