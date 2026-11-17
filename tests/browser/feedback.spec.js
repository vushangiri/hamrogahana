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
