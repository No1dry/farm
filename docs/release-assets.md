# v0.6.0 模型附件恢复

Git 仓库保存源码、资料、材质、本体数据和资产清单。较大的网页 GLB 与可编辑 Blender 源文件保存在同一版本的 [GitHub Release](https://github.com/No1dry/farm/releases/tag/v0.6.0)。下载恢复不需要 GitHub 密钥。

从项目根目录执行，仅需 Python 标准库：

```powershell
# 网页运行所需模型；应在数据库初始化和 npm run build 之前执行
python scripts/fetch_release_assets.py

# 同时恢复可编辑 Blend 和其附件
python scripts/fetch_release_assets.py --all

# 只校验当前文件，不访问网络、不修改文件
python scripts/fetch_release_assets.py --all --verify-only
```

完整项目 ZIP 已带模型时，恢复脚本会校验并跳过已存在的正确文件。只需网页 GLB 时用默认命令；`--blender` 与 `--all` 均在网页模型之外追加 Blender 包。

离线部署时，从 Release 下载 `farm-v0.6.0-models.zip` 和可选的 `farm-v0.6.0-blender.zip` 到一个目录，执行：

```powershell
python scripts/fetch_release_assets.py --all --archive-dir D:/farm-downloads
```

文件恢复到清单指定的原路径，例如 `public/models/full-area.glb` 和 `deliverables/blender/farm-full.blend`。不要仅将 ZIP 放入模型目录而不解压。恢复后继续按 README 安装依赖、初始化数据库和构建前端。

脚本使用 `data/releases/v0.6.0-assets.json` 中固定的版本、下载地址、ZIP 大小/SHA-256 及逐文件大小/SHA-256。所选包全部校验后才写入目标；拒绝额外、缺失、重复、路径穿越、Windows 盘符/替代数据流、符号链接和加密成员。网络下载只使用公开 GitHub Release HTTPS 地址及 GitHub 附件重定向，不读取运行时密钥。

已有文件与清单不一致时默认报错，保护本地编辑。确认要恢复该版本原文件时使用 `--replace`；原内容会先复制并校验到 `.release-asset-backups/<时间与随机标识>/`，再替换。这个备份目录应保留到人工确认，脚本不会删除历史备份。不要将本地修改的模型与原版本清单混用。

脚本只处理模型和 Blender 附件，不改活动数据库、运行配置或模型 API 密钥。SHA 校验失败、网络失败、磁盘错误都会以非零状态退出；不能把失败输出当作恢复完成。
