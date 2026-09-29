# ContextTrace product film

A 32-second, 1920×1080, 30 fps Remotion film. Quiet ivory/charcoal typography,
source-to-answer motion, and a locally synthesized original stereo soundtrack.
All essential information is visible without audio. Created for Samarth Vinayaka.

[Watch the published film](https://github.com/user-attachments/assets/304681e1-2e00-45cb-afd0-0c27c6400cce)
· [English captions](captions.vtt)

## Preview and render

Use Node.js 22 or newer:

```bash
cd media/contexttrace-demo
npm ci
npm run studio
```

Export the MP4 and poster:

```bash
npm run typecheck
npm run render
npm run poster
npm run silent
```

Outputs are in `out/` (ignored by Git). Remotion will provision its browser if
needed. To use an existing Chrome, append
`--browser-executable="/path/to/Chrome"` to the render or poster command after `--`.
`npm run stills` renders six review frames; its browser override is the
`REMOTION_BROWSER_EXECUTABLE` environment variable.

## Story

| Time | Scene |
| --- | --- |
| 0–3.5 s | An answer is only as good as its evidence. |
| 3.5–6.5 s | ContextTrace: follow the answer, find the evidence. |
| 6.5–14 s | An answer says 4%; its selected runbook says 2%. Contradiction. |
| 14–19.5 s | Correct the answer to 2%; verify it against the source. |
| 19.5–25 s | Replay the saved regression case: 2 traces, 4 passing checks. |
| 25–32 s | Local-first, open source, install command, repository, creator. |

The cards are an illustrated workflow, **not a recording of a shipped graphical
interface**. An on-screen label identifies the fictional demonstration.
The film does not announce 1.3, claim SOTA accuracy, advertise Jev as shipped,
or imply automatic repair. The terminal summary is an excerpt of actual output.
Source and answer prose are shortened in the comparison scene for readability.

## Evidence behind the demonstration

The example comes from the committed public fictional investigation:
`examples/investigations/ci-debugging-walkthrough/`.

From the repository root, reproduce its checks:

```bash
PYTHONPATH=packages/contexttrace:. python examples/investigations/run.py \
  --case ci-debugging-walkthrough
```

The broken trace must produce `contradicted`; the corrected trace must produce
`supported` and `no_failure_detected`. One case, two traces, four checks passed
when this film was prepared. This demonstrates the example workflow, not general
verifier accuracy. Support means grounded in the selected evidence, not independently true.
The captured four-check result is preserved in `verification.json`.

## Editing and assets

- `src/Film.tsx`: typography, copy, timing, SVG trace mark, animation.
- `src/index.tsx`: resolution, composition, and duration.
- `public/soundtrack.wav`: original synthesized music, no third-party samples.
- `scripts/soundtrack.py`: regenerate the music with Python and NumPy.
- `public/fonts/Manrope.ttf`: bundled variable font for offline rendering.
- `public/fonts/OFL.txt`: Manrope's SIL Open Font License, from Google Fonts.
- `captions.vtt`: descriptive text track, including the meaning of on-screen actions.
- `preview.html`: opens the MP4 with controls and optional captions after rendering.

No customer traces, API keys, model calls, downloaded music, or product statistics
are used in this film. Project dependencies are pinned in `package-lock.json`.
The video project is separate from the Python package and does not affect its
runtime or installation dependencies.
