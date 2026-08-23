import { Canvas, useFrame } from '@react-three/fiber';
import { useRef } from 'react';
import type { Group } from 'three';

function PromptObject() {
  const object = useRef<Group>(null);

  useFrame((state, delta) => {
    if (!object.current) return;
    const targetX = state.pointer.y * 0.14 - 0.12;
    const targetY = state.pointer.x * 0.24 - 0.34;

    object.current.rotation.x += (targetX - object.current.rotation.x) * Math.min(delta * 3, 1);
    object.current.rotation.y += (targetY - object.current.rotation.y) * Math.min(delta * 3, 1);
    object.current.position.y = Math.sin(state.clock.elapsedTime * 0.8) * 0.08;
  });

  return (
    <group ref={object}>
      <mesh>
        <boxGeometry args={[2.45, 3.15, 0.28]} />
        <meshPhysicalMaterial color="#14458f" metalness={0.34} roughness={0.22} transmission={0.08} />
      </mesh>
      <mesh position={[-0.76, -1.68, 0]} rotation={[0, 0, -0.34]}>
        <boxGeometry args={[0.78, 0.78, 0.32]} />
        <meshPhysicalMaterial color="#14458f" metalness={0.34} roughness={0.22} transmission={0.08} />
      </mesh>
      <group position={[0.04, 0.03, 0.19]} rotation={[0, 0, -0.34]}>
        <mesh position={[0.09, 0.36, 0]} rotation={[0, 0, 0.4]}>
          <boxGeometry args={[0.2, 1.02, 0.08]} />
          <meshBasicMaterial color="#f7f9ff" />
        </mesh>
        <mesh position={[-0.11, -0.36, 0]} rotation={[0, 0, 0.4]}>
          <boxGeometry args={[0.2, 1.02, 0.08]} />
          <meshBasicMaterial color="#f7f9ff" />
        </mesh>
      </group>
    </group>
  );
}

function SatelliteField() {
  const satellites: Array<[number, number, number, number]> = [
    [-2.8, 1.6, -0.3, 0.16],
    [2.7, 1.1, -0.6, 0.12],
    [3.1, -1.45, -0.4, 0.18],
    [-2.75, -1.25, -0.7, 0.1],
    [0.35, 2.45, -0.5, 0.08],
  ];

  return (
    <group>
      {satellites.map(([x, y, z, scale], index) => (
        <mesh key={`${x}-${y}`} position={[x, y, z]} scale={scale} rotation={[index, index * 0.6, 0]}>
          <icosahedronGeometry args={[1, 1]} />
          <meshStandardMaterial color={index % 2 ? '#45e3ee' : '#8b5cff'} emissive={index % 2 ? '#156a85' : '#341380'} />
        </mesh>
      ))}
    </group>
  );
}

export default function PromptCanvas() {
  return (
    <Canvas dpr={[1, 1.5]} camera={{ fov: 39, position: [0, 0.15, 7] }} gl={{ antialias: true }}>
      <ambientLight intensity={0.9} />
      <pointLight color="#45e3ee" intensity={13} distance={9} position={[-3, 2, 3]} />
      <pointLight color="#8451ff" intensity={16} distance={10} position={[3, -1, 2]} />
      <PromptObject />
      <SatelliteField />
    </Canvas>
  );
}
