// Deliberately small, escaped Markdown renderer. No arbitrary HTML or plugins.
export const escapeHtml = (value) => String(value).replace(/[&<>"']/g, c => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
}[c]));

export function safeUrl(value) {
  const url = String(value).trim();
  if (/[\u0000-\u0020\\]/.test(url) || url.startsWith('//')) return '#';
  if (/^(https?:\/\/|mailto:|#|\/)/i.test(url)) return url;
  if (/^[\w./-]+(?:#[\w-]+)?$/.test(url) && !url.includes(':')) return url;
  return '#';
}

export function inline(text) {
  const tokens = [];
  const token = (html) => `\u0000${tokens.push(html) - 1}\u0000`;
  let value = String(text).replace(/`([^`\n]+)`|(!?)\[([^\]\n]+)\]\(([^)\s]+)\)/g,
    (_, code, image, label, href) => {
      if (code !== undefined) return token(`<code>${escapeHtml(code)}</code>`);
      const url = escapeHtml(safeUrl(href));
      if (image) return token(`<img loading="lazy" src="${url}" alt="${escapeHtml(label)}">`);
      const external = /^https?:/i.test(href);
      return token(`<a href="${url}"${external ? ' target="_blank" rel="noopener noreferrer"' : ''}>${escapeHtml(label)}${external ? '<span class="external-arrow" aria-hidden="true">↗</span>' : ''}</a>`);
    });
  value = escapeHtml(value)
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '<em>$1</em>');
  return value.replace(/\u0000(\d+)\u0000/g, (_, index) => tokens[Number(index)]);
}

export const slugify = (text) => text.normalize('NFKC').toLowerCase()
  .replace(/[`*]/g, '').replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '') || 'section';

function splitCells(line) {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(x => x.trim());
}

export function renderMarkdown(markdown) {
  const lines = markdown.replace(/\r\n/g, '\n').split('\n');
  const html = [], headings = [], usedIds = new Map();
  let i = 0;
  const special = (line) => /^(#{1,6}\s|```|:::|>\s?|[-*]\s|\d+\.\s|\|)/.test(line) || /^---+\s*$/.test(line);
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    if (line.startsWith('```')) {
      const language = line.slice(3).trim() || 'text';
      const code = []; i++;
      while (i < lines.length && !lines[i].startsWith('```')) code.push(lines[i++]);
      if (i === lines.length) throw new Error('Unclosed code fence');
      i++;
      html.push(`<div class="code-block"><div class="code-toolbar"><span>${escapeHtml(language)}</span><button class="copy-code" type="button" aria-label="复制代码">复制</button></div><pre tabindex="0"><code class="language-${escapeHtml(language)}">${escapeHtml(code.join('\n'))}</code></pre></div>`);
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length, title = heading[2];
      const base = slugify(title), n = usedIds.get(base) || 0;
      usedIds.set(base, n + 1);
      const id = n ? `${base}-${n}` : base;
      headings.push({level, title: title.replace(/[`*]/g, ''), id});
      html.push(`<h${level} id="${escapeHtml(id)}">${inline(title)}${level > 1 ? `<a class="heading-anchor" href="#${encodeURIComponent(id)}" aria-label="链接到本节：${escapeHtml(title)}">#</a>` : ''}</h${level}>`);
      i++; continue;
    }
    if (/^:::(tip|info|warning|danger)(?:\s|$)/.test(line)) {
      const [, kind, title] = /^:::(tip|info|warning|danger)\s*(.*)$/.exec(line);
      const body = []; i++;
      while (i < lines.length && lines[i].trim() !== ':::') body.push(lines[i++]);
      if (i === lines.length) throw new Error('Unclosed callout');
      i++;
      const names = {tip:'提示',info:'说明',warning:'注意',danger:'重要提醒'};
      html.push(`<aside class="callout ${kind}"><p class="callout-title"><span aria-hidden="true">${kind === 'warning' || kind === 'danger' ? '!' : 'i'}</span>${escapeHtml(title || names[kind])}</p>${renderMarkdown(body.join('\n')).html}</aside>`);
      continue;
    }
    if (line.startsWith('|') && i + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[i + 1])) {
      const header = splitCells(line), rows=[]; i += 2;
      while (i < lines.length && lines[i].startsWith('|')) rows.push(splitCells(lines[i++]));
      html.push(`<div class="table-wrap" tabindex="0" role="region" aria-label="表格，可横向滚动"><table><thead><tr>${header.map(c => `<th scope="col">${inline(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${header.map((_,j) => `<td>${inline(row[j] || '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`);
      continue;
    }
    if (/^[-*]\s+/.test(line) || /^\d+\.\s+/.test(line)) {
      const ordered = /^\d+\./.test(line), pattern = ordered ? /^\d+\.\s+/ : /^[-*]\s+/;
      const items=[]; const start = ordered ? parseInt(line,10) : 1;
      while (i < lines.length && pattern.test(lines[i])) items.push(inline(lines[i++].replace(pattern,'')));
      const tag = ordered ? 'ol' : 'ul';
      html.push(`<${tag}${ordered && start !== 1 ? ` start="${start}"` : ''}>${items.map(x=>`<li>${x}</li>`).join('')}</${tag}>`);
      continue;
    }
    if (line.startsWith('>')) {
      const quote=[]; while (i < lines.length && lines[i].startsWith('>')) quote.push(lines[i++].replace(/^>\s?/,''));
      html.push(`<blockquote>${renderMarkdown(quote.join('\n')).html}</blockquote>`); continue;
    }
    if (/^---+\s*$/.test(line)) { html.push('<hr>'); i++; continue; }
    const paragraph=[line]; i++;
    while(i < lines.length && lines[i].trim() && !special(lines[i])) paragraph.push(lines[i++]);
    html.push(`<p>${inline(paragraph.join(' '))}</p>`);
  }
  return {html: html.join('\n'), headings};
}
