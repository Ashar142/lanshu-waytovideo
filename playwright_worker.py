import asyncio
import json
import re
import os
import requests
import html
import argparse
from playwright.async_api import async_playwright

COOKIES_FILE = 'cookies.json'
DOWNLOAD_DIR = '.'

async def run_playwright(prompt: str, duration: str = "10s", ratio: str = "横屏"):
    print("🚀 Starting standard Playwright engine (headless)...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = await browser.new_context()

        # 1. Load and clean cookies
        if not os.path.exists(COOKIES_FILE):
            print(f"❌ Error: {COOKIES_FILE} not found.")
            return

        with open(COOKIES_FILE, 'r') as f:
            raw_cookies = json.load(f)
            
        cleaned_cookies = []
        allowed_keys = ['name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure']
        for c in raw_cookies:
            clean = {}
            for key in allowed_keys:
                if key in c:
                    clean[key] = c[key]
            # Handle expiration differences
            if 'expirationDate' in c:
                clean['expires'] = c['expirationDate']
            cleaned_cookies.append(clean)
            
        await context.add_cookies(cleaned_cookies)
        print("✅ Cookies injected successfully.")

        page = await context.new_page()

        # 2. Navigate to Jianying Agent page
        print("🌐 Navigating to Jianying workflow...")
        await page.goto('https://xyq.jianying.com/home', wait_until='domcontentloaded')
        
        await page.wait_for_timeout(5000)
        
        # Output screenshot to verify login state
        await page.screenshot(path=os.path.join(DOWNLOAD_DIR, 'debug_after_load_pw.png'))

        # 3. Inject Prompt (Must use Chinese prefix)
        # As per user request: Configure Duration, Aspect Ratio and Force Seedance 2.0 via natural language
        full_prompt = f"生成一段沉浸式短片(SeeDance 2.0)：{prompt}。要求视频比例为{ratio}，时长为{duration}。"
        print(f"📝 Submitting prompt: {full_prompt}")

        await page.evaluate('''([text]) => {
            const el = document.querySelector('div[contenteditable="true"]');
            if(el) {
                el.innerText = text;
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }''', [full_prompt])
        
        await page.wait_for_timeout(1000)

        # 4. Trigger Submit
        print("🖱️ Clicking Submit button...")
        await page.evaluate('''() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const submitBtn = btns.find(b => b.innerText && b.innerText.includes('开始创作'));
            if(submitBtn) submitBtn.click();
        }''')
        
        await page.screenshot(path=os.path.join(DOWNLOAD_DIR, 'debug_after_submit_pw.png'))

        print("⏱️ Task Submitted! Polling for video generation completion (this may take up to 2-5 minutes)...")

        mp4_url = None
        max_attempts = 120 # Polling up to ~10 mins (120 * 5s)
        
        import html
        for attempt in range(max_attempts):
            await page.wait_for_timeout(5000)
            html_content = await page.content()
            
            mp4_links_raw = re.findall(r'https?:\/\/[^"\'\s\\]+\.mp4[^"\'\s\\]*', html_content)
            
            if mp4_links_raw:
                valid_links = [link.replace('\\"', '').replace("'", "") for link in mp4_links_raw]
                valid_links = list(set(valid_links))
                
                for link in valid_links:
                    if 'byteimg.com' in link or '365yg.com' in link:
                        mp4_url = link
                        break
                
                if not mp4_url and valid_links:
                    mp4_url = valid_links[0]
                    
                if mp4_url:
                    mp4_url = html.unescape(mp4_url)
                    print(f"\n🎉 Video generated successfully! Found Direct MP4 Link: {mp4_url}")
                    break
            
            print(".", end="", flush=True)
            
        if not mp4_url:
            print("\n❌ Timeout: Could not find MP4 link in the page source after 10 minutes.")
            await browser.close()
            return

        # 6. Download the Video
        # Clean up OS unsafe chars just in case
        safe_prompt = ''.join(e for e in prompt[:10] if e.isalnum())
        filename = f"generated_{duration}_{ratio}_{safe_prompt}.mp4"
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://xyq.jianying.com/"
        }
        
        print(f"📥 Downloading video to {filepath}...")
        try:
            response = await asyncio.to_thread(requests.get, mp4_url, headers=headers, stream=True)
            response.raise_for_status()
            
            block_size = 1024 # 1 Kibibyte
            downloaded = 0
            
            with open(filepath, 'wb') as file:
                for data in response.iter_content(block_size):
                    file.write(data)
                    downloaded += len(data)
                    if downloaded % (block_size * 1024 * 5) == 0:  # Print every 5MB
                        print(f"   Downloading... {downloaded // (1024 * 1024)}MB")
                        
            print(f"✅ Download complete! Saved to: {os.path.abspath(filepath)}")
        except Exception as e:
            print(f"⚠️ Error downloading video: {e}")
            print(f"You can download it manually here: {mp4_url}")
            
        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jianying Auto Video Generator")
    parser.add_argument("--prompt", type=str, required=True, help="Description of the video to generate")
    parser.add_argument("--duration", type=str, default="10s", choices=["5s", "10s", "15s"], help="Video duration (5s, 10s, 15s)")
    parser.add_argument("--ratio", type=str, default="横屏", choices=["横屏", "竖屏", "方屏"], help="Aspect ratio (横屏, 竖屏, 方屏)")
    
    args = parser.parse_args()
    
    if not os.path.exists(COOKIES_FILE):
        print(f"⚠️ Please create '{COOKIES_FILE}' in this directory before running.")
    else:
        asyncio.run(run_playwright(args.prompt, args.duration, args.ratio))
