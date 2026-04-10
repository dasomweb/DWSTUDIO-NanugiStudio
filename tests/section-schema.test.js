const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { listFiles, readFile } = require('./helpers');

describe('섹션 스키마 유효성', () => {
  const sectionFiles = listFiles('sections', '.liquid');
  const schemaPattern = /\{%-?\s*schema\s*-?%\}([\s\S]*?)\{%-?\s*endschema\s*-?%\}/;

  assert.ok(sectionFiles.length > 0, 'sections 폴더에 Liquid 파일이 없습니다');

  for (const file of sectionFiles) {
    const content = readFile(file);
    const match = content.match(schemaPattern);

    if (!match) continue; // 스키마가 없는 섹션은 스킵

    it(`${file} — 스키마 JSON 유효`, () => {
      let schema;
      assert.doesNotThrow(() => {
        schema = JSON.parse(match[1]);
      }, `${file}의 schema 블록이 유효한 JSON이 아닙니다`);
    });

    it(`${file} — name 필드 존재`, () => {
      const schema = JSON.parse(match[1]);
      assert.ok(schema.name, `${file}의 schema에 "name"이 없습니다`);
    });
  }

  describe('블록 스키마 유효성', () => {
    const blockFiles = listFiles('blocks', '.liquid');

    for (const file of blockFiles) {
      const content = readFile(file);
      const match = content.match(schemaPattern);

      if (!match) continue;

      it(`${file} — 스키마 JSON 유효`, () => {
        assert.doesNotThrow(() => {
          JSON.parse(match[1]);
        }, `${file}의 schema 블록이 유효한 JSON이 아닙니다`);
      });

      it(`${file} — name 필드 존재`, () => {
        const schema = JSON.parse(match[1]);
        assert.ok(schema.name, `${file}의 schema에 "name"이 없습니다`);
      });
    }
  });
});
