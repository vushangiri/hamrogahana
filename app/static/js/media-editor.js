'use strict';
(() => {
 const seen=new WeakSet();
 function init(){document.querySelectorAll('form[data-upload]').forEach(form=>{
  if(seen.has(form))return;seen.add(form);
  const file=form.querySelector('input[type=file]'),kind=form.querySelector('[name=kind]'),editor=form.querySelector('[data-media-editor]'),preview=form.querySelector('.uploadPreview');
  let url;
  const row=document.createElement('div');row.className='row wrap';
  [['Take photo','image','image/*'],['Record video','reel','video/*']].forEach(([label,value,accept])=>{
   const button=document.createElement('button');button.type='button';button.className='ghost space';button.textContent=label;
   button.addEventListener('click',()=>{kind.value=value;file.accept=accept;file.setAttribute('capture','environment');file.click();file.removeAttribute('capture')});row.append(button);
  });file.before(row);
  function update(){const video=kind.value==='reel';const imageEdits=form.querySelector('[data-image-edits]'),videoEdits=form.querySelector('[data-video-edits]');imageEdits.hidden=video;videoEdits.hidden=!video;imageEdits.querySelectorAll('input,select').forEach(el=>el.disabled=video);videoEdits.querySelectorAll('input').forEach(el=>el.disabled=!video);file.accept=video?'video/*,.mov,.mkv':'image/*';
   const img=preview.querySelector('img');if(img){img.style.transform=`rotate(${form.elements.rotate.value}deg)`;img.style.filter=`brightness(${form.elements.brightness.value})`;img.classList.toggle('squareCrop',form.elements.square.checked)}
  }
  file.addEventListener('change',()=>{if(url)URL.revokeObjectURL(url);preview.replaceChildren();const selected=file.files[0];editor.hidden=!selected;if(!selected)return;const video=selected.type.startsWith('video/')||/\.(mov|mkv|mp4|webm)$/i.test(selected.name);kind.value=video?'reel':'image';url=URL.createObjectURL(selected);const el=document.createElement(video?'video':'img');el.src=url;if(video){el.controls=true;el.playsInline=true;el.preload='metadata'}else el.alt='Photo preview';preview.append(el);update()});
  kind.addEventListener('change',update);editor.addEventListener('input',update);update();
 });}
 init();document.addEventListener('hg:content',init);document.addEventListener('htmx:afterSwap',init);
})();
