const {test,expect}=require('@playwright/test');
test.use({serviceWorkers:'block'});

test('slow navigation gives feedback and clears it after navigation and back',async({page})=>{
  await page.goto('/');
  await page.route('**/reels',async route=>{await new Promise(resolve=>setTimeout(resolve,1100));await route.continue()});
  const feedback=await page.evaluate(async()=>{
    document.querySelector('.bottom a[href="/reels"]').click();
    await new Promise(resolve=>setTimeout(resolve,800));
    return {busy:document.documentElement.classList.contains('is-navigating'),skeleton:getComputedStyle(document.getElementById('navigationSkeleton')).display};
  });
  expect(feedback.busy).toBeTruthy();
  expect(feedback.skeleton).not.toBe('none');
  await expect(page.getByRole('heading',{name:'Jewellery reels'})).toBeVisible();
  await expect(page.locator('html')).not.toHaveClass(/is-navigating/);
  await page.goBack();
  await expect(page.locator('html')).not.toHaveClass(/is-navigating/);
});

test('display unit persists and reduced motion stops skeleton movement',async({page})=>{
  await page.goto('/');
  await page.locator('#displayUnit').selectOption('gram');
  await expect(page.locator('#displayUnit')).toHaveValue('gram');
  await page.reload();
  await expect(page.locator('#displayUnit')).toHaveValue('gram');
  await expect(page.locator('.rateStrip')).toContainText('/ g');
  await page.emulateMedia({reducedMotion:'reduce'});
  expect(await page.locator('.skeleton').first().evaluate(el=>getComputedStyle(el,'::after').animationName)).toBe('none');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
