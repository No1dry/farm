# 全部竣工图的独立图纸空间提取

2026-10-29。本轮以用户提供的全部 5 份单页 PDF、原始 XLS 的 100 条业务台账为依据。主产物为 `data/spatial/drawing-entities.json`；不向后端预分配业务 UUID，不改变 XLS 原面积。

## 覆盖与证据

100 条台账均有对应原图中的编号位置及闭合田块边界。100 个田块面直接保留 PDF 内容流中的闭合矢量路径，证据含源文件 SHA-256、页码、图内编号窗口、矢量操作序号、描边颜色、边界包围盒。所有五图已做原图叠加轮廓的目视复核。

| 独立图纸空间 | 台账田块面 | 额外歧义标注 | 塘面 | 道路/沟渠线 | 功能设施标注点 |
|---|---:|---:|---:|---:|---:|
| 庙下流（台账称庙下刘） | 25 | 0 | 3 | 3 | 7 |
| 新屋湾、毛家湾及 D2/D3 | 26 | 1 | 10 | 4 | 8 |
| 张家湾 | 8 | 0 | 0 | 5 | 3 |
| 谭湾沈湾 | 5 | 0 | 0 | 3 | 1 |
| A/B/C/D/E/F 区 | 36 | 0 | 7 | 7 | 1 |
| 合计 | 100 | 1 | 20 | 22 | 20 |

共 163 个有来源的表示：120 个面、22 条线、21 个点。20 个功能设施点包括 14 处太阳能智能闸标注、2 处泵标注、3 处 PE 管标注及 1 处污水池标注；它们是图纸文字锚点，**不是已测设施占地或已核实的独立在役资产**。点明确使用 `geometry_role=source_label_anchor`、`boundary_status=boundary_unknown`，不生成推测的房屋轮廓。

`data/spatial/native-annotations.json` 保留 714 条可由 PDF 字体解码的原生文字及其矩阵。`facility-evidence.json` 从图纸实际绘图区保留 268 条设施相关文字证据，另记录排除的图例、表格或未定位文字。268 是标注数，不能用于工程设施数量求和。大量 CAD 轮廓字仍以完整高清原图保留；这份文字台账不声称对全部轮廓文字完成了语义 OCR。

## 重复编号与身份

- D2、D3 的有界田块位于新屋湾/毛家湾 PDF，不能因为另一张文件名含 D 区而另造一份位置。
- A/B/C/D/E/F 图中的 E3 有明确闭合田块面，对应 XLS E3。新屋湾图中的 E3 位于 X 区边界外白区，仅有标签，无法据此断言同一田块或重叠地理位置。后者采用独立 `drawing:...:ambiguous-E3-label` 来源键，`link_verified=false`，候选台账键只存在 `candidate_source_key`；面积为空，禁止自动合并。
- 不同图或同图中的清-1、清-5等塘编号可重复；来源键包含独立图纸与位置区分。此轮发现过清-8/清-9 在栅格处理中误连通，已修正闭运算尺度，二者最终轮廓及面积不同；验证脚本防止相同几何被重复赋给两个对象。
- 原有 `DETAIL-L18`、`DETAIL-L19`、`DETAIL-L20`、`DETAIL-QING17` 表示 ID 保留，其几何已替换为完整图纸正确位置。旧焦点图与全页 5200×3677 图之间的裁切 `(2000,1600,3600,2850)` 已用像素差确认，转换关系保留于 drawing 元数据。

## 几何含义与精度

各 PDF 原始页面约为 1190.52002×1683.71997 pt，内容横置。将原图逆时针旋转 90° 后，在 1683.71997×1190.52002 的独立纸面中表示几何，左上为原点，x 向右、y 向下。单位始终是 PDF 纸面点 `pt`。五个图纸空间互相独立；未与卫星图、现场坐标或其他图纸强行拼接。

田块采用原始闭合矢量路径。20 个塘面优先用源矢量闭合轮廓；源线分段未闭合时，用原图青色水面连通轮廓，3 px 闭运算跨越细小水面网纹，1.5 px 简化，并目视核对；这类轮廓明确为 `confirmed_visual / approximate_source_contour`。道路和沟渠是经过原图彩色线迹辅助校正的概化线，`precision=approximate_source_trace`；部分为可见连续走向，不能据此合并图上的施工分段编号或计算工程量。

`model_area_units2` 只描述纸面面积。所有 `model_area_m2`、CRS、高程基准为空。图内工程尺寸原文独立保存于 `documented_dimensions`，不据打印比例换算田块米制面积，也不据标高数字生成场地起伏。线显示宽度是视觉参数。XLS 面积列没有单位，仍保留 `area_unit=null`，推定亩只作为未经确认的独立提示。

## 重建

需要 Python、`requirements-audit.txt` 中固定版本的 pypdf、Pillow、xlrd，以及 Poppler。设置 `POPPLER_BIN` 指向 Poppler 的 bin 目录或 pdftoppm 可执行文件；未设置时先查系统 PATH，再尝试本机 Codex bundled fallback。

```powershell
python -m pip install -r requirements-audit.txt
python scripts/audit_sources.py
python scripts/audit_ledger.py
python scripts/audit_render_drawings.py
python scripts/audit_pdf_vectors.py
python scripts/audit_facility_annotations.py
python scripts/audit_drawing_geometry.py
python scripts/verify_spatial_audit.py
```

`label-anchors.json` 与 `facility-features.json` 是经过原图目视审查的输入，不是随机布局。若原图尺寸、绘图内容或源哈希改变，必须重新核对锚点及轮廓，不能盲目复用。最终完整绘图区 PNG 保存于 `data/spatial/drawings/`。轮廓和设施叠加检查图由脚本输出至 `tmp/audit/drawing-geometry/`。此实现不依赖 PyMuPDF、OpenCV 或 Shapely。

`verify_spatial_audit.py` 独立检查 5 个源哈希、100 条台账来源键一一覆盖、唯一表示 ID、闭合面、有限坐标及纸面范围、相同面重复赋值、E3 歧义隔离与单位约束。结果写入 `data/spatial/verification.json`。这证明资料提取结构和来源约束，不替代测绘或现场工程验收。
