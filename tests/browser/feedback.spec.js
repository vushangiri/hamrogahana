const {test,expect}=require('@playwright/test');

test('password visibility and discreet administrator link',async({page})=>{
  await page.goto('/login');
  await page.locator('#password').fill('example-password');
  await page.getByRole('button',{name:'Show password',exact:true}).click();
  await expect(page.locator('#password')).toHaveAttribute('type','text');
  await page.getByRole('button',{name:'Hide password',exact:true}).click();
  await expect(page.locator('#password')).toHaveAttribute('type','password');
  await expect(page.getByRole('link',{name:'Administrator sign in'})).toHaveText('⚙');
  await page.goto('/register');
  await expect(page.getByRole('button',{name:'Show password',exact:true})).toBeVisible();
});

test('empty saved collection stays empty',async({page})=>{
  await page.addInitScript(()=>localStorage.setItem('hg-saved','[]'));
  await page.goto('/saved?ids=');
  await expect(page.locator('.productCard')).toHaveCount(0);
  await expect(page.locator('#product-list')).toContainText('Tap ♡');
});

test('save and unsave round trip',async({page})=>{
  await page.addInitScript(()=>{if(!localStorage.getItem('hg-saved'))localStorage.setItem('hg-saved','[]')});
  await page.goto('/');
  test.skip(await page.locator('.productCard').count()===0,'Requires a published product');
  const save=page.locator('.productCard [data-save]').first();
  const id=await save.getAttribute('data-save');
  await save.click();
  await expect(save).toHaveAttribute('aria-pressed','true');
  await page.getByRole('link',{name:'Saved',exact:true}).click();
  await expect(page.locator(`.productCard [data-save="${id}"]`)).toHaveAttribute('aria-pressed','true');
  await page.locator(`.productCard [data-save="${id}"]`).click();
  await expect(page.locator('.productCard')).toHaveCount(0);
  await page.reload();
  await expect(page.locator('.productCard')).toHaveCount(0);
});

test('selected location is carried to saved links',async({page})=>{
  await page.addInitScript(()=>localStorage.setItem('hg-location',JSON.stringify({lat:28.2,lon:83.98,label:'Pokhara'})));
  await page.goto('/?lat=28.2&lon=83.98');
  const saved=new URL(await page.getByRole('link',{name:'Saved',exact:true}).getAttribute('href'));
  expect(saved.searchParams.get('lat')).toBe('28.2');
  expect(saved.searchParams.get('lon')).toBe('83.98');
});

test('tall and wide card images stay above product text',async({page})=>{
  await page.goto('/');
  test.skip(await page.locator('.productCard').count()===0,'Requires a published product');
  for(const [width,height] of [[80,1600],[1600,80]]){
    const bounds=await page.locator('.productCard').first().evaluate(async(card,{width,height})=>{
      const art=card.querySelector('.productArt');
      art.querySelectorAll('img').forEach(img=>img.remove());
      const img=new Image();img.width=640;img.height=640;
      img.src='data:image/svg+xml,'+encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="gold"/></svg>`);
      art.prepend(img);await img.decode();
      const image=img.getBoundingClientRect(),frame=art.getBoundingClientRect(),text=card.querySelector('.productInfo').getBoundingClientRect();
      return {bottom:image.bottom,top:image.top,left:image.left,right:image.right,frameBottom:frame.bottom,frameTop:frame.top,frameLeft:frame.left,frameRight:frame.right,textTop:text.top};
    },{width,height});
    expect(bounds.bottom).toBeLessThanOrEqual(bounds.frameBottom+1);
    expect(bounds.bottom).toBeLessThanOrEqual(bounds.textTop+1);
    expect(bounds.top).toBeGreaterThanOrEqual(bounds.frameTop-1);
    expect(bounds.right).toBeLessThanOrEqual(bounds.frameRight+1);
    expect(bounds.left).toBeGreaterThanOrEqual(bounds.frameLeft-1);
  }
});

test('large media previews fit inside the viewport',async({page})=>{
  await page.goto('/login');
  await page.evaluate(()=>{
    const link=document.createElement('a');link.href='#';link.textContent='Large photo';
    link.dataset.mediaPreview='image';
    link.dataset.mediaSrc='data:image/svg+xml,'+encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="8000"><rect width="100%" height="100%" fill="gold"/></svg>');
    document.querySelector('main').append(link);
  });
  await page.getByRole('link',{name:'Large photo'}).click();
  await expect(page.locator('#mediaDialog')).toBeVisible();
  const bounds=await page.locator('#mediaDialog').evaluate(dialog=>{
    const box=dialog.getBoundingClientRect(),image=dialog.querySelector('img').getBoundingClientRect();
    return {left:box.left,right:box.right,top:box.top,bottom:box.bottom,imageBottom:image.bottom,imageRight:image.right,width:innerWidth,height:innerHeight};
  });
  expect(bounds.left).toBeGreaterThanOrEqual(0);
  expect(bounds.top).toBeGreaterThanOrEqual(0);
  expect(bounds.right).toBeLessThanOrEqual(bounds.width);
  expect(bounds.bottom).toBeLessThanOrEqual(bounds.height);
  expect(bounds.imageBottom).toBeLessThanOrEqual(bounds.bottom);
  expect(bounds.imageRight).toBeLessThanOrEqual(bounds.right);
  await page.getByRole('button',{name:'Close',exact:true}).click();
});
