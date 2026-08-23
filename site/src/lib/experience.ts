export type SceneEnvironment = {
  reducedMotion: boolean;
  finePointer: boolean;
  wideViewport: boolean;
};

export type ScrollEnvironment = Pick<SceneEnvironment, 'reducedMotion' | 'wideViewport'>;

export const shouldUseInteractiveScene = ({
  reducedMotion,
  finePointer,
  wideViewport,
}: SceneEnvironment) => !reducedMotion && finePointer && wideViewport;

export const shouldUseScrollSequence = ({ reducedMotion, wideViewport }: ScrollEnvironment) =>
  !reducedMotion && wideViewport;
