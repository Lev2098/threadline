// Applies the saved theme before first paint (no light flash). External file, so CSP needs no 'unsafe-inline'.
try {
  var t = localStorage.getItem('threadline.theme')
  if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t
} catch (e) {}
