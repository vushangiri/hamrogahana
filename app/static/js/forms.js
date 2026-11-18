'use strict';
(() => {
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
// Password controls are rendered with the field and use delegation for partial pages.
document.addEventListener('click',event=>{
 const button=event.target.closest('[data-password-toggle]');if(!button)return;
 const input=document.getElementById(button.getAttribute('aria-controls'));if(!input)return;
 const show=input.type==='password';input.type=show?'text':'password';button.setAttribute('aria-label',show?'Hide password':'Show password');button.setAttribute('aria-pressed',String(show));
});
function productFields(){
 const form=$('[data-product-form]');if(!form)return;
 const other=form.elements.metal.value==='Other';
 $$('[data-jewellery-fields]',form).forEach(group=>{group.hidden=other;$$('input,select',group).forEach(el=>el.disabled=other)});
 const purity=form.elements.purity;
 $$('option',purity).forEach(option=>{option.disabled=option.hidden=Boolean(option.dataset.metal && option.dataset.metal!==form.elements.metal.value)});
 if(!other&&(!purity.selectedOptions.length||purity.selectedOptions[0].hidden))purity.value=form.elements.metal.value==='Silver'?'999':'24K';
 const custom=!other&&purity.value==='custom';
 $('[data-custom-purity]',form).hidden=!custom;
 form.elements.custom_purity.disabled=!custom;
 form.elements.custom_purity.required=custom;
 form.elements.description.required=other;
 $('label[for="fixed"]',form).textContent=other?'Price / NPR':'Fixed charge / NPR';
}
document.addEventListener('change',event=>{if(event.target.matches('[data-product-form] [name=metal], [data-product-form] [name=purity]'))productFields()});
['htmx:afterSwap','htmx:historyRestore','pageshow'].forEach(name=>window.addEventListener(name,productFields));
document.addEventListener('htmx:afterSwap',productFields);productFields();

})();
