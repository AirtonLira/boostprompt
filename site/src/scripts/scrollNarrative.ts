import { shouldUseScrollSequence } from '../lib/experience';

const shouldLoad = () =>
  shouldUseScrollSequence({
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    wideViewport: window.matchMedia('(min-width: 768px)').matches,
  });

export async function loadScrollNarrative() {
  if (!shouldLoad()) return;

  const root = document.querySelector<HTMLElement>('[data-scroll-narrative]');
  const progress = document.querySelector<HTMLElement>('.page-progress span');
  if (!root || !progress) return;

  const [{ gsap }, { ScrollTrigger }] = await Promise.all([import('gsap'), import('gsap/ScrollTrigger')]);
  gsap.registerPlugin(ScrollTrigger);

  const context = gsap.context(() => {
    const steps = gsap.utils.toArray<HTMLElement>('[data-narrative-step]');

    gsap.to(progress, {
      scaleX: 1,
      ease: 'none',
      scrollTrigger: { scrub: 0.15, start: 'top top', end: 'bottom bottom' },
    });

    ScrollTrigger.create({
      trigger: root,
      start: 'top 148px',
      end: 'bottom bottom-=120',
      pin: root.querySelector('.narrative__intro'),
      pinSpacing: false,
    });

    steps.forEach((step) => {
      gsap.fromTo(
        step,
        { autoAlpha: 0.3, y: 38, clipPath: 'inset(0 0 18% 0)' },
        {
          autoAlpha: 1,
          y: 0,
          clipPath: 'inset(0 0 0% 0)',
          duration: 0.7,
          ease: 'power3.out',
          scrollTrigger: { trigger: step, start: 'top 73%', end: 'top 30%', scrub: 0.35 },
        },
      );
    });
  }, root);

  const cleanup = () => context.revert();
  window.addEventListener('pagehide', cleanup, { once: true });
}
