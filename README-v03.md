# 梁湖情智慧农业数字孪生

当前为 **V0.3 可运行阶段交付**：Blender 全规划区概略资产、独立图纸局部、持久数据库、来源档案、大屏联动和可配置农业助手。**不是全项目最终验收通过版本。** 实际验证及未完成项见 `docs/acceptance.md`。

## 启动

依赖：Python 3.12、Node.js 22 LTS、支持 WebGL 2 的浏览器。Blender 4.5 LTS 仅用于编辑或重建资产。

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
npm ci
.venv/Scripts/python.exe scripts/db_init.py
.venv/Scripts/python.exe -m backend
```

另一个终端运行 `npm run dev -- --port 5173`，打开 http://127.0.0.1:5173 。API 位于 http://127.0.0.1:8000 ，Vite 转发 `/api`；API文档见 `/docs`。

本机已准备的便携运行时在父目录 `.tools`。可执行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1` 同时启动两项服务，脚本优先项目 `.venv`，其次便携环境，不自动安装系统软件。

首次初始化在启动前执行。后端启动不隐式导入。`runtime/farm.sqlite3` 为活动数据库，不提交到仓库。重复初始化按来源键更新、保留UUID和版本；迁移已有实例必须携带数据库，不能靠新建库重现随机UUID。

## 功能与资产

- 12个原始文件的指纹与覆盖审查、100条Excel田块台账。原始数值合计1010.99，单位未注。
- Blender全红线概略场景与独立坐标的庙下刘图纸局部，主体模型通过GLB加载。
- 来源、身份、空间映射、设备/关系/观测、演示历史缺氧规则及知识、方案和审计持久化。
- 资料与合成样例隔离。搜索/点击档案；L18/L19/L20按图纸证据关联局部模型；未配准对象不跳到同名卫星轮廓。
- 助手多轮上下文、歧义候选、受控定位、证据卡和显式保存。无模型时只返回明确标记的数据库结果、资料核查清单。

编辑源：`deliverables/blender/farm-full.blend`（打包纹理）。网页资产：`public/models/full-area.glb`、`detail-miaoxia.glb`、`manifest.json`。全域/局部分片按需加载，每个交互对象带spatial_id，由数据库映射UUID。未用旧JS样板导出冒充新模型。

```powershell
blender --background --python scripts/blender_build.py
blender --background deliverables/blender/farm-full.blend --python scripts/blender_scene_verify.py
python scripts/blender_verify.py
python scripts/db_init.py
```

建模约定、表现参数见 `docs/model-methodology.md`。图纸局部未与全域配准，选择地块会切到独立局部视图。概略地物不等同确权地块，台账数量、空间数量、数据库记录数分列。

## 本体整合

采用上游 `lianggeming14/liangzihu-ontology-traceability` 提交 `5776ba8d656139d3fb8dfabd137d83dd6dbba11c` 的 **ontology-platform** 身份/来源/IRI/数据性质契约与合成语义样例，使用本地SQLite适配实现。**未部署上游完整PostgreSQL/语义服务栈，不声称完整平台兼容**。未引入其前端、路由、组件、样式；历史implementation不混入运行系统。见 `docs/audit/ontology-audit.md`。

## 大模型配置

`.env.example` 是模板，默认不自动加载文件。服务启动前设置环境变量：

```powershell
$env:FARM_MODEL_BASE_URL = 'https://your-provider.example/v1'
$env:FARM_MODEL_NAME = 'your-model'
# FARM_MODEL_API_KEY 由服务器密钥管理或本机环境配置，勿提交或写入前端。
python -m backend
```

接口兼容 `/chat/completions` JSON响应，更换配置后重启后端。未配置、服务错误和结构校验失败显示明确状态。事实卡来自数据库；自由文本有引用、结构和保守内容检查，语义仍需人工复核。没有设备控制、任意SQL或代码执行工具。

## 验证与维护

```powershell
python -m pytest -q
npm test
npm run build
# 两个服务已启动，Chrome已安装
npm run test:e2e
```

实际浏览器测试、截图和性能记录在 `deliverables/verification/`。模拟模型服务只证明协议与校验流程，不算真实农业大模型验收。

资料审查见 `docs/audit/source-audit.md`；台账和出处在 `data/audit/`。更新资料须重跑提取、人工核对冲突，再执行 `scripts/db_init.py`。不能改UUID凑模型编号或自动合并同名实体。

备份恢复、版本与部署说明见 `docs/backend-operations.md`。生产静态前端为 `npm run build` 生成的dist，HTTP服务需将/api反向代理到后端，单独dist不具备数据库/助手。当前面向本地单用户；公网部署的认证、权限、TLS和运维仍待配置。

历史说明保留在 `README-focus-v02.md` 和 `README-v01.md`。`/overview-v01.html` 为历史原型，不纳入新模型验收。
