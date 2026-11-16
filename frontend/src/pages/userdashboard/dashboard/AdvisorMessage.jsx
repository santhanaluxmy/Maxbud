import { Fragment } from "react";
import { advisorText } from "./advisorText";

function Inline({ text }) {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\n]+\*)/g).map((part, i) =>
    part.startsWith("**") ? <strong key={i}>{part.slice(2, -2)}</strong> :
    part.startsWith("`") ? <code key={i}>{part.slice(1, -1)}</code> :
    part.startsWith("*") && part.endsWith("*") ? <em key={i}>{part.slice(1, -1)}</em> : <Fragment key={i}>{part}</Fragment>);
}
export default function AdvisorMessage({ answer }) {
  const lines = advisorText(answer).split(/\r?\n/);
  const blocks = [];
  for (let i = 0; i < lines.length;) {
    const line = lines[i].trim();
    if (!line || /^[-*_]{3,}$/.test(line)) { i++; continue; }
    // Present model-generated tables as readable points, not a raw spreadsheet.
    if (line.startsWith("|") && i + 1 < lines.length && /^\|?[\s:|-]+\|$/.test(lines[i + 1].trim())) {
      const headers = line.split("|").slice(1, -1).map(s => s.trim());
      i += 2; const items = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        items.push(lines[i].trim().split("|").slice(1, -1).map((cell, col) => `${headers[col] || "Detail"}: ${cell.trim()}`).join(" · ")); i++;
      }
      blocks.push(<ul key={i}>{items.map((item, n) => <li key={n}><Inline text={item}/></li>)}</ul>); continue;
    }
    if (/^#{1,6}\s/.test(line)) { blocks.push(<h3 key={i}><Inline text={line.replace(/^#{1,6}\s+/, "")}/></h3>); i++; continue; }
    if (/^(?:[-*+]\s|\d+[.)]\s)/.test(line)) {
      const ordered = /^\d/.test(line), items = [], start = i;
      while (i < lines.length && (ordered ? /^\d+[.)]\s/ : /^[-*+]\s/).test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^(?:[-*+]\s+|\d+[.)]\s+)/, "")); i++;
      }
      const List = ordered ? "ol" : "ul";
      blocks.push(<List key={start}>{items.map((item, n) => <li key={n}><Inline text={item}/></li>)}</List>); continue;
    }
    const paragraph = [line.replace(/^>\s?/, "")], start = i++;
    while (i < lines.length && lines[i].trim() && !/^(?:#|[-*+]\s|\d+[.)]\s|\|)/.test(lines[i].trim())) paragraph.push(lines[i++].trim());
    blocks.push(<p key={start}><Inline text={paragraph.join(" ")}/></p>);
  }
  return <div className="advisor-prose">{blocks}</div>;
}
