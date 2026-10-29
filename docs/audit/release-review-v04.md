# V0.4 独立发布审查

审查日期：2026-10-29。审查者为独立只读代码审查代理。范围是 `src/twin`、`backend` 与对应自动测试；没有修改产品代码、读取运行配置密钥或操作真实数据库。针对缺陷的写入复现全部使用操作系统临时目录中新建的 SQLite 库；场景竞态复现使用实际 `TwinScene` 方法与延迟资源替身，不启动页面或会话。

本文记录审查时点的证据，不等同最终模型、全量原图或现场验收。主线程和资料/Blender审查代理仍在更新设施及 E3/QING17 绑定，故不将中途模型数量或数据库数量冻结为最终交付值。

**最新状态：同日修复后独立复验已关闭 R1–R6 的对应代码问题。后端 64/64 测试通过；R3 原竞态和新对象变体经实际场景方法复验通过。完整浏览器回归及最终资产/数据库同版验收由主线程最终收据补充，见本文末尾的关闭记录。以下初次发现作为历史保留。**

## 初次审查结论

软件已经有独立 SQLite 身份与来源、受控 API、明确演示数据集、受限模型协议和显式草稿保存。现有测试通过，但审查补充复现了五项应修复的软件缺陷：跨数据集关系覆盖、无效嵌套记录破坏查询、过期导航回流、token 模式继续接受本地会话、预览与实际 SHACL 图状态不一致。应在修复并针对原场景复验后关闭这些条目，不能仅凭旧测试全绿宣称发布验收通过。

下表行号对应初次审查时点；后续修改可能移动。P2 表示需要修复的重要缺陷，P3 表示较小的记录/呈现问题。没有将缺少测绘控制点、实时设备或生产资料列为软件漏洞。

## 已复现的重要问题

| 编号 | 级别与位置 | 实际复现与影响 | 建议修复/验收 |
|---|---|---|---|
| R1 | P2，`backend/store.py:220-223`，关系表定义 `:123-125` | `relations.id` 是全局主键；导入信任来稿 `relation.id` 并 `INSERT OR REPLACE`。先在 demo 中建立 `id=same-external-relation-id` 的关系，再通过管理员 API 在 real 导入同一关系 ID，目标仍为 real 实体。preview/apply 通过，demo 对象关系数由 1 变成 0。来源 ID 冲突可覆盖另一数据集或另一主体的关系。 | 内部关系身份按数据集、主体和来源关系 ID 建立稳定命名空间；不允许来稿全局 ID 覆盖其他所有者。回归应验证 real 导入后 demo 原关系完整且 ID 不变；同数据集不同主体也不互相覆盖。 |
| R2 | P2，`backend/admin.py:11-26`、`backend/store.py:156-166`、`:405` 和 `:47` | 管理员导入 `{source_id:'review',source_key:'BAD',kind:'pond',observations:null}`：preview 返回 201，apply 返回 200，随后 `/api/entities` 和 `/api/summary` 均返回 500。预览没有验证嵌套字段，读取时对 null 遍历。一个常见的空值记录即可让完整目录和助手解析失效。 | 预览与实际写入共用结构验证：观测、设备、关系、类、上下文等字段必须具有正确类型，数组元素也需验证；清晰返回 422，且整批零写入。避免只修读取端一个 null。 |
| R3 | P2，`src/twin/scene.js:59-60`、`:79-81`，`src/twin/main.js:63-65`、`:76` | 实际方法复现：`select('A')` 等待 detail-A 资源 → `showAsset('full')` 完成 → 旧 A 资源返回。结果 `activeAsset='full'`，但 `selectedID='A'`，最后飞行目标是 A 的局部坐标 `[500,0,500]`。`showAsset` 取消旧 assetSeq，却不取消 selectSeq；旧 select 返回后仍改相机。选择无空间绑定实体也不会使旧场景选择失效。 | 用户总览/片区导航和新对象选择统一使旧导航失效；每次 await 后校验同一导航令牌与目标 asset。覆盖延迟资源后点击总览、切到无绑定档案、连续两对象等场景。数据集切换已有 cancelNavigation，不足以覆盖同数据集的选择竞争。 |
| R4 | P2，`backend/auth.py:34-54` | 使用与 local 模式相同的 session_secret，将服务配置为 `auth_mode='token'`。仍在有效期内的 local-operator cookie 配合允许的 Origin/Host，`POST /api/plans` 返回 201，created_by 为 local-operator。token 模式只阻止新建本地会话，未拒绝旧 cookie，与运维说明“只接受明确 bearer 写入”冲突。 | token 模式仅使用 bearer 身份，忽略/拒绝本地会话 cookie；回归 local→token 切换，以及正常 operator/admin bearer 和 readonly 拒绝写入。无需为此读取或轮换真实凭据。 |
| R5 | P2，`backend/semantics.py:60-69` 与 `:28` | 实际数据图只接受 `state='accepted'`，预览图却加入所有关系。导入一个 device，其唯一 managedBy 关系为 `state='rejected'`，preview 的 conforms 为 true、apply 返回 200；紧接 `/api/ontology/validate` 得到 conforms=false，原因是 Device 缺少有效 Organization 管理者。 | 预览与持久数据构图共用类和关系状态逻辑，对 rejected/tentative 等状态采用同一规则。回归“预览通过即应用后同范围 SHACL 通过”，同时保留修复既有无管理者设备的正向场景。 |

上述五项均已向主线程报告。复现中的凭据是临时测试字符串，并非用户配置或生产凭据。

## 次要一致性问题

- **R6 / P3：计划缺口未完整保存。** `src/twin/main.js:95` 保存 `suggested_plan` 时只传 `reply.gaps`，未合并 `suggested_plan.gaps`。`backend/assistant.py` 分别合并顶层与草稿缺口，模型可以只在草稿中提供一项缺口。应保存两者的去重并集，避免可见计划的限制丢失。这项依据代码路径确认，初次审查未单独运行浏览器写入复现。
- `main.js:89` 的统一标题仍为“结构化预警核查（数据库结果）”，而真实模型成功后，`assistant.py` 会将“处理建议”一节替换为模型草稿内容。建议按 `analysis_kind` 标明“数据库事实 + 模型核查建议”，避免把模型自由文字全部归为数据库事实。页面其他位置已有模型草稿标签，故此项为局部表述修正。

## 独立执行的验证

1. `../.tools/backend-venv/Scripts/python.exe -m pytest -q`：**49 passed**，耗时约 7.3 秒；有 1 条 Starlette/httpx 弃用警告。该结果证明现有后端测试通过，不覆盖上表新增边界。
2. `../.tools/node-v22.23.4-win-x64/node.exe --test tests/scene-contract.test.js`：**6 passed**，0 failed。覆盖动作白名单、文本转义、演示标签、冲突绑定、链接协议和表示优先级；未覆盖资源加载竞争。
3. 临时库 API 复现 R1、R2、R4、R5，各自收到上表列出的实际状态码与数据变化。临时目录在测试结束后释放。
4. Node 直接导入实际 `TwinScene` 类，使用 Three.js Group 和可控延迟验证 R3。没有将此单元场景称为已完成浏览器端回归。

没有重复运行可能向真实库保存方案的浏览器验收。主线程运行的真实模型、浏览器截图、资产覆盖和性能结果应在最终报告中另列来源，并与最终同版文件指纹核对。

## 已核对的软件边界

- 前端主体几何由 GLTFLoader 加载 Blender GLB；`scene.js` 不生成田块主体几何。灯光、相机、标签和高亮仍由浏览器承担。
- 浏览器定位动作仅为 `focus_entity`，用数据库 UUID 对应唯一空间绑定，不能执行模型任意脚本。模型输出的动作、证据 ID 和对象绑定均有后端校验。来源卡文本转义，链接限定 HTTP(S)，下载端检查登记、目录范围和 SHA。
- 真实记录导入强制 `imported_unverified`，演示强制 `synthetic`；显式拒绝把 synthetic/test 记录导入 real。新真实对象 UUID 由服务端生成，重复来源键复用持久 UUID。空间解绑/退役/恢复具有显式审查和事务路径，不能仅凭同名自动换绑。
- 用户选择数据集时清空对话、选择、绑定并取消导航，且查询/助手有版本检查。R1 与 R3 是这些已有边界之外的具体遗漏，不能据此说整个隔离方案不存在。
- 实际使用本地 SQLite、RDFlib 和 pySHACL 资源；`UPSTREAM.full_platform_connected=false`。没有以独立适配器冒称完整上游多库平台。SHACL 的当前核心范围是 Device 的 Organization 管理关系，不证明农业操作安全。
- 助手有真实 HTTP 模型调用路径、失败/未配置状态、证据受限结构、明确自由文本局限及草稿人工保存；没有设备控制 API。协议替身测试不能替代实际模型推理回执，实际模型回执也不能证明所有自由文字事实正确。

## 不应扩大为现场完成声明的边界

即使本报告缺陷全部关闭，也只能说明对应软件路径完成验证。5 份 PDF、100 条 XLS 来源与最终 Blender/数据库绑定须由资料和资产审查结果证明；E3 跨图歧义和 QING17 恢复须使用最终导入结果。图纸纸面坐标、标号锚点、概略卫星表示与实测地理模型必须分开。100 条台账不是“100 块已完成测绘和实时生产监控的田块”。

原表面积总原值 1010.99 的单位未经确认，纸页平方单位不能当作 m²。没有测绘控制点、连续实测高程、实际种养殖资料、实时传感器和设备可用性时，应继续明确未知。这些是资料和现场验收边界，不是要求软件凭空补足的数据；不得用合成演示、公共农业参考或模型语言代替。

## 关闭记录

初次报告写入时 R1–R5 待主线程修复与复验，R6 和模型/数据库标题待核对。后续复验应在此追加日期、实际命令与对应结果，保留发现记录，避免将初始缺陷静默改写成“从未存在”。

### 2026-10-29 同日修复后独立复验

复验仍仅使用源码和新建临时 SQLite 库，没有连接正在运行的旧版 API、操作真实数据库或读取私密配置。没有修改产品代码。

| 编号 | 最新状态 | 独立复验证据 |
|---|---|---|
| R1 | 已关闭 | 内部关系 ID 现包含 dataset、主体 UUID、来源系统 UUID 与外部关系标识。重跑原场景：real apply=200，既有 demo 关系内容和 ID 完整保留。新增自动测试还验证同一 real 数据集两个主体采用同一外部 ID 时产生三个不同内部 ID，来源 support 不丢失。 |
| R2 | 已关闭 | preview 和 `Store.import_records` 共用 `validate_record`，在任何实体写入前验证整批。原 `observations:null` 场景现为 preview=422、直接导入 ValueError，实体和统计 API 仍为200。新增9个参数场景涵盖错误观测元素/数值/时间/单位、设备、关系、类和上下文结构，并确认无预览/实体残留。 |
| R3 | 已关闭（源码及实际方法复验） | `showAsset` 取消旧选择，`select` 取消旧资产请求并在 await 后校验目标资产；主界面新选择取消旧导航，实体查询返回后检查导航版本，迟到助手回复不会覆盖新选择或导航。独立重跑原延迟GLB→总览场景，旧select返回false，总览/高亮/目标均保留；增加延迟A→选择全域B场景，最终仍为full/B且目标为B。已读4条真实浏览器延迟测试，完整运行结果不冒称为本代理独立执行。 |
| R4 | 已关闭 | cookie 分支仅在 local 模式使用。重跑 token 模式旧local cookie场景：保存返回401且没有写入方案。新增测试还验证operator/admin bearer正常、readonly拒绝。 |
| R5 | 已关闭 | preview与持久图使用同一 `add_entity_facts` 和类映射。重跑 rejected/tentative managedBy：preview conforms=false，apply=422；有效库最终校验conforms=true。重复同外部关系身份但相反状态的记录在预览前被拒绝。独立额外使用 `external_id`（而非 `id`）相同的 accepted/rejected 变体，结果同为422。 |
| R6 | 已关闭（源码核对） | 保存时现使用 `reply.gaps` 与 `suggested_plan.gaps` 的去重并集。模型/数据库统一标题已改为“事实来自数据库，建议标明生成方式”，不再将模型建议统称数据库结果。未为此向真实库保存测试草稿。 |

本次独立执行命令与结果：

- `../.tools/backend-venv/Scripts/python.exe -m pytest tests/test_backend.py -q`：**64 passed**，约7.98秒，仍有1条Starlette/httpx弃用警告。
- 临时库补充复验脚本实际结果：R4=401；R2=422/ValueError且目录与summary=200；R1 real apply=200且demo关系相等；R5两种非accepted状态均不符合且apply=422；external_id冲突变体=422。
- Node导入实际 `TwinScene` + Three.js Group 的可控延迟复验：总览与新对象两个竞态断言通过。
- `node --check src/twin/main.js`：退出码0。

此轮没有发现需要保持开放的上述软件缺陷。最终发布仍需把这份代码修复与重启后的API、最终GLB/manifest、最终绑定库以及浏览器收据对应起来；本结论不替代全量图纸审查、模型视觉覆盖、地理精度或现场生产验收。

### 后端修复复验（实现者，2026-10-29）

保留以上独立初次发现。后端针对 R1/R2/R4/R5 先新增回归并实际看到 14 项失败（另含知识缺口文案检查），再实施修复。随后补充并复现了同一关系外部 ID 的 accepted/rejected 冲突覆盖变体，予以拒收；未以放宽 SHACL 或输入约束换取通过。

- R1：内部关系 ID 现在由 dataset、持久主体 UUID、来源注册 UUID 和来源关系键组成 SHA-256 命名空间，来稿 ID 仅保存为 external_id；source_id/source_key/support 保留可追溯性。回归验证 real 管理导入不会删除 demo 关系，同一数据集中不同主体也不会互相覆盖。原实体 UUID 不变；既有 fixture 再导入时会将关系表更新为内部 ID，原断言 ID 保存在 external_id。
- R2：新增 backend/validation.py，preview、apply 和 Store.import_records 共用验证。观测/设备/关系/类等数组及元素类型、上下文字典、有限数值、带时区的已提供采样时间、UUID/IRI 和重复关系冲突均在分配身份之前检查。缺少采样时间仍可作为待补资料记录，显式提供非法时间则拒绝。九组畸形嵌套负例均返回 422，零预览/零实体落库，目录与汇总仍可读取。来源 hash 为 null 表示未知，未伪造 hash。
- R4：只有 local 模式读取本地会话 cookie；token 模式忽略旧 cookie，仅明确 bearer 可授权。已测试 local→token 切换拒绝旧 cookie、operator/admin bearer 正常，以及 readonly 拒绝写入。
- R5：预览和实际 RDF 图共用 add_entity_facts 与统一实体类映射，只接纳 accepted 关系。rejected/tentative managedBy 均不能让 Device 通过校验；修复缺管理者的正向导入及省略关系字段时保留原关系的更新，均验证“预览通过→应用→实际 SHACL 通过”。apply 在 SQLite 写锁内重新验证当前语义图，再提交同一批记录。
- 另将助手知识缺口改为“未检索到适用于当前对象的知识依据”，不再把未命中适用条目误报为整个库未接入。

最终完整命令：`../.tools/backend-venv/Scripts/python.exe -m pytest tests/test_backend.py -q --basetemp ../.tools/pytest-backend-review-full5`。
实际结果：**64 passed，0 failed，7.98 秒**；1 条既有 Starlette/httpx 测试客户端弃用警告。此为实现者回归结果，未冒称独立复审。R3/R6 及最终来源/空间导入由主线程另行记录。

### 最终同版导入复验（2026-10-29）

冻结manifest SHA-256为 `b6f1cbfc7e4f8e08de154a0be433432d082139780d89fd4d66c269a1ec664552`。执行清17显式同UUID恢复、db_init、db_verify_deployment后，完整后端 **68 passed，0 failed，7.97秒**；新增的4项父编号/别名解析回归由主线程实现。100个初始台账UUID不变、重复导入UUID/修订不变、284当前空间表示与manifest完全相同，E3独立候选及旧错误来源解绑均逐项验证。备份/恢复所有应用表校验和相等。具体UUID、关系/设施语义、备份路径及hash见 `backend-verification.json`。此记录不代替主线程的最终浏览器验证。
