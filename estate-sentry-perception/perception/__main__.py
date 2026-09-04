"""Run the perception service.

    python -m perception                 # motion gate only (no ML dependencies)
    python -m perception --detect        # with RT-DETRv2; needs the `detect` extra
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from .api_client import ApiClient
from .pipeline.detect import RTDetrDetector, StubDetector
from .pipeline.motion import MotionGate
from .service import PerceptionService
from .transport.minio_store import MinioFrameStore
from .transport.nats_bus import NatsEventBus

logger = logging.getLogger("perception")


async def main_async(args: argparse.Namespace) -> int:
    store = MinioFrameStore.from_env()
    await store.ensure_bucket()
    bus = await NatsEventBus.connect(args.nats_url)

    if args.detect:
        logger.info("loading detector %s (first run downloads weights)", args.model)
        detector = RTDetrDetector(args.model, confidence_threshold=args.confidence)
    else:
        logger.info("no detector: motion gate only (pass --detect to enable L2)")
        detector = StubDetector()

    api: ApiClient | None = None
    if not args.no_api:
        api = ApiClient(args.api_url)
        if not api.configured:
            # Said once here rather than as an auth failure on every frame.
            logger.warning(
                "no PERCEPTION_API_TOKEN set: zones cannot be loaded and no zone "
                "events will be written. Detection still runs."
            )

    service = PerceptionService(
        store,
        bus,
        detector=detector,
        gate=MotionGate(trust_producer_hint=not args.ignore_hints),
        api=api,
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    try:
        await service.run(stop=stop)
    finally:
        await bus.close()
        if api is not None:
            await api.aclose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nats-url", default=None, help="defaults to $NATS_URL")
    parser.add_argument(
        "--detect",
        action="store_true",
        help="run L2 object detection (needs: uv sync --extra detect)",
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--confidence", type=float, default=None)
    parser.add_argument(
        "--ignore-hints",
        action="store_true",
        help="always difference frames, even when a producer supplies a motion hint",
    )
    parser.add_argument("--api-url", default=None, help="defaults to $API_URL")
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="skip the API entirely: no zones loaded, no zone events written",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    # Defaults come from constants rather than argparse so there is one source of
    # truth for a tuned value.
    from .constants import DETECTION_CONFIDENCE_THRESHOLD, DETECTOR_MODEL

    args.model = args.model or DETECTOR_MODEL
    args.confidence = (
        args.confidence if args.confidence is not None else DETECTION_CONFIDENCE_THRESHOLD
    )

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    try:
        return asyncio.run(main_async(args))
    except KeyboardInterrupt:  # pragma: no cover
        return 130


if __name__ == "__main__":
    sys.exit(main())
