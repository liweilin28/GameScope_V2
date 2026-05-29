export function showToast(message) {
  const root = document.querySelector("#toast-root");
  if (!root) return;
  const node = document.createElement("div");
  node.className = "toast";
  node.textContent = message;
  root.appendChild(node);
  window.setTimeout(() => node.remove(), 3600);
}

export function setLoading(isLoading) {
  const loading = document.querySelector("#loading");
  if (loading) loading.classList.toggle("hidden", !isLoading);
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function formatNumber(value, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无";
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  });
}

export function formatPercent(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "暂无";
  return `${(Number(value) * 100).toFixed(digits)}%`;
}

export function renderTable(records, options = {}) {
  const rows = Array.isArray(records) ? records : [];
  const limit = options.limit || rows.length;
  const visibleRows = rows.slice(0, limit);
  const columns = options.columns || Array.from(new Set(visibleRows.flatMap((row) => Object.keys(row || {}))));
  const className = options.className ? ` ${escapeHtml(options.className)}` : "";

  if (!visibleRows.length || !columns.length) {
    return `<div class="empty-state">${escapeHtml(options.emptyText || "暂无数据。")}</div>`;
  }

  const head = columns.map((column) => `<th class="col-${escapeHtml(column)}">${escapeHtml(column)}</th>`).join("");
  const body = visibleRows
    .map((row) => {
      const cells = columns
        .map((column) => {
          const raw = row?.[column];
          const value = Array.isArray(raw) ? raw.join(", ") : raw;
          return `<td class="col-${escapeHtml(column)}">${escapeHtml(value ?? "")}</td>`;
        })
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");

  return `
    <div class="table-wrap${className}">
      <table class="data-table">
        <thead><tr>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>
  `;
}

export function renderTableFromPayload(table, options = {}) {
  if (!table || !Array.isArray(table.rows)) {
    return `<div class="empty-state">暂无数据。</div>`;
  }
  return renderTable(table.rows, { ...options, columns: table.columns || options.columns });
}

export function renderList(items, keyName = null) {
  const values = Array.isArray(items) ? items : [];
  if (!values.length) return `<div class="empty-state">暂无数据。</div>`;
  return `
    <div class="tag-cloud">
      ${values
        .map((item) => {
          const text = keyName ? item[keyName] : item;
          return `<span class="tag">${escapeHtml(text)}</span>`;
        })
        .join("")}
    </div>
  `;
}

function sanitizeMarkdownHref(href) {
  const trimmed = String(href || "").trim();
  if (!trimmed || /[\u0000-\u001f\s]/.test(trimmed)) return "";
  if (/^https?:\/\//i.test(trimmed) || /^mailto:/i.test(trimmed)) return trimmed;
  if (/^(\/(?!\/)|#|\?|\.\/|\.\.\/)/.test(trimmed)) return trimmed;
  return "";
}

function renderInlineMarkdown(value) {
  const placeholders = [];
  const stash = (html) => {
    const token = `@@MDTOKEN${placeholders.length}@@`;
    placeholders.push([token, html]);
    return token;
  };

  let text = String(value ?? "");
  text = text.replace(/`([^`\n]+)`/g, (_, code) => stash(`<code>${escapeHtml(code)}</code>`));
  text = text.replace(/\[([^\]\n]+)\]\(([^)\s]+)\)/g, (_, label, href) => {
    const safeHref = sanitizeMarkdownHref(href);
    if (!safeHref) return `${label} (${href})`;
    return stash(`<a href="${escapeHtml(safeHref)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label)}</a>`);
  });

  let html = escapeHtml(text);
  html = html
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_]+)__/g, "<strong>$1</strong>")
    .replace(/(^|[^\w])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>")
    .replace(/(^|[^\w])_([^_\n]+)_(?!_)/g, "$1<em>$2</em>");

  for (const [token, replacement] of placeholders) {
    html = html.replaceAll(token, replacement);
  }
  return html;
}

function splitMarkdownTableRow(line) {
  let text = String(line || "").trim();
  if (!text.includes("|")) return [];
  if (text.startsWith("|")) text = text.slice(1);
  if (text.endsWith("|")) text = text.slice(0, -1);
  return text.split("|").map((cell) => cell.trim());
}

function isMarkdownTableDivider(line) {
  const cells = splitMarkdownTableRow(line);
  return cells.length > 0 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function renderMarkdownTable(lines) {
  const header = splitMarkdownTableRow(lines[0]);
  const rows = lines.slice(2).map(splitMarkdownTableRow).filter((row) => row.length);
  if (!header.length) return "";

  return `
    <div class="markdown-table-wrap">
      <table>
        <thead><tr>${header.map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`).join("")}</tr></thead>
        <tbody>
          ${rows
            .map(
              (row) => `
                <tr>
                  ${header.map((_, index) => `<td>${renderInlineMarkdown(row[index] || "")}</td>`).join("")}
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

export function renderMarkdown(markdown) {
  const lines = String(markdown || "").split(/\r?\n/);
  const html = [];
  let listType = "";
  let paragraphLines = [];
  let inCodeBlock = false;
  let codeLanguage = "";
  let codeLines = [];

  const closeList = () => {
    if (listType) {
      html.push(`</${listType}>`);
      listType = "";
    }
  };
  const closeParagraph = () => {
    if (paragraphLines.length) {
      html.push(`<p>${paragraphLines.map(renderInlineMarkdown).join("<br />")}</p>`);
      paragraphLines = [];
    }
  };
  const openList = (type) => {
    if (listType !== type) {
      closeList();
      html.push(`<${type}>`);
      listType = type;
    }
  };
  const closeCodeBlock = () => {
    const language = /^[a-z0-9_-]+$/i.test(codeLanguage) ? ` class="language-${escapeHtml(codeLanguage)}"` : "";
    html.push(`<pre><code${language}>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
    inCodeBlock = false;
    codeLanguage = "";
    codeLines = [];
  };

  for (let index = 0; index < lines.length; index += 1) {
    const rawLine = lines[index];
    const line = rawLine.trim();

    if (inCodeBlock) {
      if (line.startsWith("```")) {
        closeCodeBlock();
      } else {
        codeLines.push(rawLine);
      }
      continue;
    }

    if (line.startsWith("```")) {
      closeParagraph();
      closeList();
      inCodeBlock = true;
      codeLanguage = line.slice(3).trim();
      continue;
    }

    if (!line) {
      closeParagraph();
      closeList();
      continue;
    }

    const tableDivider = lines[index + 1] ? isMarkdownTableDivider(lines[index + 1].trim()) : false;
    if (line.includes("|") && tableDivider) {
      closeParagraph();
      closeList();
      const tableLines = [rawLine, lines[index + 1]];
      index += 2;
      while (index < lines.length && lines[index].trim() && lines[index].includes("|")) {
        tableLines.push(lines[index]);
        index += 1;
      }
      index -= 1;
      html.push(renderMarkdownTable(tableLines));
      continue;
    }

    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    if (heading) {
      closeParagraph();
      closeList();
      const level = Math.min(Number(heading[1].length) + 1, 5);
      html.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }

    const unordered = line.match(/^[-*]\s+(.+)$/);
    if (unordered) {
      closeParagraph();
      openList("ul");
      html.push(`<li>${renderInlineMarkdown(unordered[1])}</li>`);
      continue;
    }

    const ordered = line.match(/^\d+\.\s+(.+)$/);
    if (ordered) {
      closeParagraph();
      openList("ol");
      html.push(`<li>${renderInlineMarkdown(ordered[1])}</li>`);
      continue;
    }

    if (line.startsWith("> ")) {
      closeParagraph();
      closeList();
      html.push(`<blockquote>${renderInlineMarkdown(line.slice(2))}</blockquote>`);
      continue;
    }

    closeList();
    paragraphLines.push(line);
  }

  if (inCodeBlock) closeCodeBlock();
  closeParagraph();
  closeList();
  return html.join("");
}

export function readCsvList(value) {
  const text = String(value || "").trim();
  if (!text) return null;
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isNaN(parsed) ? null : parsed;
}
