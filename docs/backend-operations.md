# 本地后端与模型运维

本项目是单机持久化适配服务：Python 3.12、FastAPI、SQLite、本地 Qwen 推理，以及实际运行的 RDF/SHACL 校验。它没有部署完整 Liangzihu 多库平台，未引入上游前端。默认仅监听本机：前端 5173、API 8000、模型 8081。

## 安装、启动和配置

在 `farm` 目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/deploy_backend.ps1
powershell -ExecutionPolicy Bypass -File scripts/start.ps1 -Production
```

部署脚本在相邻 `.tools/backend-venv` 安装锁定依赖，先备份并迁移数据库，再导入已审查资料，下载/验证模型与运行时并启动模型。集成启动脚本由前端流程管理 API 与网页。仅需要数据库查询时，可分别使用 `deploy_backend.ps1 -WithoutModel` 和 `start.ps1 -WithoutModel`。不会删除数据库或重新生成既有身份。首次需网络、Python 3.12 和前端所需 Node.js；本次已实际运行部署脚本并验证已有资产重用。

模型下载由 `backend/local-model-manifest.json` 锁定官方精确 URL、revision、字节数、SHA-256 和许可证：Qwen/Qwen3-4B-GGUF 的 Q4_K_M，revision `bc640142c66e1fdd12af0bd68f40445458f3869b`，Apache-2.0；llama.cpp b11960 Windows Vulkan，MIT。模型 SHA 为 `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5`；运行时 ZIP SHA 为 `bac6914b5e83523eb008c6789eaa12669f93fbc196c3b9e8237b6672323b33e9`。下载后实际验 hash；许可证保存在各安装目录。相同运行时文件不重复覆盖，避免 Windows 锁住正在使用的 DLL。

本机 RTX 5070 Ti 16GB 使用 Vulkan 实际推理。服务 alias 为 `qwen3-4b-local`，base URL 为 `http://127.0.0.1:8081/v1`，上下文 12288、最大输出 1800、关闭额外思考。生成的本地 API key 用于服务隔离，不依赖付费密钥。`scripts/start-local-model.ps1 -Restart` 只在 PID 对应确切运行时路径时重启；日志为 `runtime/logs/model-*.log`。

配置优先级：`runtime/backend-config.json` < 项目 `.env` < 进程环境变量。`.env.example` 现在是可复制的加载示例；不要用空模型变量覆盖已安装配置。`FARM_CONFIG_FILE` 可通过进程环境指定私密 JSON 的位置。`FARM_DB_PATH` 相对项目根解析。服务使用 `backend.config.load_settings()` 显式加载，启动 API 不会自动导入或清空库。

```powershell
../.tools/backend-venv/Scripts/python.exe -m uvicorn backend.app:create_app --factory --host 127.0.0.1 --port 8000
```

模型配置键为 `FARM_MODEL_BASE_URL`、`FARM_MODEL_NAME`、`FARM_MODEL_API_KEY`、`FARM_MODEL_TIMEOUT_SECONDS`、`FARM_MODEL_MAX_TOKENS`、`FARM_MODEL_CONSTRAINED_JSON`。只将 JSON schema 约束开关用于支持该格式的提供方。私密配置、key 文件和运行数据不放入前端或审查报告。

## 权限和受控导入

默认 `FARM_AUTH_MODE=local`。只读 API 无需登录；浏览器从准确允许的本机 Origin/Host 发起 `POST /api/auth/local-session` 才能取得 8 小时 HttpOnly、SameSite=Strict 的 operator cookie，响应为 `{actor:{id,role,expires},mode}`。operator 只能显式保存草稿，不能做管理导入。跨站 Origin、伪 Host 和远程客户端不能取得本地会话。

管理员使用私密配置中的 bearer token；没有自动管理员网页会话。`token` 模式禁用本地浏览器会话，只接受明确 bearer 写入；`readonly` 模式拒绝写入。当前没有完整账号、组织、OIDC 或公网安全验收。远程网页应视为只读；远程管理 API 需由部署者提供 TLS 和网络访问控制。

管理导入每批最多 500 条，只接收结构化记录。preview 做来源键、类型、同数据集关系目标及上游 SHACL 校验，不修改实体；apply 要求 preview ID 与 digest，检查 30 分钟有效期和旧修订号，在同一事务中写入，重复 apply 返回同一收据。过期/竞争更新或 SHACL 失败不写数据。禁止任意 SQL、脚本、真实库 synthetic 数据和客户端指定真实 UUID。

preview、apply 和本地 Store 导入共用嵌套结构验证：列表不能以 null 替代，观测必须有有限数值及字符串单位；已提供的时间必须包含时区。坏批次在分配身份前拒收。关系仅 accepted 状态进入预览与正式语义图；冲突的重复来源关系键拒绝导入。内部关系 ID 按数据集、主体、来源命名空间生成，原 ID 保存为 external_id，防止外部关系编号覆盖另一主体或数据集。

```powershell
../.tools/backend-venv/Scripts/python.exe scripts/db_import_api.py preview data/audit/entities.json --output runtime/preview.json
# 审阅收据后显式应用，凭据只由 CLI 读取，不输出：
../.tools/backend-venv/Scripts/python.exe scripts/db_import_api.py apply runtime/preview.json --output runtime/applied.json
```

## 接口与语义边界

| 路由 | 主要字段或权限 |
|---|---|
| GET /api/health | 数据库、schema_version=2、模型配置、auth_mode、device_control=false |
| GET /api/summary?dataset=real或demo | entity_count、ledger_count、spatial_count（关联空间实体）、representation_count（表示数量）、实际知识库数量 |
| GET /api/entities | dataset、q、kind、limit；默认/最大 1000 |
| GET /api/entities/{uuid} | 档案、UUID/IRI、来源、版本、观测、设备、关系、预警、多种 representations |
| GET /api/relations/{uuid} | dataset、depth=1或2；限制同数据集的邻接图 |
| GET /api/ontology/schema | 实际加载的上游类/属性/SHACL 指纹 |
| POST /api/ontology/validate | `{dataset}`；实际 pySHACL/RDFS 结果 |
| GET /api/knowledge | dataset、q、kind；本地公开参考与独立合成样例 |
| GET /api/sources/{id}/file | dataset；仅已登记、路径白名单且 hash 一致的原文件 |
| POST /api/assistant | message、selected_entity_id、dataset、history |
| GET /api/plans | dataset；已保存草稿 |
| POST /api/plans | operator；title、entity_id、dataset、content、evidence_ids、conditions、gaps |
| POST /api/admin/imports/preview、apply | admin；受控预览/事务应用 |

真实实体首次分配 UUIDv4，之后按 dataset + 来源注册 UUID + canonical_key 持久复用；IRI 为 `urn:lzo:object:UUID`。上游 fixture 的 UUIDv5 仅在 demo 保留。台账 canonical_key 不含文件 hash，版本变化不会换 UUID。`data/audit/entity-mapping.json` 是从数据库导出的快照，不能代替数据库备份。

本体文件来自锁定上游 commit，位于 `backend/ontology`，加载前检查 SHA。RDFlib 实际构图，pySHACL 运行上游 DeviceShape：Device（包括 RDFS 子类 Sensor/Pump）恰有一个 Organization 管理者。该校验不证明鱼种、水质或生物安全。有限邻接查询没有开放任意 SPARQL。管理 preview 对已存在实体按预期更新构图，允许修复缺失管理者，不保留待替换的旧主体断言。

台账面积原值与单位保留；未给单位时为 null，1010.99 不能直接宣称为亩。图纸纸页坐标为 `paper_point`；`model_area_units2` 是纸页单位平方，`model_area_m2=null`，不可换算为实际地面面积。实体多种表示不重复计入实体/台账统计。图纸与业务编号关联不等于卫星配准。

## 检索、模型和方案

公开知识来自 `data/knowledge/curated.json`，保存发布方、URL、抓取时间、hash、版本、适用条件、限制和原创摘要。`reference_verified=true` 只表示参考来源经过核查，`site_fact=false`，不会把本地资料升级为现场 verified。

助手执行实体解析、档案/关系/观测/来源、知识检索和历史草稿查询并记录审计。公开知识按实体类别、关键词和明确记录的季节条件筛选；季节未知时不混入需要特定天气的条目，不凭当前日期推断高温。知识浏览接口仍可列出带适用条件的完整参考。当前是本地条目检索，不是生产规模向量 RAG。

模型通过真正的 OpenAI-compatible HTTP 服务推理，服务端传入数据库事实卡与已检索证据。结构、证据 ID、空间动作和保守文本校验均在服务端执行；本地 provider 还使用受限 JSON 解码。自由文字的语义仍无法由合法引用 ID 完全证明，需人工复核。原始无约束模型曾生成无依据 3 mg/L 阈值；初版检索也曾混入不适用季节步骤。缺陷与修复证据保存在 `docs/audit/local-model-raw-limitations.json`、`model-scope-regression.json`，不作为应用建议。

返回状态有 unconfigured、not_found、needs_clarification、ok、unavailable、invalid_response。未配置模型仍可真实查询和定位。明确不存在的新编号不会沿用旧选择。唯一动作是有数据库空间绑定时的 `focus_entity`；没有设备控制、任意代码执行或自动保存。

七部分输出为：对象、事实与证据、判断边界、处理建议、设备需求、复测与跟踪、来源。无模型时为结构化核查清单；成功真实推理时为 `model_assisted_evidence_review`，仍 `production_plan_accepted=false`。真实现场缺观测、物种、校准/容量和生产适用阈值时只提供补充核查方案。独立 `DEMO-CHECK-POND` 有完整合成上下文、固定时间观测与真实数据库关系，用于正向演示；它不映射真实田塘，超过有效时限会自动过期。原历史缺氧样例继续明确 stale。

用户显式保存才写入 plans；证据必须属于该对象/数据集或可适用公共参考。`saved_plans` 为当前实体最近 10 条草稿，不能当作已执行处置或设备运行历史。

## 迁移、备份、恢复与表示更新

schema v2 是实际单调迁移：保留 v1 全部身份，增加迁移记录、公共知识表和导入预览表。未知更高版本拒绝打开，不重置版本。没有实现历史 implementation 或完整上游 PostgreSQL 的自动迁移。

```powershell
../.tools/backend-venv/Scripts/python.exe scripts/db_migrate.py
../.tools/backend-venv/Scripts/python.exe scripts/db_backup.py runtime/backups/farm-unique-name.sqlite3
../.tools/backend-venv/Scripts/python.exe scripts/db_restore.py runtime/backups/farm-unique-name.sqlite3 runtime/restored-farm.sqlite3
```

迁移命令先用 SQLite backup API 备份；在线备份取得一致快照，不要只复制活动 WAL 主文件。备份不覆盖已有目标，恢复检查 integrity/schema，只写不存在的新目标。停止 API 后将 FARM_DB_PATH 指向恢复库，重启并核对 UUID、方案与数量；切回旧路径可回退。

```powershell
../.tools/backend-venv/Scripts/python.exe scripts/db_init.py
../.tools/backend-venv/Scripts/python.exe scripts/db_export.py --db runtime/farm.sqlite3 --output data/audit
```

db_init 校验台账/fixture/图纸证据 hash，导入公开知识与当前 manifest；每个来源导入批次事务化，manifest 整批更新/退休/审计在同一 SQLite 事务内，任一失败全部回滚该快照。db_init 的不同来源阶段是独立事务；部署前备份可回退整个批次。

当前 manifest 被视为经审查的完整空间快照，缺失表示将退役并保留历史。仅空间来源实体随之退役；业务台账 UUID 永远不因表示消失而退役。更新记录保存旧/新表示审计。已退役 ID 不能自动复活；同源对象在最终图纸重新出现时须显式恢复原 UUID：

```powershell
../.tools/backend-venv/Scripts/python.exe scripts/db_restore_spatial.py DETAIL-QING17 --reason '复核最终图纸中的同源清17对象，恢复既有身份'
../.tools/backend-venv/Scripts/python.exe scripts/db_init.py
```

SAT-LAKE-002 是经审查合并后持续退役的错误初始水面，不应恢复。重复 E3 标签仅在明确 candidate_source_key、ambiguous_repeated_code、link_verified=false 和审查证据齐备时解除旧业务绑定，记录审计，保留原业务身份并分配独立图纸身份。

## 验证

```powershell
../.tools/backend-venv/Scripts/python.exe -m pytest tests/test_backend.py -q --basetemp ../.tools/pytest-backend-NEW
../.tools/backend-venv/Scripts/python.exe scripts/verify_local_model.py --scenario historical
../.tools/backend-venv/Scripts/python.exe scripts/verify_local_model.py --scenario ready
```

Windows 默认 pytest 临时目录不可用，需指定新的项目外临时目录。测试覆盖持久身份、原子回滚、权限、真实/演示隔离、来源穿越、语义校验、修订竞争、空间退休/恢复、知识适用性与模型负例。真实推理收据记录实际 token usage、延时、证据与七部分输出；自动测试包含协议替身，二者在报告中分开。

仍不宣称：真实传感器接入、实际设备可用、测绘配准、已获生产处置标准、生物效果验证、公网账号平台、完整上游多库吞吐。当前交付覆盖本地资料—关系—参考检索—实际模型核查草稿—显式保存的闭环。

## 历史图纸版数据库快照（2026-10-29，早于全域样例扩充）

已导入冻结 manifest `b6f1cbfc7e4f8e08de154a0be433432d082139780d89fd4d66c269a1ec664552`：284 个空间表示、284 个 real 资料实体、18 个 synthetic demo 实体；100/100 台账都有当前图纸表示，初始100个台账UUID集合完全不变，另保留9条退役身份。20个设施标注为原图标记锚点，不能解释为20个已核验独立现场资产或在线设备。

DETAIL-QING17 经显式恢复继续使用 UUID `7cce3a4c-9fba-4674-8b8f-b84eaff78ebf`。台账E3仅保留 DRAW-pdf-05-E3；DRAW-pdf-02-E3 已使用独立候选身份，并移除对台账E3的不当图纸来源关联，原来源行和审计仍保留。20条本体关系使用来源命名空间内部ID，原断言ID保存在external_id。

最终验证68项后端测试通过；重复导入UUID/revision不变，SQLite integrity=ok，真实/演示SHACL均通过。备份为 `runtime/backups/farm-verified-20261029T020050Z.sqlite3`，SHA-256 `d53b25e021d26abfc22eea354c83b3974c488ec935fe67ca271be6b14f7a8c9a`。恢复到新文件后，全部应用表的数据校验和相同；报告详见 `docs/audit/backend-verification.json`。报告中的方案数量仅对应备份时间，之后用户仍可显式保存新草稿。

最终浏览器及模型运行后另生成交付快照 `runtime/backups/farm-delivery-20261029T021212Z.sqlite3`，SHA-256 `e458582895f38e84f38c9ac3fbfa5ecb053d304da3a11737c9d4fc461bd8604a`。已恢复至新文件并再次比较12张应用表；见 `deliverables/verification/final-backup.json`。该快照包含最后一次浏览器显式保存的演示草稿。模型和角色密钥在独立的服务端私密配置中，不包含于数据快照。

面积导出同时保留 `model_area_m2`、`model_area_units2` 和 `model_source_unit`。纸面图形的前者为空，后两者记录纸面面积与 `paper_point`，不得将纸面值转换成实地面积或用于凑齐台账总数。

## 全域样例场景更新

后续用户已授权缺失业务先用样例，默认页面现为全域演示，新增 171 条独立合成实体，真实资料保持独立。上述 18 条 demo/68 项测试是历史快照口径，不是当前总数。配置替换、场景身份、设备位置和最新验证见 [全域本体场景](backend-full-scene.md)，当前导入回执为 `deliverables/verification/full-scene-import.json`。最终模型资产与总库备份仍以最后一次集成验收回执为准。
