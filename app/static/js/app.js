'use strict';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
function read(key,fallback){try{return JSON.parse(localStorage.getItem(key))??fallback}catch{return fallback}}
function write(key,value){try{localStorage.setItem(key,JSON.stringify(value));return true}catch{toast('Device storage is unavailable.');return false}}
let toastTimer;
function toast(message){const t=$('#toast');if(!t)return;t.textContent=message;t.classList.remove('hidden');clearTimeout(toastTimer);toastTimer=setTimeout(()=>t.classList.add('hidden'),4000)}
function savedButtons(){const saved=new Set(read('hg-saved',[]));$$('[data-save]').forEach(b=>{const on=saved.has(b.dataset.save);b.textContent=b.classList.contains('saveBtn')?(on?'♥':'♡'):(on?'♥ Saved':'♡ Save');b.setAttribute('aria-pressed',String(on))})}
const loc=read('hg-location',null);
if(loc){$$('.locationLabel').forEach(el=>el.textContent='⌖ '+loc.label);const form=$('#searchForm');if(form){form.elements.lat.value=loc.lat;form.elements.lon.value=loc.lon}if(['/','/stores'].includes(location.pathname)&&!new URLSearchParams(location.search).has('lat')){const url=new URL(location.href);url.searchParams.set('lat',loc.lat);url.searchParams.set('lon',loc.lon);location.replace(url)}}
if(location.pathname==='/saved'){const ids=read('hg-saved',[]).slice(0,100).join(',');const url=new URL(location.href);if((url.searchParams.get('ids')||'')!==ids){url.searchParams.set('ids',ids);location.replace(url)}}
savedButtons();
document.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.hasAttribute('data-category')){const form=$('#searchForm');form.elements.category.value=b.dataset.category;$$('[data-category]').forEach(x=>x.classList.toggle('active',x===b));form.requestSubmit()}if(b.dataset.save){let ids=read('hg-saved',[]),id=b.dataset.save;if(ids.includes(id))ids=ids.filter(x=>x!==id);else{if(ids.length>=100)return toast('You can save up to 100 pieces on this device.');ids.push(id)}if(write('hg-saved',ids)){savedButtons();toast(ids.includes(id)?'Jewellery saved':'Removed from saved')}}if(b.dataset.theme)window.hgTheme(b.dataset.theme);if(b.hasAttribute('data-back'))history.back()});
document.addEventListener('htmx:afterSwap',()=>savedButtons());
document.addEventListener('htmx:responseError',e=>toast(e.detail.xhr.status===400?'Check your search filters.':'Could not load results. Please try again.'));
document.addEventListener('htmx:sendError',()=>toast('Connection lost. Please try again.'));
// Native document navigation retains browser history and back-scroll restoration.
if('scrollRestoration' in history)history.scrollRestoration='auto';
let slide=0;const banners=$$('[data-banner]');function showSlide(n){if(!banners.length)return;slide=(n+banners.length)%banners.length;banners.forEach((el,i)=>el.classList.toggle('hidden',i!==slide));$$('[data-dot]').forEach((el,i)=>el.classList.toggle('active',i===slide))}$$('[data-slide]').forEach(b=>b.addEventListener('click',()=>showSlide(slide+Number(b.dataset.slide))));$$('[data-dot]').forEach(b=>b.addEventListener('click',()=>showSlide(Number(b.dataset.dot))));if(!matchMedia('(prefers-reduced-motion: reduce)').matches)setInterval(()=>{if(!document.hidden&&!document.activeElement?.closest('.bannerCarousel'))showSlide(slide+1)},6500);
function map(container,lat,lon,tileURL){if(!window.L){container.textContent='Map could not load. Use the coordinate fields below.';return null}const m=L.map(container).setView([lat,lon],14);L.tileLayer(tileURL,{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(m);return m}
$$('.mapPicker').forEach(picker=>{const lat=$('[name=latitude]',picker),lon=$('[name=longitude]',picker);if(location.pathname==='/location'&&loc){lat.value=loc.lat;lon.value=loc.lon;$('#locationName').value=loc.label}const m=map($('.realMap',picker),Number(lat.value),Number(lon.value),picker.dataset.tileUrl);let marker=m?L.marker([Number(lat.value),Number(lon.value)],{draggable:true}).addTo(m):null;function setPoint(a,b,label){if(!Number.isFinite(Number(a))||!Number.isFinite(Number(b))||Math.abs(a)>90||Math.abs(b)>180)return toast('Enter valid coordinates.');lat.value=Number(a).toFixed(7);lon.value=Number(b).toFixed(7);marker?.setLatLng([a,b]);m?.panTo([a,b]);if(label&&$('#locationName'))$('#locationName').value=label;if(label&&$('#address'))$('#address').value=label}m?.on('click',e=>setPoint(e.latlng.lat,e.latlng.lng));marker?.on('dragend',()=>{const p=marker.getLatLng();setPoint(p.lat,p.lng)});[lat,lon].forEach(el=>el.addEventListener('change',()=>setPoint(lat.value,lon.value)));$('[data-geolocate]',picker).addEventListener('click',()=>{if(!navigator.geolocation)return toast('Geolocation is unavailable.');navigator.geolocation.getCurrentPosition(p=>setPoint(p.coords.latitude,p.coords.longitude,'Current location'),()=>toast('Location permission denied or unavailable. Choose a pin instead.'),{enableHighAccuracy:true,timeout:10000,maximumAge:60000})});const search=$('[data-geosearch]',picker);search.addEventListener('click',async()=>{const q=$('#placeQuery',picker).value.trim();if(!q)return;const results=$('.geoResults',picker);search.disabled=true;results.textContent='Searching…';try{const response=await fetch('/api/geocode?q='+encodeURIComponent(q));const data=await response.json();if(!response.ok)throw new Error(data.error||'Search unavailable');results.replaceChildren();data.forEach(item=>{const b=document.createElement('button');b.type='button';b.className='ghost';b.textContent=item.label;b.addEventListener('click',()=>{setPoint(Number(item.lat),Number(item.lon),item.label);results.replaceChildren()});results.append(b)});if(!data.length)results.textContent='No matches. Place a pin manually.'}catch(error){results.textContent=error.message}finally{search.disabled=false}});$('#placeQuery',picker).addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();search.click()}})});
$('#applyLocation')?.addEventListener('click',()=>{const lat=Number($('#latitude').value),lon=Number($('#longitude').value);if(!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)return toast('Enter valid coordinates.');if(write('hg-location',{lat,lon,label:$('#locationName').value.trim()||'Selected location'}))location.href=`/?lat=${lat}&lon=${lon}`});
const storesMap=$('#storesMap');if(storesMap){const markers=$$('.storeMarker');const m=map(storesMap,Number(markers[0]?.dataset.lat||loc?.lat||27.704),Number(markers[0]?.dataset.lon||loc?.lon||85.311),storesMap.dataset.tileUrl);if(m){markers.forEach(el=>{const marker=L.marker([Number(el.dataset.lat),Number(el.dataset.lon)]).addTo(m);const popup=document.createElement('div');popup.textContent=el.querySelector('strong')?.textContent||el.textContent;marker.bindPopup(popup)});if(markers.length>1)m.fitBounds(markers.map(el=>[Number(el.dataset.lat),Number(el.dataset.lon)]),{padding:[25,25]})}}
document.addEventListener('submit',e=>{const form=e.target.closest('form[data-upload]');if(!form)return;e.preventDefault();const xhr=new XMLHttpRequest(),progress=$('progress',form),button=$('button',form),status=$('.uploadStatus',form);button.disabled=true;progress.classList.remove('hidden');xhr.open('POST',form.action);xhr.upload.addEventListener('progress',event=>{if(event.lengthComputable){progress.value=event.loaded/event.total*100;status.textContent=Math.round(progress.value)+'% uploaded'}});xhr.addEventListener('load',()=>{if(xhr.status>=200&&xhr.status<300)location.href='/merchant?tab=Media';else{button.disabled=false;const page=new DOMParser().parseFromString(xhr.responseText,'text/html');status.textContent=page.querySelector('[role=alert]')?.textContent||'Upload failed. Check the file and try again.'}});xhr.addEventListener('error',()=>{button.disabled=false;status.textContent='Connection lost. Check upload status before retrying.'});xhr.send(new FormData(form))});
const reelObserved = new WeakSet();
function initReels(){
  const videos = $$('video[data-src]');
  if (!('IntersectionObserver' in window)) return;
  videos.filter(v => !reelObserved.has(v)).forEach(v => {
    reelObserved.add(v);
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if(entry.intersectionRatio > .65 && !document.hidden){
        if(!v.src){v.src=v.dataset.src;v.load()}
        v.play().catch(()=>{});
      } else v.pause();
    }), {root: $('.reelFeed'), threshold:[0,.65]});
    observer.observe(v);
  });
}
initReels();
document.addEventListener('visibilitychange',()=>{if(document.hidden)$$('video[data-src]').forEach(v=>v.pause())});
let installPrompt;
const standalone=()=>window.matchMedia('(display-mode: standalone)').matches||navigator.standalone===true;
const installBanner=$('#installBanner'),installButton=$('#installApp'),installMessage=$('#installMessage');
function showInstallBanner(){if(installBanner&&!standalone())installBanner.classList.remove('hidden')}
showInstallBanner();
window.matchMedia('(display-mode: standalone)').addEventListener('change',()=>{if(standalone())installBanner?.classList.add('hidden');else showInstallBanner()});
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();installPrompt=e;if(installButton)installButton.textContent='Install app';showInstallBanner()});
window.addEventListener('appinstalled',()=>{installPrompt=null;localStorage.setItem('hg-installed','1');if(installMessage)installMessage.textContent='App installed — open it from your home screen';if(installButton)installButton.classList.add('hidden')});
if(localStorage.getItem('hg-installed')&&installMessage)installMessage.textContent='Open Hamro Gahana from your home screen';
installButton?.addEventListener('click',async()=>{if(installPrompt){const prompt=installPrompt;installPrompt=null;await prompt.prompt();await prompt.userChoice}else if(installMessage){installMessage.textContent=/iPad|iPhone|iPod/.test(navigator.userAgent)?'Tap Share → Add to Home Screen → Open as Web App':'Browser menu → Install app. Already installed? Open its home screen icon.'}});
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
const mediaDialog=$('#mediaDialog'),mediaContent=$('#mediaDialogContent');
document.addEventListener('click',e=>{const link=e.target.closest('a[data-media-preview]');if(!link||!mediaDialog?.showModal||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();const video=link.dataset.mediaPreview==='reel';const el=document.createElement(video?'video':'img');el.src=link.dataset.mediaSrc;if(video){el.controls=true;el.playsInline=true;el.preload='metadata';el.setAttribute('controlslist','nodownload');el.setAttribute('aria-label','Reel preview')}else{el.alt=link.querySelector('img')?.alt||'Image preview'}mediaContent.replaceChildren(el);$$('video').forEach(v=>{if(v!==el)v.pause()});mediaDialog.showModal()});
$('#closeMediaPreview')?.addEventListener('click',()=>mediaDialog.close());
mediaDialog?.addEventListener('click',e=>{if(e.target===mediaDialog){const r=mediaDialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)mediaDialog.close()}});
mediaDialog?.addEventListener('close',()=>{const v=$('video',mediaContent);if(v){v.pause();v.removeAttribute('src');v.load()}mediaContent.replaceChildren()});

// Each list owns its next-page link, so replaced searches cannot append stale results.
const infiniteObserved = new WeakSet();
const infiniteObserver = 'IntersectionObserver' in window ? new IntersectionObserver(entries => {
  entries.forEach(entry => { if (entry.isIntersecting) loadNext(entry.target); });
}, {threshold: 0}) : null;
function initInfinite() {
  $$('[data-infinite-next]').forEach(link => {
    if (infiniteObserved.has(link)) return;
    infiniteObserved.add(link);
    link.addEventListener('click', event => { event.preventDefault(); loadNext(link); });
    const scrollRoot = link.closest('[data-infinite-scroll]');
    if (scrollRoot && 'IntersectionObserver' in window) {
      const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => { if (entry.isIntersecting) loadNext(entry.target); });
      }, {root: scrollRoot});
      observer.observe(link);
      link._infiniteObserver = observer;
    } else infiniteObserver?.observe(link);
  });
}
async function loadNext(link) {
  if (link.dataset.loading || !link.isConnected) return;
  const target = document.getElementById(link.dataset.infiniteNext);
  if (!target) return;
  link.dataset.loading = 'true';
  link.textContent = 'Loading…';
  link.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(link.href, {headers: {'HX-Request': 'true'}});
    if (!response.ok || response.redirected) throw new Error('Could not load more items.');
    const doc = new DOMParser().parseFromString(await response.text(), 'text/html');
    const incoming = doc.getElementById(target.id);
    if (!incoming) throw new Error('Could not load more items.');
    if (!link.isConnected || document.getElementById(target.id) !== target) return;
    const nodes = [...incoming.children];
    target.append(...nodes);
    nodes.forEach(node => { window.htmx?.process(node); window.Alpine?.initTree(node); });
    const next = doc.querySelector(`[data-infinite-next="${target.id}"]`);
    infiniteObserver?.unobserve(link);
    link._infiniteObserver?.disconnect();
    if (next) link.replaceWith(next); else link.remove();
    savedButtons();
    initInfinite();
    initReels();
  } catch (error) {
    link.textContent = 'Could not load items. Tap to retry';
    // Leave retries to the user instead of repeatedly requesting a failing page.
    infiniteObserver?.unobserve(link);
    link._infiniteObserver?.disconnect();
  } finally {
    delete link.dataset.loading;
    link.removeAttribute('aria-busy');
  }
}
initInfinite();
document.addEventListener('htmx:afterSwap', initInfinite);
