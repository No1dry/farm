# 三维建模与原大屏恢复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox syntax for tracking.

**Goal:** 修正截图式场景与擅改界面，恢复原大屏并交付可近看、可编辑的 Blender 立体资产。

**Architecture:** 原 focus 页面保留布局和渲染风格，GLTF 适配器替换主体几何，原面板显示后端数据。Blender 根据已审计轮廓创建体积和 PBR 表面，图片仅保留隐藏参考。已有后端与身份保持不变。

**Tech Stack:** Blender 4.5 LTS / Python、Three.js / Vite、现有 FastAPI / SQLite。

**Spec:** `docs/superpowers/specs/2026-10-29-model-ui-correction.md`

## Global Constraints

- 不另设计大屏；原 focus CSS 冻结。
- 卫星图与整张 CAD 图不出现在默认三维主体或其颜色贴图中。
- 不改变业务 UUID 和来源轮廓；表现参数不作为业务事实。
- 不重建数据库，不引入本体仓库前端。

## Review Focus

- 看似恢复但仍由新样式覆盖原布局：比对 CSS 哈希及同尺寸元素位置。
- 有网格但主体仍是一张图：检查导出材质，并看低角度灰模。
- 模型有立体结构但镜头落空、钻地或太远：实际操作全部四镜头。
- 原样板恢复后丢了全域和数据库：逐资产加载、任意已关联地块查询与重名处理。
- 模型重做破坏设备/观测来源或触发旧异步导航：保持实体隔离，实测助手与快速切换。

## Task 1: 原界面恢复（ontology_audit）

Files: `index.html`, `src/focus/main.js`, 新增 GLTF/数据库/助手适配模块。

- [x] 保存原页面实际桌面与窄屏基线、布局坐标。
- [x] 原 DOM 和 CSS 基础上替换主体加载与档案查询，新增最小助手入口。
- [x] 与模型作者确认 camera_views，原四镜头实际显示相应结构。
- [x] 核对来源、搜索、歧义、点击与助手，复测导航取消行为。

## Task 2: Blender 实体重模（blender_assets）

Files: `scripts/blender*.py`, `deliverables/blender/`, `public/models/`, `docs/model-methodology.md`。

- [x] 现场照片和原 focus 视觉对照，建模样区低角度材质及灰模检查。
- [x] 生成全红线及五图立体场景，隐藏来源图，导出不含来源图的 GLB。
- [x] 打包依赖并重新打开 .blend；核对稳定身份与来源几何。
- [x] 提供可复现四镜头坐标与构建、材质、几何验证记录。

## Task 3: 独立视觉审查（source_audit / root）

Files: `docs/audit/model-correction-criteria.md`, `deliverables/verification/`。

- [x] 用灰模与低角度图判定立体结构；不能以网格数代替此检查。
- [x] 对比原大屏；修复不必要的布局偏离。
- [x] 实际启动、加载全部资产、浏览器性能与数据库/助手闭环测试。
- [x] 更新 README、验收记录与制品清单，明确 V0.4 视觉交付被用户否定。
