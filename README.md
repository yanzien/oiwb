# yanzien 信奥工作台

> 一个零依赖、纯本地存储、手机 / 电脑通用的 OI（信息学奥赛）备赛工作台。题目管理、比赛倒计时、模拟决斗、OJ 一键导入、数据统计——全部塞进**单个 HTML 文件**，离线可用，数据只存在你自己的浏览器里。

---

## ✨ 功能特性

- 📚 **题目管理**：难度分级（洛谷八档配色）、标签、题解链接、掌握度标记
- ⏱️ **比赛倒计时**：联网抓取 Codeforces / AtCoder / 洛谷 / 牛客 / Vjudge 即将开始的比赛，实时倒计时
- ⚔️ **模拟决斗**：自定义题目清单，限时自测，赛前热身
- 📥 **OJ 一键导入**：浏览器端脚本抓取洛谷 / CF / AtCoder / Vjudge 的题目与比赛，复制粘贴即导入（已做重复检测）
- 📊 **数据统计 & 学习看板**：刷题量、正确率、科目分布一目了然
- 🎨 **主题与排版**：暗色模式、紧凑模式、字体大小调节
- 💾 **数据安全**：localStorage 持久化 + 一键导出 / 导入 JSON 备份，累计 30 条自动提醒
- 📱 **移动端适配**：窄屏自动单列，添加到主屏幕即变 APP
- 🧭 **首访新手指引**：镂空蒙层引导，8 步带你跑通核心功能

---

## 🚀 快速开始

### 方式一：本地直接打开（最省事）
双击 `index.html`，数据存在浏览器 `localStorage`，**离线可用**。适合个人电脑。

### 方式二：GitHub Pages（推荐在线托管）
> 本仓库根目录已是 `index.html`，开箱即用，直接整体推到 GitHub 即可。
1. 把本文件夹整体推到仓库。
2. 仓库 **Settings → Pages → Source** 选 `main` 分支根目录 → Save。
3. 几分钟后访问 `https://<用户名>.github.io/<仓库名>/`。

### 方式三：其他静态托管
Vercel / Netlify / CloudStudio / 任意能放单文件的服务器，上传这一个 HTML 即可。

> 无论哪种方式，前端都是**纯静态、零后端依赖**。部署地址只是方便访问，数据永远在你自己浏览器里。

---

## 📁 项目结构

```
index.html                     # 前端单文件（核心，GitHub Pages 默认入口）
scrape.py                      # 聚合爬虫：抓取 CF/洛谷/AtCoder/牛客 → contests.json
requirements.txt               # 爬虫依赖
contests.json                  # 爬虫输出（含题目数组，会被 workflow 自动更新）
.github/workflows/scrape.yml   # 每 30 分钟定时跑爬虫并自动提交
backend/                       # 其他后端源码（参考用，非前端运行必需）
├── cloudflare-worker/         # 洛谷直连兜底（服务端解析，避开风控）
│   └── luogu-contests.js
└── 部署指南.md                # 后端部署详细步骤
README.md                      # 本文件
.gitignore                     # 排除临时文件 / 内部目录
```

---

## 🔧 可选后端（让洛谷比赛也能自动进来）

纯前端已经能用：比赛走内置公共源实时抓（CF / AtCoder / kontests / Vjudge），题目 / 决斗 / 工具全部本地可用。**后端只是让洛谷和题目列表也能自动进来，且更稳。**

- **GitHub Actions 爬虫**：本仓库已把 `scrape.py` / `requirements.txt` / `contests.json` / `.github/workflows/scrape.yml` 直接放在**根目录**（GitHub Actions 要求 `.github` 在根），推上去后开启 Actions 的「Read and write permissions」，每 30 分钟自动产出 `contests.json`。
- **Cloudflare Worker**：把 `backend/cloudflare-worker/luogu-contests.js` 粘贴进新建的 Worker，补洛谷直连兜底。

前后端对接方式（在前端「比赛倒计时 → 数据源」里填 URL）详见 **`backend/部署指南.md`**。

---

## 🔒 隐私

所有数据**只存在你自己的浏览器 `localStorage`，不会上传任何服务器**。部署后的页面是公开链接，但**看不到你的任何数据**。请勿在公开页面预填真实隐私信息。

---

## 📄 许可

MIT License —— 可自由使用、修改、分发。
