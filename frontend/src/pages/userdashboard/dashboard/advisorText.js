// Presentation only: never changes stored history, quotas or financial context.
const replyKeys = ["answer", "response", "message", "text", "content", "advice"];
function readable(value, depth = 0) {
  if (depth > 5 || value == null) return "";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(item => readable(item, depth + 1)).filter(Boolean).map(item => `- ${item}`).join("\n");
  if (typeof value === "object") {
    for (const key of replyKeys) if (value[key] != null) return readable(value[key], depth + 1);
    return ["summary", "analysis", "recommendations", "next_steps", "suggestions", "conclusion"]
      .filter(key => value[key] != null).map(key => `## ${key.replaceAll("_", " ")}\n\n${readable(value[key], depth + 1)}`).join("\n\n");
  }
  return "";
}
export function advisorText(value) {
  let text = readable(value).trim();
  const fenced = text.match(/^```(?:json|markdown|md|text)?\s*([\s\S]*?)\s*```$/i);
  if (fenced) text = fenced[1].trim();
  for (let depth = 0; /^[{[]/.test(text); depth++) {
    if (depth === 3) return "This response could not be displayed clearly. Please ask for a plain-language explanation.";
    try { text = readable(JSON.parse(text)).trim(); }
    catch { return "This response could not be displayed clearly. Please ask the advisor to explain it in plain language."; }
  }
  if (!text) return "This response could not be displayed clearly. Please try asking a shorter question.";
  return text.replace(/\bLKR\s*([+-]?\d[\d,]*(?:\.\d+)?)/g, (match, amount) => {
    const number = Number(amount.replaceAll(",", ""));
    return Number.isFinite(number) ? `LKR ${number.toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : match;
  });
}
