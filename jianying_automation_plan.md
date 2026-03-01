# 小云雀 (Jianying) 视频生成自动化执行计划

这份文档详细规划了两种在本地（Mac）或云端（VPS）自动化操控小云雀 `https://xyq.jianying.com/` 生成视频的完整方案。我们将采用 **Python** 作为核心开发语言，并使用大名鼎鼎的 **Playwright** 作为自动化底座。

---

## 方案 A：伪装潜入流 (Camoufox + Playwright)

本方案使用经过深度防检测定制的浏览器内核 `Camoufox`，通过注入 Cookie 模拟真实用户的免密登录请求。

### 适用场景
* 需要部署在无图形界面的云服务器（VPS）上长期运行。
* 作为 API 服务或 Telegram 机器人的底层驱动引擎。
* 全后台静默运行，无需人工干预。

### 优势与劣势
* **优势**：完美规避常见的高级浏览器指纹检测（WAF / Cloudflare），全自动无头运行。
* **劣势**：高度依赖导出的 Cookie。如果小云雀更改了安全策略导致 Cookie 频繁失效，需要频繁人工导出续期。

### 实施步骤
1. **环境准备**：使用 `pip install camoufox[playwright]` 安装 Camoufox 引擎。
2. **提取凭证**：在物理机正常登录小云雀后，使用浏览器插件（如 Cookie-Editor）导出 Cookie 并保存为 `cookies.json`。
3. **编写脚本**：
   * 读取并清洗 `cookies.json`（去除不合规的 `sameSite` 属性）。
   * 启动 `AsyncCamoufox(headless=True)`。
   * 访问目标网页并注入 Cookie。
   * 通过 `page.evaluate()` 绕过前端限制强行填入带中文前缀的指令。
   * 点击生成按钮后，使用定期轮询网页 DOM 或者抓包正则匹配捞出 `.mp4` 直链。
4. **下载穿透**：通过 Python 的 `requests` 库或命令行 `curl` 将直链视频保存到本地。

---

## 方案 B：借尸还魂流 (CDP + Playwright + 本地 Chrome)

本方案避开了反爬对抗的重灾区，直接通过 Chrome 开发者工具协议 (CDP) 接管你电脑上日常在用的真实 Chrome 浏览器。

### 适用场景
* 在 Mac 物理机本地运行。
* 不想折腾 Cookie 清洗与频繁过期问题。
* 作为本地日常提效的辅助工具。

### 优势与劣势
* **优势**：零封号率、零拦截率（因为使用的就是真实的常规环境）；完全免除 Cookie 管理的折腾；甚至可以通过监听 Network 直接截获视频流地址，无需正则硬搜。
* **劣势**：必须在本地开启一个有界面的 Chrome，具有独占性，无法轻易移植到云端纯无头 Linux 服务器上运行。

### 实施步骤
1. **启动调试版 Chrome**：
   * 在 Mac 终端通过命令启动 Chrome 并开放调试端口：
     ```bash
     /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="/tmp/chrome_dev_test"
     ```
2. **手动就绪**：在这个弹出的 Chrome 中手动打开小云雀并扫码登录（只需登录一次，状态会保存在 `/tmp/chrome_dev_test` 中）。
3. **环境准备**：使用 `pip install playwright` 安装原生 Playwright。
4. **编写脚本**：
   * 使用 `playwright.chromium.connect_over_cdp("http://localhost:9222")` 接管刚才打开的浏览器。
   * 自动导航到输入页面，通过 `page.evaluate()` 填入指令并点击生成。
   * **进阶操作**：使用 `page.on("response", handler)` 监听浏览器后台的网络请求，直接截获包含 `.mp4` 的数据包。
5. **下载穿透**：接管到直链后，用 `requests` 或 `curl` 下载。

---

## 🚀 后续开发路线图 (Next Steps)

如果您确认了这两套方案的逻辑，我们可以按照以下步骤在您的 `/Users/lank/code/lanshu-waytovideo` 目录中开始编码实战：

1. **第一阶段：工程初始化**
   * 创建 Python 虚拟环境。
   * 安装核心依赖 (`playwright`, `camoufox`, `requests` 等)。

2. **第二阶段：开发方案 B (CDP 接管模式)**
   * 这套方案最适合在您的 Mac 本地直接跑通，见效最快，能立刻验证小云雀工作流的可用性。我们将编写 `cdp_worker.py`。

3. **第三阶段：开发方案 A (Camoufox 无头模式)**
   * 在本地验证完核心逻辑后，将其剥离并封装成独立的 `camoufox_worker.py`，配置 Cookie 读取系统，为未来可能部署到云端做准备。

4. **第四阶段：组件融合**
   * 编写统一的调用入口或 CLI 工具，让您可以通过简单的命令行（如 `python main.py --mode cdp --prompt "..."`）来一键生成视频。
