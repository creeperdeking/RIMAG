import React, { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { columnPoses } from "./ZoneChart";

type Props = {
  rOuter: number;
  stackM: number;
  columns: number;
};

const ColumnsView: React.FC<Props> = ({ rOuter, stackM, columns }) => {
  const hostRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color("#f3f0e8");
    const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 200);
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    host.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    const light = new THREE.DirectionalLight(0xffffff, 1.1);
    light.position.set(4, 8, 6);
    scene.add(light);
    scene.add(new THREE.AmbientLight(0xffffff, 0.55));

    const group = new THREE.Group();
    scene.add(group);

    const poses = columnPoses(columns, rOuter);
    const material = new THREE.MeshStandardMaterial({
      color: "#64748b",
      metalness: 0.1,
      roughness: 0.65,
    });
    for (const [x, y] of poses) {
      const geom = new THREE.CylinderGeometry(rOuter, rOuter, Math.max(stackM, 0.05), 64);
      const mesh = new THREE.Mesh(geom, material);
      mesh.position.set(x, stackM / 2, -y);
      group.add(mesh);
    }

    const span = Math.max(rOuter * columns * 2.2, stackM * 1.4, 2);
    camera.position.set(span * 0.9, span * 0.7, span * 0.9);
    controls.target.set(0, stackM / 2, 0);
    controls.update();

    const resize = () => {
      const width = host.clientWidth || 480;
      const height = 280;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(host);

    let frame = 0;
    const tick = () => {
      frame = requestAnimationFrame(tick);
      controls.update();
      renderer.render(scene, camera);
    };
    tick();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      controls.dispose();
      group.traverse((obj) => {
        if (obj instanceof THREE.Mesh) {
          obj.geometry.dispose();
          if (Array.isArray(obj.material)) obj.material.forEach((m) => m.dispose());
          else obj.material.dispose();
        }
      });
      renderer.dispose();
      host.removeChild(renderer.domElement);
    };
  }, [rOuter, stackM, columns]);

  return (
    <div className="border rounded bg-white p-2">
      <div className="fw-semibold mb-1">Column cylinders</div>
      <div ref={hostRef} style={{ height: 280 }} />
      <div className="small text-secondary mt-1">
        One cylinder per column. Diameter is the disk diameter; height is the stack height.
      </div>
    </div>
  );
};

export default ColumnsView;
