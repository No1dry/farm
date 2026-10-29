# 原大屏恢复独立代码审查

审查日期：2026-10-29。审查范围为 `src/focus/main.js`、`twin-adapter.js`、`assistant.js`、`assistant.css`、`index.html` 及对应 focus/browser 测试。未修改实现、数据库、密钥或模型。实测入口为 `http://127.0.0.1:5174`；以下行号指发现时版本。

最终状态：发现的 2 项 P1 与 2 项 P2 均已由实现代理修复，并通过独立浏览器复验。此审查范围内没有剩余的已复现阻塞问题。

## 已复现问题

### P1：启动阶段的迟到认证响应会覆盖用户选择

- 位置：`src/focus/assistant.js:77`，`initialize()`。
- 原因：等待 `loadData()` 和 `/auth/local-session` 后，不检查初始化期间是否发生用户操作，直接选择默认 `L19`。
- 复现：Playwright 暂缓 `/api/auth/local-session` 返回；等待页面及实体列表可用；点击原面板 `L18`；释放认证响应。
- 实测：释放前 `selected=L18, selectionVersion=3`；释放后 `selected=L19, selectionVersion=4`，助手上下文同步改为 L19。
- 影响：用户已明确选择的对象被迟到 API 抢回。现有竞态测试均从初始化完成以后开始，未覆盖此窗口。
- 修正要求：默认选择仅在初始化期间没有发生选择、导航或数据集改变时应用。
- 状态：ontology_audit 已修复。独立使用原复现脚本复验通过：释放真实认证响应后仍为 L18；正常首次加载的默认 L19 也保持可用。

### P1：未绑定空间对象的点击不取消旧 GLB 导航

- 位置：`src/focus/assistant.js:33`，`selectSpatial()` 的 `!identifier` 分支。
- 原因：`navigate:false` 时仅增加 `selectionVersion`，未取消 adapter 导航版本及正在进行的飞行。
- 复现：切换 demo（实测 18 条记录且空间 bindings 为 0）；暂缓 `full-area-lod.glb`；从目录选择全域；模型加载中点击原面板 `L18`；释放 GLB。
- 实测：点击后 `activeAsset=detail-miaoxia, selectedID=DETAIL-L18, navigationVersion=8`；释放后变为 `activeAsset=full, selectedID=null`，版本仍为 8，而档案面板仍显示 L18。
- 影响：旧资源加载覆盖较新的空间选择，并造成模型片区与档案不一致。
- 修正要求：无业务绑定的空间选择也应取消旧导航/飞行，即使本次不要求移动镜头。
- 状态：ontology_audit 已修复。独立使用原复现脚本复验通过：释放旧 GLB 后仍为 `detail-miaoxia / DETAIL-L18`，业务实体保持 null，不串入真实数据。

### P2：其他片区的近景按钮会跳回庙下刘

- 位置：`src/focus/main.js:48–49` 与 `src/focus/twin-adapter.js:81–84` 的 `view()`。
- 原因：进入新片区会清空选择；此后 `field` 硬选 L19、`pond` 硬选 P17，adapter 再按该对象的 `asset_id` 决定片区。新片区已具备的 field/pond 镜头无法通过此路径使用。
- 复现：从目录选择 `detail-abcdef`，确认片区已加载且没有对象选择；点击底部“农田近景”。
- 实测：`activeAsset=detail-abcdef, selected=null` 变成 `activeAsset=detail-miaoxia, selected=L19, current tab=field`。全域同样受影响；水塘按钮有同一硬编码分支。
- 影响：用户在刚切换的片区使用近景控制，实际被送回原重点片区。
- 修正要求：保持按钮和布局；非默认片区没有当前对象时使用当前片区镜头，默认重点片区保留原快捷行为。
- 状态：ontology_audit 已修复。独立在 `detail-abcdef` 和 `full` 分别执行 field/pond/channel/overview 共 8 次，片区保持不变且业务选择保持 null；随后原 L19 快捷按钮仍可正确返回 `detail-miaoxia`。

### P2：全屏模式下目录和来源弹窗处于全屏元素之外

- 位置：`src/focus/main.js:60`、`:62`，`requestFullscreen()` 与 `modal()`。
- 原因：全屏元素为 `#twin`，但弹窗追加到 `document.body`，并非全屏元素的后代。
- 复现：点击全屏按钮，再点击片区标签打开目录。
- 实测：`document.fullscreenElement.id === 'twin'`；`#search` 已创建但 `fullscreenElement.contains(search) === false`；其中心点的 `document.elementFromPoint()` 命中 Three.js canvas，而非目录。
- 影响：新目录、照片及来源弹窗在全屏展示时不可见/无法正常鼠标交互；退出全屏才显示。这是继承的容器行为，但新目录依赖此弹窗。
- 修正要求：在全屏元素内挂载弹窗；普通模式仍可使用原 body 容器，无需改变布局样式。
- 状态：ontology_audit 已修复。独立复验全屏目录位于全屏元素内，输入框中心命中 `#search`，实际点击和输入可筛出 L18；原照片弹窗也位于全屏元素内。

## 已完成的独立验证

- `src/focus/style.css` SHA-256 与原基线完全一致：`874531436ffa156b232ca89766c1acfdd1f715ef22b4b2eba473cb5702a7c1cd`。
- 在 1600×1000 实测基线的 7 个布局选择器：位置、宽高和 display 均无超过 1px 的差异。
- 修复后再次运行 `node --test tests/focus-adapter.test.js`：9/9 通过，包含新增的片区镜头和未核验锚点显示回归。
- 主体模型通过 `GLTFLoader` 加载，未发现 JS 恢复生成主要地块/道路/沟渠几何；水面反射复用 Blender 水面几何。
- 查阅真实/demo 切换清理、来源卡片、未配置/不可用模型提示、受约束 focus action 和保存方案调用路径；除上列竞态外，未发现额外可复现的重大问题。保存接口仅由显式“保存此方案记录”按钮触发。
- 本审查不对模型美术效果、Blender 可编辑性或全域几何质量作验收结论。
