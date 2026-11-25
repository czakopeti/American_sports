(() => {
/* Fair odds for the NFL, NBA and NHL. Data: data/odds.json, built by scripts/run.py. */
const D = JSON.parse(document.getElementById("data").textContent);
const app = document.getElementById("app");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const odd = (p) => (p > 0 && p < 1 ? (1 / p).toFixed(2) : "–");
const pc = (p) => Math.round(p * 100) + "%";
const S = { sp: -1, g: {} }; // -1: the Bets page
try { const s = JSON.parse(localStorage.getItem("am-odds") || "{}"); if (Number.isInteger(s.sp) && s.sp >= -1 && s.sp < D.sports.length) S.sp = s.sp; } catch (e) { /* storage blocked */ }
if (location.hash === "#bets") S.sp = -1;
const save = () => { try { localStorage.setItem("am-odds", JSON.stringify({ sp: S.sp })); } catch (e) { /* storage blocked */ } };
const tfmt = (t) => new Date(t).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" });
const dfmt = (d) => new Date(d + "T12:00:00Z").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
const glabel = (s, g) => (s.group_kind === "week" ? `Week ${g}` : dfmt(g));
const line = (sp, home) => (sp == null ? "–" : sp > 0 ? `${home} −${sp}` : sp < 0 ? `${home} +${-sp}` : "pick");
const pct = (x) => (x > 0 ? "+" : "") + (x * 100).toFixed(1) + "%";
// Everything reads away first, home second, like "away @ home".
// Bookmaker away and home prices, the win chances in them (margin taken out), and our chance minus theirs.
const pp = (x) => (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x * 100).toFixed(1);
const edgeCells = (m) => {
  if (!m.bh || !m.ba || m.pm == null) return `<td class="mono">–</td><td class="mono">–</td><td class="mono">–</td>`;
  const ia = 1 / m.ba, ih = 1 / m.bh, ba = ia / (ia + ih), bh = ih / (ia + ih);
  const g = [(1 - m.pm) - ba, m.pm - bh];
  const c = (x) => `<span class="${x >= 0.05 ? "ok" : ""}">${pp(x)}</span>`;
  return `<td class="mono">${m.ba.toFixed(2)} · ${m.bh.toFixed(2)}</td><td class="mono">${pc(ba)} · ${pc(bh)}</td><td class="mono">${c(g[0])} / ${c(g[1])}</td>`;
};
const EDGE_TH = "<th>Book odds<br>away · home</th><th>Book win %<br>away · home</th><th>Gap (points)<br>away / home</th>";
const ml2dec = (ml) => (ml == null ? null : ml > 0 ? 1 + ml / 100 : 1 + 100 / -ml);
const NOTES = {
  nfl: "EPA per play (expected points added, the NFL's counterpart of expected goals) for offence and defence, adjusted for the opponent: runs and passes while the game is still in doubt, recent weeks counting more, last season as a starting point. The EPA gap becomes an expected margin (home advantage about 2 points) and a win chance from a normal spread of results (13.2-point standard deviation); the expected total is from points scored and allowed. The market line is the closing spread, total and moneyline from nflverse, shown for comparison.",
  nba: "Points scored and allowed, adjusted for the opponent. Each date is predicted only from earlier dates. Half of last season's rating carries over, fading as games pile up. Home advantage is last season's average home margin. Win chance from a normal spread of results (14.6 points).",
  nhl: "Three-way odds for regulation time (60 minutes): away win, draw, home win. Built on expected goals (xG) from MoneyPuck.com: every unblocked shot is worth the chance that a shot like it goes in, so a team's strength settles much sooner than from goals alone. Expected goals for and against, all situations, adjusted for the opponent; each date is predicted only from earlier dates, with last season's ratings as the starting point. Chances from Poisson goals, with the draw chance scaled to last season's share of games that went to overtime. OT and SO mark games decided in overtime or a shootout: a draw after 60 minutes. Expected goals data: MoneyPuck.com.",
};
// Open on today's games: the first date (US Eastern, where the league plays) that is today or later.
// For the NFL, the week of the next game still to be played.
function today(s) {
  if (s.group_kind === "week") {
    const now = Date.now(), up = s.groups.find((x) => x.games.some((m) => new Date(m.t).getTime() + 4 * 3600e3 > now));
    return up ? up.g : null;
  }
  const et = new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" });
  const up = s.groups.find((x) => x.g >= et);
  return up ? up.g : null;
}
const sgn = (x) => (x > 0 ? "+" : "") + x.toFixed(2);
const tally = (L) => (L.length ? `${L.length} bets, ${L.filter((x) => x.won).length} won, <b>${sgn(L.reduce((a, x) => a + x.profit, 0))}</b> units (${pct(L.reduce((a, x) => a + x.profit, 0) / L.length)})` : "no bets yet");
const rulesOf = (s) => s.rules || (s.rule ? [s.rule] : []);
const picksOf = (m) => m.picks || [];
const badge = (s, m, side) => picksOf(m).filter((p) => p[1] === side).map((p) => ` <span style="display:inline-block;padding:0 6px;border-radius:5px;background:var(--ink);color:var(--bg);font-weight:800;font-size:11px">${esc(p[0])}</span>`).join("");
// Skip: the bookmaker (margin taken out) rates our favourite at least 10 points lower than we do.
// In two seasons our favourite then won only 38-43% of the time, and neither side paid reliably.
const skipGap = (m) => {
  if (!m.bh || !m.ba || m.pm == null) return null;
  const ih = 1 / m.bh, ia = 1 / m.ba, qh = ih / (ih + ia), home = m.pm >= 0.5;
  return (home ? qh - m.pm : (1 - qh) - (1 - m.pm));
};
// Not on the NFL page: since the EPA model, the gap there has its own reading.
const skipTag = (m) => { if (["nfl", "nhl", "nba"].includes(D.sports[S.sp].key)) return ""; const g = skipGap(m); return g != null && g <= -0.10 ? ` <span style="display:inline-block;padding:0 6px;border-radius:5px;border:1px solid var(--bad);color:var(--bad);font-weight:800;font-size:11px">SKIP</span>` : ""; };
function ruleCard(s) { return rulesOf(s).map((r) => oneRule(s, r)).join(""); }
// The live record is the bet log: every pick shown before kick-off, at the price when it first appeared,
// kept even if the signal later went away. The season line is the backtest on closing prices.
const settled = (r) => (r.live || []).filter((x) => x.won != null && x.t.slice(0, 10) >= r.tracking_from);
const logRow = (x) => `<tr><td class="l"><span class="sub">${esc(dfmt(x.t.slice(0, 10)))}${x.on === false ? " · signal went away later" : ""}</span>${esc(x.side === "a" ? x.a : x.h)} <span class="sub" style="display:inline">${x.side === "a" ? "away at " + esc(x.h) : "home v " + esc(x.a)}</span></td><td class="mono">${x.price.toFixed(2)}</td><td class="mono">${x.won == null ? "–" : `${x.as_}–${x.hs}${x.pt ? ` <span class="sub" style="display:inline">${esc(x.pt)}</span>` : ""}`}</td><td class="mono">${x.won == null ? '<span class="sub" style="display:inline">open</span>' : `<span class="${x.won ? "ok" : "no"}">${sgn(x.profit)}</span>`}</td></tr>`;
function oneRule(s, r) {
  const reg = r.market === "reg";
  const live = settled(r);
  const recent = [...(r.live || [])].filter((x) => x.t.slice(0, 10) >= r.tracking_from).reverse().slice(0, 12);
  return `<div class="panel" style="padding:12px 14px;margin:10px 0"><b>Rule ${esc(r.name)}${reg ? " · 60 minutes" : ""}</b>
    <p class="note" style="margin-top:6px">${esc(r.text)} ${reg ? "Priced at the bookmaker's estimated 60-minute price: the moneyline chance with the margin taken out, less half our chance of a draw after 60 minutes, with a 7.8% three-way margin on top (this matched real 1X2 prices)." : "Priced at the bookmaker's moneyline."}</p>
    <p class="note" style="margin-top:6px">${esc(r.found)}</p>
    <p class="note" style="margin-top:6px"><b>Bet log</b> from ${esc(dfmt(r.tracking_from))}: ${tally(live)}. Every pick this page showed before kick-off, at the price when it first appeared; a pick stays in even if the signal goes away later, and one that only appears after kick-off is never counted.</p>
    <p class="note" style="margin-top:4px">Backtest this season on closing prices: ${tally(r.record)}. Closing prices include late moves you could not have seen, so this flatters or hurts the rule.</p>
    ${recent.length ? `<div class="tw"><table><thead><tr><th class="l">Pick</th><th>Price</th><th>Result</th><th>Profit</th></tr></thead><tbody>${recent.map(logRow).join("")}</tbody></table></div>` : ""}
    <p class="note" style="margin-top:6px">The ${esc(r.name)} badge in the table marks the side to bet, using the latest price we have seen.</p></div>`;
}
// Excel export: every week (or day) of the season for the open league, away first like the table.
const r1 = (x) => (x == null || !isFinite(x) ? "" : Math.round(x * 10) / 10);
const r2 = (x) => (x == null || !isFinite(x) ? "" : Math.round(x * 100) / 100);
function exportRows(s) {
  const three = s.groups.some((g) => g.games.some((m) => m.p1 != null)), nfl = s.key === "nfl";
  const head = [s.group_kind === "week" ? "Week" : "Date", "Kick-off", "Away", "Home", "Exp. away", "Exp. home", "Exp. total"];
  if (three) head.push("60min away %", "60min draw %", "60min home %", "Odds away", "Odds draw", "Odds home", "Ours incl. OT away %", "Ours incl. OT home %");
  else head.push("Our win % away", "Our win % home", "Odds away", "Odds home");
  if (nfl) head.push("Market spread", "Market total");
  head.push("Book odds away", "Book odds home", "Book win % away", "Book win % home", "Gap away (pts)", "Gap home (pts)", "Score away", "Score home", "Winner", "Our favourite", "Favourite won");
  if (three) head.push("Ended");
  if (rulesOf(s).length) head.push("Rule");
  const rows = [head];
  for (const g of s.groups) for (const m of g.games) {
    const ka = new Date(m.t);
    const r = [s.group_kind === "week" ? +g.g : g.g, ka.toLocaleString("en-GB", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }), m.a, m.h, r1(m.ea), r1(m.eh), r1(m.ea + m.eh)];
    let fav;
    if (three) { r.push(r1(m.p2 * 100), r1(m.px * 100), r1(m.p1 * 100), r2(1 / m.p2), r2(1 / m.px), r2(1 / m.p1), m.pm != null ? r1((1 - m.pm) * 100) : "", m.pm != null ? r1(m.pm * 100) : ""); fav = m.pm != null ? (m.pm >= 0.5 ? m.h : m.a) : ""; }
    else { r.push(r1((1 - m.ph) * 100), r1(m.ph * 100), r2(1 / (1 - m.ph)), r2(1 / m.ph)); fav = m.ph > 0.5 ? m.h : m.ph < 0.5 ? m.a : ""; }
    if (nfl) r.push(m.sp == null ? "" : `${m.h} ${m.sp > 0 ? "-" : "+"}${Math.abs(m.sp)}`, m.tot ?? "");
    let ba = "", bh = "", ga = "", gh = "";
    if (m.bh && m.ba && m.pm != null) { const ia = 1 / m.ba, ih = 1 / m.bh; ba = ia / (ia + ih); bh = ih / (ia + ih); ga = r1(((1 - m.pm) - ba) * 100); gh = r1((m.pm - bh) * 100); ba = r1(ba * 100); bh = r1(bh * 100); }
    const played = m.hs != null, win = played ? (m.hs > m.as_ ? m.h : m.as_ > m.hs ? m.a : "tie") : "";
    r.push(m.ba ? r2(m.ba) : "", m.bh ? r2(m.bh) : "", ba, bh, ga, gh, played ? m.as_ : "", played ? m.hs : "", win, fav, played && fav ? (win === fav ? "yes" : "no") : "");
    if (three) r.push(m.pt || "");
    if (rulesOf(s).length) r.push(picksOf(m).map((p) => `${p[0]} ${p[1] === "h" ? "home" : "away"}`).join(", "));
    rows.push(r);
  }
  return rows;
}
function download(name, blob) {
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}
function loadXLSX() {
  if (window.XLSX) return Promise.resolve(window.XLSX);
  return new Promise((ok, no) => {
    const sc = document.createElement("script");
    sc.src = "https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js";
    sc.onload = () => (window.XLSX ? ok(window.XLSX) : no(new Error("no XLSX"))); sc.onerror = no;
    document.head.appendChild(sc);
  });
}
async function exportExcel() {
  const s = D.sports[S.sp], rows = exportRows(s), name = `${s.label}_${s.season}_fair_odds`.replace(/[^A-Za-z0-9_]+/g, "-");
  try {
    const X = await loadXLSX();
    const ws = X.utils.aoa_to_sheet(rows);
    ws["!cols"] = rows[0].map((h, i) => ({ wch: Math.max(8, Math.min(22, Math.max(...rows.slice(0, 60).map((r) => String(r[i] ?? "").length)) + 2)) }));
    ws["!autofilter"] = { ref: X.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: rows.length - 1, c: rows[0].length - 1 } }) };
    ws["!freeze"] = { xSplit: 0, ySplit: 1 };
    const wb = X.utils.book_new(); X.utils.book_append_sheet(wb, ws, s.label);
    download(name + ".xlsx", new Blob([X.write(wb, { bookType: "xlsx", type: "array" })], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }));
  } catch (e) {
    // Fallback: a CSV that Excel opens too.
    const csv = rows.map((r) => r.map((v) => (/[",;\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : v)).join(",")).join("\r\n");
    download(name + ".csv", new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  }
}
const TABS = () => `<div class="tabs" role="tablist"><button role="tab" aria-selected="${S.sp === -1}" data-sp="-1">Bets</button>${D.sports.map((x, i) => `<button role="tab" aria-selected="${i === S.sp}" data-sp="${i}">${esc(x.label)}</button>`).join("")}</div>`;
const HEAD = () => `<span class="kicker">Updated ${esc(new Date(D.updated).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }))}</span>`;
const LC = { nfl: "#2fb36b", nba: "#f07a2a", nhl: "#4f8df5" }; // one colour per league on the Bets page
const lg = (s) => `<span style="display:inline-block;padding:1px 8px;border-radius:999px;background:${LC[s.key] || "var(--muted)"};color:#fff;font-weight:700;font-size:12px">${esc(s.label)}</span>`;
const lbar = (s) => `box-shadow:inset 4px 0 0 ${LC[s.key] || "transparent"}`;
// The bookmaker's 60-minute price estimated from its moneyline (same formula as the build).
const estReg = (m, side, mg) => { const ih = 1 / m.bh, ia = 1 / m.ba, q = (side === "h" ? ih : ia) / (ih + ia); return 1 / ((q - 0.5 * m.px) * (1 + mg)); };
const dayKey = (t) => new Date(t).toLocaleDateString("en-CA");
const dayLabel = (k) => new Date(k + "T12:00:00").toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });
const hm = (t) => new Date(t).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
// Every pick of every rule, still to be played, and the last few days' results.
function betsPage() {
  const now = Date.now(), open = [], done = [];
  D.sports.forEach((s, si) => {
    const rules = Object.fromEntries(rulesOf(s).map((r) => [r.name, r]));
    s.groups.forEach((g) => g.games.forEach((m) => {
      if (m.hs != null || new Date(m.t).getTime() > now + 7 * 86400e3) return; // the coming week only
      picksOf(m).forEach(([name, side]) => {
        const r = rules[name] || {}, reg = r.market === "reg";
        const team = side === "a" ? m.a : m.h, opp = side === "a" ? m.h : m.a;
        const book = side === "a" ? m.ba : m.bh;
        const ours = reg ? (side === "a" ? m.p2 : m.p1) : (side === "a" ? 1 - m.pm : m.pm);
        const est = reg && m.bh && m.ba ? estReg(m, side, s.reg_margin ?? 0.078) : null;
        open.push({ s, si, m, name, side, reg, team, opp, book, ours, est, started: new Date(m.t).getTime() <= now });
      });
    }));
    rulesOf(s).forEach((r) => (r.live || []).forEach((x) => {
      if (x.won != null) done.push({ s, r, x });
      else if (x.on === false && new Date(x.t).getTime() > now) {
        const reg = r.market === "reg";
        open.push({ s, si, m: { t: x.t, a: x.a, h: x.h }, name: r.name, side: x.side, reg, team: x.side === "a" ? x.a : x.h, opp: x.side === "a" ? x.h : x.a, book: x.price, est: reg ? x.price : null, ours: null, gone: true, started: false });
      }
    }));
  });
  open.sort((a, b) => a.m.t.localeCompare(b.m.t));
  const days = [...new Set(open.map((o) => dayKey(o.m.t)))];
  const cutoff = now - 3 * 86400e3;
  const recent = done.filter((d) => new Date(d.x.t).getTime() >= cutoff).sort((a, b) => b.x.t.localeCompare(a.x.t));
  const row = (o) => `<tr><td class="l mono" style="${lbar(o.s)};padding-left:12px">${esc(hm(o.m.t))}${o.started ? ' <span class="sub" style="display:inline">started</span>' : ""}</td>
    <td class="l">${lg(o.s)}</td><td><span style="display:inline-block;padding:0 6px;border-radius:5px;background:var(--ink);color:var(--bg);font-weight:800;font-size:11px">${esc(o.name)}</span></td>
    <td class="l"><b>${esc(o.team)}</b> <span class="sub" style="display:inline">${o.side === "a" ? "away at " + esc(o.opp) : "home v " + esc(o.opp)}</span>${o.gone ? '<span class="sub">signal went away: do not bet now; if you already did, it still counts</span>' : ""}</td>
    <td class="l">${o.reg ? "60 minutes (1X2)" : "Moneyline"}</td>
    <td class="mono">${o.reg ? `${o.est ? o.est.toFixed(2) : "–"}${o.ours != null ? `<span class="sub">ours ${odd(o.ours)}</span>` : ""}` : (o.book ? o.book.toFixed(2) : "–")}</td>
    <td class="mono">${o.ours != null ? pc(o.ours) : "–"}</td></tr>`;
  const tallyRule = (s, r) => { const live = settled(r); return `<tr><td class="l" style="${lbar(s)};padding-left:12px">${lg(s)}</td><td><span style="display:inline-block;padding:0 6px;border-radius:5px;background:var(--ink);color:var(--bg);font-weight:800;font-size:11px">${esc(r.name)}</span></td><td class="l">${r.market === "reg" ? "60 minutes" : "Moneyline"}</td><td class="l note">${tally(live)}</td><td class="l note">${tally(r.record)}</td></tr>`; };
  app.innerHTML = `${HEAD()}<h1>Bets</h1>
  <p class="note">Every bet our rules call for, across the NFL, NBA and NHL, in your time zone. NBA and NHL picks appear once the bookmaker has a price, usually on the day of the game, and can still come or go as prices move until the last update of the day. The page updates every hour from about 8:00 to 23:00 Budapest time; for the night's NBA and NHL games, look in the evening. Single bets, 1 unit each.</p>
  ${TABS()}
  ${days.length ? days.map((k) => `<div class="panel"><b>${esc(dayLabel(k))}</b><div class="tw"><table><thead><tr><th class="l">Time</th><th class="l">League</th><th>Rule</th><th class="l">Bet on</th><th class="l">Market</th><th>Price</th><th>Our chance</th></tr></thead><tbody>
    ${open.filter((o) => dayKey(o.m.t) === k).map(row).join("")}</tbody></table></div></div>`).join("") : `<div class="panel"><p class="note" style="margin:10px 0">No bets right now. NBA and NHL prices usually come in during the day; check again in the evening.</p></div>`}
  <p class="note">Price: the bookmaker's moneyline (DraftKings, or the NFL market line), the latest we have seen; take the bet if your bookmaker pays about the same or more. For 60-minute bets we have no bookmaker three-way price: the first number is the bookmaker's price estimated from its moneyline (about what you will be offered), the second our own fair odds (the model sees value if your bookmaker pays at least that).</p>
  <div class="panel"><b>Last three days (bet log)</b><div class="tw"><table><thead><tr><th class="l">Game</th><th class="l">League</th><th>Rule</th><th class="l">Bet on</th><th>Price</th><th>Result</th><th>Profit</th></tr></thead><tbody>
    ${recent.length ? recent.map((d) => `<tr><td class="l" style="${lbar(d.s)};padding-left:12px"><span class="sub">${esc(new Date(d.x.t).toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }))}</span>${esc(d.x.a)} @ ${esc(d.x.h)}</td><td class="l">${lg(d.s)}</td><td><span style="display:inline-block;padding:0 6px;border-radius:5px;background:var(--ink);color:var(--bg);font-weight:800;font-size:11px">${esc(d.r.name)}</span></td><td class="l">${esc(d.x.side === "a" ? d.x.a : d.x.h)}${d.r.market === "reg" ? ' <span class="sub" style="display:inline">60 min</span>' : ""}</td><td class="mono">${d.x.price.toFixed(2)}</td><td class="mono">${d.x.as_}–${d.x.hs}${d.x.pt ? ` <span class="sub" style="display:inline">${esc(d.x.pt)}</span>` : ""}</td><td class="mono"><span class="${d.x.won ? "ok" : "no"}">${sgn(d.x.profit)}</span></td></tr>`).join("") : `<tr><td class="l note" colspan="7">No settled bets in the last three days.</td></tr>`}
  </tbody></table></div></div>
  <div class="panel"><b>Rules</b><div class="tw"><table><thead><tr><th class="l">League</th><th>Rule</th><th class="l">Market</th><th class="l">Bet log (live)</th><th class="l">Backtest, closing prices</th></tr></thead><tbody>
    ${D.sports.map((s) => rulesOf(s).map((r) => tallyRule(s, r)).join("")).join("")}</tbody></table></div>
    <p class="note">The full wording of each rule is on its league's tab. Bet log: every pick shown here before kick-off, at the price when it first appeared, kept even if the signal later went away. Backtest: the whole season on closing prices, which include late moves you could not have seen.</p></div>
  ${D.errors && D.errors.length ? `<p class="note">Update problems: ${D.errors.map(esc).join(" · ")}</p>` : ""}`;
}
function render() {
  if (S.sp === -1) return betsPage();
  const s = D.sports[S.sp];
  const keys = s.groups.map((x) => x.g);
  if (!S.g[s.key] || !keys.includes(S.g[s.key])) S.g[s.key] = today(s) || s.current || keys[keys.length - 1];
  const gi = keys.indexOf(S.g[s.key]), G = s.groups[gi];
  const done = G.games.filter((m) => m.hs != null), favOk = done.filter((m) => (m.ph > 0.5) === (m.hs > m.as_)).length;
  const nfl = s.key === "nfl", u = s.unit === "goals" ? "goals" : "points", three = G.games.some((m) => m.p1 != null);
  app.innerHTML = `
  ${HEAD()}
  <h1>Fair odds</h1>
  <p class="note">Our own ratings and odds for the NFL, NBA and NHL: expected ${u}, win chance and fair odds (1 ÷ chance, no bookmaker margin). Times are shown in your time zone. <a href="https://czakopeti.github.io/soccer_stats/odds.html">Football: La Liga, Bundesliga, Serie A, Ligue 1</a></p>
  ${TABS()}
  ${s.stale ? `<p class="note">Today's update for ${esc(s.label)} failed. This is the last good copy.</p>` : ""}
  <div class="bar"><button class="nav" data-step="-1" ${gi === 0 ? "disabled" : ""} aria-label="Previous">‹</button>
    <select id="grp">${s.groups.map((x) => `<option value="${esc(x.g)}" ${x.g === G.g ? "selected" : ""}>${esc(glabel(s, x.g))}${x.g === today(s) ? (s.group_kind === "week" ? " (this week)" : " (today)") : ""}</option>`).join("")}</select>
    <button class="nav" data-step="1" ${gi === keys.length - 1 ? "disabled" : ""} aria-label="Next">›</button>
    <button class="nav" id="xls" title="Every ${s.group_kind === "week" ? "week" : "day"} of the season in one Excel file">Excel ↓</button>
    <span class="note">${s.label} ${esc(s.season)} · ${three && s.reg_known ? `60-minute favourite right ${s.reg_fav_won} of ${s.reg_known} (${s.reg_draws} went to overtime)` : `favourite won ${s.fav_won} of ${s.played}`}${done.length && !three ? ` · this ${s.group_kind === "week" ? "week" : "day"}: ${favOk} of ${done.length}` : ""}</span></div>
  ${ruleCard(s)}
  <div class="panel"><div class="tw"><table><thead><tr><th class="l">Game (away @ home)</th><th>Expected</th><th>Total</th>${three ? "<th>60 min<br>away · draw · home</th><th>Odds<br>away</th><th>Odds<br>draw</th><th>Odds<br>home</th><th>Ours incl. OT<br>away · home</th>" : "<th>Win %<br>away · home</th><th>Odds<br>away</th><th>Odds<br>home</th>"}${nfl ? "<th>Market</th>" : ""}${EDGE_TH}<th>Result</th></tr></thead><tbody>
  ${three ? G.games.map((m) => {
    const p = [m.p1, m.px, m.p2], pick = p.indexOf(Math.max(...p));
    const res = m.hs != null ? `${m.as_}–${m.hs}${m.pt && m.pt !== "REG" ? ` <span class="sub" style="display:inline">${esc(m.pt)}</span>` : ""}${m.reg != null ? ` <span class="${pick === m.reg ? "ok" : "no"}">${pick === m.reg ? "✓" : "✗"}</span>` : ""}` : "–";
    return `<tr><td class="l"><span class="sub">${esc(tfmt(m.t))}</span><span class="${pick === 2 ? "fav" : ""}">${esc(m.a)}</span>${badge(s, m, "a")} @ <span class="${pick === 0 ? "fav" : ""}">${esc(m.h)}</span>${badge(s, m, "h")}${skipTag(m)}</td>
      <td class="mono">${m.ea.toFixed(1)}–${m.eh.toFixed(1)}</td><td class="mono">${(m.ea + m.eh).toFixed(1)}</td><td class="mono">${pc(m.p2)} · ${pc(m.px)} · ${pc(m.p1)}</td>
      <td class="mono">${odd(m.p2)}</td><td class="mono">${odd(m.px)}</td><td class="mono">${odd(m.p1)}</td><td class="mono">${m.pm != null ? odd(1 - m.pm) + " · " + odd(m.pm) : "–"}</td>${edgeCells(m)}<td class="mono">${res}</td></tr>`;
  }).join("") : G.games.map((m) => {
    const res = m.hs != null ? `${m.as_}–${m.hs} <span class="${(m.ph > 0.5) === (m.hs > m.as_) ? "ok" : "no"}">${(m.ph > 0.5) === (m.hs > m.as_) ? "✓" : "✗"}</span>` : "–";
    const fa = m.ph < 0.5, fh = m.ph > 0.5;
    const mkt = nfl ? `<td class="mono">${esc(line(m.sp, m.h))}<span class="sub">total ${m.tot ?? "–"} · ${ml2dec(m.mla) ? ml2dec(m.mla).toFixed(2) : "–"} / ${ml2dec(m.mlh) ? ml2dec(m.mlh).toFixed(2) : "–"}</span></td>` : "";
    return `<tr><td class="l"><span class="sub">${esc(tfmt(m.t))}</span><span class="${fa ? "fav" : ""}">${esc(m.a)}</span>${badge(s, m, "a")} @ <span class="${fh ? "fav" : ""}">${esc(m.h)}</span>${badge(s, m, "h")}${skipTag(m)}</td>
      <td class="mono">${m.ea.toFixed(1)}–${m.eh.toFixed(1)}</td><td class="mono">${(m.ea + m.eh).toFixed(1)}</td><td class="mono">${pc(1 - m.ph)} · ${pc(m.ph)}</td>
      <td class="mono">${odd(1 - m.ph)}</td><td class="mono">${odd(m.ph)}</td>${mkt}${edgeCells(m)}<td class="mono">${res}</td></tr>`;
  }).join("")}
  </tbody></table></div></div>
  <p class="note" style="margin-top:12px">${esc(NOTES[s.key] || "")} The model knows nothing about injuries, rest or lineups.</p>
  <p class="note">Every column reads away first, then home, in the same order as "away @ home" and the result. Book: the bookmaker's away and home moneyline as decimal odds, ${nfl ? "from nflverse (the closing line once a game is played)" : "DraftKings via ESPN: the closing price for games played in the last week and since, the latest price for games to come (prices appear on the day of the game)"}${three ? ", overtime and shootout included, so it is compared with our odds incl. OT" : ""}. Book win %: the chances in those prices with the bookmaker's margin taken out (1 ÷ odds, scaled to add up to 100%). Gap: our win chance minus the bookmaker's, in percentage points, for the away and the home side; green from +5 points.</p>
  ${D.errors && D.errors.length ? `<p class="note">Update problems: ${D.errors.map(esc).join(" · ")}</p>` : ""}`;
}
app.addEventListener("click", (e) => {
  if (e.target.closest("#xls")) { exportExcel(); return; }
  const t = e.target.closest("[data-sp]"); if (t) { S.sp = +t.dataset.sp; save(); render(); return; }
  const n = e.target.closest("[data-step]"); if (n) { const s = D.sports[S.sp], k = s.groups.map((x) => x.g), i = k.indexOf(S.g[s.key]) + +n.dataset.step; if (i >= 0 && i < k.length) { S.g[s.key] = k[i]; render(); } }
});
app.addEventListener("change", (e) => { if (e.target.id === "grp") { S.g[D.sports[S.sp].key] = e.target.value; render(); } });
render();
window.__odds = { S, render };
})();
