"""
小云雀 (Jianying) 自动化视频生成 v4
引擎: Playwright + Chromium
核心改进: 所有 UI 交互改用 Playwright locator.click() (模拟真实鼠标事件)，
         不再用 evaluate + element.click() (会被 React 忽略)
"""
import asyncio
import json
import re
import os
import html
import argparse
from playwright.async_api import async_playwright

COOKIES_FILE = 'cookies.json'
DOWNLOAD_DIR = '.'

def load_and_clean_cookies():
    with open(COOKIES_FILE, 'r') as f:
        raw = json.load(f)
    cleaned = []
    allowed = ['name', 'value', 'domain', 'path', 'expires', 'httpOnly', 'secure']
    for c in raw:
        clean = {}
        for key in allowed:
            if key == 'expires':
                val = c.get('expirationDate') or c.get('expires')
                if val is not None:
                    clean['expires'] = val
                continue
            if key in c and c[key] is not None:
                clean[key] = c[key]
        cleaned.append(clean)
    return cleaned

async def screenshot(page, name):
    path = os.path.join(DOWNLOAD_DIR, f'step_{name}.png')
    await page.screenshot(path=path)
    print(f"  📸 Screenshot: {path}")

async def safe_click(page, locator_or_selector, label, timeout=5000):
    """用 Playwright locator.click() 点击元素，模拟真实鼠标事件"""
    try:
        if isinstance(locator_or_selector, str):
            loc = page.locator(locator_or_selector).first
        else:
            loc = locator_or_selector
        await loc.click(timeout=timeout)
        print(f"  ✅ {label}: clicked")
        return True
    except Exception as e:
        print(f"  ❌ {label}: {e}")
        return False

async def run(prompt: str, duration: str = "10s", ratio: str = "横屏", model: str = "Seedance 2.0", dry_run: bool = False):
    print("🚀 Starting Playwright + Chromium (headless)...")
    if dry_run:
        print("⚠️ DRY-RUN MODE: will fill form but NOT click '开始创作'")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )

        # === Step 1: Cookie 注入 ===
        print("🔑 [Step 1] Injecting cookies...")
        cookies = load_and_clean_cookies()
        await context.add_cookies(cookies)
        print(f"  ✅ {len(cookies)} cookies injected")

        page = await context.new_page()

        # === Step 2: 导航 ===
        print("🌐 [Step 2] Navigating to xyq.jianying.com/home...")
        await page.goto('https://xyq.jianying.com/home', wait_until='domcontentloaded')
        await page.wait_for_timeout(8000)
        await screenshot(page, '2_loaded')

        # === Step 3: 登录验证 ===
        print("🔍 [Step 3] Checking login status...")
        content = await page.content()
        is_logged_in = '开始创作' in content or '登录' not in content
        if is_logged_in:
            print("  ✅ LOGIN_SUCCESS")
        else:
            print("  ❌ LOGIN_FAILED — 请重新导出 cookies.json！")
            await browser.close()
            return

        # === Step 3.5: 点击 "+ 新建" ===
        # 使用 Playwright locator 精确匹配左上角的按钮
        print("🆕 [Step 3.5] Clicking '+ 新建'...")
        await safe_click(page, page.locator('text=新建').first, '新建')
        await page.wait_for_timeout(3000)
        await screenshot(page, '3_5_new_page')

        # === Step 4: 选模式 "沉浸式短片" ===
        # 关键: 用 Playwright locator.click() 而不是 JS .click()
        # 因为 React 事件系统只响应真实 DOM 事件
        print("🎬 [Step 4] Selecting mode: 沉浸式短片...")

        # 4a: 点击 "模式" 下拉按钮（在工具栏里，用 text= 匹配）
        mode_opened = await safe_click(page, page.locator('text=模式').nth(0), '模式下拉')
        await page.wait_for_timeout(2000)
        await screenshot(page, '4a_dropdown')

        if mode_opened:
            # 4b: 在下拉菜单中点击 "沉浸式短片"
            # 下拉菜单中有三个选项：沉浸式短片、智能长视频、图片
            # 需要精确点击菜单项，避免点到左侧边栏
            # 策略：用 text= 匹配，但限定区域 (排除左侧 sidebar x<220)
            mode_selected = await page.evaluate('''() => {
                const items = Array.from(document.querySelectorAll('*'));
                // 找到所有包含"沉浸式短片"的元素
                const candidates = items.filter(el => {
                    const text = el.innerText && el.innerText.trim();
                    return text === '沉浸式短片' && el.offsetHeight < 50 && el.offsetHeight > 10;
                });
                // 按x坐标排序，优先选择靠近中间的（下拉菜单的位置）
                candidates.sort((a, b) => {
                    const ra = a.getBoundingClientRect();
                    const rb = b.getBoundingClientRect();
                    return rb.left - ra.left; // 先取 x 最大的
                });
                for (const el of candidates) {
                    const rect = el.getBoundingClientRect();
                    if (rect.left > 300) {
                        // 通过 dispatchEvent 模拟完整的鼠标事件链
                        el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true}));
                        el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true}));
                        el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
                        return 'selected (x=' + Math.round(rect.left) + ', y=' + Math.round(rect.top) + ')';
                    }
                }
                // 返回调试信息
                return 'NOT_FOUND: candidates=' + candidates.map(el => {
                    const r = el.getBoundingClientRect();
                    return '(' + Math.round(r.left) + ',' + Math.round(r.top) + ')';
                }).join(';');
            }''')
            print(f"  沉浸式短片: {mode_selected}")
            await page.wait_for_timeout(3000)
        await screenshot(page, '4b_mode_selected')

        # === Step 5: 选模型 ===
        print(f"🤖 [Step 5] Selecting model: {model}...")

        # 5a: 精确点击工具栏的 "2.0 Fast" 按钮
        # 关键约束: text.length < 15 排除匹配到整个工具栏容器
        model_click = await page.evaluate('''() => {
            const items = Array.from(document.querySelectorAll('*'));
            const btn = items.find(el => {
                const text = el.innerText && el.innerText.trim();
                if (!text || !text.includes('2.0')) return false;
                // 关键: 文本长度 < 15，只匹配 "2.0 Fast" 这样的短文本
                // 排除整个工具栏容器 ("沉浸式短片\\n2.0 Fast\\n参考\\n5s")
                if (text.length > 15) return false;
                const rect = el.getBoundingClientRect();
                // 工具栏区域: y > 370, x > 600, 小元素
                return rect.top > 370 && rect.left > 600 && el.offsetHeight < 50 && el.offsetHeight > 15;
            });
            if (btn) {
                btn.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true}));
                btn.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true}));
                btn.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
                const r = btn.getBoundingClientRect();
                return 'opened: ' + btn.innerText.trim() + ' (x=' + Math.round(r.left) + ', y=' + Math.round(r.top) + ')';
            }
            return 'NOT_FOUND';
        }''')
        print(f"  Model button: {model_click}")
        await page.wait_for_timeout(2000)
        await screenshot(page, '5a_model_dropdown')

        if 'opened' in model_click:
            # 5b: 在下拉菜单中选目标模型
            # 下拉结构:
            #   "Seedance 2.0 Fast" (标题) + "更快更便宜的Seedance 2.0模型" (描述)
            #   "Seedance 2.0" (标题) + "15 秒内效果无损..." (描述)
            #   "Seedance 1.5" (标题) + "画面直出..." (描述)
            # 关键: 标题行是纯英文/数字/空格/点，描述行含中文
            model_select = await page.evaluate('''([wantFast]) => {
                const items = Array.from(document.querySelectorAll('*'));
                const candidates = items.filter(el => {
                    const text = el.innerText && el.innerText.trim();
                    if (!text) return false;
                    // 只匹配纯英文+数字+空格+点的标题行，排除含中文的描述行
                    if (!/^Seedance\s+\d/.test(text)) return false;
                    // 不能含中文字符
                    if (/[\u4e00-\u9fff]/.test(text)) return false;
                    if (el.offsetHeight > 40 || el.offsetHeight < 10) return false;
                    const rect = el.getBoundingClientRect();
                    return rect.left > 300 && rect.left < 1100 && rect.top > 400;
                });
                for (const el of candidates) {
                    const text = el.innerText.trim();
                    const isFast = text.includes('Fast');
                    if (wantFast === isFast) {
                        el.dispatchEvent(new MouseEvent('mousedown', {bubbles:true, cancelable:true}));
                        el.dispatchEvent(new MouseEvent('mouseup', {bubbles:true, cancelable:true}));
                        el.dispatchEvent(new MouseEvent('click', {bubbles:true, cancelable:true}));
                        const r = el.getBoundingClientRect();
                        return 'selected: ' + text + ' (x=' + Math.round(r.left) + ', y=' + Math.round(r.top) + ')';
                    }
                }
                return 'NOT_FOUND: candidates=' + candidates.map(el => {
                    const r = el.getBoundingClientRect();
                    return '"' + el.innerText.trim() + '"(x=' + Math.round(r.left) + ',y=' + Math.round(r.top) + ')';
                }).join('; ');
            }''', ["Fast" in model])
            print(f"  Model select: {model_select}")
            await page.wait_for_timeout(1500)
        await screenshot(page, '5b_model_selected')

        # === Step 6: 选时长 ===
        print(f"⏱️ [Step 6] Selecting duration: {duration}...")
        
        # 6a: 点击当前时长按钮 (显示 "5s"、"10s" 或 "15s")
        dur_btn = page.locator('text=/^\\d+s$/').first
        dur_opened = await safe_click(page, dur_btn, '时长按钮')
        await page.wait_for_timeout(1500)
        await screenshot(page, '6a_duration_dropdown')

        if dur_opened:
            # 6b: 在下拉中选择目标时长
            try:
                # 精确匹配目标时长
                dur_item = page.locator(f'text=/^{duration}$/').first
                await dur_item.click(timeout=3000)
                print(f"  ✅ 时长选择: {duration}")
            except Exception as e:
                print(f"  ⚠️ 时长选择: {e}")
            await page.wait_for_timeout(1000)
        await screenshot(page, '6b_duration_selected')

        # === Step 7: 注入 Prompt ===
        print(f"📝 [Step 7] Injecting prompt: {prompt}")
        inject_result = await page.evaluate('''([text]) => {
            const el = document.querySelector('div[contenteditable="true"]');
            if (el) {
                el.innerText = text;
                el.dispatchEvent(new Event('input', { bubbles: true }));
                return 'OK: ' + el.innerText.substring(0, 30) + '...';
            }
            return 'FAILED: no contenteditable found';
        }''', [prompt])
        print(f"  Inject: {inject_result}")
        await page.wait_for_timeout(1000)
        await screenshot(page, '7_prompt')

        # === Step 8: 验证/提交 ===
        if dry_run:
            await screenshot(page, '8_DRY_RUN_FINAL')
            status_text = await page.evaluate('''() => {
                const all = Array.from(document.querySelectorAll('*'));
                const info = all.find(el => {
                    const t = el.innerText && el.innerText.trim();
                    return t && t.includes('积分') && t.includes('秒') && el.offsetHeight < 40;
                });
                return info ? info.innerText.trim() : 'NOT_FOUND';
            }''')
            print(f"\n✅ DRY-RUN 完成！请检查截图 step_8_DRY_RUN_FINAL.png")
            print(f"📊 底部状态栏: {status_text}")
            print(f"\n确认无误后，去掉 --dry-run 参数重新运行即可提交任务。")
            await browser.close()
            return

        print("🖱️ [Step 8] Clicking '开始创作'...")
        submit_clicked = await safe_click(page, page.locator('text=开始创作').first, '开始创作')
        await page.wait_for_timeout(3000)
        await screenshot(page, '8_submitted')

        if not submit_clicked:
            print("  ❌ Submit failed. Aborting.")
            await browser.close()
            return

        # === Step 9: 轮询 MP4 ===
        print("⏳ [Step 9] Polling for MP4 link (up to 10 min)...")
        mp4_url = None
        for i in range(120):
            await page.wait_for_timeout(5000)
            page_html = await page.content()
            links = re.findall(r'https?:\/\/[^"\'\s\\]+\.mp4[^"\'\s\\]*', page_html)
            if links:
                mp4_url = html.unescape(links[0])
                print(f"\n  🎉 Found MP4 at attempt {i+1}!")
                print(f"  🔗 {mp4_url[:120]}...")
                break
            if i % 12 == 0 and i > 0:
                print(f"  ⏳ Still generating... ({i*5}s elapsed)")
            print(".", end="", flush=True)

        if not mp4_url:
            print("\n  ❌ Timeout after 10 min")
            await screenshot(page, '9_timeout')
            await browser.close()
            return

        # === Step 10: 下载 ===
        # 用 Playwright 的 context.request API (自动共享浏览器 cookies/session)
        safe_name = ''.join(c for c in prompt[:15] if c.isalnum() or c in '_ ')
        filename = f"{safe_name}_{duration}.mp4"
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        print(f"📥 [Step 10] Downloading to {filepath}...")

        try:
            # 方法1: Playwright API request (共享浏览器 session)
            api_resp = await context.request.get(mp4_url, headers={
                "Referer": "https://xyq.jianying.com/",
            })
            if api_resp.ok:
                body = await api_resp.body()
                with open(filepath, 'wb') as f:
                    f.write(body)
                size_mb = len(body) / (1024 * 1024)
                print(f"  ✅ Saved: {os.path.abspath(filepath)} ({size_mb:.1f}MB)")
            else:
                raise Exception(f"API request failed: status={api_resp.status}")
        except Exception as e:
            print(f"  ⚠️ Playwright API download failed: {e}")
            # 方法2: 在浏览器页面内用 fetch() 下载 (完全同源)
            print("  🔄 Trying in-page fetch()...")
            try:
                b64_data = await page.evaluate('''async (url) => {
                    const resp = await fetch(url, {
                        headers: { 'Referer': 'https://xyq.jianying.com/' }
                    });
                    if (!resp.ok) return 'FETCH_FAILED:' + resp.status;
                    const blob = await resp.blob();
                    return new Promise((resolve) => {
                        const reader = new FileReader();
                        reader.onload = () => resolve(reader.result);
                        reader.readAsDataURL(blob);
                    });
                }''', mp4_url)

                if b64_data.startswith('FETCH_FAILED'):
                    raise Exception(b64_data)

                import base64
                # data:video/mp4;base64,XXXX...
                raw = base64.b64decode(b64_data.split(',', 1)[1])
                with open(filepath, 'wb') as f:
                    f.write(raw)
                size_mb = len(raw) / (1024 * 1024)
                print(f"  ✅ Saved via fetch: {os.path.abspath(filepath)} ({size_mb:.1f}MB)")
            except Exception as e2:
                print(f"  ❌ All download methods failed: {e2}")
                print(f"  📋 Manual link: {mp4_url}")

        await browser.close()

    print("\n🏁 Done!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jianying SeeDance 2.0 Video Generator")
    parser.add_argument("--prompt", type=str, default="一个美女在跳舞", help="Video description")
    parser.add_argument("--duration", type=str, default="10s", choices=["5s", "10s", "15s"])
    parser.add_argument("--ratio", type=str, default="横屏", choices=["横屏", "竖屏", "方屏"])
    parser.add_argument("--model", type=str, default="Seedance 2.0",
                        choices=["Seedance 2.0", "Seedance 2.0 Fast"])
    parser.add_argument("--dry-run", action="store_true", help="Only fill form, don't submit")
    args = parser.parse_args()

    if not os.path.exists(COOKIES_FILE):
        print(f"⚠️ {COOKIES_FILE} not found!")
    else:
        asyncio.run(run(args.prompt, args.duration, args.ratio, args.model, args.dry_run))
