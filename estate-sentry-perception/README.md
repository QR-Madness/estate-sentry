# Estate Sentry Perception

Async perception pipeline for camera frames. Consumes frame notifications from the
Switchboard, runs inference, and reports detections upstream.

The authoritative design is [`docs/Specification.md`](../docs/Specification.md).
This service implements its L1–L3 layers; L4 (identity) onward are not built.

## The seam

Everything upstream of this service — the mock camera rig during development, a
Raspberry Pi edge agent later — talks to it through one contract:

```
frame bytes  ->  object store at  frames/{camera_id}/{date}/{iso}.jpg
notification ->  bus subject      frames.{camera_id}.raw
```

The notification carries a **reference**, never the frame itself. A message bus is
the wrong place for megabytes of JPEG: it would make every subscriber pay for
payloads most of them discard at the motion gate.

That contract is what makes the hardware swap cheap. Replacing the mock rig with a
real camera is a change of producer, not a change of pipeline.

## Layout

```
perception/
  transport/
    protocols.py   FrameRef, FrameStore, EventBus — the seam itself
    memory.py      in-process implementations, so tests need no Docker
  pipeline/
    motion.py      L1 motion gate
    detect.py      L2 object detection, behind a Detector protocol
  ring.py          bounded fan-out, drop-oldest under back-pressure
  constants.py     tunables, each with the reasoning behind its value
```

## Back-pressure

`ring.FrameRing` is the load-bearing piece. A slow consumer — a backgrounded
browser tab, a stalled dashboard — must be unable to either stall the capture loop
or grow memory without bound. So subscriber queues are bounded and full queues
**evict the oldest entry**.

Dropping the oldest is not a compromise here, it is the correct behaviour: a stale
frame has no value, and nobody wants to watch a growing delay play out in slow
motion. Blocking the producer instead — the usual alternative — would couple
capture rate to the slowest client on the network.

Evictions are counted (`Subscription.dropped`) rather than silently absorbed,
because silent loss looks identical to an idle camera from the outside.

## Install

```bash
uv sync
```

Two optional extras, kept out of the default install:

```bash
uv sync --extra capture   # opencv-python-headless (bundles FFmpeg; no system ffmpeg needed)
uv sync --extra detect    # transformers + torch — multiple GB
```

`detect` uses **RT-DETRv2** (Apache-2.0). Ultralytics/YOLOv8 is AGPL-3.0, which
would conflict with this project's MIT licence; the `Detector` protocol keeps that
choice reversible.

## Tests

```bash
uv run pytest
```

No infrastructure required. The properties worth asserting — a full queue drops
the oldest frame, a slow consumer cannot stall the producer — belong to this code
rather than to NATS or MinIO, so the suite runs against the in-memory transports.
