'use strict';
// Native navigation starts immediately. Feedback never holds up a request.
(() => {
  const root = document.documentElement;
  const status = document.getElementById('navigationStatus');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let progressTimer, skeletonTimer, recoveryTimer;
  function finishNavigation() {
    clearTimeout(progressTimer); clearTimeout(skeletonTimer); clearTimeout(recoveryTimer);
    root.classList.remove('is-navigating', 'navigation-slow');
    document.getElementById('main')?.removeAttribute('aria-busy');
    if (status) status.textContent = '';
  }
  function startNavigation() {
    finishNavigation();
    progressTimer = setTimeout(() => {
      root.classList.add('is-navigating');
      document.getElementById('main')?.setAttribute('aria-busy', 'true');
      if (status) status.textContent = 'Loading page…';
    }, 100);
    skeletonTimer = setTimeout(() => root.classList.add('navigation-slow'), 650);
    recoveryTimer = setTimeout(() => {
      finishNavigation();
      if (status) status.textContent = 'This is taking longer than usual. Check your connection or try again.';
    }, 15000);
  }
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || link.hasAttribute('download') || (link.target && link.target !== '_self') || link.matches('[data-infinite-next],[data-media-preview],[hx-get]') || link.closest('[hx-boost="true"]')) return;
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !['http:', 'https:'].includes(url.protocol) || (url.pathname === location.pathname && url.search === location.search && url.hash)) return;
    queueMicrotask(() => { if (!event.defaultPrevented) startNavigation(); });
  });
  document.addEventListener('submit', event => {
    const form = event.target;
    if (form.matches('[data-upload],[hx-get],[hx-post]') || form.method === 'dialog' || (form.target && form.target !== '_self')) return;
    queueMicrotask(() => { if (!event.defaultPrevented) startNavigation(); });
  });
  document.addEventListener('hg:navigate', startNavigation);
  window.addEventListener('pageshow', finishNavigation);
  window.addEventListener('pagehide', finishNavigation);
  window.addEventListener('pageswap', finishNavigation);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') finishNavigation(); });

  document.querySelector('[data-unit-picker] select')?.addEventListener('change', event => event.target.form.requestSubmit());
  const pendingRequests = new Set();
  document.addEventListener('htmx:beforeRequest', event => {
    pendingRequests.add(event.detail.xhr);
    root.classList.add('is-fetching');
    event.detail.target?.setAttribute('aria-busy', 'true');
  });
  document.addEventListener('htmx:afterRequest', event => {
    pendingRequests.delete(event.detail.xhr);
    if (!pendingRequests.size) root.classList.remove('is-fetching');
    event.detail.target?.removeAttribute('aria-busy');
  });

  const seen = new WeakSet();
  function initMedia() {
    document.querySelectorAll('.productArt img,.productGallery img,.mediaViewer img').forEach(img => {
      if (seen.has(img)) return;
      seen.add(img);
      img.decoding = 'async';
      const container = img.parentElement;
      function complete() {
        container.classList.remove('media-pending');
        if (!img.naturalWidth) {
          container.classList.add('media-failed');
          img.alt = 'Image unavailable';
        }
      }
      if (img.complete) complete();
      else {
        container.classList.add('media-pending');
        img.addEventListener('load', complete, {once:true});
        img.addEventListener('error', complete, {once:true});
      }
    });
    document.querySelectorAll('.reel video,.mediaViewer video').forEach(video => {
      if (seen.has(video)) return;
      seen.add(video);
      const container = video.parentElement;
      let timer;
      const clear = () => { clearTimeout(timer); container.classList.remove('video-buffering'); };
      video.addEventListener('waiting', () => { clearTimeout(timer); timer = setTimeout(() => container.classList.add('video-buffering'), 250); });
      ['playing','canplay','error','pause','emptied'].forEach(name => video.addEventListener(name, clear));
    });
  }
  initMedia();
  ['htmx:afterSwap','hg:content','hg:preview'].forEach(name => document.addEventListener(name, initMedia));
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-save]');
    if (!button || reduced.matches || !button.animate) return;
    button.animate([{transform:'scale(1)'},{transform:'scale(1.16)'},{transform:'scale(1)'}], {duration:220,easing:'ease-out'});
  });
})();
