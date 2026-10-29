# 智慧农业数字孪生 · V0.6 全域模型与本体联动

**发布版本：[v0.6.0](https://github.com/No1dry/farm/releases/tag/v0.6.0)**。Release 提供完整工程包、网页模型包、可编辑 Blender 包及 SHA-256 清单。GitHub 自动生成的 Source code ZIP 只含 Git 源码；克隆源码后先运行 `python scripts/fetch_release_assets.py --all` 恢复大资产。完整工程包已含资产，同一命令只做校验。

本版以完整卫星红线三维场景为首页，保留 `src/focus/` 原大屏的顶栏、双侧六块悬浮面板、照片、工具栏和底部四视角，原 `style.css` 未修改。图中的地块、设备和预警标记连接持久化本体数据；原面板显示 UUID、观测、来源及关系，农业助手为独立浮动入口。`src/twin/` 旧界面不作为首页入口。

主体在 Blender 中重新构建：红线内 9 处村落、农田、湖塘、林地、道路和灌排环境，以及独立的五个图纸片区。补充资料含 192 个屋顶候选与 57 个样例建筑实例；房屋有立体墙体、门窗及屋顶，树木采用枝干与叶片，田面、土埂、塘底、岸坡和沟槽具有体积。卫星图和整页 CAD 不进入网页主体材质。深度、高程、植被、建筑细节及缺失的业务信息依用户授权采用可替换样例，不能作为测绘或现场生产事实。

V0.4 的截图式模型与界面改动、V0.5 的全域细节不足均被用户否定，历史软件测试不能作为本版效果验收。当前实际检查见 [交付检查](docs/acceptance.md)，历史问题记录见 [V0.4](docs/acceptance-v04-rejected.md)、[V0.5](docs/acceptance-v05-rejected.md)。

## 本机运行

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1
```

打开 **http://127.0.0.1:5173**。`-Production` 使用构建后的 `dist`，`-WithoutModel` 跳过本地模型启动。脚本优先使用项目 `.venv`，其次使用父目录已准备的 `.tools` 便携运行时；退出只停止该脚本创建的应用进程。

默认展示全域与明确标记的演示业务。点击图中实体或器材可打开数据库档案；点击场景左上标签打开全域、五片区与资料目录。原底部四按钮查看当前区域总览、农田、沟渠与塘岸。档案面板可切换真实资料/样例，查看完整来源和关系。操作及后续替换说明见 [大屏使用说明](docs/user-guide.md)。

## 交付文件

- 可独立编辑的源文件：`deliverables/blender/farm-full.blend`，依赖材质打包；来源图片仅在隐藏参考集合中。
- 网页 GLB、LOD 和身份清单：`public/models/manifest.json`。
- 来源清单、台账、面积核对与身份映射：`data/audit/`。
- 100 个田块原 PDF 轮廓、塘面、路渠和设施证据：`data/spatial/`。
- 全域补充轮廓：`data/spatial/full-region-enrichment.json`；表现参数：`data/model/`；可替换业务及设备位置：`data/demo/full-area-*.json`。
- 原大屏及适配：`src/focus/`；持久数据和助手：`backend/`。
- 本地验证、相机视图、性能和文件指纹：`deliverables/verification/`。

五份图纸仍采用独立纸面坐标，缺少控制点、统一 CRS 和高程，**未宣称已完成测绘配准或无缝工程拼接**。全域卫星判读对象不能按同名自动绑定台账对象。详见 [模型约定](docs/model-methodology.md) 和 [资料缺口](docs/data-gaps.md)。

## 数据、本体和农业助手

SQLite 服务实际持久化实体、关系、来源、观测、预警、方案和审计；前端经 `/api` 查询。100 条台账保留原始 UUID，XLS 合计原值 1010.99，但原表未注明单位，不擅自填写亩。真实资料、合成演示与缺失字段分开处理，无随机实时数值。

首次安装使用经校验的公开初始化种子，保留本版 100 条台账及其他当前实体的 UUID；已有数据库不会被种子覆盖。种子只含来源业务档案和隔离样例，不含本机对话、操作审计、保存方案或密钥。范围、来源与恢复方式见 [公开种子说明](docs/release-data-seed.md)。

全域演示场景独立建立 121 个主对象、49 个设备和 1 个管理组，带 265 条固定观测及 20 条合成规则。设备三维模型、图标和数据库通过同一个 key 关联；切回资料模式会隐藏演示器材。样例可按空间 ID / 设备 key 覆盖，详见 [全域样例契约](docs/backend-full-scene.md)。

采用上游 `lianggeming14/liangzihu-ontology-traceability` 中 `ontology-platform` 的适用身份、来源契约、本体和 SHACL 资源，锁定提交 `5776ba8d656139d3fb8dfabd137d83dd6dbba11c`。未引入上游前端，也未声称启动完整多库平台。边界见 [本体审查](docs/audit/ontology-audit.md)。

农业助手采用数据库与关系查询、知识检索、真实模型回答、结构/来源/动作校验。当前本机配置 Qwen3-4B GGUF 与 llama.cpp Vulkan，也支持服务端配置其他兼容接口。模型不可用时明确显示状态，不返回固定话术冒充模型。模型只能提出经 UUID 校验的场景定位；方案须点击保存，系统没有现场设备控制接口。

服务配置见 `.env.example`。密钥仅在服务端环境或忽略提交的本机配置中，不能写入前端。API 文档：`http://127.0.0.1:8000/docs`。本地模型服务仅绑定 `127.0.0.1:8081`。

## 在其他机器安装

依赖：Python 3.12、Node.js 22、WebGL 2 浏览器；编辑资产需要 Blender 4.5 LTS。模型推理的硬件与固定下载版本见运维文档。

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
npm ci
python scripts/fetch_release_assets.py --all
.venv/Scripts/python.exe scripts/db_init.py
# 可选的本地模型，或者配置其他兼容服务
.venv/Scripts/python.exe scripts/setup_local_model.py
.venv/Scripts/python.exe scripts/configure_local_model.py
npm run build
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1 -Production
```

## 更新与验证

浏览器回归需要保持服务运行：构建后在另一终端执行 `scripts/start.ps1 -Production`，确认5173页面及后端可访问。测试终端显式指定同一地址，避免使用开发环境的5174默认值。

```powershell
# Blender 内运行的依赖见 scripts/blender-requirements.txt
blender --background --python scripts/blender_build.py
blender --background deliverables/blender/farm-full.blend --python scripts/blender_scene_verify.py
python scripts/verify_model_correction.py
python scripts/blender_verify.py
python scripts/blender_drawing_verify.py
python scripts/blender_full_region_verify.py
python scripts/blender_material_verify.py
.venv/Scripts/python.exe scripts/db_init.py
npm run build
$env:FARM_TEST_BASE_URL='http://127.0.0.1:5173'
npm test
npm run test:e2e
.venv/Scripts/python.exe -m pytest -q
# 保持生产服务运行，采集全域及全部九处村落的实际浏览器视图与性能
node scripts/browser-full-region-review.mjs
.venv/Scripts/python.exe scripts/verify_backup_restore.py
```

重建不应更换业务 UUID 或删除数据库。导入有校验、事务、重复导入和身份审查；更新前先备份。启动、部署、权限、备份恢复和数据更新详见 [运维说明](docs/backend-operations.md)。

Release 大资产通过固定文件清单、压缩包和逐文件 SHA-256 校验恢复，默认拒绝覆盖用户改过的模型；离线下载与备份替换见 [资产恢复说明](docs/release-assets.md)。本地开发工具、模型推理权重、依赖目录和运行时数据不在公开工程包中，由锁定依赖及下载脚本安装。第三方来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

低角度材质图与灰模用于人工复核，`verify_model_correction.py` 仅检查导出物没有来源截图且具有体积，不能替代外观验收。公开知识不是现场鱼种、设备状态或天气依据；真实遥测、现场高程和生产阈值未提供时保持未知。
