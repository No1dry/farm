# 原 V0.2 大屏恢复与数据适配

日期：2026-10-29。此记录只验收界面恢复和适配代码；Blender 资产的几何、来源及最终视觉验收另见模型审查记录。

## 原版保留范围

入口 `index.html` 已恢复为 `src/focus/main.js`。原顶栏、左右六个半透明卡片、底栏四镜头、照片轮播与放大、资料弹窗和窄屏抽屉保留；主侧栏仍只有 L18、L19、L20、清-17 四个原始快捷项。

`src/focus/style.css` 没有改动，其 SHA-256 为 `874531436ffa156b232ca89766c1acfdd1f715ef22b4b2eba473cb5702a7c1cd`。原 `data.js`、`model.js` 亦保留；旧 `model.js` 不再用于生成主体。新增 CSS 仅作用于 `.focus-assistant*` 内的助手。

原文件副本及真实 Chrome 截图位于 `deliverables/verification/focus-restore/original-source/`、`original-desktop.png`、`original-mobile.png`。1600 × 1000 下实测顶栏、标题、左右栏、底栏、照片卡片、工具栏七处矩形坐标和尺寸与原版差异均为 0 像素。390 × 844 对照截图为 `restored-mobile-390.png`；760 像素抽屉截图属于另一个测试视口。

## 数据和模型替换范围

`twin-adapter.js` 只加载 manifest 声明的 Blender GLB，并保留原页面的 HDR、天空、雾、灯光和 OrbitControls。选取依赖 GLB `spatial_id` 与 API 的显式 UUID 映射；重名、不唯一关联或当前数据集没有对应关系时不制造绑定。隐藏的参考图网格不能被点击，也不参与回退镜头边界。

全域近远 LOD 使用同一空间身份，切换保留选中对象并不移动镜头。镜头优先使用模型资产的 `camera_views`；初始镜头使用默认片区的 `focus`，用户点击“片区总览”使用整片 `overview`。水面反射复用既有 GLB 水面几何和变换，每个详细资产至多一块反射面，不在浏览器重建田块、道路、沟渠或岸坡。

原监测四项保持未接入空态。地块卡片读取数据库台账，原表未注明面积单位时明确显示“原表单位未注”；演示对象明确标记“演示数据”。工程量仍以原界面的图纸档案形式展示，未改称实时监测或测绘结果。

完整对象搜索、真实/演示切换和全域/五片区选择放入原资料弹窗；`.scene-tag` 是同样样式的入口。新增最小助手按钮打开独立浮层；结构化证据、七部分分析、缺失项、候选澄清、用户显式保存方案沿用后端契约。方案合并回复及方案自身的判断边界，历史草稿明确不是执行记录。

## 接口与可复现验证

`window.farmTwin` 提供 `state`、`scene`、`selectEntity`、`selectSpatial`、`openCatalog`、`openAssistant` 和 `metrics()`。`scene` 是适配器，包含 `activeAsset`、`activeRoot()`、`objects`、`camera`、`controls`、`flight`、`pending`、`lod` 与 `assetSpan`。

`metrics()` 记录最近最多 300 个实际动画帧的 `samples`、`medianFrameMs`、`p95FrameMs`，以及 `assetLoadMs`、`loadMs`、视口、像素比、GPU、逻辑处理器数、绘制次数和三角形数。它是当前浏览器运行测量，不是硬编码性能承诺。

用户入口选择器：`.scene-tag`、`#search`、`[data-entity]`、`[data-dataset]`、`[data-asset]`、`#assistant-toggle`、`#chat-input`、`#send`、`[data-candidate]`、`[data-save-plan]`。原 `[data-unit]`、`[data-view]`、照片和抽屉选择器保留。

适配回归包含 `tests/focus-adapter.test.js` 10 项与 `tests/focus-assistant-races.test.js` 8 项；新增缺陷测试先观察失败再修复。覆盖迟到资产加载、导航取消、LOD 身份保持、隐藏网格、反射材质、数据集切换发送按钮、助手实体查询期间手动镜头、片区上下文清空、固定快捷项回到原资产、认证迟到不覆盖用户选择、未绑定对象取消旧导航、数据库标题文字化及全屏可操作弹窗。复跑主线程的原布局/照片/窄屏 2 项和隔离 4 项通过。主线程随后负责统一生产构建和整套浏览器验收。

切换数据集时会同步清除旧候选行、旧对象和聊天上下文；旧异步响应不得恢复它们。相机拖动、缩放、原镜头按钮和片区切换均能取消迟到定位。API 不可用、模型加载失败或空间未绑定时显示明确空态，不生成替代现场事实。

独立审查另外复验了两项初始化/导航竞态和两项片区镜头/全屏弹窗问题，均确认关闭。非默认片区无选中对象时，四镜头使用该资产的预设，不自动跳回 L19 或清-17。未核验设施及文字点位标注默认隐藏，可通过原图层入口或显式选择显示；已核验设施不按此规则隐藏。相机近裁剪面随观察距离在 0.1 至 20 之间调整，减少全域远景深度冲突，不改变模型实体。
