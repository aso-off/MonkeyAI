import { Marked } from "marked";
import markedKatex from "marked-katex-extension";
import hljs from "highlight.js/lib/common";
import DOMPurify from "dompurify";

const COPY_ICON =
  '<svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">' +
  '<path d="M7 7V4.2C7 3.08 7 2.52 7.22 2.09C7.41 1.72 7.72 1.41 8.09 1.22C8.52 1 9.08 1 10.2 1H15.8' +
  "C16.92 1 17.48 1 17.91 1.22C18.28 1.41 18.59 1.72 18.78 2.09C19 2.52 19 3.08 19 4.2V9.8C19 10.92 " +
  "19 11.48 18.78 11.91C18.59 12.28 18.28 12.59 17.91 12.78C17.48 13 16.92 13 15.8 13H13M7 7H4.2C3.08 " +
  "7 2.52 7 2.09 7.22C1.72 7.41 1.41 7.72 1.22 8.09C1 8.52 1 9.08 1 10.2V15.8C1 16.92 1 17.48 1.22 " +
  "17.91C1.41 18.28 1.72 18.59 2.09 18.78C2.52 19 3.08 19 4.2 19H9.8C10.92 19 11.48 19 11.91 18.78" +
  'C12.28 18.59 12.59 18.28 12.78 17.91C13 17.48 13 16.92 13 15.8V13M7 7H9.8C10.92 7 11.48 7 11.91 ' +
  '7.22C12.28 7.41 12.59 7.72 12.78 8.09C13 8.52 13 9.08 13 10.2V13" stroke="currentColor" ' +
  'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';

const CALLOUTS: Record<string, string> = {
  NOTE: "Note",
  TIP: "Tip",
  IMPORTANT: "Important",
  WARNING: "Warning",
  CAUTION: "Caution",
};

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

const marked = new Marked({ gfm: true, breaks: true });

marked.use(markedKatex({ throwOnError: false, output: "html" }));

marked.use({
  renderer: {
    code({ text, lang }) {
      const raw = (lang || "").trim().split(/\s+/)[0].toLowerCase();
      const known = raw && hljs.getLanguage(raw) ? raw : "";
      let body: string;
      try {
        body = known
          ? hljs.highlight(text, { language: known, ignoreIllegals: true }).value
          : escapeHtml(text);
      } catch {
        body = escapeHtml(text);
      }
      const label = known || raw || "code";
      return (
        '<div class="code-block">' +
        '<div class="code-block__head"><span class="code-block__lang">' +
        escapeHtml(label) +
        '</span><button class="code-copy" type="button" aria-label="copy">' +
        COPY_ICON +
        "</button></div>" +
        '<pre class="code-block__pre"><code class="hljs">' +
        body +
        "</code></pre></div>"
      );
    },
    blockquote({ tokens }) {
      const inner = this.parser.parse(tokens);
      const m = inner.match(/^\s*<p>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*(<br\s*\/?>)?\s*/i);
      if (m) {
        const type = m[1].toUpperCase();
        const body = inner.replace(m[0], "<p>");
        return (
          `<div class="md-callout md-callout--${type.toLowerCase()}">` +
          `<div class="md-callout__title">${CALLOUTS[type]}</div>` +
          `<div class="md-callout__body">${body}</div></div>`
        );
      }
      return `<blockquote>${inner}</blockquote>`;
    },
    checkbox({ checked }) {
      return `<input class="md-task" type="checkbox" disabled${checked ? " checked" : ""}> `;
    },
  },
});

// внешние ссылки - всегда в новой вкладке и безопасно
DOMPurify.addHook("afterSanitizeAttributes", (node) => {
  if (node.nodeName === "A") {
    node.setAttribute("target", "_blank");
    node.setAttribute("rel", "noopener noreferrer");
  }
});

const SANITIZE_OPTS = {
  USE_PROFILES: { html: true, svg: true, mathMl: true },
  ADD_ATTR: ["style", "aria-hidden", "target", "rel"],
};

/**
 * Незакрытые во время стрима блоки (```код или $$формула) показываем как
 * обычный текст до прихода закрывающего разделителя - без мигания полу-блока.
 */
function splitUnclosed(text: string): { md: string; tail: string } {
  const lines = text.split("\n");
  let fenceLine = -1;
  let fenceChar = "";
  for (let i = 0; i < lines.length; i++) {
    const fm = lines[i].match(/^\s{0,3}(`{3,}|~{3,})/);
    if (!fm) continue;
    const ch = fm[1][0];
    if (fenceLine === -1) {
      fenceLine = i;
      fenceChar = ch;
    } else if (ch === fenceChar) {
      fenceLine = -1;
      fenceChar = "";
    }
  }
  if (fenceLine !== -1) {
    return { md: lines.slice(0, fenceLine).join("\n"), tail: lines.slice(fenceLine).join("\n") };
  }
  const noCode = text.replace(/```[\s\S]*?```/g, "").replace(/~~~[\s\S]*?~~~/g, "");
  if ((noCode.split("$$").length - 1) % 2 === 1) {
    const idx = text.lastIndexOf("$$");
    return { md: text.slice(0, idx), tail: text.slice(idx) };
  }
  return { md: text, tail: "" };
}

export function renderMarkdown(text: string): string {
  const { md, tail } = splitUnclosed(text);
  let html = marked.parse(md, { async: false }) as string;
  if (tail) {
    html += `<span class="md-stream-tail">${escapeHtml(tail).replace(/\n/g, "<br>")}</span>`;
  }
  return DOMPurify.sanitize(html, SANITIZE_OPTS);
}