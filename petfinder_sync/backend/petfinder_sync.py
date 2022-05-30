import logging

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def handler(event, _):
    logging.info("received event: {}".format(event))
    return
