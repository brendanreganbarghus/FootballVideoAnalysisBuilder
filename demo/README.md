# Team demo

Build the current demo:

```powershell
python -m football_poc.demo_cli
```

The build also creates a downsized VP8/WebM copy of the annotated video because
the OpenCV FMP4 output is not supported by Chromium-based browsers.

Serve the project root:

```powershell
python -m http.server 8000
```

Open `http://localhost:8000/demo/`.

An independently selected, more balanced minute is available at
`http://localhost:8000/demo/window-3/`. Its counters include events from both
teams and its weaker clip-level evaluation should be presented as a
generalization test, not as a best-case example.

## Presenter flow

1. Explain the fixed panoramic source and amateur-club use case.
2. Play the annotated video and identify player/team and ball overlays.
3. Walk through ingest, tiled detection, tracking, team classification, event
   inference, and reporting.
4. Show provisional totals after each overlapping replay chunk.
5. Present the three-window benchmark rather than the best single window.
6. Close with limitations: CPU latency, ball recall, model licensing, privacy,
   behind-goal camera validation, and the need for club pilot footage.

Blue/white event counters update at each detected event timestamp while the
verification video plays. Chunk publication status advances separately at each
completed replay boundary. This demonstrates event timing, state, overlap, and
incremental reporting; it is not real-time model inference on the current CPU.
