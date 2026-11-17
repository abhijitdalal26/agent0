// Tiny 5-field cron describer. Returns null for shapes it does not understand.
const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

const pad = (n: string | number) => String(n).padStart(2, "0");
const isNum = (s: string) => /^\d+$/.test(s);

function dowText(s: string): string | null {
  if (s === "*") return "";
  if (s === "1-5") return "weekday";
  if (s === "0,6" || s === "6,0") return "weekend day";
  const names: string[] = [];
  for (const p of s.split(",")) {
    if (!/^[0-7]$/.test(p)) return null;
    names.push(DAYS[Number(p) % 7]);
  }
  return names.join(", ");
}

export function describeCron(expr: string): string | null {
  const f = expr.trim().split(/\s+/);
  if (f.length !== 5) return null;
  const [min, hour, dom, mon, dow] = f;

  if (f.every((x) => x === "*")) return "every minute";
  let m = /^\*\/(\d+)$/.exec(min);
  if (m && hour === "*" && dom === "*" && mon === "*" && dow === "*") return `every ${m[1]} minutes`;
  if (isNum(min) && Number(min) < 60 && hour === "*" && dom === "*" && mon === "*" && dow === "*") return `every hour at :${pad(min)}`;
  m = /^\*\/(\d+)$/.exec(hour);
  if (isNum(min) && Number(min) < 60 && m && dom === "*" && mon === "*" && dow === "*") return `every ${m[1]} hours at :${pad(min)}`;

  if (!isNum(min) || !isNum(hour) || Number(min) > 59 || Number(hour) > 23) return null;
  const time = `${pad(hour)}:${pad(min)}`;

  if (dom === "*" && mon === "*") {
    const d = dowText(dow);
    if (d === null) return null;
    if (d === "") return `every day ${time}`;
    if (d === "weekday") return `every weekday ${time}`;
    if (d === "weekend day") return `every weekend day ${time}`;
    return `every ${d} ${time}`;
  }
  if (isNum(dom) && dow === "*") {
    const d = Number(dom);
    if (d < 1 || d > 31) return null;
    if (mon === "*") return `day ${d} of every month ${time}`;
    if (isNum(mon) && Number(mon) >= 1 && Number(mon) <= 12) return `${MONTHS[Number(mon) - 1]} ${d} ${time}`;
  }
  return null;
}
