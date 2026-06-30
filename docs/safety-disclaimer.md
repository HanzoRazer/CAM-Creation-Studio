# Safety Disclaimer

**Read this before using any output from CAM-Creation-Studio.**

CAM-Creation-Studio is an **educational and authoring tool**. It does **not**
certify machine readiness, replace professional CAM validation, or guarantee
safe machine execution.

## What the tool does and does not promise

- The generated G-code is a **starting point**, not certified machine output.
- The preview is a simple XY plot — it is **not** a simulation. It does not
  model your machine, your stock, tool geometry, collisions, or material.
- Feeds and speeds are a **suggested starting point that requires operator
  verification**. They are conservative guidance, not hard claims.
- The dialect/machine entries are **starter profiles**, not certified
  post-processors.

## Before you run anything

1. **Read the program.** G-code does exactly what it says — including the mistakes.
2. **Confirm units** (G20/G21) before running.
3. **Confirm the work coordinate system** and where part zero actually is.
4. **Confirm spindle/laser mode** and that speeds/power are sane for your setup.
5. **Confirm tool clearance** and safe-Z heights.
6. **Air-cut first** — run above the stock to catch crashes while it is still free.
7. Keep a hand on **feed-hold / emergency stop** the first time you run any new
   program.

## Liability

You are responsible for verifying every program before running it on real
hardware. Use at your own risk.
