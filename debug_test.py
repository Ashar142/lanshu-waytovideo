import asyncio, json, os
from playwright.async_api import async_playwright

COOKIES_FILE = 'cookies.json'

async def debug():
    with open(COOKIES_FILE, 'r') as f:
        raw_cookies = json.load(f)
    cleaned = []
    for c in raw_cookies:
        clean = {}
        for k in ['name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure']:
            if k in c:
                clean[k] = c[k]
        if 'expirationDate' in c:
            clean['expires'] = c['expirationDate']
        cleaned.append(clean)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        await context.add_cookies(cleaned)
        page = await context.new_page()

        # Step 1: Navigate
        print("[1] Navigating...")
        await page.goto('https://xyq.jianying.com/home', wait_until='domcontentloaded')
        await page.wait_for_timeout(5000)
        await page.screenshot(path='debug_step1_loaded.png')
        print("[1] Done - screenshot saved")

        # Step 2: Check if contenteditable exists
        has_input = await page.evaluate('''() => {
            const el = document.querySelector('div[contenteditable="true"]');
            return el ? el.tagName + ' found' : 'NOT FOUND';
        }''')
        print(f"[2] Input box status: {has_input}")

        # Step 3: Check if submit button exists
        has_btn = await page.evaluate('''() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const submitBtn = btns.find(b => b.innerText && b.innerText.includes('开始创作'));
            return submitBtn ? 'FOUND: ' + submitBtn.innerText : 'NOT FOUND. All buttons: ' + btns.map(b => b.innerText).join(' | ');
        }''')
        print(f"[3] Submit button status: {has_btn}")

        # Step 4: Inject text
        prompt = "生成一段沉浸式短片(SeeDance 2.0)：赛博朋克雨夜。要求视频比例为横屏，时长为5s。"
        result = await page.evaluate('''([text]) => {
            const el = document.querySelector('div[contenteditable="true"]');
            if(el) {
                el.innerText = text;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                return 'Text injected: ' + el.innerText.substring(0, 30) + '...';
            }
            return 'FAILED: no contenteditable found';
        }''', [prompt])
        print(f"[4] Text injection: {result}")
        await page.wait_for_timeout(1000)
        await page.screenshot(path='debug_step4_text_injected.png')
        print("[4] Done - screenshot saved")

        # Step 5: Click submit
        click_result = await page.evaluate('''() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const submitBtn = btns.find(b => b.innerText && b.innerText.includes('开始创作'));
            if(submitBtn) {
                submitBtn.click();
                return 'Clicked!';
            }
            return 'FAILED: button not found';
        }''')
        print(f"[5] Click result: {click_result}")
        await page.wait_for_timeout(3000)
        await page.screenshot(path='debug_step5_after_click.png')
        print("[5] Done - screenshot saved")

        # Step 6: Wait and check page title / url to see if navigated
        print(f"[6] Current URL: {page.url}")
        print(f"[6] Page title: {await page.title()}")

        # Step 7: Poll briefly for mp4 (30s only for debug)
        import re, html as html_mod
        for i in range(6):
            await page.wait_for_timeout(5000)
            content = await page.content()
            links = re.findall(r'https?:\/\/[^"\'\s\\]+\.mp4[^"\'\s\\]*', content)
            if links:
                url = html_mod.unescape(links[0])
                print(f"[7] 🎉 Found MP4 at attempt {i+1}: {url[:80]}...")
                break
            print(f"[7] Polling {i+1}/6...")
        else:
            await page.screenshot(path='debug_step7_timeout.png')
            print("[7] No MP4 found in 30s (expected for 5s generation)")

        await browser.close()
        print("\n✅ Debug complete! Check the debug_step*.png files.")

asyncio.run(debug())
