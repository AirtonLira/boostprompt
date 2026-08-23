import { lazy, Suspense, useEffect, useState } from 'react';

import { browserSceneEnvironment, shouldUseInteractiveScene } from '../lib/experience';

const PromptCanvas = lazy(() => import('./PromptCanvas'));

const sceneIsAvailable = () =>
  shouldUseInteractiveScene(browserSceneEnvironment((query) => window.matchMedia(query).matches));

export default function PromptScene() {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const mediaQueries = [
      window.matchMedia('(prefers-reduced-motion: reduce)'),
      window.matchMedia('(pointer: fine)'),
      window.matchMedia('(min-width: 768px)'),
    ];
    const update = () => setEnabled(sceneIsAvailable());

    update();
    mediaQueries.forEach((query) => query.addEventListener('change', update));
    return () => mediaQueries.forEach((query) => query.removeEventListener('change', update));
  }, []);

  if (!enabled) return null;

  return (
    <div className="prompt-scene-canvas" aria-hidden="true">
      <Suspense fallback={null}>
        <PromptCanvas />
      </Suspense>
    </div>
  );
}
