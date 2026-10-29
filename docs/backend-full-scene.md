# 全域本体场景与可替换样例

2026-10-29。用户已授权缺少的业务信息先采用样例，本次新增数据严格置于 `demo` 数据集。卫星轮廓是空间引用，不证明这些作物、鱼种、设备或观测真实存在。

## 可见行为与身份

原 `src/focus/style.css` 和六面板布局保留，默认打开 `full` 资产及“演示业务 · 卫星轮廓”。左上统计由 `/api/summary` 返回，列表保持四项以适应原面板；完整检索仍在原资料窗口。档案直接显示 UUID、本体分类、来源、数据性质和面积口径。图中实体、设备及样例条件标记可以点击，右侧直接展示数据库关系；有已登记空间锚点的关系绘制连线。

全域样例包含 121 个独立主对象（38 田、36 塘、1 湖、20 路、5 沟、9 村、9 林、3 待用地）、49 个独立设备实体和 1 个管理组。初始配置有 265 条观测快照、20 条合成规则。原上游及独立历史情景继续保留。建筑、树木、草叶等外观子网格不能据其数量推定真实资产数。

样例 UUID 由 `farm:scenario:<scenario_id>:<spatial_id或设备key>` 生成并持久化。设备没有父地块的业务 UUID，也不写父对象的空间身份绑定；其 `scene_anchor` 只表达演示位置。`scenario_properties.device_key` 与 Blender 节点 `extras.scene_device_key` 一致，点击器材模型或设备图标均查设备本身。切到“资料”会移除样例标记、关系和器材模型。

真实台账和空间对象仍使用原 UUID。示例位置引用允许同一 `spatial_id` 在 real/demo 各有独立绑定，任何跨数据集读取均须显式指定 dataset。演示模式下搜索不到真实 L18 时，助手提供明确“到真实资料查找”按钮；用户切换并选择真实候选后才定位。

## 修改样例数据

- `data/demo/full-area-scenario.json`：固定时间、分类默认值、鱼种/作物、观测、规则与用途。`overrides` 按空间 ID 覆盖，`device_overrides` 按设备 key 覆盖。模型面积独立保存在 `scenario_properties.model_area_m2`，显示“模型估算面积（演示）”，不伪造台账面积。
- `data/demo/full-area-device-layout.json`：设备 key、类型及位置。坐标为 Three Y-up，位置严格为最终 manifest 中父对象 `center + offset`。设备模型与图标读取同一参数，标签另行抬高便于阅读。改位置后需要重新生成 Blender 器材子网格并刷新数据库。
- 所有观测均为固定快照，不滚动伪装实时。超过 `stale_after_hours` 会标为过期。合成阈值不代表农业生产标准，导入器强制 `production_approved=false`，不生成当前可执行设备动作。

仅刷新样例（会先生成 SQLite 备份并核对真实实体 payload/revision 指纹）：

```powershell
& ../.tools/backend-venv/Scripts/python.exe scripts/db_refresh_scenario.py --receipt deliverables/verification/full-scene-import.json
```

完整来源/模型更新继续使用 `scripts/db_init.py`；只有已审查且已冻结的 manifest 才执行全量导入。不要删除数据库来更新数据。

同一配置重复导入保持 UUID 和内容版本稳定。删除本场景设备条目会在本场景事务内将旧实体退役并移除其当前关系，其他真实/上游演示实体保持原样；重新加入相同 key 恢复相同 UUID。改 key 是新身份。重复 key、未知父对象、非法位置、非法配置结构会在写入前被拒绝；场景记录、关系、空间绑定、退役和审计在一个事务内更新。

## 接口和安全边界

复用 `/api/entities`、`/api/entities/{uuid}`、`/api/relations/{uuid}?depth=1` 与 `/api/assistant`。实体增加 `scenario`、`scenario_properties`、`scene_anchor`；summary 增加 `scene` 子统计。既有模型 JSON/证据/动作校验、用户明确保存草稿、只读设备能力保持原约束。关系接口失败会显示暂不可用，不假称没有关系。

图标与3D器材只在实体数据集、样例来源、场景 ID、父空间 ID、设备 key 均匹配时关联。重复设备 key 候选拒绝取首条。选择、切区、切数据集会取消旧导航，迟到的实体/关系/助手响应不能覆盖新上下文。原资料表面积缺少单位的事实保持“原表单位未注”。

## 本轮验证记录

代码冻结前完整 Python 测试 79 项通过；Node/Chrome 组合回归 31 项通过，包括受控器材身份解析、数据隔离、迟到认证/导航/关系、全屏弹窗和原 CSS 字节校验。新增设备解析、配置验证及关系失败状态均先观察到失败再修复。既有 Starlette/httpx 弃用警告仍在，不影响当前运行。

`deliverables/verification/full-scene-import.json` 记录当前配置/位置哈希、导入数量、真实数据不变校验和备份位置。该回执与旧版 `backend-verification.json` 具有不同时间范围。最终模型视觉、器材落地位置及真实大模型七段回答由集成验收另行留证，不能以单元测试代替现场事实或最终视觉验收。

## V06 最终空间同步回执

已导入最终冻结 V06 manifest `2fc32f4cba5ef33e68eefa16e3d9ec41f8374f29ecfbdbd8f2ce68227d39c673`，材质导出修订为 `v06-canonical-rgba-multiply`。最终数据库有 284 条活动真实资料实体、189 条活动演示实体、284 个真实空间表示、9 条退役身份；100/100 台账均有当前图纸表示。全域演示仍为 121 主对象、49 独立设备和 1 管理组，另保留 18 条历史演示实体。

100 个台账 UUID 与最初备份相同，台账完整来源 payload、全部真实业务字段以及其他演示 fixture 未被覆盖。7 个 GLB 的文件 SHA 与 manifest 相符，其实际节点空间 ID 集合与各片区清单精确相等；49 个父中心、偏移及数据库锚点与最终落地表一致。材质修正前后 284 条空间对象元数据逐项相同。重复导入不改变 UUID 或内容版本；SQLite integrity、真实/演示 SHACL 均通过，备份恢复后 12 张应用表校验和一致。

最终设备落地报告重新生成时，仅理由文字因偏移已应用而变化；冻结 layout 未更改，49 条数值全部等价。新旧报告哈希及该差异已写入 [V06 数据库回执](../../deliverables/verification/v06-database-import.json)。该回执取代前一轮全域样例导入回执的空间版本口径。

验证后备份：`runtime/backups/farm-v06-verified-20261029T053021Z.sqlite3`，SHA-256 `70c7b71a95dd248f74be5c975cc4d680af3bf7223e4bb111e0c5361dfa8c75ab`。恢复副本与导入前备份路径也在回执中；后续浏览器显式保存的草稿按其时间另行备份。材质修正前的回执归档为 `deliverables/verification/v06-database-import-before-material-fix.json`。
