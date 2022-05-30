import logging
from typing import Any, Dict

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def handler(event: Dict[str, Any], _: Any) -> None:
    logging.info("received event: {}".format(event))
