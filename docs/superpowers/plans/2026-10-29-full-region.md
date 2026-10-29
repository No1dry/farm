# 全域完整建模与图中本体数据 Implementation Plan

> **For agentic workers:** Apply executing-plans or subagent-driven-development. This workspace has no Git metadata; preserve original inputs and track receipts here instead of claiming commits.

**Goal:** 首页展示完整卫星红线三维场景，并直接展示可追溯的本体实体/样例关系与监测。

**Architecture:** 卫星原轮廓+新增native像素补充JSON→Blender全域资产；SQLite真实资料与演示场景分开→原大屏及空间标注；统一spatial_id定位但不把样例业务写为现场事实。

**Tech Stack:** Blender4.5/Python、Three.js/Vite、FastAPI/SQLite。

**Spec:** `docs/superpowers/specs/2026-10-29-full-region-design.md`。

## Constraints / Review focus

- 原CSS/六面板布局不变；首屏必须全域，而不是隐藏目录中的选项。
- 缺失允许样例填充，显式标明并可替换；真实UUID/来源不得覆盖。
- 不能用截图材质代替主体；村庄/树林/道路/岸线在近远景都需要可辨形态。
- 切换真实/演示、实体、片区时不可出现旧异步响应/旧关系覆盖。
- 数据在图中可见；设备和预警支持查询来源、时间与关系，不能只做静态图标。

## Task 1: 全域卫星补充（source_audit）

- [x] 逐区查看卫星原图和当前轮廓，记录漏项。
- [x] 写`data/spatial/full-region-enrichment.json`：native像素几何、kind、parent_spatial_id、source_hash、confidence、sample标记；和建模作者同步契约。
- [x] 校验边界/避让/非空村落覆盖，区别真实判读与样例填充。

## Task 2: 全域Blender重建（blender_assets）

- [x] 改造`scripts/blender*.py`并新增参数JSON，消费Task1数据，细化全部村落、树林、农田和路塘岸线。
- [x] 导出full近/远GLB及包含全域场景的Blend，设manifest默认full；保留原121身份和5详图。
- [x] 重新打开Blend，检查打包依赖、稳定身份、无截图主体；全域/村落/田塘近景目检。

## Task 3: 图中本体联动（ontology_audit）

- [x] 为完整演示场景建立持久化实体/关系/来源/观测/预警，独立样例dataset与id，允许显式演示位置引用。
- [x] 原大屏内容改全域统计/列表/档案；新增受控空间标注与关系视图，默认全域场景且样例可见。
- [x] 回归真实样例隔离、点击实体/设备/预警、导航取消、助手查询与保存。

## Task 4: 集成与验收（root）

- [x] 查成熟案例并记录借鉴点，核对实际全域视觉和九聚落覆盖，不用数量代替目检。
- [x] 最终构建运行；测首屏full、本体空间标注可见、数据API驱动、真实/演示切换、搜索助手预警。
- [x] 更新使用/替换数据/模型/验收文档和实际证据；备份数据库及制品指纹。

## Progress

2026-10-29：用户授权缺失信息先使用样例，三条职责并行；没有Git工作树。源数据原图SHA256 `99217e959c5e448d376ff448c4ce00c6abd4065a1243ccbb0af9e2403b22189a`。现有全域38田、37水域、9林、9聚落、3裸地，主要视觉不足为聚落/树林/田面表达稀疏和首屏错误。

2026-10-29 最终交付检查：7 GLB 与 Blend 冻结、100 台账身份保持、49 演示设备联动；33 JavaScript/适配、81 后端、23 生产浏览器测试通过，16 实际视图及九村独立目检完成。模型/来源事实限制见 docs/acceptance.md，软件通过不等于用户视觉验收。
