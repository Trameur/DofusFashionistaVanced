const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.connectOverCDP('http://localhost:9222');
  const pages = await browser.contexts()[0].pages();
  const page = pages.find(p => p.url().includes('solution'));
  if (!page) { console.log('no page found'); await browser.close(); return; }
  
  for (const w of [1400, 900, 600, 430, 360]) {
    await page.setViewportSize({ width: w, height: 800 });
    await page.waitForTimeout(300);
    const info = await page.evaluate(() => {
      const proj = document.querySelector('.proj_info');
      const mc = document.querySelector('.maincontent');
      if (!proj || !mc) return null;
      const pr = proj.getBoundingClientRect();
      const mr = mc.getBoundingClientRect();
      return {
        proj: { left: Math.round(pr.left), right: Math.round(pr.right), w: Math.round(pr.width) },
        mc: { left: Math.round(mr.left), right: Math.round(mr.right), w: Math.round(mr.width) },
        overL: pr.left < mr.left - 5,
        overR: pr.right > mr.right + 5
      };
    });
    console.log('w=' + w + ':', JSON.stringify(info));
  }
  await browser.close();
})().catch(e => console.error(e));
