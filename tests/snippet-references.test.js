const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { listFiles, readFile, fileExists } = require('./helpers');

describe('스니펫 참조 무결성', () => {
  // render 'snippet-name' 또는 render "snippet-name" 패턴 추출
  const renderPattern = /\{%-?\s*render\s+['"]([^'"]+)['"]/g;

  const liquidDirs = ['sections', 'snippets', 'layout', 'blocks'];
  const allLiquidFiles = liquidDirs.flatMap(dir => listFiles(dir, '.liquid'));

  // 모든 Liquid 파일에서 render 호출 수집
  const references = new Map(); // snippetName -> [referencing files]

  for (const file of allLiquidFiles) {
    const content = readFile(file);
    let match;
    const regex = new RegExp(renderPattern.source, 'g');
    while ((match = regex.exec(content)) !== null) {
      const snippetName = match[1];
      if (!references.has(snippetName)) references.set(snippetName, []);
      references.get(snippetName).push(file);
    }
  }

  assert.ok(references.size > 0, 'render 호출이 하나도 발견되지 않았습니다');

  for (const [snippetName, files] of references) {
    it(`snippets/${snippetName}.liquid 파일 존재 (${files.length}곳에서 참조)`, () => {
      const exists = fileExists(`snippets/${snippetName}.liquid`);
      assert.ok(exists, `snippets/${snippetName}.liquid 파일이 없습니다. 참조: ${files.join(', ')}`);
    });
  }
});
