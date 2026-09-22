(() => {
  let value;
  try { value = localStorage.getItem('tg2cloud-theme'); } catch {}
  if (value !== 'dark' && value !== 'light') {
    value = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  document.documentElement.dataset.theme = value;
})();
