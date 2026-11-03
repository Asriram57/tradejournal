#!/usr/bin/env python3
"""Upgrades Trade Pulse Pro's cloud sync for static hosting (GitHub Pages).
Usage: put your current app file here as index.html, then run: python3 patch_sync.py [path]"""
import re, sys, shutil
path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
s = open(path, encoding='utf-8').read()
if 'oaFinish' in s: sys.exit('Already patched.')
shutil.copy(path, path + '.bak')

def sub(old, new, count_ok=1):
    global s
    assert s.count(old) == count_ok, 'anchor not found: ' + old[:60]
    s = s.replace(old, new)

def rsub(pat, new, flags=0):
    global s
    s, n = re.subn(pat, lambda m: new, s, count=1, flags=flags)
    assert n == 1, 'pattern not found: ' + pat[:60]

def rsub_tail(pat, new, flags=0):
    global s
    i = s.index('const Providers = {')
    t, n = re.subn(pat, lambda m: new, s[i:], count=1, flags=flags)
    assert n == 1, 'pattern not found: ' + pat[:60]
    s = s[:i] + t

# 1. keys: config.js -> localStorage override
rsub(r"const GOOGLE_CLIENT_ID = '[^']*';\s*const DROPBOX_APP_KEY = '[^']*';", r'''const CFG = Object.assign({googleClientId:'',dropboxAppKey:'',onedriveClientId:''}, window.TP_CONFIG||{});
const _ls = k => { try{ return localStorage.getItem(k)||''; }catch(e){ return ''; } };
let GOOGLE_CLIENT_ID = _ls('tp_cfg_google') || CFG.googleClientId;
let DROPBOX_APP_KEY = _ls('tp_cfg_dropbox') || CFG.dropboxAppKey;
let ONEDRIVE_CLIENT_ID = _ls('tp_cfg_onedrive') || CFG.onedriveClientId;''')

# 2. OAuth (PKCE, refresh tokens, no backend/secret) helpers
sub("const Providers = {", r'''/* ---- OAuth 2 PKCE for static sites (Dropbox, OneDrive) ---- */
const REDIRECT = location.origin + location.pathname;
const OA = {
  dropbox:{auth:'https://www.dropbox.com/oauth2/authorize', token:'https://api.dropboxapi.com/oauth2/token', id:()=>DROPBOX_APP_KEY, scope:''},
  onedrive:{auth:'https://login.microsoftonline.com/common/oauth2/v2.0/authorize', token:'https://login.microsoftonline.com/common/oauth2/v2.0/token', id:()=>ONEDRIVE_CLIENT_ID, scope:'Files.ReadWrite.AppFolder offline_access'}
};
async function pkcePair(){
  const abc='abcdefghijklmnopqrstuvwxyz0123456789';
  const v=Array.from(crypto.getRandomValues(new Uint8Array(64))).map(b=>abc[b%36]).join('');
  const d=await crypto.subtle.digest('SHA-256', new TextEncoder().encode(v));
  const c=btoa(String.fromCharCode(...new Uint8Array(d))).replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'');
  return {v,c};
}
async function oauthStart(prov, extra){
  const p = await pkcePair(), cfg = OA[prov];
  localStorage.setItem('tp_pkce', JSON.stringify({prov, v:p.v}));
  const q = new URLSearchParams(Object.assign({client_id:cfg.id(), response_type:'code', redirect_uri:REDIRECT, code_challenge:p.c, code_challenge_method:'S256'}, cfg.scope?{scope:cfg.scope}:{}, extra||{}));
  location.href = cfg.auth + '?' + q;
}
async function oaPost(url, body){
  const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded'}, body:new URLSearchParams(body)});
  if(!r.ok) throw new Error('auth');
  return r.json();
}
function oaSave(prov, t){
  const o = JSON.parse(localStorage.getItem('tp_oa_'+prov)||'{}');
  o.access = t.access_token; o.refresh = t.refresh_token || o.refresh; o.exp = Date.now() + (t.expires_in||3600)*1000 - 60000;
  localStorage.setItem('tp_oa_'+prov, JSON.stringify(o));
  return o.access;
}
async function oaToken(prov){
  const o = JSON.parse(localStorage.getItem('tp_oa_'+prov)||'null');
  if(!o) throw new Error('auth');
  if(Date.now() < o.exp) return o.access;
  if(!o.refresh) throw new Error('auth');
  const c = OA[prov], body = {grant_type:'refresh_token', refresh_token:o.refresh, client_id:c.id()};
  if(c.scope) body.scope = c.scope;
  return oaSave(prov, await oaPost(c.token, body));
}
async function oaFinish(){
  const code = new URLSearchParams(location.search).get('code'), st = localStorage.getItem('tp_pkce');
  if(!code || !st) return null;
  localStorage.removeItem('tp_pkce'); history.replaceState(null,'',REDIRECT);
  const {prov, v} = JSON.parse(st), c = OA[prov];
  const body = {grant_type:'authorization_code', code, redirect_uri:REDIRECT, client_id:c.id(), code_verifier:v};
  if(c.scope) body.scope = c.scope;
  try{ oaSave(prov, await oaPost(c.token, body)); return prov; }catch(e){ alert('Sign-in failed. Check the key and the redirect URI (see README).'); return null; }
}
function saveKey(){
  const v = document.getElementById('syncKey').value.trim(); if(!v) return;
  if(syncProvider==='gdrive'){ GOOGLE_CLIENT_ID=v; driveTokenClient=null; localStorage.setItem('tp_cfg_google',v); }
  else if(syncProvider==='dropbox'){ DROPBOX_APP_KEY=v; localStorage.setItem('tp_cfg_dropbox',v); }
  else if(syncProvider==='onedrive'){ ONEDRIVE_CLIENT_ID=v; localStorage.setItem('tp_cfg_onedrive',v); }
}

const Providers = {''')

# 3. Dropbox (PKCE) + OneDrive providers
rsub_tail(r"  dropbox:\{.*?(?=\n  gist:\{)", r'''  dropbox:{
    needsToken:false,
    help:'Create a free app at the <b>Dropbox App Console</b> (Scoped access → <b>App folder</b>, enable <code>files.content.read</code> + <code>files.content.write</code>), add this page\'s exact URL as a <b>Redirect URI</b>, paste the <b>App key</b> above and press Connect. Sign-in lasts (auto-refresh). Data goes to <code>Apps/&lt;your app&gt;/trade-pulse-pro-data.json</code>.',
    async connect(){ if(!DROPBOX_APP_KEY){ alert('Paste your Dropbox App key first.'); return; } await oauthStart('dropbox', {token_access_type:'offline'}); },
    disconnect(){ localStorage.removeItem('tp_oa_dropbox'); },
    async pull(){
      const res = await fetch('https://content.dropboxapi.com/2/files/download', {method:'POST', headers:{Authorization:'Bearer '+await oaToken('dropbox'), 'Dropbox-API-Arg': JSON.stringify({path:'/'+SYNC_FILE})}});
      if(res.status===401) throw new Error('auth');
      if(res.status===409) return null;
      if(!res.ok) throw new Error('dropbox '+res.status);
      return res.json();
    },
    async push(payload){
      const res = await fetch('https://content.dropboxapi.com/2/files/upload', {method:'POST', headers:{Authorization:'Bearer '+await oaToken('dropbox'), 'Content-Type':'application/octet-stream', 'Dropbox-API-Arg': JSON.stringify({path:'/'+SYNC_FILE, mode:'overwrite', mute:true})}, body: JSON.stringify(payload)});
      if(res.status===401) throw new Error('auth');
      if(!res.ok) throw new Error('dropbox upload '+res.status);
    }
  },

  onedrive:{
    needsToken:false,
    help:'Register an app in <b>Azure → App registrations</b> (accounts: personal + work), add platform <b>Single-page application</b> with this page\'s exact URL as redirect URI, paste the <b>Application (client) ID</b> above and press Connect. Data goes to your OneDrive <code>Apps</code> folder.',
    url(){ return 'https://graph.microsoft.com/v1.0/me/drive/special/approot:/'+SYNC_FILE+':/content'; },
    async connect(){ if(!ONEDRIVE_CLIENT_ID){ alert('Paste your Azure client ID first.'); return; } await oauthStart('onedrive'); },
    disconnect(){ localStorage.removeItem('tp_oa_onedrive'); },
    async pull(){
      const res = await fetch(this.url(), {headers:{Authorization:'Bearer '+await oaToken('onedrive')}});
      if(res.status===401) throw new Error('auth');
      if(res.status===404) return null;
      if(!res.ok) throw new Error('onedrive '+res.status);
      return res.json();
    },
    async push(payload){
      const res = await fetch(this.url(), {method:'PUT', headers:{Authorization:'Bearer '+await oaToken('onedrive'), 'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      if(res.status===401) throw new Error('auth');
      if(!res.ok) throw new Error('onedrive upload '+res.status);
    }
  },
''', re.DOTALL)

# 4. wiring
sub("else if(syncProvider==='dropbox' && Providers.dropbox.tok()){ onConnected(); }",
    "else if((syncProvider==='dropbox'||syncProvider==='onedrive') && localStorage.getItem('tp_oa_'+syncProvider)){ onConnected(); }")
sub("  refreshAll();\n  initSync();\n  initMantras();",
    "  refreshAll();\n  oaFinish().then(p=>{ if(p){ syncProvider=p; localStorage.setItem('tp_sync_provider',p); } initSync(); });\n  initMantras();")
sub("({gdrive:'Google Drive', dropbox:'Dropbox', gist:'GitHub Gist', file:'Local file'})",
    "({gdrive:'Google Drive', dropbox:'Dropbox', onedrive:'OneDrive', gist:'GitHub Gist', file:'Local file'})")
sub('<option value="dropbox">Dropbox</option>', '<option value="dropbox">Dropbox</option>\n            <option value="onedrive">OneDrive</option>')
sub('Local file / synced folder (OneDrive, iCloud, Dropbox app)', 'Local file / synced folder (TeraBox, pCloud, MEGA, iCloud…)')
sub("your OneDrive, iCloud Drive, Dropbox or Google Drive desktop app", "your TeraBox, pCloud, MEGA, OneDrive, iCloud, Dropbox or Google Drive desktop app")
sub('<div class="sync-actions">', '''<div class="field" id="syncKeyWrap" style="display:none; margin-top:10px;"><label id="syncKeyLabel">Client ID</label><input id="syncKey" autocomplete="off" placeholder="Paste your own Client ID / App key"></div>
        <div class="sync-actions">''')
sub("document.getElementById('syncHelp').innerHTML = p.help;", r'''document.getElementById('syncHelp').innerHTML = p.help;
  const kmap = {gdrive:['Google OAuth Client ID',()=>GOOGLE_CLIENT_ID], dropbox:['Dropbox App key',()=>DROPBOX_APP_KEY], onedrive:['Azure Application (client) ID',()=>ONEDRIVE_CLIENT_ID]}, k = kmap[syncProvider];
  document.getElementById('syncKeyWrap').style.display = (k && !syncConnected) ? '' : 'none';
  if(k){ document.getElementById('syncKeyLabel').textContent = k[0]; document.getElementById('syncKey').value = k[1](); }''')
sub("try{ await Providers[syncProvider].connect(); }", "try{ saveKey(); await Providers[syncProvider].connect(); }")
sub('<script src="https://accounts.google.com/gsi/client" async defer></script>', '<script src="config.js"></script>\n<script src="https://accounts.google.com/gsi/client" async defer></script>')

open(path, 'w', encoding='utf-8').write(s)
print('Patched OK. Backup saved as', path + '.bak')
