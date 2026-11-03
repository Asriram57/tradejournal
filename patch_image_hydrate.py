#!/usr/bin/env python3
"""Stage 3: retry missing Drive screenshots after every sync (fixes 'data loads, images missing').
Run after patch_google_first.py:  python3 patch_image_hydrate.py [path]"""
import sys
path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
s = open(path, encoding='utf-8').read()
if 'hydrateImages' in s: sys.exit('Already patched.')
assert 'driveImgGet' in s, 'Run patch_google_first.py first.'
def sub(old, new):
    global s
    assert s.count(old) == 1, 'anchor not found: ' + old[:70]
    s = s.replace(old, new)
sub("    if(remote) await mergeRemoteData(remote); else await syncPush();\n    setSyncStatus('connected');",
    "    if(remote) await mergeRemoteData(remote); else await syncPush();\n    setSyncStatus('connected');\n    hydrateImages();")
sub("function onConnected(){", r'''async function hydrateImages(){
  if(syncProvider!=='gdrive' || !syncConnected || !driveAccessToken) return;
  const need = trades.filter(t=>t.imageId && !t.image);
  if(!need.length) return;
  let got = 0;
  for(let i=0; i<need.length; i+=4){
    await Promise.all(need.slice(i,i+4).map(async t=>{
      try{
        const d = await driveImgGet(t.imageId);
        if(d){ t.image = d; got++; } else console.warn('Drive image not found/denied:', t.imageId);
      }catch(e){ console.warn('Drive image download failed', e); }
    }));
  }
  if(got){ try{ localStorage.setItem(TRADES_KEY, JSON.stringify(trades)); }catch(e){} refreshAll(); }
}

function onConnected(){''')
open(path, 'w', encoding='utf-8').write(s)
print('Stage 3 OK')
