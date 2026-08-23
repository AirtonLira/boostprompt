import { readFile } from 'node:fs/promises';

const html = await readFile(new URL('../dist/index.html', import.meta.url), 'utf8');
const required = [
  'Descubra antes. Construa certo.',
  'Discovery adaptativo',
  'Pesquisa auditável',
  'Prompt mestre',
  'data-scene-fallback',
  'https://github.com/AirtonLira/boostprompt',
];

for (const fragment of required) {
  if (!html.includes(fragment)) {
    throw new Error(`Missing landing fragment: ${fragment}`);
  }
}
