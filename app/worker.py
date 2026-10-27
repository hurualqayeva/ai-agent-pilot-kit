"""Queue worker: reads Telegram updates from Redis and runs the agent.

Run: REDIS_URL=redis://localhost:6379/0 python -m app.worker
"""

import logging
import os
import socket

from app.main import get_agent, get_queue, handle_message

log = logging.getLogger("pilot.worker")


def main() -> None:
    queue = get_queue()
    if queue is None:
        raise SystemExit("REDIS_URL is not set")
    agent = get_agent()
    consumer = os.getenv("WORKER_NAME", f"{socket.gethostname()}-{os.getpid()}")
    queue.ensure_group()
    log.info("worker %s listening", consumer)
    while True:
        queue.process(consumer, lambda message: handle_message(agent, message))


if __name__ == "__main__":
    main()
