  "use client";

import * as THREE from "three";
import React, { useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";

/** ====== TUNING (غيري الأرقام دي بسهولة) ====== */
const ROTATION_SPEED = 0.03; // أبطأ: قلليها (0.03) / أسرع: زوديها (0.08)
const STREAK_SPEED = 0.05; // سرعة حركة الخط الأبيض (أبطأ: 0.05)
const STREAK_LENGTH = 0.5; // طول الجزء المنور من الخط (أكبر = يفضل منور أطول)
const STREAK_RADIUS = 5; // سُمك الخط
const GEO_DETAIL = 7; // كثافة التراينجلز (Cloudflare-ish: 7..8)

function makeGreatCircleArcPoints(segments = 260) {
  // اختيارات نقاط بتدي diagonal قريب من Cloudflare
  const a = new THREE.Vector3(-0.28, -0.95, 0.20).normalize();
  const b = new THREE.Vector3(0.88, 0.32, 0.42).normalize();

  const pts: THREE.Vector3[] = [];

  // manual slerp (Vector3 مفيهاش slerp)
  const omega = Math.acos(THREE.MathUtils.clamp(a.dot(b), -1, 1));
  const sinOmega = Math.sin(omega);

  for (let i = 0; i <= segments; i++) {
    const t = i / segments;

    let p: THREE.Vector3;
    if (sinOmega === 0) {
      p = a.clone();
    } else {
      const s1 = Math.sin((1 - t) * omega) / sinOmega;
      const s2 = Math.sin(t * omega) / sinOmega;

      p = new THREE.Vector3(
        a.x * s1 + b.x * s2,
        a.y * s1 + b.y * s2,
        a.z * s1 + b.z * s2
      );
    }

    // على سطح الكرة + سنة صغيرة عشان مفيش z-fighting
    pts.push(p.normalize().multiplyScalar(1.013));
  }

  return pts;
}

function GlobeMesh() {
  const pivot = useRef<THREE.Group>(null);

  // ألوان Cloudflare-like
  const ORANGE_A = new THREE.Color("rgba(42, 165, 184, 0.6)");
  const ORANGE_B = new THREE.Color("rgba(42, 165, 184, 0.3)");
  const WIRE = new THREE.Color("#ffe6cf"); // warm white
  const DOT = new THREE.Color("#fff6ee");

  /** 1) Mesh triangles (Wireframe) */
  const { baseGeom, wireGeom } = useMemo(() => {
    const g = new THREE.IcosahedronGeometry(1, GEO_DETAIL);
    const w = new THREE.WireframeGeometry(g);
    return { baseGeom: g, wireGeom: w };
  }, []);

  /** 2) Orb shader (بدون lights) — gradient بسيط مش “نور فجأة” */
  const orbMat = useMemo(() => {
    return new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      uniforms: {
        cA: { value: ORANGE_A },
        cB: { value: ORANGE_B },
      },
      vertexShader: `
        varying vec3 vN;
        varying vec3 vP;
        void main(){
          vN = normalize(normalMatrix * normal);
          vP = position;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vN;
        varying vec3 vP;
        uniform vec3 cA;
        uniform vec3 cB;

        float sat(float x){ return clamp(x, 0.0, 1.0); }

        void main(){
          // Gradient ناعم: أفتح فوق + أفتح شوية قدام
          float top = sat(vP.y * 0.55 + 0.55);
          float front = sat(vN.z * 0.50 + 0.50);
          float mixv = sat(0.62 * top + 0.38 * front);

          vec3 col = mix(cA, cB, mixv);

          // Rim خفيف جدًا (مش نور قوي)
          float rim = pow(1.0 - sat(dot(vN, vec3(0.0,0.0,1.0))), 2.2);
          col += vec3(1.0, 0.97, 0.93) * rim * 0.03;

          gl_FragColor = vec4(col, 1.0);
        }
      `,
    });
  }, []);

  /** 3) Dots */
  const dotsGeom = useMemo(() => {
    const pts: THREE.Vector3[] = [];
    const count = 1700; // هادية زي Cloudflare (مش noisy)
    for (let i = 0; i < count; i++) {
      const u = Math.random();
      const v = Math.random();
      const theta = 2 * Math.PI * u;
      const phi = Math.acos(2 * v - 1);

      const r = 1.009;
      const x = r * Math.sin(phi) * Math.cos(theta);
      const y = r * Math.cos(phi);
      const z = r * Math.sin(phi) * Math.sin(theta);

      pts.push(new THREE.Vector3(x, y, z));
    }
    return new THREE.BufferGeometry().setFromPoints(pts);
  }, []);

  const dotsMat = useMemo(() => {
    return new THREE.PointsMaterial({
      color: DOT,
      size: 0.006,
      transparent: true,
      opacity: 0.14,
      depthWrite: false,
      sizeAttenuation: true,
    });
  }, []);

  /** 4) Streak geometry على سطح الكرة (tube) */
  const streakGeom = useMemo(() => {
    const pts = makeGreatCircleArcPoints(260);
    const curve = new THREE.CatmullRomCurve3(pts);
    return new THREE.TubeGeometry(curve, 320, STREAK_RADIUS, 10, false);
  }, []);

  /** 5) Streak shader: جزء من الخط بيجري + glow + أبطأ */
  const streakMat = useMemo(() => {
    return new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0.0 },
      },
      vertexShader: `
        varying vec2 vUv;
        void main(){
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
        }
      `,
      fragmentShader: `
        varying vec2 vUv;
        uniform float uTime;

        float sat(float x){ return clamp(x, 0.0, 1.0); }

        void main(){
          // حركة الرأس على طول الخط
          float head = fract(uTime * ${STREAK_SPEED.toFixed(4)});

          // مسافة على طول الخط (مع wrap)
          float d = abs(vUv.x - head);
          d = min(d, 1.0 - d);

          // core + glow (أطول وأنعم)
          float w = ${STREAK_LENGTH.toFixed(4)};
          float core = 1.0 - smoothstep(0.0, w * 0.55, d);
          float glow = 1.0 - smoothstep(w * 0.20, w * 2.20, d);

          // تخانة عبر عرض الـ tube
          float across = 1.0 - abs(vUv.y - 0.5) * 2.0;
          across = pow(sat(across), 2.0);

          // alpha النهائي (منور + glow)
          float alpha = (core * 1.00 + glow * 0.55) * across;

          // يخليها “تظهر وتختفي” شوية زي Cloudflare
          float fade = smoothstep(0.02, 0.10, vUv.x) * (1.0 - smoothstep(0.90, 0.98, vUv.x));
          alpha *= fade;

          vec3 col = vec3(1.0, 0.98, 0.95); // warm white
          gl_FragColor = vec4(col, alpha);
        }
      `,
    });
  }, []);

  /** Animation */
  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;

    if (pivot.current) {
      // ✅ world-globe rotation: Y فقط (left/right)
      pivot.current.rotation.y += delta * ROTATION_SPEED;

      // ✅ مفيش sway ولا wobble (زي ما طلبتي)
      pivot.current.rotation.x = 0.0;
      pivot.current.rotation.z = 0.0;
    }

    (streakMat.uniforms.uTime as any).value = t;
  });

  return (
    <group
      // نفس placement بتاعك: نص الكرة داخل من اليمين
      position={[1.55, 0.25, 0]}
      rotation={[0.12, 0.42, 0]}
      scale={[2.65, 2.65, 2.65]}
    >
      <group ref={pivot}>
        {/* ORB */}
        <mesh geometry={baseGeom} material={orbMat} />

        {/* TRIANGLE MESH LINES */}
        <lineSegments geometry={wireGeom}>
          <lineBasicMaterial
            color={WIRE}
            transparent
            opacity={0.72} // لو عايزاها أفتح زوديها 0.80
            depthWrite={false}
          />
        </lineSegments>

        {/* DOTS */}
        <points geometry={dotsGeom} material={dotsMat} />

        {/* DIAGONAL MOVING WHITE LINE */}
        <mesh geometry={streakGeom} material={streakMat} />
      </group>
    </group>
  );
}

export default function GlobeHero() {
  return (
    <div className="globe-orb-wrap" aria-hidden="true">
      <Canvas
        dpr={[1, 2]}
        camera={{ position: [3.2, 0.25, 3.2], fov: 38 }}
        gl={{ antialias: true, alpha: true, premultipliedAlpha: false }}
      >
        {/* no lights */}
        <GlobeMesh />
      </Canvas>
    </div>
  );
}