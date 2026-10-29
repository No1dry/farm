# 梁子湖本体工程采用审查

审查日期：2026-10-29。结论：采用新版 `ontology-platform` 的可适用身份、来源和语义表示契约，配套本地 SQLite 适配层；没有运行或宣称接入完整多库平台，也没有引入上游前端。

## 版本和证据

- 目标仓库：[lianggeming14/liangzihu-ontology-traceability](https://github.com/lianggeming14/liangzihu-ontology-traceability/tree/5776ba8d656139d3fb8dfabd137d83dd6dbba11c)。`git ls-remote` 核实 HEAD/main 为 `5776ba8d656139d3fb8dfabd137d83dd6dbba11c`，提交时间 2026-10-23T13:43:41+08:00。
- 新版目录 `ontology-platform`；`SYNC_ORIGIN.json` 指向源仓库 `No1dry/Ontology-Farm` 的 `8ee79416073ce91d9eb5e724fefb04241e6187b5`。目标提交是代码同步快照，不能推断存在运行数据库。
- 根目录 `implementation` 是历史 v0.4.0 工程。其 `run_server.py`、8787端口、SQLite实现及“378 passed”记录不适用于新版，未作为本项目后端实现来源。
- 本地已有 `deliverables/liangzihu-samples/source-manifest.json` 正是目标 commit，声明 `data_nature=synthetic`。20份原文件的 SHA-256 全部复核一致。用于数据库导入的仅新版3份 semantic fixture；地图、遥测与历史种子仍作为样例资料保留。
- 审查实际读取了 ingestion/identity.py、ingestion/schemas.py、semantic/facts.py、semantic/schemas.py、router、config、main、锁定依赖和验收记录。指纹详见 [ontology-source-review.json](ontology-source-review.json)。

## 实际采用的契约

| 部分 | 上游代码行为 | 本项目实现 |
|---|---|---|
| 来源身份 | SourceKey包含source_id、source_system、source_instance、collection、canonical_key；IdentityService以source_id+canonical_key查持久绑定 | `backend/contracts.py`保留同名结构；`source_systems`与`entities`保存来源UUID和规范键，另加dataset隔离 |
| 实体UUID | 首次reserve且没有已确认共享业务键时调用uuid4；重复来源复用已绑定UUID | 真实对象首次导入UUIDv4，重复导入和版本更新不改UUID。数据库必须备份，删库重建不保证原UUID |
| 样例UUID | 固定semantic fixtures使用UUIDv5便于重放 | 导入时保留原resource_id，严格放在demo。不得把fixture的UUIDv5当成真实来源UUID生成规则 |
| 实体IRI | semantic/facts.py使用`urn:lzo:object:{UUID}` | 直接采用该IRI契约；Field/Pond/Orchard等采用原`https://w3id.org/lzo/ontology/`类IRI |
| 数据性质 | synthetic/test/imported_unverified/verified | 保留四种词汇；当前真实资料标imported_unverified、演示标synthetic，绝不以“文件是真实提供”推断现场事实已验证 |
| 证据和版本 | 来源支持、修订、候选与采纳状态分离 | 记录文件hash、表/行/单元格、source_key、immutable entity_versions；来源hash是内容校验，不证明内容真实 |
| 跨来源合并 | 上游需完整身份路径、已确认对齐规则及审批；不能因名称相近自动合并 | 不实施自动合并。空间ID独立持久绑定；只有manifest明确business_source_key、link_verified与link_evidence且唯一匹配才关联 |

具体身份依据见[上游身份解析实现](https://github.com/lianggeming14/liangzihu-ontology-traceability/blob/5776ba8d656139d3fb8dfabd137d83dd6dbba11c/ontology-platform/backend/src/lzo/ingestion/identity.py)。本地契约是独立编写的适配层，不是把依赖完整治理事务的上游IdentityService直接拷出运行。

台账source_key采用 `xls:workbook-area-register:全域田块面积汇总:<原编号>`，不含文件hash。hash变化表示来源版本变化，不应产生新实体。编号只在对应来源/集合内唯一。五张完整图纸逐项核查后可将100台账与各自图纸表示关联；多种表示不重复实体计数。重复E3标签保留独立来源候选，不能仅按编号合并。这些都是业务身份关联，不是坐标配准；全域卫星对象仍独立。

## 上游实际接口及运行依赖

新版实际FastAPI前缀为 `/api/v1`，有objects、links、geometry、graph/neighborhood、query/sparql、imports/preview、imports/apply、sources、identity/merges/preview、identity/merges、identity/aliases等。写操作依赖认证主体、治理事务、revision/If-Match或幂等命令，身份合并不是一个简单“覆盖UUID”的工具。[实际摄取路由](https://github.com/lianggeming14/liangzihu-ontology-traceability/blob/5776ba8d656139d3fb8dfabd137d83dd6dbba11c/ontology-platform/backend/src/lzo/ingestion/router.py)

新版pyproject限定Python >=3.12,<3.13，完整依赖以requirements.lock为准。运行完整平台需PostgreSQL治理库、Jena Fuseki/TDB2、OIDC身份服务、独立worker；split模式另需GIS/PostGIS、时序、资料目录数据库；S3配置还需endpoint、bucket及凭据文件。完整API入口是 `uvicorn lzo.main:create_app --factory`，不是历史implementation的run_server.py。[后端运行说明](https://github.com/lianggeming14/liangzihu-ontology-traceability/blob/5776ba8d656139d3fb8dfabd137d83dd6dbba11c/ontology-platform/backend/README.md)

本项目实际入口和接口为 `backend.app:create_app --factory`、8000端口与 `/api/*`，使用SQLite。没有把本地 `/api/entities` 伪称为上游 `/api/v1/objects` 的完全兼容替代。完整接口见 [backend-operations.md](../backend-operations.md)。

## 已实施与未实施

本节早期测试数量属于对应历史实现。当前V0.6运行检查为81个后端用例、189个演示实体，见 ../acceptance.md；发布准备额外增加资产恢复与公开种子测试，见 ../releases/v0.6.0.md。首次安装可使用保留本版UUID的公开种子，详见 ../release-data-seed.md。

本项目已实现：真实台账100条导入及来源hash校验、持久身份、修订、来源证据、空间映射及退役/恢复、真实/演示隔离、本体关系查询、资料质量检查、具名演示业务规则、适用条件检索审计、实际本地模型推理、JSON响应约束、显式保存方案、权限分级、受控导入预览/事务应用、schema v1→v2迁移和SQLite备份恢复。

最终同版后端测试68项通过，回归命令与修复记录见 [release-review-v04.md](release-review-v04.md)。冻结manifest的284个表示已全部导入：284个real资料实体、18个synthetic演示实体、9条退役历史身份；100个初始台账UUID保持不变。最终数据导入、实体数量及备份恢复证据见 [backend-verification.json](backend-verification.json)。这些测试是本地适配服务的证据，不是完整上游平台测试结果。另有实际HTTP推理收据 [历史预警](local-model-verification.json) 和 [独立合成核查情景](local-model-verification-ready.json)，不是协议替身返回。

上游semantic fixture本身没有本项目所需的缺氧处理知识。`data/demo/oxygen-scenario.json`是本次额外编写的合成测试场景，关联上游演示Pond，固定历史观测和测试阈值均明确标synthetic。它不是从上游“发现”的生产规则。原telemetry fixture使用占位object_id，未自动拼接到semantic UUID，以免制造假关系。

新增 `data/demo/inspection-ready-scenario.json` 是独立合成管理组/塘/传感器/水泵情景，不绑定用户田塘。固定时间观测、鱼种阶段和设备关系用于正向核查闭环；仍无生产阈值承诺，数据到期自动过期。公开农业参考来自另行核查的官方网页与FAO材料，保留来源URL/hash/时间及适用条件，绝不伪称上游自带生产知识或本地现场事实。

实际语义复用已超过IRI字段与样例：`backend/ontology`保留锁定commit的core/agriculture/devices TTL、core SHACL与finite-profile文件及SHA清单。RDFlib从数据库构建RDF图，pySHACL执行RDFS推断及上游DeviceShape：Device及其Sensor/Pump子类恰有一个Organization管理者。真实/演示图验证及邻接关系查询已运行；导入preview同样执行该校验，不合格无法apply。finite-profile作为版本依据保留，没有宣称运行其全部上游投影队列。

本项目未实施：上游Jena事实投影、任意SPARQL服务、完整审批和OIDC账号系统、专业多库事务/投递/恢复、来源扫描调度及生产设备接入。当前有本机operator会话和CLI bearer管理员，权限范围与完整账号平台不同；默认仅127.0.0.1，未作公网部署验收。未迁移或改动上游运行数据。

上游验收记录显示10,000实体/100,000关系/10用户负载70次操作中50完成、20次SPARQL_TIMEOUT，图谱和SPARQL各10次全失败；runner的pytest通过不代表性能通过。Docker部署、物理断网和现场设备验收未完成。本轮未重新执行该完整平台测试，因此不继承其任何通过数量为本项目结果。[上游验收原始说明](https://github.com/lianggeming14/liangzihu-ontology-traceability/blob/5776ba8d656139d3fb8dfabd137d83dd6dbba11c/ontology-platform/docs/database/acceptance.md)

## 当前边界

- 原台账列“种植面积”未标单位，1010.99只作为原数值合计；推定亩单独展示。图纸paper_point²不是m²；model_area_m2为空时不保留旧的示意米尺度面积，也不与台账计算误差或合计。
- 真实监测、鱼种、设备可用性与经现场审定的生产阈值仍缺失；官方参考已经接入，但缺资料、过期或单位冲突仍不能产生确定处置结论。
- Qwen3-4B Q4_K_M已在本机RTX 5070 Ti上经llama.cpp Vulkan实际运行。官方版本、SHA与Apache-2.0/MIT许可证见[模型资产验证](local-model-assets.json)。没有付费API依赖。成功模型输出分为七部分核查草稿，不能验收为已批准生产处置方案。
- 模型证据ID校验、JSON结构、动作allowlist和保守文本检查能拒绝已覆盖的负例，不能证明所有自由文本语义都真实。事实卡固定来自DB，模型回答需人工复核。
- 原始无约束模型曾给出未提供的3 mg/L阈值；初次知识召回还混入不适用低温步骤。已保留缺陷记录并加季节范围过滤回归，不能据单次成功推理宣称完全防编造。
- 未发现上游工程独立项目级许可证声明；本次只复制明确列出的本体/shape资产，没有复制整套上游源码或前端。若对外整套复用/分发，需要补查该部分授权条款。本地模型和运行时有独立明确开源许可证。
