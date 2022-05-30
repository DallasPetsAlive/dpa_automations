import configparser
import logging
from typing import Any, Dict

import requests

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def handler(event: Dict[str, Any], _: Any) -> None:
    logging.info("sync received event: {}".format(event))

    config = configparser.ConfigParser()
    config.read("config.ini")
    shelterluv_key = config["shelterluv"]["SHELTERLUV_API_KEY"]

    animals = get_shelterluv_pets(shelterluv_key)
    logger.info(animals)


def get_shelterluv_pets(shelterluv_key: str) -> Dict[str, Any]:

    headers: Dict[str, str] = {"x-api-key": shelterluv_key}
    offset = 0
    animals = {}

    url = "https://www.shelterluv.com/api/v1/animals?status_type=publishable"

    while response := requests.get(url, headers=headers):

        # check http response code
        if response.status_code != 200:
            logger.error("invalid response code")
            raise requests.RequestException(response)

        response_json = response.json()

        if response_json["success"] != 1:
            logger.error("invalid attempt")
            raise requests.RequestException(response)

        total_count = response_json["total_count"]

        if total_count == 0:
            logger.error("no animals found - error")
            raise requests.RequestException("no animals found")

        # add each animal to the dict
        for animal in response_json["animals"]:
            id = animal["ID"]
            if id in animals:
                logger.warning("animal already exists")
                continue

            animals[id] = animal

        # check for more animals
        if response_json["has_more"]:
            offset += 100
            url = (
                "https://www.shelterluv.com/api/v1/"
                + "animals?status_type=publishable&offset="
                + str(offset)
            )
        else:
            break

    # we should have all the animals now
    if str(animals.__len__()) != str(total_count):
        logger.error("something went wrong, missing animals")

    return animals
