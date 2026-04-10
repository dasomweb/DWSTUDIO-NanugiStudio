const { describe, it } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const { resolve, fileExists, listFiles } = require('./helpers');

describe('테마 구조 검증', () => {

  describe('필수 폴더 존재', () => {
    const requiredDirs = ['assets', 'config', 'layout', 'locales', 'sections', 'snippets', 'templates'];

    for (const dir of requiredDirs) {
      it(`${dir}/ 폴더 존재`, () => {
        assert.ok(fs.existsSync(resolve(dir)), `${dir}/ 폴더가 없습니다`);
      });
    }
  });

  describe('필수 파일 존재', () => {
    const requiredFiles = [
      'layout/theme.liquid',
      'config/settings_schema.json',
      'config/settings_data.json',
      'templates/index.json',
      'templates/product.json',
      'templates/collection.json',
      'templates/cart.json',
      'templates/404.json',
    ];

    for (const file of requiredFiles) {
      it(`${file} 존재`, () => {
        assert.ok(fileExists(file), `${file} 파일이 없습니다`);
      });
    }
  });

  describe('레이아웃 파일 검증', () => {
    it('theme.liquid에 {{ content_for_header }} 포함', () => {
      const content = fs.readFileSync(resolve('layout/theme.liquid'), 'utf-8');
      assert.ok(content.includes('content_for_header'), 'content_for_header 태그가 없습니다');
    });

    it('theme.liquid에 {{ content_for_layout }} 포함', () => {
      const content = fs.readFileSync(resolve('layout/theme.liquid'), 'utf-8');
      assert.ok(content.includes('content_for_layout'), 'content_for_layout 태그가 없습니다');
    });

    it('theme.liquid에 <html> 태그 포함', () => {
      const content = fs.readFileSync(resolve('layout/theme.liquid'), 'utf-8');
      assert.ok(content.includes('<html'), '<html> 태그가 없습니다');
    });
  });

  describe('로캘 파일 검증', () => {
    it('기본 로캘 (en.default.json 또는 ko.default.json) 존재', () => {
      const hasDefault = fileExists('locales/en.default.json') || fileExists('locales/ko.default.json');
      assert.ok(hasDefault, '기본 로캘 파일이 없습니다');
    });

    it('기본 로캘 스키마 파일 존재', () => {
      const hasSchema = fileExists('locales/en.default.schema.json') || fileExists('locales/ko.default.schema.json');
      assert.ok(hasSchema, '기본 로캘 스키마 파일이 없습니다');
    });
  });

  describe('빈 폴더 없음', () => {
    const dirs = ['assets', 'sections', 'snippets', 'templates'];

    for (const dir of dirs) {
      it(`${dir}/ 폴더에 파일 존재`, () => {
        const files = fs.readdirSync(resolve(dir));
        assert.ok(files.length > 0, `${dir}/ 폴더가 비어있습니다`);
      });
    }
  });
});
