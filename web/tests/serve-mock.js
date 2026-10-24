// Sirve el panel con el Supabase falso (tests/mock-supabase.js) en lugar del real.
// Uso:  node tests/serve-mock.js            → http://localhost:5511
//       http://localhost:5511/?migracion=009 → con las funciones de la propuesta 009
//       http://localhost:5511/?espacios=1    → con la tabla espacios (migración 006)
// No necesita dependencias. No se conecta a internet salvo las fuentes y el QR del CDN.
const http = require('http');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const port = Number(process.env.PORT || 5511);
const types = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.svg': 'image/svg+xml', '.json': 'application/json' };

function indexWithMock() {
  const html = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  const cdn = /<script src="https:\/\/cdn\.jsdelivr\.net\/npm\/@supabase\/supabase-js@[^"]+"><\/script>/;
  if (!cdn.test(html)) throw new Error('No se encontró la etiqueta de supabase-js en index.html');
  return html.replace(cdn, [
    '<script src="tests/mock-supabase.js"></script>',
    "<script>window.NCLUB_SUPABASE_CONFIG = { url: 'https://mock-nclub.supabase.co', publishableKey: 'sb_publishable_mock' };</script>",
  ].join('\n  '));
}

http.createServer((req, res) => {
  const urlPath = decodeURIComponent(req.url.split('?')[0]);
  try {
    if (urlPath === '/' || urlPath === '/index.html') {
      res.writeHead(200, { 'Content-Type': types['.html'], 'Cache-Control': 'no-store' });
      return res.end(indexWithMock());
    }
    const file = path.join(root, urlPath);
    if (!file.startsWith(root)) { res.writeHead(403); return res.end(); }
    const data = fs.readFileSync(file);
    res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    return res.end(data);
  } catch (err) {
    res.writeHead(err.code === 'ENOENT' ? 404 : 500);
    return res.end(err.code === 'ENOENT' ? 'No encontrado' : String(err.message));
  }
}).listen(port, () => console.log(`Panel con Supabase falso en http://localhost:${port}`));
