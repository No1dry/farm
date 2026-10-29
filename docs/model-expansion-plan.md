# Five-drawing Blender expansion plan

> Implementation uses the existing Blender generator with separate source-driven drawing assembly and independent verification.

Goal: represent every supported object across all five PDF pages without inventing parcel boundaries, coordinate registration or facilities.

Architecture: `data/spatial/drawing-entities.json` supplies rotated paper-space records, identifiers and evidence. `scripts/blender_drawings.py` creates one scene collection and GLB per PDF. `scripts/blender_build.py` builds the satellite-wide model, assembles the five collections, packs images and writes one manifest and editable Blend.

Constraints: paper-point geometry remains independent from metres; unknown boundaries use selectable point markers with null area; business IDs derive only from verified source keys; engineering dimensions remain separate from rendering assumptions; no coordinates are inferred from XLS area values.

- [x] Add verification for five source drawing assets, reference planes and anchor-only records.
- [x] Build drawing polygons/lines/points with provenance and source identifiers.
- [x] Replace generic full-area decorative masses and repeated field patterns with source-projected PBR surfaces; preserve editable banks, berms and road/channel sections.
- [x] Export a light whole-area LOD and five independently loaded drawing GLBs, with embedded dependencies.
- [x] Run Blender, reopen the saved Blend, verify source-object coverage and bounds, and inspect each exported view.
- [x] Update model methodology, dependency inventory and validation artifacts.

Final validation: 284 editable resource groups, 719 meshes, 6 switchable Blender scenes, 20 packed images. Source dataset SHA256 `8353749c4105c8fadf2944e1140e06e91a7f9843d76e877a159eaea5de8cfaff`; 163 drawing representations match source geometry individually, including 21 explicitly unknown-boundary anchors. No duplicate coincident drawing surfaces. Build hashes and independent reopened-source verification are in `deliverables/blender/build-report.json`.

Review focus: rotation/axis consistency, unknown boundary area stays null, point marker is visibly symbolic, no facility appears without a source identifier, all five references render, existing business UUIDs are untouched.
