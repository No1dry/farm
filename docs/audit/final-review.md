# V0.6 全域模型与本体联动复核索引

本轮按用户要求补齐红线内三维内容，并将本体实体、设备、观测和预警直接显示在原大屏中。缺失信息先使用明确标记的可替换样例。原 `src/focus/style.css` 字节未变。V0.4/V0.5 被否定的模型与历史测试不是本轮通过依据。

- 来源与视觉独立复核：[full-region-enrichment-review.md](full-region-enrichment-review.md)。逐一检查九处村落，区分源判读轮廓、样例外观和未测参数。
- 资料、原始单位、五图坐标与本体整合边界：[ontology-audit.md](ontology-audit.md)、[../data-gaps.md](../data-gaps.md)。
- 当前模型：`deliverables/blender/build-report.json`、`verification.json`、`full-region-export-verification.json`、`material-export-verification.json`。Blend 重开、材质因子、活动 Scene 精确身份范围及设备位置均有独立检查。
- 实际浏览器：`deliverables/verification/full-region/review.json`，16 个视图包含全域首屏、九村、湖塘田渠、回总览和真实资料切换。静态截图是检查证据；产品实际加载 GLB 并查询后端。
- 数据导入：`deliverables/verification/v06-database-import.json`。100 个台账 UUID 和原始记录、全部真实业务值保留；49 设备位置吻合；重复导入、SHACL、备份恢复校验通过。
- 回归、最终性能、备份与制品指纹见 [../acceptance.md](../acceptance.md) 及其中原始报告。

## 代码复核关闭项

独立复核已关闭跨场景/退役设备误关联、入向关系颠倒、助手当前水塘被旧泛名实体抢占的问题。当前指代、明确编号、未知编号、两字别名、多编号和同码消歧均有定向检验。

生产浏览器目检发现的白地、黑水没有以 Blender 内预览通过掩盖：旧 MixRGB 乘色节点改为 glTF 可识别的 RGBA Multiply；多个水网格反复调暗共享材质的操作移除。后者先观察到回归失败，再修复并独立验证共享材质、LOD与选中 Shader 三项通过。材质导出逐项与 Blender 快照核对，没有前端补色。

保存的多 Scene 文件重新导出时曾出现额外片区混入，已限定活动 Scene。独立解析最终 7 个 GLB，full/LOD 各 121 个身份，五份详图分别 38/49/16/9/51，集合严格等于对应清单、每文件一个 Scene，无 extra/missing；所有文件哈希与清单一致。

设备点击测试先确认像素下是实际 canvas，再要求可信 pointerup 和从父塘 UUID 切到设备 UUID，排除了 DOM 图标代替几何点选。五图覆盖测试对实际 hover 射线确认可见田面，避免把田中心穿过的道路误当作田面；保留 100 身份、五片区、原多边形与准确 UUID 断言。窄屏测试通过真实抽屉按钮切换数据集，不直接点击隐藏控件。

备份验证比较恢复后的全部应用表，目标必须为新路径；来源哈希与内容校验用显式异常，普通/优化模式均不会因 assert 被禁用而写出假成功。当前检查不等于用户视觉验收、现场测绘确认或真实生产设备验收。
