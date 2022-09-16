import gspread
import logging
import sys
from configparser import ConfigParser
from typing import Any, Dict, List

from constants import TAB_MAPPING

logger: logging.Logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def handler(event: Dict[str, Any], _: Any) -> None:
    """Entry point for AWS lambda handler."""
    logger.debug(event)

    try:
        parser = ConfigParser()
        parser.read("config.ini")
        file_key = parser["sheets"]["file_key"]

        volunteers = get_volunteer_data(file_key)
        logger.info("Got {} volunteers".format(len(volunteers)))
    except Exception as e:
        logger.exception("Exception occurred.")
        raise Exception from e

def get_volunteer_data(file_key: str) -> List[Dict[str, str]]:
    sheets = gspread.service_account(filename="service_account.json")
    sheet = sheets.open_by_key(file_key)

    volunteers = []
    emails_already_added = []

    for tab in TAB_MAPPING:
        logger.debug(f"Processing tab: {tab}")
        tab_data = sheet.worksheet(tab)

        (
            first_names,
            last_names,
            emails,
        ) = tab_data.batch_get([
            TAB_MAPPING[tab]["first_name"],
            TAB_MAPPING[tab]["last_name"],
            TAB_MAPPING[tab]["email"],
        ])

        vol_length = min(
            len(first_names),
            len(last_names),
            len(emails),
        )

        count = 0
        for x in range(vol_length):
            if (
                first_names[x] and last_names[x] and emails[x]
                and emails[x][0] not in emails_already_added
                and emails[x][0].lower() != "email"
            ):
                volunteers.append({
                    "first_name": first_names[x][0],
                    "last_name": last_names[x][0],
                    "email": emails[x][0],
                })
                emails_already_added.append(emails[x][0])
                count += 1

        logger.debug(f"Found {count} volunteers in tab: {tab}")

        if count == 0:
            raise Exception (f"No volunteers found in tab: {tab}")

    return volunteers


if __name__ == "__main__":
    handler({}, {})
