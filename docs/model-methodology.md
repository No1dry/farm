# Blender 全域三维模型 V0.6

本版以完整卫星红线区域为默认场景。主体由 Blender 直接构建：田床与田埂、作物行和叶簇、湖塘岸坡与底部、道路路肩与基础、挖槽沟渠、连续林冠和接地枝干、九处村落的屋面/墙/门窗/门廊/院坪，以及样例监测和增氧设备。卫星截图及 CAD 整页仅在 Blend 的隐藏参考集合保存，七份运行时 GLB 均不含截图主平面。

用户授权“没有的信息先用样例数据建模，后面再更改”。本版主动补全缺失外观，同时把影像判读与样例参数分开保存。建筑高度、楼层、屋顶结构、单株树木、作物状态、地形起伏、设备和运行数据均不冒充现场测量。这是完整区域的可替换三维表达，不是照片测量重建或实测竣工模型。

## 交付与编辑

- `deliverables/blender/farm-full.blend`：全域和五个独立图纸 Scene。建筑逐栋可编辑；树木为可编辑链接网格实例；岸坡、田面、路肩、渠壁分别成面。
- `public/models/full-area.glb`、`full-area-lod.glb`：全域近景与远景，默认资产 `full`。
- 五个 `detail-*.glb`：独立图纸片区，不与卫星空间强拼接。
- `public/models/manifest.json`：稳定空间 ID、来源、修订外观引用、显示中心/范围、相机和制品哈希。
- `deliverables/blender/v06-full-preview.png`、`v06-village-preview.png`、`v06-field-preview.png`：实际 Blender 全域、村落和低机位预览；正式全域渲染为 `full-area-review.png`。
- `full-region-export-verification.json` 与 `full-region-scene-verification.json`：导出字节及重新打开 Blend 的核验；真实浏览器截图在 `deliverables/verification`。

运行时图片嵌入 GLB；Blend 打包照片 PBR、通用叶簇材质、HDRI 和隐藏参考图。Text 数据块嵌入最终 manifest、冻结五图、全域补充数据、样例参数/实例/设备布局及五份构建源码。重建不读取旧 Three.js 样板，不把旧 JS 转格式冒充模型。

## 来源、覆盖和身份

原全域 121 个 owner ID 保持：38 田面、36 塘、1 湖、9 林地、9 聚落、3 裸地、20 路、5 沟。它们是影像地物解释，不是台账确权边界。新增屋面、作物、树木和器材均为外观部件，不增加真实业务实体或改变 UUID。

增强输入 `data/spatial/full-region-enrichment.json` 冻结为 `region-02`，SHA256 `941f7ddd74709ef88082588473f5f6667dd19ee5e07ee591f949bc41554dc1db`。435 条记录包括九处聚落修订范围、192 屋顶候选、村内及连接街巷、37 水体细化轮廓、38 田区颜色参考、残余地类及明确样例回填、外部湖河和洲。192 是低至中置信的屋顶状表面候选数，不能当作实测建筑户数。它替代旧 `appearance-roof-footprints.json` 的两个屋顶，避免重复。

原未分类地表按来源大类分为林地、草地、田地、裸地和混合地表；难以定类处采用 `sample` 小田与树丛。原身份及源几何保留；已知错位的村落和水体外观采用修订轮廓，当前 `center`、显示范围、模型面积随之更新，旧值保存在 `source_center/source_bounds/source_model_area_m2`，并附 `appearance_geometry_override`。

外部仅输出来源确认的西南湖、北河和洲，连续草土地表延伸镜头外。视觉审查发现任意外部矩形塘和棋盘地块产生拼贴感，已停止输出这些未确认回填。它们没有进入业务统计。

五图 `data/spatial/drawing-entities.json` 不变，SHA256 `8353749c4105c8fadf2944e1140e06e91a7f9843d76e877a159eaea5de8cfaff`。163 表示为 100 台账田块面、20 塘面、17 道路线、5 沟线、20 设施文字锚点和一个歧义 E3 点。21 个未知边界点保持 `Point/boundary_unknown`、空面积和默认隐藏符号，不伪造为已知实体。`DETAIL-L18/L19/L20/DETAIL-QING17` 延续稳定 ID。

## 可替换参数及坐标

`data/model/full-region-parameters.json` 实际控制 seed、林地起伏、背景范围、建筑高度/层高/屋脊/檐宽/窗间距/院坪、林木间距和尺寸、作物行与叶簇尺寸、湖塘水位/显示深度、道路端点吸附距离和肩宽。未生效的配置项已移除。

`data/model/full-region-generated-instances.json` 保存建筑实例。每条声明坐标系及单位：来源候选为 `SATELLITE_SCREENSHOT_NATIVE_PIXELS`，样例实例为 `BLENDER_LOCAL_XY / metres_illustrative`。记录父 owner、源记录、`observed/sample` 和替换参数。树木由 seed/参数确定，Blend 中可单独移动缩放；Make Single User 可将链接网格变为独立网格。

全域原图 2940×1912，旧画布 1952×1269，参考原点 [1110,740]，用截图 300m 标尺约 101 像素估算量纲。Blender XY 为平面、Z 向上；GLB/Three 为 X 右、Z 向图下、Y 向上。无 CRS、控制点或 DEM。

精化村落/水岸的 manifest `center`、`bounds`、`model_area_m2` 对应当前显示轮廓；原始 `geometry`、`points`、`centroid` 保留作来源版本，旧显示值另存 `source_center/source_bounds/source_model_area_m2`，并以 `appearance_geometry_override` 指向补充记录。网页定位及设备布局必须使用当前 `center`，不能将旧来源 `centroid` 当作新版显示锚点。

五图仍用旋正纸面坐标，一个显示单位是一纸面 pt，**不是一米**；`model_area_m2=null`，纸页面积另存 `model_area_units2`。22.75、22.30 等平整标高基准未知，不当作海拔，也不据此给全域加坡度。

全域固定地面基准 0，田床约 0.05、田埂约 0.30、作物行 0.08–0.16、叶簇 0.3–0.6、水面 -0.78、塘显示深度 2.85、湖显示深度 4.8、林地起伏最高 7.5；沟深 1.4、浅水高于底 0.18。均为表现参数，不是测绘成果。五图使用其纸面显示断面，原文工程尺寸仅通过 `documented_dimensions` 透传。

## 样例设备契约

`data/demo/full-area-device-layout.json` 是 49 个演示设备的共享布局。土壤仪有探头/控制盒，摄像杆有基座/杆/相机/太阳能板，水质仪为浮标，增氧机有浮筒/机架/电机/叶轮。

器材节点保留 `scene_device_key`、`scene_scenario_id`、`data_nature='synthetic'`、父 `spatial_id` 和 `base_position_three`；近景/LOD 均不合批丢失键。底部满足当前父 `center + offset`，标签抬高独立处理。`data/model/device-grounding-updates.json` 保存 49 个地形/水位采样位置供共享布局及数据库同步。林地仪器按丘面采样，渠浮标在源沟中心线和显示浅水位，不能沿用塘面高度；样例设备避让已建墙面。

## 几何、材质与性能

多边形保留孔洞，用约束 Delaunay 三角化，地表真实扣除水体/沟槽。塘有草岸、斜坡、独立低位水面、底部与土体。沟顶采用等距多边形坡带，避免宽扫掠转角翻面。庙下刘西部源沟短段的混凝土框具有实际贯穿孔；照片只支持构造外观，不能证明该源沟实际材料。

土/草/碎石/混凝土复用照片 PBR。作物照片明度归一后乘生长期色，避免暗图重复乘色。屋瓦为程序纹理及屋脊/接缝几何，门窗/门廊为网格。绿色作物是演示季节，不宣称现场品种或状态。

树木有接地树干、分枝、冠芯与 Poly Haven Tree Small 02 的 CC0 枝叶裁片；材质采用 glTF `MASK` alpha 裁切和双面显示。许可、作者、哈希在 `public/focus/textures/foliage/source-manifest.json` 和素材来源清单。未引入高面数整树下载模型，不宣称现场树种。

导出时按 owner/图层/水面类别临时合批，Blend 保留独立编辑结构。树体用 `EXT_mesh_gpu_instancing`，现有 Three GLTFLoader 支持。LOD 保留全部建筑、树木数量、设备、岸坡和断面，只简化叶簇密度、细窗框及草叶微细节。五图分片加载。LOD 不退化为截图。

## 重建和核验

官方 Blender 4.5.15 LTS 便携版位于 `../.tools/blender-4.5.15-windows-x64`，无系统安装。依赖自带 Python 3.11、numpy 1.26.4，以及 Shapely 2.1.2（`scripts/blender-requirements.txt`）。从 farm 目录运行：

    ../.tools/blender-4.5.15-windows-x64/blender.exe --background --python-exit-code 1 --python scripts/blender_build.py
    ../.tools/blender-4.5.15-windows-x64/blender.exe --background deliverables/blender/farm-full.blend --python-exit-code 1 --python scripts/blender_scene_verify.py
    python scripts/blender_full_region_verify.py
    python scripts/blender_material_verify.py
    python scripts/blender_verify.py
    python scripts/blender_drawing_verify.py
    python scripts/verify_model_correction.py

核验稳定身份、五图源证据、49 设备位置/场景键、GPU 实例、alpha 裁片、GLB 自包含、无截图主材质、真实高度、地形孔洞/水面遮挡、渠顶法线、Blend 图片打包和嵌入 manifest 一致。自动通过不代表视觉验收。全域、九村、田塘道路近景和实际浏览器另行目检；不以网格数或“测试通过”冒称照片级真实。

浏览器复核曾发现全域白地：Blender 4.5 的 glTF 导出器不识别旧 `ShaderNodeMixRGB` 乘色常量，灰度照片纹理丢失绿色/屋面色因子。已改为导出器识别的 `ShaderNodeMix`、RGBA、MULTIPLY 节点，保持 Blender 外观不变。构建时另将全部七份当前 manifest 资产的 `baseColorFactor` 与实际 Blend shader socket 对照；直接图片驱动的 alpha 叶簇明确记录为无需乘色，不静默跳过。水面运行时共享材质的重复衰减由前端独立修复，模型水色参数未变。
