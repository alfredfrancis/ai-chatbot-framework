import { useMemo, type MouseEvent } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { rawUrl } from "../api";

export const MARKDOWN = /\.(md|markdown)$/i;
const SCHEME = /^[a-z][a-z0-9+.-]*:/i;

/**
 * Where a link or image in the document at `base` points, as a path in Files; null when it points outside them.
 * Relative paths go from the document's folder; `/workspace/…` and `file:///workspace/…` are paths in Files.
 */
export function resolveIn(base: string, href: string): string | null {
  let p = href.split(/[?#]/)[0];
  try { p = decodeURIComponent(p); } catch { /* keep it as written */ }
  if (p.startsWith("file:///workspace/")) p = p.slice("file:///workspace/".length);
  else if (p.startsWith("/workspace/")) p = p.slice("/workspace/".length);
  else if (p.startsWith("/") || SCHEME.test(p)) return null;
  else p = (base.includes("/") ? base.slice(0, base.lastIndexOf("/") + 1) : "") + p;
  const parts: string[] = [];
  for (const part of p.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") { if (!parts.length) return null; parts.pop(); } else parts.push(part);
  }
  return parts.length ? parts.join("/") : null;
}

const plainClick = (e: MouseEvent) => e.button === 0 && !e.metaKey && !e.ctrlKey && !e.shiftKey && !e.altKey;

/**
 * A markdown file from Files, rendered. Images load from Files; a link to another markdown file calls `onOpen`;
 * other files and web pages open in a new tab. Raw HTML in the file is left out, never run.
 */
export function MarkdownDoc({ source, path, onOpen }: { source: string; path: string; onOpen?: (path: string) => void }) {
  const components = useMemo<Components>(() => ({
    a: ({ node: _node, href, children, ...rest }) => {
      const to = href ?? "";
      if (!to || to.startsWith("#")) return <a {...rest} href={to || undefined}>{children}</a>;
      if (SCHEME.test(to) && !to.startsWith("file:")) return <a {...rest} href={to} target="_blank" rel="noreferrer">{children}</a>;
      const target = resolveIn(path, to);
      if (!target) return <span>{children}</span>;
      if (onOpen && MARKDOWN.test(target)) {
        return <a {...rest} href={`?doc=${encodeURIComponent(target)}`} onClick={(e) => { if (plainClick(e)) { e.preventDefault(); onOpen(target); } }}>{children}</a>;
      }
      return <a {...rest} href={rawUrl(target)} target="_blank" rel="noreferrer">{children}</a>;
    },
    img: ({ node: _node, src, alt, ...rest }) => {
      const s = typeof src === "string" ? src : "";
      const target = s && !(SCHEME.test(s) && !s.startsWith("file:")) ? resolveIn(path, s) : null;
      // Web images are left as written; the page's content policy only loads images from Files.
      return <img {...rest} src={target ? rawUrl(target) : s || undefined} alt={alt ?? ""} />;
    },
  }), [path, onOpen]);
  return <div className="answer doc-body"><Markdown remarkPlugins={[remarkGfm]} components={components} skipHtml>{source}</Markdown></div>;
}
