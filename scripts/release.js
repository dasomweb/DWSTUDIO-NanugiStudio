#!/usr/bin/env node
/**
 * 릴리즈 스크립트
 *
 * 사용법:
 *   npm run release           → 마지막 태그 기준 patch 버전 +1, 태그 생성·푸시
 *   npm run release -- minor  → minor 버전 +1
 *   npm run release -- major  → major 버전 +1
 *   npm run release -- 1.2.3  → 명시적 버전 지정
 *
 * 동작:
 *   1. 마지막 v* 태그 조회
 *   2. 새 버전 계산
 *   3. v{version} 태그 생성 후 푸시 (push 시 GitHub Actions가 settings_schema.json의
 *      theme_version을 자동 업데이트하여 배포)
 */

const { execSync } = require('child_process');

function sh(cmd) {
  return execSync(cmd, { encoding: 'utf8' }).trim();
}

function getLastTag() {
  try {
    const tags = sh('git tag -l "v*"').split('\n').filter(Boolean);
    if (tags.length === 0) return 'v0.0.0';
    return tags
      .map(t => t.replace(/^v/, '').split('.').map(Number))
      .filter(parts => parts.length === 3 && parts.every(n => !isNaN(n)))
      .sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2])
      .map(parts => 'v' + parts.join('.'))
      .pop() || 'v0.0.0';
  } catch {
    return 'v0.0.0';
  }
}

function bumpVersion(current, type) {
  const [major, minor, patch] = current.replace(/^v/, '').split('.').map(Number);
  if (/^\d+\.\d+\.\d+$/.test(type)) return type;
  if (type === 'major') return `${major + 1}.0.0`;
  if (type === 'minor') return `${major}.${minor + 1}.0`;
  return `${major}.${minor}.${patch + 1}`;
}

const arg = process.argv[2] || 'patch';
const lastTag = getLastTag();
const newVersion = bumpVersion(lastTag, arg);
const newTag = 'v' + newVersion;

console.log(`Last tag: ${lastTag}`);
console.log(`New tag:  ${newTag}`);

// 작업 트리 깨끗한지 확인
const status = sh('git status --porcelain');
if (status) {
  console.error('\n[ERROR] Working tree is not clean. Commit or stash first:');
  console.error(status);
  process.exit(1);
}

// main 브랜치 최신화 확인
const branch = sh('git rev-parse --abbrev-ref HEAD');
if (branch !== 'main') {
  console.error(`\n[ERROR] Not on main branch (current: ${branch}). Switch to main first.`);
  process.exit(1);
}

console.log(`\nCreating tag ${newTag}...`);
sh(`git tag ${newTag} -m "Release ${newTag}"`);

console.log(`Pushing tag to origin...`);
sh(`git push origin ${newTag}`);

console.log(`\nDone. GitHub Actions will:`);
console.log(`  - Bump theme_version in settings_schema.json to ${newVersion}`);
console.log(`  - Deploy theme to Shopify`);
console.log(`  - Create GitHub Release\n`);
