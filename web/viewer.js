import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { groundGrid } from './ground-grid.js';
import { beamColor, wireframeColor, engineColor } from './plot-colors.js';
import { surfaceFillColor } from './surface-shading.js';
import { createSoftwareViewer } from './software-viewer.js';
import { surfaceFaces } from './surface-faces.js';
import { copyViewerFrame } from './viewer-capture.js';
const vec = a => new THREE.Vector3(a[0], a[2], -a[1]);

export function createViewer(element) {
  // Rendering can fail after startup (for example when a mobile browser evicts
  // its GPU context). Keep scene data outside either renderer so recovery never
  // needs to reload the model or run the solver.
  let backend, disposed=false, beams=[], attachments=[], ground=null, overlay=[];
  let preset='perspective', gridVisible=true, streamwiseChords=true;
  function recover() {
    if (disposed || backend?.kind==='canvas2d') return;
    backend?.dispose();
    backend=createSoftwareViewer(element);
    backend.update(beams,[...attachments,...overlay],ground,{streamwiseChords});
    backend.fit(preset);
    backend.setGridVisible(gridVisible);
  }
  try { backend=createWebGLViewer(element,recover); }
  catch { recover(); }
  return {
    update(data,objects=[],plane=null,{fit:refit=true}={}) {
      if(disposed)return;
      beams=data;attachments=objects;ground=plane;overlay=[];
      if(refit)preset='perspective';
      backend.update(beams,attachments,ground,{fit:refit,streamwiseChords});
    },
    setOverlay(objects=[]) {
      if(disposed||(!objects.length&&!overlay.length))return;
      overlay=objects;
      backend.update(beams,[...attachments,...overlay],ground,{fit:false,streamwiseChords});
    },
    setChordProjection(value) {
      if(disposed)return;
      streamwiseChords=!!value;
      backend.update(beams,[...attachments,...overlay],ground,{fit:false,streamwiseChords});
    },
    fit(view='perspective') {if(!disposed){preset=view;backend.fit(view);}},
    toggleGrid() {if(!disposed){gridVisible=!gridVisible;backend.setGridVisible(gridVisible);}},
    capture(target,options) {
      if(disposed)throw new Error('The aircraft view is unavailable.');
      return backend.capture(target,options);
    },
    dispose() {if(!disposed){disposed=true;backend?.dispose();beams=[];attachments=[];overlay=[];ground=null;}},
  };
}

function createWebGLViewer(element,onContextLost) {
  // Register resources as they are acquired, including the partial startup
  // path. A failed backend must not leave observers or GPU resources behind.
  const cleanup=[];
  let disposed=false, pendingFrame=null;
  function release() {
    for(const action of cleanup.splice(0).reverse()) {
      try { action(); } catch { /* Continue releasing the other resources. */ }
    }
  }
  try {
  const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true });
  cleanup.push(()=>renderer.domElement.remove(),()=>renderer.dispose());
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setClearColor(0x131d20, 1);
  renderer.domElement.setAttribute('aria-label', 'Aircraft geometry. Drag to orbit; scroll to zoom.');
  renderer.domElement.dataset.renderer='webgl';
  element.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  cleanup.push(()=>scene.traverse(object=>{
    object.geometry?.dispose();
    for(const material of [object.material].flat())material?.dispose();
  }));
  const camera = new THREE.PerspectiveCamera(35, 1, .01, 100000);
  camera.up.set(0, 1, 0);
  const controls = new OrbitControls(camera, renderer.domElement);
  // Disconnect controls before canvas removal: they also own document events.
  cleanup.push(()=>controls.dispose());
  controls.enableDamping = true;
  const geometry = new THREE.Group();
  scene.add(geometry);
  const grid = new THREE.GridHelper(20, 20, 0x3c5257, 0x233337);
  scene.add(grid);
  const axes = new THREE.AxesHelper(2);
  scene.add(axes);
  let groundLines=null;
  scene.add(new THREE.HemisphereLight(0xe6fff8, 0x526977, 2.1));
  const light = new THREE.DirectionalLight(0xffffff, 2.3);
  light.position.set(-10, 20, 5);
  scene.add(light);
  let bounds = new THREE.Box3(new THREE.Vector3(-1,-1,-6), new THREE.Vector3(1,1,6));

  function fit(view='perspective') {
    const center = bounds.getCenter(new THREE.Vector3());
    const size = bounds.getSize(new THREE.Vector3());
    const radius = Math.max(size.length(), 1);
    const distance = radius / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov/2))) * 1.12;
    const direction = view === 'top' ? new THREE.Vector3(.001,1,0) : view === 'front' ? new THREE.Vector3(-1,.01,0) : new THREE.Vector3(-.65,.75,1);
    camera.position.copy(center).addScaledVector(direction.normalize(), distance / Math.min(camera.aspect, 1));
    camera.near = radius / 10000;
    camera.far = radius * 1000;
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();
    invalidate();
  }

  function update(beams, attachments=[], ground=null, {fit:refit=true,streamwiseChords=true}={}) {
    if(groundLines){scene.remove(groundLines);groundLines.geometry.dispose();groundLines.material.dispose();groundLines=null;}
    for (const child of [...geometry.children]) {
      child.geometry?.dispose(); child.material?.dispose(); geometry.remove(child);
    }
    beams.forEach(beam => {
      const color = beamColor(beams, beam.index);
      const points = [];
      const faces = surfaceFaces(beam,{streamwise:streamwiseChords});
      for (const face of faces) {
        for (let j=1;j<face.length-1;j++) for (const k of [0,j,j+1]) points.push(...vec(face[k]).toArray());
      }
      if (points.length) {
        const g = new THREE.BufferGeometry();
        g.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
        g.computeVertexNormals();
        const mesh = new THREE.Mesh(g, new THREE.MeshStandardMaterial({ color: surfaceFillColor(color), side: THREE.DoubleSide, roughness: .6, metalness: .1 }));
        geometry.add(mesh);
        const lines = [];
        for (const face of faces) for (let j=0;j<face.length;j++) lines.push(...vec(face[j]).toArray(), ...vec(face[(j+1)%face.length]).toArray());
        const linesGeometry = new THREE.BufferGeometry();
        linesGeometry.setAttribute('position', new THREE.Float32BufferAttribute(lines, 3));
        geometry.add(new THREE.LineSegments(linesGeometry, new THREE.LineBasicMaterial({ color: wireframeColor(color), transparent: true, opacity: .9 })));
      }
      const lines = beam.axis.flatMap(segment => segment.flatMap(a => vec(a).toArray()));
      const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(lines, 3));
      geometry.add(new THREE.LineSegments(g, new THREE.LineBasicMaterial({ color: wireframeColor(color), depthTest: false })));
    });
    function addObject(object) {
      const points=object.segments.flatMap(segment=>segment.flatMap(a=>vec(a).toArray()));
      const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(points,3));
      const line=new THREE.LineSegments(g,new THREE.LineBasicMaterial({color:object.color??(object.kind==='engine'?engineColor:0xe8ba77),depthTest:!object.overlay}));
      if(object.overlay)line.renderOrder=2;
      geometry.add(line);
    }
    for(const object of attachments.filter(o=>!o.overlay))addObject(object);
    bounds = new THREE.Box3().setFromObject(geometry);
    for(const object of attachments.filter(o=>o.overlay))addObject(object);
    invalidate();
    if (bounds.isEmpty()) return;
    const size = Math.max(bounds.getSize(new THREE.Vector3()).length(), 1);
    grid.scale.setScalar(size/12);
    grid.position.y = bounds.min.y - size*.04;
    const center=bounds.getCenter(new THREE.Vector3());
    const plane=groundGrid(ground,[center.x,-center.z,center.y],size);
    grid.visible=axes.visible&&!plane;
    if(plane){
      const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(plane.segments.flatMap(s=>s.flatMap(p=>vec(p).toArray())),3));
      groundLines=new THREE.LineSegments(g,new THREE.LineBasicMaterial({color:plane.color}));
      groundLines.visible=axes.visible;scene.add(groundLines);
    }
    axes.scale.setScalar(size/12);
    if(refit)fit();
  }
  const resize = new ResizeObserver(() => {
    if(disposed)return;
    const { width, height } = element.getBoundingClientRect();
    if (!width || !height) return;
    renderer.setSize(width, height);
    camera.aspect = width / height; camera.updateProjectionMatrix();
    invalidate();
  });
  cleanup.push(()=>resize.disconnect());
  resize.observe(element);
  // Draw changed scenes and damping frames; external mode/time playback calls update.
  let contextLost = false;
  function invalidate() {
    if (!disposed && !contextLost && pendingFrame === null) pendingFrame = requestAnimationFrame(draw);
  }
  function draw() {
    pendingFrame = null;
    if(disposed || contextLost)return;
    controls.update();
    renderer.render(scene, camera);
  }
  controls.addEventListener('change', invalidate);
  cleanup.push(()=>controls.removeEventListener('change',invalidate));
  function lost(event) {
    event.preventDefault();
    contextLost = true;
    if (pendingFrame !== null) cancelAnimationFrame(pendingFrame);
    pendingFrame = null;
    // Finish the browser/Three event dispatch before removing their handlers.
    queueMicrotask(()=>{if(!disposed)onContextLost();});
  }
  function visible() {
    if (!document.hidden) invalidate();
  }
  renderer.domElement.addEventListener('webglcontextlost', lost);
  cleanup.push(()=>renderer.domElement.removeEventListener('webglcontextlost',lost));
  document.addEventListener('visibilitychange', visible);
  cleanup.push(()=>document.removeEventListener('visibilitychange',visible));
  function dispose() {
    if(disposed)return;
    disposed=true;
    if(pendingFrame!==null)cancelAnimationFrame(pendingFrame);
    pendingFrame=null;
    release();
  }
  invalidate();
  return {kind:'webgl',update,fit,dispose,
    capture(target,options){
      if(disposed||contextLost)throw new Error('The aircraft view is recovering. Try the download again.');
      renderer.render(scene,camera);
      return copyViewerFrame(renderer.domElement,target,options);
    },
    setGridVisible(visible) {axes.visible=visible;grid.visible=visible&&!groundLines;if(groundLines)groundLines.visible=visible;invalidate();}};
  } catch(error) {
    disposed=true;
    if(pendingFrame!==null)cancelAnimationFrame(pendingFrame);
    release();
    throw error;
  }
}
