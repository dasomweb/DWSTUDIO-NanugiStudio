const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

function resolve(...segments) {
  return path.join(ROOT, ...segments);
}

function listFiles(dir, ext) {
  const fullDir = resolve(dir);
  if (!fs.existsSync(fullDir)) return [];
  return fs.readdirSync(fullDir)
    .filter(f => f.endsWith(ext))
    .map(f => path.join(dir, f));
}

function readFile(relPath) {
  return fs.readFileSync(resolve(relPath), 'utf-8');
}

function fileExists(relPath) {
  return fs.existsSync(resolve(relPath));
}

/** Shopify JSON 파일은 상단에 /* ... *\/ 주석이 있을 수 있음 — 제거 후 파싱 */
function stripJsonComments(content) {
  return content.replace(/\/\*[\s\S]*?\*\//g, '').trim();
}

function parseShopifyJson(relPath) {
  const raw = readFile(relPath);
  const stripped = stripJsonComments(raw);
  return JSON.parse(stripped);
}

module.exports = { ROOT, resolve, listFiles, readFile, fileExists, stripJsonComments, parseShopifyJson };
