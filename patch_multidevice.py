#!/usr/bin/env python3
"""Stage 4: several devices signed in at once. Record-level merge (no overwriting), delete tombstones,
auto-refresh every 60 s and on tab focus, Google token kept + silently renewed, 'Tap to reconnect' instead of logout.
Run after patch_image_hydrate.py:  python3 patch_multidevice.py [path]"""
import sys, re
path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
s = open(path, encoding='utf-8').read()
if 'syncAll' in s: sys.exit('Already patched.')
assert 'hydrateImages' in s, 'Run patch_image_hydrate.py first.'
def sub(old, new):
    global s
    assert s.count(old) == 1, 'anchor not found: ' + old[:70]
    s = s.replace(old, new)

# Google token: remember it, renew it, never throw the session away
sub("console.warn('Drive auth error', resp);", "console.warn('Drive auth error', resp); if(window.__gRefresh){ const f=window.__gRefresh; window.__gRefresh=null; f(false); return; }")
sub("driveAccessToken = resp.access_token;", "driveAccessToken = resp.access_token; try{ localStorage.setItem('tp_gtok', JSON.stringify({t:driveAccessToken, exp:Date.now()+((resp.expires_in||3600)-120)*1000})); }catch(e){}\n          if(window.__gRefresh){ const f=window.__gRefresh; window.__gRefresh=null; f(true); return; }")
sub("['tp_was_connected_gdrive','tp_drive_folder','tp_drive_file_id']", "['tp_was_connected_gdrive','tp_drive_folder','tp_drive_file_id','tp_gtok']")
sub("g.push = async function(payload){\n    const out = [];", "g.push = async function(payload){\n    await ensureGToken();\n    const out = [];")
sub("g.pull = async function(){\n    const r = await ol(); if(!r) return r;", "g.pull = async function(){\n    await ensureGToken();\n    const r = await ol(); if(!r) return r;")
sub("    if(localStorage.getItem('tp_was_connected_gdrive')==='1' && GOOGLE_CLIENT_ID){",
    "    const _o = (()=>{ try{ return JSON.parse(localStorage.getItem('tp_gtok')||'null'); }catch(e){ return null; } })();\n    if(_o && Date.now()<_o.exp && localStorage.getItem('tp_was_connected_gdrive')==='1'){ driveAccessToken=_o.t; onConnected(); }\n    else if(localStorage.getItem('tp_was_connected_gdrive')==='1' && GOOGLE_CLIENT_ID){")
sub("function schedulePush(){\n  touchLocal();", "function schedulePush(){\n  if(stamp(true)) persistAll();\n  syncDirty = true;\n  touchLocal();")
sub("  oaFinish().then(p=>{", "  if(!localStorage.getItem(SNAP_KEY)) stamp(false);\n  oaFinish().then(p=>{")

# replace syncPull + syncPush with one merge-based engine
s, n = re.subn(r"async function syncPull\(\)\{.*?(?=function handleSyncError)",
  lambda m: "async function syncPull(){ return syncAll(false,false); }\nasync function syncPush(){ return syncAll(syncDirty,false); }\n", s, count=1, flags=re.S)
assert n == 1, 'syncPull/syncPush not found'

sub("function onConnected(){", r'''/* ---- multi-device: record-level merge, tombstones, auto refresh ---- */
const SNAP_KEY = 'tp_snap', TOMB_KEY = 'tp_tomb';
let syncDirty = false, needReauth = false, lastRemoteTs = 0;
const _jp = (k,d)=>{ try{ return JSON.parse(localStorage.getItem(k)||'null') || d; }catch(e){ return d; } };
function _sig(x){
  const str = JSON.stringify(x, (k,v)=> k==='_u' ? undefined : (k==='image' && typeof v==='string' ? v.length : v));
  let h = 5381; for(let i=0;i<str.length;i++) h = ((h<<5)+h+str.charCodeAt(i))|0; return h;
}
function persistAll(){
  try{ localStorage.setItem(TRADES_KEY, JSON.stringify(trades)); localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts)); localStorage.setItem(JOURNAL_KEY, JSON.stringify(journalEntries)); }catch(e){}
}
function stamp(doStamp){
  const snap = _jp(SNAP_KEY,{}), tomb = _jp(TOMB_KEY,{}), now = Date.now(), cur = {}; let changed = false;
  [['t',trades],['a',accounts],['j',journalEntries]].forEach(([p,arr])=>arr.forEach(x=>{
    const key = p+':'+x.id, sg = _sig(x); cur[key] = sg;
    if(doStamp && snap[key]!==sg){ x._u = now; changed = true; }
    if(tomb[key] && tomb[key] < (x._u||0)) delete tomb[key];
  }));
  if(doStamp) for(const k in snap) if(!(k in cur) && !tomb[k]){ tomb[k] = now; changed = true; }
  localStorage.setItem(SNAP_KEY, JSON.stringify(cur)); localStorage.setItem(TOMB_KEY, JSON.stringify(tomb));
  return changed;
}
function mergeLists(p, local, remote, tomb){
  const m = new Map(); (remote||[]).forEach(x=>m.set(x.id,x));
  (local||[]).forEach(x=>{ const o = m.get(x.id); if(!o || (x._u||0) >= (o._u||0)) m.set(x.id,x); });
  return Array.from(m.values()).filter(x=>{ const d = tomb[p+':'+x.id]; return !(d && d > (x._u||0)); });
}
function newerThan(arr, other){
  const o = new Map((other||[]).map(x=>[x.id,x]));
  return arr.some(x=>{ const r = o.get(x.id); return !r || (x._u||0) > (r._u||0); });
}
async function ensureGToken(){
  const o = _jp('tp_gtok', null);
  if(o && Date.now() < o.exp){ driveAccessToken = o.t; return; }
  const ok = await new Promise(res=>{
    window.__gRefresh = res;
    setTimeout(()=>{ if(window.__gRefresh===res){ window.__gRefresh = null; res(false); } }, 20000);
    try{ if(!Providers.gdrive.setup()) throw 0; driveTokenClient.requestAccessToken({prompt:''}); }catch(e){ window.__gRefresh = null; res(false); }
  });
  if(!ok) throw new Error('reauth');
}
async function syncAll(force, auto){
  if(!syncConnected || syncBusy) return;
  if(auto && needReauth) return;
  syncBusy = true; setSyncStatus('syncing');
  try{
    if(stamp(true)) persistAll();
    const prov = Providers[syncProvider];
    const remote = await prov.pull();
    let needPush = !!force || syncDirty || !remote, changedLocal = false;
    if(remote){
      const tomb = Object.assign({}, remote.tombstones||{}), lt = _jp(TOMB_KEY,{});
      for(const k in lt) tomb[k] = Math.max(tomb[k]||0, lt[k]);
      const old = new Map(trades.map(t=>[t.id,t]));
      const mt = mergeLists('t', trades, remote.trades, tomb), ma = mergeLists('a', accounts, remote.accounts, tomb), mj = mergeLists('j', journalEntries, remote.journalEntries, tomb);
      mt.forEach(t=>{ if(t.imageId && !t.image){ const o = old.get(t.id); if(o && o.image && o.imageId===t.imageId) t.image = o.image; } });
      needPush = needPush || newerThan(mt,remote.trades) || newerThan(ma,remote.accounts) || newerThan(mj,remote.journalEntries) || Object.keys(tomb).length > Object.keys(remote.tombstones||{}).length;
      changedLocal = (remote.updatedAt||0) !== lastRemoteTs;
      trades = mt; accounts = ma.length ? ma : [{id:'default', name:'Main Account'}]; journalEntries = mj;
      if((remote.updatedAt||0) > (parseInt(localStorage.getItem('tp_local_updated_at')||'0',10)) && remote.settings){ settings = Object.assign(settings, remote.settings); delete settings.theme; }
      localStorage.setItem(TOMB_KEY, JSON.stringify(tomb));
      saveTrades(true); saveAccounts(true); saveJournal(true); saveSettings(true);
      stamp(false); lastRemoteTs = remote.updatedAt||0;
    }
    if(needPush){
      const payload = {trades, accounts, settings, journalEntries, tombstones:_jp(TOMB_KEY,{}), updatedAt:Date.now()};
      await prov.push(payload);
      localStorage.setItem('tp_local_updated_at', String(payload.updatedAt));
      lastRemoteTs = payload.updatedAt; syncDirty = false; stamp(false);
    }
    if(changedLocal){ renderAccountSelect(); refreshAll(); }
    needReauth = false; syncBusy = false; setSyncStatus('connected');
    hydrateImages();
  }catch(e){
    syncBusy = false;
    if(e && e.message==='reauth'){ needReauth = true; setSyncStatus('error'); const b = document.getElementById('syncBtnText'); if(b) b.textContent = 'Tap to reconnect'; return; }
    handleSyncError(e);
  }
}
setInterval(()=>{ if(document.visibilityState==='visible') syncAll(false,true); }, 60000);
document.addEventListener('visibilitychange', ()=>{ if(document.visibilityState==='visible') syncAll(false,true); });

function onConnected(){''')
open(path, 'w', encoding='utf-8').write(s)
print('Stage 4 OK')
