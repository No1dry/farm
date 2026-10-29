import {defineConfig} from 'vite';
export default defineConfig({server:{proxy:{'/api':'http://127.0.0.1:8000'}},preview:{proxy:{'/api':'http://127.0.0.1:8000'}},build:{rollupOptions:{input:{main:'index.html',overview:'overview-v01.html'},output:{manualChunks:{three:['three','three/addons/controls/OrbitControls.js','three/addons/loaders/GLTFLoader.js','three/addons/loaders/RGBELoader.js']}}}}});
