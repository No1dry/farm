// 依据竣工图东侧局部人工描绘。图像参照为旋正后的 PDF 渲染图，
// 在 (2000,1600) 起点截取的 1600 × 1250 局部。局部比例仅作展示，待 CAD 配准。
export const source={name:'庙下刘东侧样板区',basis:'竣工图局部描绘 + 现场照片外观参考',crs:'LOCAL_ILLUSTRATIVE',metersPerPixel:.42,origin:[650,650],georeferenced:false,elevationSurveyed:false,photoLocationsMatched:false};
export const local=([x,z])=>[(x-650)*.42,(z-650)*.42];
export const fields=[
 {id:'L18',name:'北侧农田',type:'农田',points:[[338,384],[430,389],[440,408],[446,466],[452,478],[504,504],[539,540],[543,590],[556,631],[551,659],[489,722],[207,584],[217,485],[301,510],[319,502],[327,430]],photo:'/focus/photos/field-01.jpg'},
 {id:'L19',name:'中部农田',type:'农田',points:[[196,608],[470,742],[364,895],[163,839]],photo:'/focus/photos/channel-02.jpg'},
 {id:'L20',name:'南侧农田',type:'农田',points:[[157,858],[353,918],[395,967],[405,1010],[397,1085],[380,1133],[342,1175],[92,1054],[120,961]],photo:'/focus/photos/field-03.jpg'}
];
export const pond={id:'P17',drawingId:'清-17',name:'东侧水塘',type:'水塘',points:[[1500,-20],[1540,56],[1595,145],[1615,192],[1595,214],[1544,269],[1505,328],[1468,389],[1436,417],[1445,430],[1430,469],[1426,551],[1437,600],[1460,645],[1462,715],[1450,783],[1420,832],[1342,823],[1260,850],[1200,887],[1160,913],[1083,959],[1065,944],[1050,887],[1010,799],[965,766],[927,734],[890,697],[903,647],[946,597],[971,578],[1019,568],[1037,543],[1054,492],[1075,457],[1090,386],[1091,320],[1090,291],[1105,170],[1121,140],[1185,128],[1269,108],[1338,86],[1355,65],[1371,31],[1401,16],[1451,9]],photo:'/focus/photos/pond-05.jpg'};
export const objects=[...fields,pond];
export const roads=[
 {id:'R-MAIN',name:'西侧田间道路',width:4.2,points:[[263,140],[223,345],[184,572],[152,797],[98,1026],[52,1180],[15,1350]]},
 {id:'R-5',name:'生产路Ⅱ型-5',width:3,documentedLength:223.18,points:[[184,578],[308,638],[483,734]]},
 {id:'R-3',name:'南侧田间道路',width:3.2,points:[[98,1058],[244,1120],[343,1191],[303,1270]]},
 {id:'R-PUMP',name:'水塘连接通道',width:3.2,points:[[372,899],[540,954],[657,991],[762,1065],[849,1088],[947,1054],[1031,1010]]}
];
export const channels=[
 {id:'C-WEST',name:'田间灌排沟渠',points:[[198,342],[166,565],[130,802],[72,1038],[43,1184],[-6,1327]],topWidth:5.8,bottomWidth:1.4,depth:1.55,lined:true},
 {id:'C-NORTH',name:'北侧排水沟',points:[[205,467],[312,504],[329,379],[439,384],[450,471],[514,507],[552,546],[552,592],[566,637],[556,670],[492,733]],topWidth:4.1,bottomWidth:1,depth:1.1,lined:true},
 {id:'C-CENTER',name:'田间排水沟',points:[[187,597],[327,664],[482,744],[374,901],[410,970],[416,1041],[394,1131],[349,1190]],topWidth:4,bottomWidth:1.1,depth:1.15,lined:true},
 {id:'C-LOW',name:'南侧排水沟',points:[[153,850],[259,881],[367,913]],topWidth:3.1,bottomWidth:.8,depth:.9,lined:false}
];
export const facilities=[{id:'GATE-01',name:'太阳能智能闸',point:[225,495],type:'gate'},{id:'GATE-02',name:'太阳能智能闸',point:[190,730],type:'gate'},{id:'GATE-03',name:'太阳能智能闸',point:[132,985],type:'gate'},{id:'PUMP-01',name:'泵站',point:[1031,1010],type:'pump'}];
export const centroid=p=>p.reduce((s,v)=>[s[0]+v[0]/p.length,s[1]+v[1]/p.length],[0,0]);
export const provenance={pdf:'2026.4.16竣工图（庙下流）.pdf',drawingAreaMu:262.79,leveledAreaMu:151.45,road5LengthM:223.18,drain12LengthM:392,pumpDrawingPowerKW:37,notes:['所示 3 块农田及 1 块水塘为本次样板范围。','262.79 亩是整张图标注的施工面积，不代表本次样板面积。','几何轮廓据竣工图描绘，局部尺度和高程尚未完成测绘配准。','照片的确切拍摄位置未对应，仅用于材质和设施外观参考。','实时监测、作物和养殖数据未接入。']};
