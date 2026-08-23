import { describe, expect, it } from 'vitest';

import {
  browserSceneEnvironment,
  shouldUseInteractiveScene,
  shouldUseScrollSequence,
} from './experience';

describe('experience eligibility', () => {
  it('keeps the 3D scene disabled for reduced motion, coarse pointers and narrow screens', () => {
    expect(
      shouldUseInteractiveScene({ reducedMotion: true, finePointer: true, wideViewport: true }),
    ).toBe(false);
    expect(
      shouldUseInteractiveScene({ reducedMotion: false, finePointer: false, wideViewport: true }),
    ).toBe(false);
    expect(
      shouldUseInteractiveScene({ reducedMotion: false, finePointer: true, wideViewport: false }),
    ).toBe(false);
    expect(
      shouldUseInteractiveScene({ reducedMotion: false, finePointer: true, wideViewport: true }),
    ).toBe(true);
  });

  it('enables scroll choreography only on a motion-safe desktop viewport', () => {
    expect(shouldUseScrollSequence({ reducedMotion: false, wideViewport: true })).toBe(true);
    expect(shouldUseScrollSequence({ reducedMotion: true, wideViewport: true })).toBe(false);
  });

  it('maps browser media results to the 3D eligibility environment', () => {
    const matches = (query: string) => query !== '(prefers-reduced-motion: reduce)';

    expect(browserSceneEnvironment(matches)).toEqual({
      reducedMotion: false,
      finePointer: true,
      wideViewport: true,
    });
  });
});
