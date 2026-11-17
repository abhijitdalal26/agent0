import { Fragment, type ReactNode } from "react";

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[[^\]]+\]\(https?:[^)]+\))/g;
  let last = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("`")) out.push(<code key={m.index} className="px-1 rounded bg-muted font-mono text-[0.9em]">{t.slice(1, -1)}</code>);
    else if (t.startsWith("**")) out.push(<strong key={m.index}>{t.slice(2, -2)}</strong>);
    else if (t.startsWith("*")) out.push(<em key={m.index}>{t.slice(1, -1)}</em>);
    else {
      const [, label, href] = /\[([^\]]+)\]\(([^)]+)\)/.exec(t)!;
      out.push(<a key={m.index} href={href} target="_blank" rel="noreferrer" className="text-blue-500 hover:underline">{label}</a>);
    }
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Markdown({ source }: { source: string }) {
  const lines = source.replace(/\r/g, "").split("\n");
  const blocks: ReactNode[] = [];
  let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith("```")) {
      const code: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) code.push(lines[i++]);
      i++;
      blocks.push(<pre key={i} className="p-2.5 rounded bg-muted/60 font-mono text-[11px] overflow-x-auto">{code.join("\n")}</pre>);
    } else if (/^#{1,6}\s/.test(l)) {
      const level = l.match(/^#+/)![0].length;
      const cls = level <= 2 ? "text-base font-bold" : "text-sm font-semibold";
      blocks.push(<div key={i} className={cls}>{inline(l.replace(/^#+\s*/, ""))}</div>);
      i++;
    } else if (/^\s*([-*]|\d+\.)\s/.test(l)) {
      const ordered = /^\s*\d+\./.test(l);
      const items: string[] = [];
      while (i < lines.length && /^\s*([-*]|\d+\.)\s/.test(lines[i])) items.push(lines[i++].replace(/^\s*([-*]|\d+\.)\s+/, ""));
      const Tag = ordered ? "ol" : "ul";
      blocks.push(
        <Tag key={i} className={`pl-5 space-y-0.5 ${ordered ? "list-decimal" : "list-disc"}`}>
          {items.map((it, k) => <li key={k}>{inline(it)}</li>)}
        </Tag>,
      );
    } else if (l.trim() === "") {
      i++;
    } else {
      const para: string[] = [];
      while (i < lines.length && lines[i].trim() !== "" && !/^(```|#{1,6}\s|\s*([-*]|\d+\.)\s)/.test(lines[i])) para.push(lines[i++]);
      blocks.push(<p key={i}>{para.map((p, k) => <Fragment key={k}>{k > 0 && <br />}{inline(p)}</Fragment>)}</p>);
    }
  }
  return <div className="space-y-2 text-xs leading-relaxed text-foreground">{blocks}</div>;
}
