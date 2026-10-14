const sc = $('Dip-regels').first().json;
const existing = $input.all().map((i) => i.json).filter((r) => r && r.id);
const active = {};
for (const e of existing) { if (!active[e.ticker]) active[e.ticker] = e; }
const patches = [], inserts = [];
for (const a of sc.alertCandidates) {
  const ex = active[a.ticker];
  if (ex) {
    const old = Number(ex.peak_score);
    if (!(old >= a.score)) patches.push({ json: { kind: 'patch', id: ex.id, patch: { peak_score: a.score, peak_score_at: a.alert_timestamp } } });
  } else inserts.push(a);
}
const out = patches.slice();
if (inserts.length) out.push({ json: { kind: 'insert', rows: inserts } });
return out;