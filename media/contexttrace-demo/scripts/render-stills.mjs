import {bundle} from '@remotion/bundler';
import {selectComposition, renderStill} from '@remotion/renderer';
import path from 'node:path';

const browserExecutable = process.env.REMOTION_BROWSER_EXECUTABLE || undefined;
const serveUrl = await bundle({entryPoint: path.resolve('src/index.tsx')});
const composition = await selectComposition({serveUrl, id:'ContextTrace', browserExecutable});
for (const frame of [75, 165, 345, 525, 690, 870]) {
  await renderStill({serveUrl, composition, frame, output: `out/frame-${frame}.png`, browserExecutable});
  console.log(`Rendered frame ${frame}`);
}
