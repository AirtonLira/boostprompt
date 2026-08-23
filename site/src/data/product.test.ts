import { describe, expect, it } from 'vitest';

import { product } from './product';

describe('product landing content', () => {
  it('links the primary CTA to the canonical repository', () => {
    expect(product.repositoryUrl).toBe('https://github.com/AirtonLira/boostprompt');
  });

  it('contains the documented discovery, research and delivery differentiators', () => {
    expect(product.features.map(({ id }) => id)).toEqual(
      expect.arrayContaining(['adaptive-discovery', 'auditable-research', 'validated-delivery']),
    );
    expect(product.questionRange).toEqual([30, 50]);
  });
});
