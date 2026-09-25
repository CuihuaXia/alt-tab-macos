# AltTab 历史版本归档 / Release archive

这个目录用来长期保存 AltTab 最近的正式版本（默认 10 个），保证以后 upstream（[lwouis/alt-tab-macos](https://github.com/lwouis/alt-tab-macos)）升级大版本、删掉旧文件后，仍然能找到并安装旧版本。

## 存放方式

| 内容 | 放在哪里 | 为什么 |
| --- | --- | --- |
| 安装包 `AltTab-<版本>.zip` | 本 fork 的 **GitHub Releases**（tag 与 upstream 相同，如 `v11.7.1`） | 二进制不进 git history，不会让仓库越来越大；单个文件上限 2 GB，不占 Git LFS 配额 |
| 版本清单 `releases.json` | git（本目录） | 每个版本的发布时间、最低 macOS、大小、SHA-256、Sparkle 签名、fork 和 upstream 两个下载地址 |
| 校验文件 `SHA256SUMS` | git（本目录） | 可以直接用 `shasum -a 256 -c SHA256SUMS` 校验 |
| 工具 `archive.py` | git（本目录） | 下载、校验、安装、更新清单；只用 Python 3 标准库 |
| 自动归档 `.github/workflows/archive_releases.yml` | git | 每周一自动把 upstream 新发布的版本上传到本 fork 的 Releases |

说明：

- AltTab 官方只发布 `.zip`（里面是已签名、已公证的 `AltTab.app`），**没有 `.dmg`**，所以归档的就是这个官方 zip，原样保存，SHA-256 与 upstream 完全一致。
- 没有用 Git LFS：fork 的 LFS 对象会占用你自己的 LFS 存储和带宽配额，而且 LFS 文件依然和代码仓库绑定；Release assets 没有这些限制，下载链接也最直观。
- 归档只增不删：upstream 发布新版本后，旧版本仍保留在 fork 的 Releases 和 `releases.json` 里。

## 当前已记录的版本

| 版本 | upstream 发布日期 | 最低 macOS | 大小 |
| --- | --- | --- | --- |
| 11.7.1 | 2026-09-20 | 12.0 | 5.5 MB |
| 11.7.0 | 2026-09-17 | 12.0 | 5.4 MB |
| 11.6.1 | 2026-09-11 | 10.14.4 | 5.4 MB |
| 11.6.0 | 2026-09-05 | 10.14.4 | 5.4 MB |
| 11.5.0 | 2026-08-19 | 10.14.4 | 5.0 MB |
| 11.4.4 | 2026-08-06 | 10.13 | 8.5 MB |
| 11.4.3 | 2026-07-09 | 10.13 | 8.2 MB |
| 11.4.2 | 2026-07-03 | 10.13 | 8.2 MB |
| 11.4.1 | 2026-07-03 | 10.13 | 8.2 MB |
| 11.4.0 | 2026-07-02 | 10.13 | 8.2 MB |

完整、最新的信息以 [`releases.json`](releases.json) 为准。

## 第一次启用（只需做一次）

1. 把这些文件合并进 fork 的默认分支 `master`（定时任务和手动运行按钮只认默认分支上的 workflow）。
2. 在 fork 的 **Settings → Actions → General** 里允许运行 Actions，并在 “Workflow permissions” 选 **Read and write permissions**。
3. upstream 自带的 `ci_cd.yml` 是作者的发版流程，在 fork 里只会因缺少签名证书而失败，所以已加了 `if: github.repository == 'lwouis/alt-tab-macos'`，在 fork 中自动跳过。
4. 打开 **Actions → archive releases → Run workflow**。几分钟后，fork 的 Releases 页面就会出现这 10 个版本，每个都附带 zip。

之后每周一会自动检查一次；想立即归档，也可以随时手动运行。

## 以后如何安装旧版本

**方法一：网页下载**

1. 打开 `https://github.com/CuihuaXia/alt-tab-macos/releases`，找到想要的版本，下载 `AltTab-<版本>.zip`。
2. 退出正在运行的 AltTab，双击 zip 解压，把 `AltTab.app` 拖进“应用程序”，替换旧的。
3. 可选校验：`shasum -a 256 AltTab-11.6.1.zip`，结果应与 `SHA256SUMS` 中对应行一致。

**方法二：命令行（自动校验 SHA-256）**

```sh
python3 archive/archive.py list                 # 列出已归档版本
python3 archive/archive.py download 11.6.1      # 下载到当前目录并校验
python3 archive/archive.py install 11.6.1       # 下载、校验、验证签名、装到 /Applications
```

脚本优先从 fork 的 Releases 下载，失败时再从 upstream 下载；只要文件的 SHA-256 与清单不符就拒绝使用。

**降级前后的注意事项**

- 先查一下表里的“最低 macOS”是否满足你的系统。
- 装回旧版本后，在 AltTab 设置里把更新选项改成 “Don’t check for updates periodically”，否则它会再提示升级到最新版。
- 跨大版本降级时，建议先备份设置：`defaults export com.lwouis.alt-tab-macos ~/alttab-prefs.plist`，需要时用 `defaults import com.lwouis.alt-tab-macos ~/alttab-prefs.plist` 恢复。

## 维护

- 改保留数量：手动运行 workflow 时填写 `count`，或在本地运行 `python3 archive/archive.py manifest --count 20 --archive-repo CuihuaXia/alt-tab-macos`。
- 同步 upstream：fork 页面上的 “Sync fork” 照常使用即可。本方案除了 `ci_cd.yml` 里新增的一行 `if:` 外只新增文件；若哪天同步时这一行冲突，保留这一行即可。
