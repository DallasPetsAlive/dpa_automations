"""
AWS lambda handler.

Airtable New Digs to RescueGroups.org sync.
"""
import configparser
import csv
import ftplib
import logging
from typing import Any, Dict, List, Optional

import requests

logger: logging.Logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

config = configparser.ConfigParser()
config.read("config.ini")

CSV_HEADERS = [
    "externalID",
    "status",
    "internalID",
    "rescueID",
    "name",
    "type",
    "priBreed",
    "secBreed",
    "mix",
    "sex",
    "okwithdogs",
    "okwithcats",
    "okwithkids",
    "declawed",
    "housebroken",
    "age",
    "specialNeeds",
    "altered",
    "size",
    "uptodate",
    "color",
    "pattern",
    "coatLength",
    "courtesy",
    "dsc",
    "found",
    "foundDate",
    "foundZipcode",
    "photo1",
    "photo2",
    "photo3",
    "photo4",
    "videoUrl",
]


def handler(event: Dict[str, Any], _: Any) -> None:
    """Entry point for AWS lambda handler."""
    logger.debug(event)

    # get the pets from Airtable
    try:
        airtable_pets: List[Dict[str, Any]] = get_airtable_pets()

        # create CSV file of available pets
        csv_file: str = create_csv_file(airtable_pets)

        # upload CSV file to rescuegroups.org
        upload_to_rescue_groups(csv_file)
    except Exception as e:
        logger.exception("Exception occurred.")
        raise Exception from e
        
    logger.debug("Done")


def get_airtable_pets() -> Any:
    """Get the new digs pets from Airtable."""
    url = "https://api.airtable.com/v0/" + config["airtable"]["BASE"] + "/Pets"
    headers = {"Authorization": "Bearer " + config["airtable"]["API_KEY"]}
    
    quit = False
    pets = []
    offset = None
    
    while not quit:
        
        params = {}

        if offset:
            params = {
                "offset": offset,
            }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != requests.codes.ok:
            logger.error("Airtable response: ")
            logger.error(response)
            logger.error("URL: %s", url)
            logger.error("Headers: %s", str(headers))
            raise Exception
    
        airtable_response = response.json()
        
        if not airtable_response.get("offset"):
            quit = True
        else:
            offset = airtable_response["offset"]
        
        pets += airtable_response["records"]

    logger.info("got {} pets from Airtable".format(len(pets)))

    return pets


def create_csv_file(airtable_pets: List[Dict[str, Any]]) -> str:
    """Create a CSV file of new digs pets."""
    # pylint: disable=too-many-statements
    filename: str = "newdigs.csv"
    file: str = str(config["local"]["FILEPATH"]) + filename
    with open(file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # headers from rescuegroups.org sample file
        writer.writerow(CSV_HEADERS)

        # figure out where the columns we have data for reside
        indexes: Dict[str, int] = {
            "id": CSV_HEADERS.index("externalID"),
            "name": CSV_HEADERS.index("name"),
            "status": CSV_HEADERS.index("status"),
            "species": CSV_HEADERS.index("type"),
            "breed": CSV_HEADERS.index("priBreed"),
            "mix": CSV_HEADERS.index("mix"),
            "sex": CSV_HEADERS.index("sex"),
            "ok_dog": CSV_HEADERS.index("okwithdogs"),
            "ok_cat": CSV_HEADERS.index("okwithcats"),
            "ok_kid": CSV_HEADERS.index("okwithkids"),
            "declawed": CSV_HEADERS.index("declawed"),
            "house": CSV_HEADERS.index("housebroken"),
            "age": CSV_HEADERS.index("age"),
            "needs": CSV_HEADERS.index("specialNeeds"),
            "fixed": CSV_HEADERS.index("altered"),
            "size": CSV_HEADERS.index("size"),
            "utd": CSV_HEADERS.index("uptodate"),
            "color": CSV_HEADERS.index("color"),
            "length": CSV_HEADERS.index("coatLength"),
            "courtesy": CSV_HEADERS.index("courtesy"),
            "dsc": CSV_HEADERS.index("dsc"),
            "found": CSV_HEADERS.index("found"),
            "photo1": CSV_HEADERS.index("photo1"),
            "photo2": CSV_HEADERS.index("photo2"),
            "photo3": CSV_HEADERS.index("photo3"),
            "photo4": CSV_HEADERS.index("photo4"),
        }

        pets_found = False
        dog_count = 0
        cat_count = 0
        for pet in airtable_pets:
            # if pet isn't available or isn't a supported species, bail
            status: str = pet["fields"].get("Status", "")
            if "Published - Available" not in status:
                continue

            species: str = pet["fields"].get("Pet Species", "")
            if species not in ("Dog", "Cat"):
                continue

            pets_found = True

            pet_row: List[Optional[str]] = [None for _ in range(len(CSV_HEADERS))]

            pet_row[indexes["id"]] = pet["id"]
            pet_row[indexes["name"]] = pet["fields"].get("Pet Name")
            pet_row[indexes["status"]] = "Available"
            pet_row[indexes["species"]] = species
            pet_row[indexes["sex"]] = pet["fields"].get("Sex")
            pet_row[indexes["age"]] = pet["fields"].get("Pet Age")
            pet_row[indexes["needs"]] = pet["fields"].get("Special Needs")
            pet_row[indexes["size"]] = pet["fields"].get("Pet Size")
            pet_row[indexes["length"]] = pet["fields"].get("Coat Length")
            pet_row[indexes["courtesy"]] = "Yes"
            pet_row[indexes["found"]] = "No"

            if pet["fields"].get("Mixed Breed") == "No":
                pet_row[indexes["mix"]] = "No"
            else:
                pet_row[indexes["mix"]] = "Yes"

            if species == "Dog":
                dog_count += 1
                pet_row[indexes["breed"]] = pet["fields"].get("Breed - Dog")
                pet_row[indexes["color"]] = pet["fields"].get("Color - Dog")
            elif species == "Cat":
                cat_count += 1
                pet_row[indexes["breed"]] = pet["fields"].get("Breed - Cat")
                pet_row[indexes["color"]] = pet["fields"].get("Color - Cat")

            pet_row[indexes["ok_dog"]] = pet["fields"].get("Okay with Dogs")
            pet_row[indexes["ok_cat"]] = pet["fields"].get("Okay with Cats")
            pet_row[indexes["ok_kid"]] = pet["fields"].get("Okay with Kids")
            pet_row[indexes["declawed"]] = pet["fields"].get("Declawed")
            pet_row[indexes["house"]] = pet["fields"].get("Housetrained")
            pet_row[indexes["fixed"]] = pet["fields"].get("Altered")
            pet_row[indexes["utd"]] = pet["fields"].get("Up-to-date on Shots etc")

            description: str = pet["fields"].get("Public Description", "")
            description = description.replace("\r", "<br />")
            description = description.replace("\n", "<br />")
            pet_row[indexes["dsc"]] = description

            pictures: List[str] = []
            url = "https://dpa-media.s3.us-east-2.amazonaws.com/new-digs-photos/"
            for picture in pet["fields"].get("Pictures", []):
                photo_filename = picture["filename"]
                photo_filename = photo_filename.replace(" ", "_")
                photo_filename = photo_filename.replace("%20", "_")
                pictures.append(url + pet["id"] + "/" + photo_filename)

            if pictures:
                pet_row[indexes["photo1"]] = pictures.pop(0)
            if pictures:
                pet_row[indexes["photo2"]] = pictures.pop(0)
            if pictures:
                pet_row[indexes["photo3"]] = pictures.pop(0)
            if pictures:
                pet_row[indexes["photo4"]] = pictures.pop(0)

            pet_row = fix_unknowns(pet_row, indexes)

            writer.writerow(pet_row)

        if not pets_found:
            # for empty pet list
            logger.info("No adoptable pets found")

            pet_row = [None for _ in range(len(CSV_HEADERS))]

            pet_row[indexes["id"]] = "1"
            pet_row[indexes["name"]] = "Temporary Deleted Dog"
            pet_row[indexes["status"]] = "Deleted"
            pet_row[indexes["species"]] = "Dog"
            pet_row[indexes["breed"]] = "Beagle"
            pet_row[indexes["color"]] = "Tan"

            pet_row[indexes["dsc"]] = ""

            writer.writerow(pet_row)

        logger.info("Found %d dogs and %d cats adoptable", dog_count, cat_count)

        return filename


def fix_unknowns(
    pet_row: List[Optional[str]], indexes: Dict[str, int]
) -> List[Optional[str]]:
    """Change unknown fields to blank."""
    unknown_keys: List[int] = [
        indexes["utd"],
        indexes["fixed"],
        indexes["house"],
        indexes["declawed"],
        indexes["ok_dog"],
        indexes["ok_cat"],
        indexes["ok_kid"],
    ]

    for key in unknown_keys:
        if pet_row[key] == "Unknown":
            pet_row[key] = ""

    return pet_row


def upload_to_rescue_groups(csv_file: str) -> None:
    """Upload the new digs pets to rescuegroups.org."""
    logger.info("Uploading to RG")
    file_upload: str = str(config["local"]["FILEPATH"]) + csv_file
    try:
        with ftplib.FTP(
            "ftp.rescuegroups.org",
            config["rescuegroups"]["FTP_USERNAME"],
            config["rescuegroups"]["FTP_PASSWORD"],
            timeout=30,
        ) as ftp, open(file_upload, "rb") as file:
            ftp.cwd("import")
            ftp.storbinary(f"STOR {csv_file}", file)
    except Exception:
        logger.warning("Failed to upload to RG")
