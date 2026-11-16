(() => {
/* Fair odds for the NFL, NBA and NHL. Data: data/odds.json, built by scripts/run.py. */
const D = JSON.parse(document.getElementById("data").textContent);
const app = document.getElementById("app");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const odd = (p) => (p > 0 && p < 1 ? (1 / p).toFixed(2) : "–");
const pc = (p) => Math.round(p * 100) + "%";
const S = { sp: 0, g: {} };
try { const s = JSON.parse(localStorage.getItem("am-odds") || "{}"); if (Number.isInteger(s.sp) && s.sp < D.sports.length) S.sp = s.sp; } catch (e) { /* storage blocked */ }
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
  nfl: "Points scored and allowed, adjusted for the opponent. Last season counts as a few games of prior early on. Home advantage 2.6 points. Win chance from a normal spread of results (13.2-point standard deviation). The market line is the closing spread, total and moneyline from nflverse, shown for comparison.",
  nba: "Points scored and allowed, adjusted for the opponent. Each date is predicted only from earlier dates. Half of last season's rating carries over, fading as games pile up. Home advantage is last season's average home margin. Win chance from a normal spread of results (14.6 points).",
  nhl: "Three-way odds for regulation time (60 minutes): away win, draw, home win. Goals scored and allowed in regulation, adjusted for the opponent; an overtime or shootout winner's extra goal is left out. Each date is predicted only from earlier dates. Hockey is close to a coin flip, so the ratings are pulled strongly towards average early on. Chances from Poisson goals. OT and SO mark games decided in overtime or a shootout: a draw after 60 minutes.",
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
const badge = (s, m, side) => (m.pick === side && s.rule ? ` <span style="display:inline-block;padding:0 6px;border-radius:5px;background:var(--ink);color:var(--bg);font-weight:800;font-size:11px">${esc(s.rule.name)}</span>` : "");
// Skip: the bookmaker (margin taken out) rates our favourite at least 10 points lower than we do.
// In two seasons our favourite then won only 38-43% of the time, and neither side paid reliably.
const skipGap = (m) => {
  if (!m.bh || !m.ba || m.pm == null) return null;
  const ih = 1 / m.bh, ia = 1 / m.ba, qh = ih / (ih + ia), home = m.pm >= 0.5;
  return (home ? qh - m.pm : (1 - qh) - (1 - m.pm));
};
const skipTag = (m) => { const g = skipGap(m); return g != null && g <= -0.10 ? ` <span style="display:inline-block;padding:0 6px;border-radius:5px;border:1px solid var(--bad);color:var(--bad);font-weight:800;font-size:11px">SKIP</span>` : ""; };
function ruleCard(s) {
  const r = s.rule; if (!r) return "";
  const live = r.record.filter((x) => x.t.slice(0, 10) >= r.tracking_from);
  const recent = [...live].reverse().slice(0, 12);
  return `<div class="panel" style="padding:12px 14px;margin:10px 0"><b>Rule ${esc(r.name)}</b>
    <p class="note" style="margin-top:6px">${esc(r.text)} Paid at the bookmaker's price; the record uses the closing price.</p>
    <p class="note" style="margin-top:6px">${esc(r.found)}</p>
    <p class="note" style="margin-top:6px">From ${esc(dfmt(r.tracking_from))}, the real test: ${tally(live)}.</p>
    <p class="note" style="margin-top:4px">This season so far${s.key === "nfl" ? "" : ", games with prices (from 1 November)"}: ${tally(r.record)}.</p>
    ${recent.length ? `<div class="tw"><table><thead><tr><th class="l">Pick</th><th>Price</th><th>Result</th><th>Profit</th></tr></thead><tbody>${recent.map((x) => `<tr><td class="l"><span class="sub">${esc(dfmt(x.t.slice(0, 10)))}</span>${esc(x.side === "a" ? x.a : x.h)} <span class="sub" style="display:inline">${x.side === "a" ? "away at " + esc(x.h) : "home v " + esc(x.a)}</span></td><td class="mono">${x.price.toFixed(2)}</td><td class="mono">${x.as_}–${x.hs}</td><td class="mono"><span class="${x.won ? "ok" : "no"}">${sgn(x.profit)}</span></td></tr>`).join("")}</tbody></table></div>` : ""}
    <p class="note" style="margin-top:6px">The ${esc(r.name)} badge in the table marks the side to bet, using the latest price we have seen.</p></div>`;
}
function render() {
  const s = D.sports[S.sp];
  const keys = s.groups.map((x) => x.g);
  if (!S.g[s.key] || !keys.includes(S.g[s.key])) S.g[s.key] = today(s) || s.current || keys[keys.length - 1];
  const gi = keys.indexOf(S.g[s.key]), G = s.groups[gi];
  const done = G.games.filter((m) => m.hs != null), favOk = done.filter((m) => (m.ph > 0.5) === (m.hs > m.as_)).length;
  const nfl = s.key === "nfl", u = s.unit === "goals" ? "goals" : "points", three = G.games.some((m) => m.p1 != null);
  app.innerHTML = `
  <span class="kicker">Updated ${esc(new Date(D.updated).toLocaleString("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }))}</span>
  <h1>Fair odds</h1>
  <p class="note">Our own ratings and odds for the NFL, NBA and NHL: expected ${u}, win chance and fair odds (1 ÷ chance, no bookmaker margin). Times are shown in your time zone. <a href="https://czakopeti.github.io/soccer_stats/odds.html">Football: La Liga, Bundesliga, Serie A, Ligue 1</a></p>
  <div class="tabs" role="tablist">${D.sports.map((x, i) => `<button role="tab" aria-selected="${i === S.sp}" data-sp="${i}">${esc(x.label)}</button>`).join("")}</div>
  ${s.stale ? `<p class="note">Today's update for ${esc(s.label)} failed. This is the last good copy.</p>` : ""}
  <div class="bar"><button class="nav" data-step="-1" ${gi === 0 ? "disabled" : ""} aria-label="Previous">‹</button>
    <select id="grp">${s.groups.map((x) => `<option value="${esc(x.g)}" ${x.g === G.g ? "selected" : ""}>${esc(glabel(s, x.g))}${x.g === today(s) ? (s.group_kind === "week" ? " (this week)" : " (today)") : ""}</option>`).join("")}</select>
    <button class="nav" data-step="1" ${gi === keys.length - 1 ? "disabled" : ""} aria-label="Next">›</button>
    <span class="note">${s.label} ${esc(s.season)} · ${three && s.reg_known ? `60-minute favourite right ${s.reg_fav_won} of ${s.reg_known} (${s.reg_draws} went to overtime)` : `favourite won ${s.fav_won} of ${s.played}`}${done.length && !three ? ` · this ${s.group_kind === "week" ? "week" : "day"}: ${favOk} of ${done.length}` : ""}</span></div>
  ${ruleCard(s)}
  <div class="panel"><div class="tw"><table><thead><tr><th class="l">Game (away @ home)</th><th>Expected</th><th>Total</th>${three ? "<th>60 min<br>away · draw · home</th><th>Odds<br>away</th><th>Odds<br>draw</th><th>Odds<br>home</th><th>Ours incl. OT<br>away · home</th>" : "<th>Win %<br>away · home</th><th>Odds<br>away</th><th>Odds<br>home</th>"}${nfl ? "<th>Market</th>" : ""}${EDGE_TH}<th>Result</th></tr></thead><tbody>
  ${three ? G.games.map((m) => {
    const p = [m.p1, m.px, m.p2], pick = p.indexOf(Math.max(...p));
    const res = m.hs != null ? `${m.as_}–${m.hs}${m.pt && m.pt !== "REG" ? ` <span class="sub" style="display:inline">${esc(m.pt)}</span>` : ""}${m.reg != null ? ` <span class="${pick === m.reg ? "ok" : "no"}">${pick === m.reg ? "✓" : "✗"}</span>` : ""}` : "–";
    return `<tr><td class="l"><span class="sub">${esc(tfmt(m.t))}</span><span class="${pick === 2 ? "fav" : ""}">${esc(m.a)}</span> @ <span class="${pick === 0 ? "fav" : ""}">${esc(m.h)}</span>${skipTag(m)}</td>
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
  <p class="note">SKIP: the bookmaker rates our favourite at least 10 points lower than we do (margin taken out). Usually a missing or rested player we cannot see. Over the last two seasons our favourite then won only 38–43% of the time, and betting either side did not pay reliably, so leave these games alone.</p>
  ${D.errors && D.errors.length ? `<p class="note">Update problems: ${D.errors.map(esc).join(" · ")}</p>` : ""}`;
}
app.addEventListener("click", (e) => {
  const t = e.target.closest("[data-sp]"); if (t) { S.sp = +t.dataset.sp; save(); render(); return; }
  const n = e.target.closest("[data-step]"); if (n) { const s = D.sports[S.sp], k = s.groups.map((x) => x.g), i = k.indexOf(S.g[s.key]) + +n.dataset.step; if (i >= 0 && i < k.length) { S.g[s.key] = k[i]; render(); } }
});
app.addEventListener("change", (e) => { if (e.target.id === "grp") { S.g[D.sports[S.sp].key] = e.target.value; render(); } });
render();
window.__odds = { S, render };
})();
