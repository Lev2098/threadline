// Runs before first paint (external file, so the CSP needs no 'unsafe-inline'):
// 1. applies the saved theme (no light flash);
// 2. marks the page as JS-capable, so the server-rendered markup (for crawlers
//    and no-JS clients) is not painted and then swapped for the app, which would
//    shift the layout. If the app hasn't mounted after 4 s, the markup is shown.
document.documentElement.classList.add('js')
setTimeout(function () {
  if (!document.documentElement.hasAttribute('data-app')) document.documentElement.classList.remove('js')
}, 4000)
try {
  var t = localStorage.getItem('threadline.theme')
  if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t
} catch (e) {}
