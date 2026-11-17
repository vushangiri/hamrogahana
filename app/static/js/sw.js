const VERSION='hg-1.3.1';
const ASSETS=['/offline','/static/css/design.css?v=1.3.1','/static/css/app.css?v=1.3.1','/static/js/theme.js?v=1.3.1','/static/js/forms.js?v=1.3.1','/static/js/app.js?v=1.3.1','/static/js/motion.js?v=1.3.1','/static/js/media-editor.js?v=1.3.1','/static/vendor/htmx.min.js','/static/vendor/alpine-csp.min.js','/static/vendor/leaflet.js','/static/vendor/leaflet.css','/static/icons/icon-192.png','/static/icons/icon-512.png'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(VERSION).then(cache=>cache.addAll(ASSETS)).then(()=>self.skipWaiting()))});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==VERSION).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',event=>{const url=new URL(event.request.url);if(url.origin!==self.location.origin)return;if(event.request.method!=='GET'){pendingPages.clear();return;}if(event.request.mode==='navigate'){const key=event.request.url,entry=pendingPages.get(key);pendingPages.delete(key);event.respondWith((async()=>{if(entry&&Date.now()-entry.at<8000){const response=await entry.response;if(response)return response;}return fetch(event.request)})().catch(()=>caches.match('/offline')));return}if(ASSETS.includes(url.pathname+url.search)&&url.pathname!=='/offline'){event.respondWith(caches.open(VERSION).then(async cache=>{const hit=await cache.match(event.request);return hit||fetch(event.request)}))}});

// At most three speculative documents, kept only in worker memory for eight seconds.
// A normal navigation consumes its response once; mutations invalidate all speculation.
const pendingPages=new Map();
function navigationURL(raw){const url=new URL(raw,self.location.origin);return url.origin===self.location.origin&&(/^\/(saved|stores|reels|products)(\/|$)/.test(url.pathname))?url.href:null}
self.addEventListener('message',event=>{
 if(event.data?.type==='clear-prefetch'){pendingPages.clear();return}
 if(event.data?.type!=='prefetch')return;
 const url=navigationURL(event.data.url);if(!url)return;if(pendingPages.has(url)&&Date.now()-pendingPages.get(url).at<8000)return;
 while(pendingPages.size>=3)pendingPages.delete(pendingPages.keys().next().value);
 const entry={at:Date.now()};pendingPages.set(url,entry);
 entry.response=fetch(url,{headers:{'X-HG-Prefetch':'1'},cache:'no-store'}).then(response=>response.ok&&!response.redirected?response:null).catch(()=>null);
 event.waitUntil(entry.response);
});
