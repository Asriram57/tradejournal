#!/usr/bin/env python3
"""Stage 2: one-click 'Sign in with Google', hidden keys, screenshots stored as files in Drive.
Run AFTER patch_sync.py:  python3 patch_google_first.py [path]"""
import sys, shutil
path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
s = open(path, encoding='utf-8').read()
if 'driveImgUpload' in s: sys.exit('Already patched.')
assert 'oaFinish' in s, 'Run patch_sync.py first.'
shutil.copy(path, path + '.bak2')
def sub(old, new):
    global s
    assert s.count(old) == 1, 'anchor not found: ' + old[:70]
    s = s.replace(old, new)

# one-click Google sign-in from the header button
sub("document.getElementById('syncBtn').addEventListener('click', ()=>{ if(syncConnected) syncPush(); else openSettings(); });",
    "document.getElementById('syncBtn').addEventListener('click', ()=>{ if(syncConnected) syncPush(); else if(syncProvider==='gdrive' && GOOGLE_CLIENT_ID) Providers.gdrive.connect(); else openSettings(); });")
sub("btn:L('sync'),", "btn:(syncProvider==='gdrive' ? 'Sign in with Google' : L('sync')),")
# users never see key boxes when the site owner configured config.js
sub("document.getElementById('syncKeyWrap').style.display = (k && !syncConnected) ? '' : 'none';",
    "document.getElementById('syncKeyWrap').style.display = (k && !syncConnected && !k[1]()) ? '' : 'none';")
# data file lives in the 'Trade Pulse Pro' Drive folder; disconnect forgets cached ids
sub("${JSON.stringify({name:SYNC_FILE, mimeType:'application/json'})}",
    "${JSON.stringify(Object.assign({name:SYNC_FILE, mimeType:'application/json'}, id?{}:{parents:[await driveFolder()]}))}")
sub("disconnect(){ driveAccessToken = null; localStorage.removeItem('tp_was_connected_gdrive'); },",
    "disconnect(){ driveAccessToken = null; ['tp_was_connected_gdrive','tp_drive_folder','tp_drive_file_id'].forEach(k=>localStorage.removeItem(k)); },")

sub("function onConnected(){", r'''/* ---- Drive image storage: screenshots become real files in Drive/Trade Pulse Pro ---- */
async function driveFolder(){
  let id = localStorage.getItem('tp_drive_folder'); if(id) return id;
  const H = {Authorization:'Bearer '+driveAccessToken};
  const q = encodeURIComponent("name='Trade Pulse Pro' and mimeType='application/vnd.google-apps.folder' and trashed=false");
  let r = await fetch('https://www.googleapis.com/drive/v3/files?q='+q+'&fields=files(id)', {headers:H});
  if(r.status===401) throw new Error('auth');
  const f = ((await r.json()).files||[])[0]; id = f && f.id;
  if(!id){
    r = await fetch('https://www.googleapis.com/drive/v3/files', {method:'POST', headers:Object.assign({'Content-Type':'application/json'},H), body:JSON.stringify({name:'Trade Pulse Pro', mimeType:'application/vnd.google-apps.folder'})});
    if(r.status===401) throw new Error('auth');
    if(!r.ok) throw new Error('folder '+r.status);
    id = (await r.json()).id;
  }
  localStorage.setItem('tp_drive_folder', id); return id;
}
async function driveImgUpload(dataUrl, name){
  try{
    const blob = await (await fetch(dataUrl)).blob(), b = 'tppimg'+Date.now();
    const meta = JSON.stringify({name, mimeType:'image/jpeg', parents:[await driveFolder()]});
    const body = new Blob(['--'+b+'\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+meta+'\r\n--'+b+'\r\nContent-Type: image/jpeg\r\n\r\n', blob, '\r\n--'+b+'--']);
    const r = await fetch('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart', {method:'POST', headers:{Authorization:'Bearer '+driveAccessToken, 'Content-Type':'multipart/related; boundary='+b}, body});
    if(r.status===401) throw new Error('auth');
    if(!r.ok) throw new Error('img '+r.status);
    return (await r.json()).id;
  }catch(e){ if(e.message==='auth') throw e; localStorage.removeItem('tp_drive_folder'); console.warn('image upload failed', e); return null; }
}
async function driveImgGet(id){
  const r = await fetch('https://www.googleapis.com/drive/v3/files/'+id+'?alt=media', {headers:{Authorization:'Bearer '+driveAccessToken}});
  if(r.status===401) throw new Error('auth');
  if(!r.ok) return null;
  const blob = await r.blob();
  return new Promise(res=>{ const fr = new FileReader(); fr.onload = ()=>res(fr.result); fr.onerror = ()=>res(null); fr.readAsDataURL(blob); });
}
(function(){
  const g = Providers.gdrive, op = g.push.bind(g), ol = g.pull.bind(g);
  g.push = async function(payload){
    const out = [];
    for(const t of payload.trades){
      const c = Object.assign({}, t);
      if(t.image){
        if(!t.imageId || t.imageLen !== t.image.length){
          const id = await driveImgUpload(t.image, 'trade-'+t.id+'.jpg');
          if(id){ t.imageId = id; t.imageLen = t.image.length; try{ localStorage.setItem(TRADES_KEY, JSON.stringify(trades)); }catch(e){} }
        }
        if(t.imageId) delete c.image;
      }
      out.push(c);
    }
    return op(Object.assign({}, payload, {trades: out}));
  };
  g.pull = async function(){
    const r = await ol(); if(!r) return r;
    const need = [];
    for(const t of (r.trades||[])){
      if(t.imageId && !t.image){
        const loc = trades.find(x=>x.id===t.id);
        if(loc && loc.image && loc.imageId===t.imageId) t.image = loc.image; else need.push(t);
      }
    }
    for(let i=0; i<need.length; i+=5)
      await Promise.all(need.slice(i,i+5).map(async t=>{ try{ t.image = await driveImgGet(t.imageId); }catch(e){ if(e.message==='auth') throw e; } }));
    return r;
  };
})();

function onConnected(){''')
open(path, 'w', encoding='utf-8').write(s)
print('Stage 2 OK. Backup:', path + '.bak2')
