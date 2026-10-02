# GitHub 发布材料与操作说明

日期：2026-10-02。本文件提供可直接使用的仓库简介和发布步骤；尚未替你创建或上传 GitHub 仓库。

## 推荐填写内容

**Repository name**

```text
shanghai-strategy-lab
```

**Description / About（英文，直接粘贴）**

```text
Interactive A-share strategy research with staged entries, walk-forward validation, trade-level explanations and offline reports. Built with Python, React and FastAPI.
```

**中文说明（用于中文介绍或社交分享）**

一个可交互的上海 A 股策略研究平台，支持阈值交易、分批建仓、滚动验证、交易决策追溯与离线报告导出，将金融规则转化为可解释、可复现的产品体验。

**Topics（分别添加）**

```text
fintech
backtesting
quantitative-finance
a-share
walk-forward-validation
data-visualization
python
react
typescript
fastapi
plotly
offline-first
```

**Website 字段**：目前留空。此项目是本地 FastAPI 应用，没有已部署的在线演示地址。不要将 localhost 填成公共网址；以后有公开视频或真实部署地址时再添加。

## 仓库首页展示什么

根目录 README.md 使用英文，适合金融科技申请与国际读者。它包括：

- 大幅真实界面截图、产品定位和功能表。
- 滚动验证、交易详情、分批建仓及多实验比较截图。
- 可展开的建仓计划和英文报告预览。
- 精选结果及其回顾性研究口径。
- 源码安装、合成数据启动、架构图和研究限制。

原来的详细中文 README 已保留为 [USER_GUIDE_ZH.md](USER_GUIDE_ZH.md)。截图都使用仓库内相对路径；发布时必须同时上传 `docs/screenshots/v3`，不要只复制 README 的文字。

## 使用哪个压缩包

使用项目 `dist` 下的 **Shanghai_Strategy_Lab_GitHub_Source.zip**。它包含源码、依赖清单、截图、文档、合成数据示例和 GitHub 工作流。

它排除了 `storage/`、`.runtime/`、`node_modules/`、虚拟环境、日志、缓存、已有 ZIP 和本地运行数据库。原先 `storage/Shanghai_Strategy_Lab_Offline.zip` 是本机历史案例交付包，不是本次整理的公开源码包。

公开源码可通过 `scripts/prepare_demo.py` 在本地生成合成数据与一个完整实验。该数据明确标记为 synthetic，不冒充截图中的 100 股历史回测。原始行情快照保留在你的本机。

## 方式一：用 Git 推送整个解压目录

1. 解压源码包，进入包含 README.md、frontend、lab 等文件的那一层目录。
2. 在 GitHub 创建新仓库，填入上面的仓库名和 Description，按你的发布计划选择 Public。
3. 创建空仓库时，不再勾选生成 README、License 或 .gitignore，因为压缩包中已包含这些文件。
4. 将下面的 `YOUR_USERNAME` 替换为真实用户名，并在解压后的项目根目录运行：

```powershell
git init
git add .
git commit -m "Publish Shanghai Strategy Lab"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/shanghai-strategy-lab.git
git push -u origin main
```

这些命令适用于新建空仓库。如果远端已有内容，应先拉取并合并，不能用强制推送覆盖它。GitHub 身份验证按你已有的 Git 凭证设置完成，不要把密码或令牌写进 README、脚本或仓库。

## 方式二：在 GitHub 网页上传

1. 同样先创建仓库并解压。
2. 使用仓库中的 **Add file → Upload files**，上传解压后的文件和文件夹。
3. 不要只上传 ZIP 本身：GitHub 不会把 ZIP 内的 README 自动显示成仓库首页。
4. 保持目录结构不变，README.md 位于仓库根目录，截图位于 docs/screenshots/v3。
5. 浏览器上传每次最多 100 个文件；文件多时分批上传，并确认 `.github`、`.gitignore` 等隐藏项目也已包含。单文件限制为 25 MiB。规则见 [GitHub 官方上传说明](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)。

本项目涉及多个目录，推荐方式一，以完整保留目录和隐藏配置。

## 发布后检查

1. 根目录能直接显示英文 README，所有截图正常加载。
2. 右侧 About 填写 Description 和 Topics；可参考 [GitHub 仓库自定义说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository)。
3. Actions 中查看实际检查状态。随包提供工作流不代表远端检查已经完成。
4. 在新目录按 Quick start 启动合成演示，确认没有依赖你本机的真实行情数据。
5. 不要把 1.48 描述为滚动策略结果或独立留出测试：滚动案例为 1.30，公开合成演示结果另算。

## 可选：分享链接的封面

可在仓库 Settings → Social preview 上传 `docs/screenshots/v3/overview-1440.png` 作为现成封面。它是实际应用截图。若以后另做封面，GitHub 推荐 1280 × 640、文件小于 1 MB，详见 [官方 Social preview 说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/customizing-your-repositorys-social-media-preview)。

## 以后重新打包

在项目根目录使用已安装 Python：

```powershell
python scripts/package_github.py
```

打包使用明确的文件范围，并验证 ZIP 内文件哈希。生成的 ZIP 和清单位于 dist，该目录已忽略，不会被再次装进包内。
