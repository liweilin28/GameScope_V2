from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_markdown_rendering_and_qa_integration():
    script = r"""
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';

const root = process.argv[1];
const utilsPath = path.join(root, 'frontend', 'js', 'utils.js');
const qaPath = path.join(root, 'frontend', 'js', 'pages', 'qa.js');

const utilsSource = fs.readFileSync(utilsPath, 'utf8');
const transformed = utilsSource
  .replace(/export function /g, 'function ')
  .replace(/export const /g, 'const ');
const factory = new Function(`${transformed}\nreturn { renderMarkdown };`);
const { renderMarkdown } = factory();

const markdown = [
  '# 标题',
  '',
  '**重点** 和 *斜体*',
  '',
  '- 列表一',
  '- 列表二',
  '',
  '| 名称 | 价格 |',
  '| --- | --- |',
  '| A | 9.99 |',
  '',
  '```js',
  'const price = 9.99;',
  '```',
  '',
  '<script>alert(1)</script>',
  '',
  '[链接](https://example.com)',
].join('\n');

const html = renderMarkdown(markdown);
assert.match(html, /<h2>标题<\/h2>/);
assert.match(html, /<strong>重点<\/strong>/);
assert.match(html, /<em>斜体<\/em>/);
assert.match(html, /<ul>[\s\S]*<li>列表一<\/li>[\s\S]*<li>列表二<\/li>[\s\S]*<\/ul>/);
assert.match(html, /<div class="markdown-table-wrap">[\s\S]*<table>/);
assert.match(html, /<pre><code class="language-js">const price = 9\.99;<\/code><\/pre>/);
assert.ok(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'));
assert.ok(!html.includes('<script>alert(1)</script>'));
assert.match(html, /target="_blank"/);
assert.match(html, /rel="noopener noreferrer"/);

const qaSource = fs.readFileSync(qaPath, 'utf8');
assert.match(qaSource, /renderMarkdown/);
assert.match(qaSource, /markdown-body/);
assert.match(qaSource, /renderTableFromPayload/);
assert.match(qaSource, /renderEchartsOption/);
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(ROOT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
