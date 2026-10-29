# v0.6.0 公开初始化种子

`data/seed/farm-v0.6.0.sqlite3` 用于首次安装，保留本次验收的实体 UUID，尤其是 100 条面积台账的真实资料实体。它是公开业务数据种子，不是工作环境数据库备份，也不代表已接入现场生产监测。

`real` 表示来自已登记资料、尚未完成现场核实；`demo` 是隔离的合成演示数据。台账单位、定位精度等不确定性仍保留在档案中。样例鱼种、设备和监测值不能据此当成现场事实。

## 首次安装与已有安装

在项目根目录运行：

```powershell
python scripts/release_data_seed.py
python scripts/db_init.py --db runtime/farm.sqlite3
```

第一条检查文件哈希、表和列白名单、完整性、数据集数量、UUID 指纹及空历史表。第二条仅在目标文件**不存在**时验证并复制公开种子，然后按现有导入器幂等刷新资料。返回 `release_seed_initialized: true` 表示使用了发布种子。后续启动返回 `false`，继续使用已有数据库。

已有目标文件始终不会被种子覆盖，即使文件为空或不是有效 SQLite 数据库。后续正常导入仍会更新已审核业务资料并生成本机导入审计；种子中的零审计记录不代表安装后禁用审计。迁移、备份和恢复仍使用项目原有运维流程。

需要独立新分配真实资料 UUID 时，可显式使用 `--without-release-seed`；这不会与本发布的 UUID 保持一致，因此常规部署不使用该参数。不要将公开种子还原到已有生产数据库之上。

## 公开范围与来源

制作脚本 `scripts/release_data_seed.py` 使用 SQLite `mode=ro` 和只读事务读取来源数据库中的当前业务实体、来源系统身份。它创建全新的临时数据库，从仓库中经过哈希校验的资料重新导入来源、空间绑定、关系与知识，然后核对每个实体的 UUID、来源键、内容摘要和修订号没有变化。显示名称等缓存列也必须与公开 payload 一致。

该流程没有复制运行库的文件页，没有读取对话、方案、审计或导入预览的内容。历史实体版本和 9 条退役模型实体不进入公开种子；每个当前实体仅保留一个当前版本。工具拒绝未审核的表、列、视图、触发器和业务来源系统，也拒绝与仓库公开资料不一致的当前实体。

| 表 | 公开行数 | 列内容及来源 |
| --- | ---: | --- |
| `source_systems` | 5 | 保留当前来源系统 UUID、real/demo 数据集及已审核来源键 |
| `entities` | 473 | 保留当前 UUID、来源键、业务档案、内容摘要、当前修订号与合法更新时间；284 条 real，189 条 demo |
| `entity_versions` | 473 | 根据当前实体重建一条当前版本，不包含历史 payload |
| `sources` | 499 | 从仓库台账、模型 manifest、隔离样例及知识资料重建的证据 payload |
| `entity_sources` | 997 | 由当前公开导入器重建的实体与来源关联 |
| `spatial_bindings` | 405 | 由当前 manifest 和样例布局重建的空间 ID、实体 UUID 及定位元数据 |
| `relations` | 239 | 由公开模型、样例和本体导入规则重建的关系身份、主客体、谓词及依据 |
| `knowledge_entries` | 4 | 仓库 `data/knowledge/curated.json` 中的知识、版本及摘要 |
| `schema_migrations` | 2 | 新建库执行现有迁移产生的版本、时间和说明 |
| `plans` | 0 | 表结构保留，已保存处置方案不公开 |
| `audit_log` | 0 | 表结构保留，工具调用与运行审计不公开 |
| `import_previews` | 0 | 表结构保留，导入预览、操作者与回执不公开 |

种子不包含认证、会话、凭据、密钥、助手对话等表或记录；制作过程不读取运行环境的模型密钥或服务端配置文件。若后续数据库加入新表或新列，必须重新审核并更新白名单，不能直接沿用本次发布判断。

完整公开资料路径及 SHA-256、100 个台账 UUID 和所有表计数见 `data/seed/manifest.json`。完整实体身份指纹涵盖 UUID、数据集、来源 UUID、来源键、内容摘要和修订号。

- 种子大小：5,718,016 字节。
- 文件 SHA-256：`96a384f675a954ae6910a9f0c8e950e897d108404929183bb6a795d69e191377`。
- 实体身份指纹：`81b4c1053daca6da10796475a62266177372713a9cf3a995444a89a95e4f5680`。
- 对应模型 manifest SHA-256：`2fc32f4cba5ef33e68eefa16e3d9ec41f8374f29ecfbdbd8f2ce68227d39c673`。

## 重建与测试

生成操作拒绝覆盖输出文件。审核新发布时应使用新的输出路径；源库只读，不能作为输出路径：

```powershell
python scripts/release_data_seed.py --source runtime/farm.sqlite3 --seed tmp/review-seed.sqlite3 --manifest tmp/review-seed.json
python scripts/release_data_seed.py --seed tmp/review-seed.sqlite3 --manifest tmp/review-seed.json
python -m pytest tests/test_release_seed.py -q
```

迁移执行时间、种子制作时间等可能使重新生成的 SQLite 文件哈希不同；当前业务 UUID、内容摘要、修订号及身份指纹必须一致。重建不是自动发布授权，仍需审核来源资料与公开范围。

新增测试覆盖：首次安装及重复初始化的 UUID 稳定性、全部当前实体一致性、业务表完整性、历史表为空、向方案/审计/预览/旧版本插入私有标记后重建不泄露任何标记字节、源文件哈希不变、哈希损坏拒绝初始化、额外凭据表拒绝导出、已有数据库永不替换，以及缓存名称被私有内容污染时拒绝导出。

2026-10-29 本次实际执行 `python -m pytest tests/test_release_seed.py -q`：6 项通过。完整项目验收以本版本发布测试报告为准；这些种子测试不能替代网页与三维交互验收。
