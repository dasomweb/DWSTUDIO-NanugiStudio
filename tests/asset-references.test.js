const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { listFiles, readFile, fileExists } = require('./helpers');

describe('에셋 참조 무결성', () => {
  // asset_url 필터 패턴: 'filename' | asset_url
  const assetUrlPattern = /['"]([^'"]+?)['"]\s*\|\s*asset_url/g;

  const liquidDirs = ['sections', 'snippets', 'layout', 'blocks'];
  const allLiquidFiles = liquidDirs.flatMap(dir => listFiles(dir, '.liquid'));

  // 모든 Liquid 파일에서 asset_url 참조 수집
  const references = new Map(); // assetName -> [referencing files]

  for (const file of allLiquidFiles) {
    const content = readFile(file);
    let match;
    const regex = new RegExp(assetUrlPattern.source, 'g');
    while ((match = regex.exec(content)) !== null) {
      const assetName = match[1];
      // Liquid 변수를 포함한 동적 참조는 스킵
      if (assetName.includes('{') || assetName.includes('%')) continue;
      if (!references.has(assetName)) references.set(assetName, []);
      references.get(assetName).push(file);
    }
  }

  assert.ok(references.size > 0, 'asset_url 참조가 하나도 발견되지 않았습니다');

  for (const [assetName, files] of references) {
    it(`assets/${assetName} 파일 존재 (${files.length}곳에서 참조)`, () => {
      const exists = fileExists(`assets/${assetName}`);
      assert.ok(exists, `assets/${assetName} 파일이 없습니다. 참조: ${files.join(', ')}`);
    });
  }
});
