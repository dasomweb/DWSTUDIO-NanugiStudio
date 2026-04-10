const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const { listFiles, parseShopifyJson, readFile, stripJsonComments } = require('./helpers');

describe('JSON 유효성 검증', () => {

  describe('templates/*.json', () => {
    const files = listFiles('templates', '.json');
    assert.ok(files.length > 0, 'templates 폴더에 JSON 파일이 없습니다');

    for (const file of files) {
      it(`${file} — 유효한 JSON`, () => {
        assert.doesNotThrow(() => parseShopifyJson(file), `${file} 파싱 실패`);
      });

      it(`${file} — sections 키 존재`, () => {
        const data = parseShopifyJson(file);
        assert.ok(data.sections, `${file}에 "sections" 키가 없습니다`);
      });
    }
  });

  describe('config/settings_schema.json', () => {
    it('유효한 JSON이고 배열 형태', () => {
      const data = parseShopifyJson('config/settings_schema.json');
      assert.ok(Array.isArray(data), 'settings_schema.json은 배열이어야 합니다');
    });

    it('theme_info 블록 포함', () => {
      const data = parseShopifyJson('config/settings_schema.json');
      const themeInfo = data.find(s => s.name === 'theme_info');
      assert.ok(themeInfo, 'theme_info 블록이 없습니다');
      assert.ok(themeInfo.theme_name, 'theme_name이 비어있습니다');
      assert.ok(themeInfo.theme_version, 'theme_version이 비어있습니다');
      assert.ok(themeInfo.theme_author, 'theme_author가 비어있습니다');
    });
  });

  describe('config/settings_data.json', () => {
    it('유효한 JSON이고 current 키 존재', () => {
      const data = parseShopifyJson('config/settings_data.json');
      assert.ok(data.current, '"current" 키가 없습니다');
    });
  });

  describe('sections/*.json', () => {
    const files = listFiles('sections', '.json');

    for (const file of files) {
      it(`${file} — 유효한 JSON`, () => {
        assert.doesNotThrow(() => parseShopifyJson(file), `${file} 파싱 실패`);
      });
    }
  });
});
