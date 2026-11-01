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
const ml2dec = (ml) => (ml == null ? null : ml > 0 ? 1 + ml / 100 : 1 + 100 / -ml);
const NOTES = {
  nfl: "Points scored and allowed, adjusted for the opponent. Last season counts as a few games of prior early on. Home advantage 2.6 points. Win chance from a normal spread of results (13.2-point standard deviation). The market line is the closing spread, total and moneyline from nflverse, shown for comparison.",
  nba: "Points scored and allowed, adjusted for the opponent. Each date is predicted only from earlier dates. Half of last season's rating carries over, fading as games pile up. Home advantage is last season's average home margin. Win chance from a normal spread of results (14.6 points).",
  nhl: "Three-way odds for regulation time (60 minutes): home win, draw, away win. Goals scored and allowed in regulation, adjusted for the opponent; an overtime or shootout winner's extra goal is left out. Each date is predicted only from earlier dates. Hockey is close to a coin flip, so the ratings are pulled strongly towards average early on. Chances from Poisson goals. OT and SO mark games decided in overtime or a shootout: a draw after 60 minutes.",
};
function render() {
  const s = D.sports[S.sp];
  const keys = s.groups.map((x) => x.g);
  if (!S.g[s.key] || !keys.includes(S.g[s.key])) S.g[s.key] = s.current || keys[keys.length - 1];
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
    <select id="grp">${s.groups.map((x) => `<option value="${esc(x.g)}" ${x.g === G.g ? "selected" : ""}>${esc(glabel(s, x.g))}${x.g === s.current ? " (current)" : ""}</option>`).join("")}</select>
    <button class="nav" data-step="1" ${gi === keys.length - 1 ? "disabled" : ""} aria-label="Next">›</button>
    <span class="note">${s.label} ${esc(s.season)} · ${three && s.reg_known ? `60-minute favourite right ${s.reg_fav_won} of ${s.reg_known} (${s.reg_draws} went to overtime)` : `favourite won ${s.fav_won} of ${s.played}`}${done.length && !three ? ` · this ${s.group_kind === "week" ? "week" : "day"}: ${favOk} of ${done.length}` : ""}</span></div>
  <div class="panel"><div class="tw"><table><thead><tr><th class="l">Game (away @ home)</th><th>Expected</th><th>Total</th>${three ? "<th>Home · Draw · Away (60 min)</th><th>Odds 1</th><th>Odds X</th><th>Odds 2</th>" : "<th>Home win</th><th>Odds away</th><th>Odds home</th>"}${nfl ? "<th>Market</th>" : ""}<th>Result</th></tr></thead><tbody>
  ${three ? G.games.map((m) => {
    const p = [m.p1, m.px, m.p2], pick = p.indexOf(Math.max(...p));
    const res = m.hs != null ? `${m.as_}–${m.hs}${m.pt && m.pt !== "REG" ? ` <span class="sub" style="display:inline">${esc(m.pt)}</span>` : ""}${m.reg != null ? ` <span class="${pick === m.reg ? "ok" : "no"}">${pick === m.reg ? "✓" : "✗"}</span>` : ""}` : "–";
    return `<tr><td class="l"><span class="sub">${esc(tfmt(m.t))}</span><span class="${pick === 2 ? "fav" : ""}">${esc(m.a)}</span> @ <span class="${pick === 0 ? "fav" : ""}">${esc(m.h)}</span></td>
      <td class="mono">${m.ea.toFixed(1)}–${m.eh.toFixed(1)}</td><td class="mono">${(m.ea + m.eh).toFixed(1)}</td><td class="mono">${pc(m.p1)} · ${pc(m.px)} · ${pc(m.p2)}</td>
      <td class="mono">${odd(m.p1)}</td><td class="mono">${odd(m.px)}</td><td class="mono">${odd(m.p2)}</td><td class="mono">${res}</td></tr>`;
  }).join("") : G.games.map((m) => {
    const res = m.hs != null ? `${m.as_}–${m.hs} <span class="${(m.ph > 0.5) === (m.hs > m.as_) ? "ok" : "no"}">${(m.ph > 0.5) === (m.hs > m.as_) ? "✓" : "✗"}</span>` : "–";
    const fa = m.ph < 0.5, fh = m.ph > 0.5;
    const mkt = nfl ? `<td class="mono">${esc(line(m.sp, m.h))}<span class="sub">total ${m.tot ?? "–"} · ${ml2dec(m.mla) ? ml2dec(m.mla).toFixed(2) : "–"} / ${ml2dec(m.mlh) ? ml2dec(m.mlh).toFixed(2) : "–"}</span></td>` : "";
    return `<tr><td class="l"><span class="sub">${esc(tfmt(m.t))}</span><span class="${fa ? "fav" : ""}">${esc(m.a)}</span> @ <span class="${fh ? "fav" : ""}">${esc(m.h)}</span></td>
      <td class="mono">${m.ea.toFixed(1)}–${m.eh.toFixed(1)}</td><td class="mono">${(m.ea + m.eh).toFixed(1)}</td><td class="mono">${pc(m.ph)}</td>
      <td class="mono">${odd(1 - m.ph)}</td><td class="mono">${odd(m.ph)}</td>${mkt}<td class="mono">${res}</td></tr>`;
  }).join("")}
  </tbody></table></div></div>
  <p class="note" style="margin-top:12px">${esc(NOTES[s.key] || "")} The model knows nothing about injuries, rest or lineups.</p>
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
