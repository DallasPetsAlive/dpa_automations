from json import loads
from typing import Any, Dict
import logging

import boto3

logger: logging.Logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

ses_client = boto3.client("ses")


def handler(event: Dict[str, Any], _: Any) -> None:
    """Entry point for AWS lambda handler."""
    logger.debug(event)

    body = event.get("body")
    body = loads(body)

    if body.get("signedDocumentTitle") != "Foster Care Provider Agreement":
        logger.info("Not a foster care provider agreement")
        return

    participants = body.get("participants", [])
    if len(participants) != 1:
        logger.info("Not a single participant")
        return

    participant = participants[0]
    name = participant.get("name")
    email = participant.get("email")
    completed = body.get("completedDate")
    url = body.get("signedDocumentURL")

    ses_client.send_email(
        Destination={
            "ToAddresses": ["foster-apps@dallaspetsalive.org"],
        },
        Message={
            "Body": {
                "Text": {
                    "Charset": "UTF-8",
                    "Data": f"Foster agreement signed by {name} on {completed}.\nURL: {url}",
                },
            },
            "Subject": {
                "Charset": "UTF-8",
                "Data": f"Foster Agreement Signed: {name}",
            },
        },
        ReplyToAddresses=[email],
        Source=f"{name} <webapps@dallaspetsalive.org>",
    )
