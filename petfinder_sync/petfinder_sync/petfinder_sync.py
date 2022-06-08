import configparser
import datetime
import logging
from typing import Any, Dict, List, Tuple

import requests

from . import constants

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


def handler(event: Dict[str, Any], _: Any) -> None:
    logging.info("sync received event: {}".format(event))

    config = configparser.ConfigParser()
    config.read("config.ini")
    assert "shelterluv" in config.sections()
    assert "airtable" in config.sections()
    shelterluv_key: str = config["shelterluv"]["SHELTERLUV_API_KEY"]
    airtable_section: configparser.SectionProxy = config["airtable"]

    shelterluv_pets: Dict[str, Any] = get_shelterluv_pets(shelterluv_key)
    airtable_pets: Dict[str, Any] = get_airtable_pets(airtable_section)

    shelterluv_pets_list: List[Dict[str, Any]] = shelterluv_to_csv(shelterluv_pets)
    airtable_pets_list: List[Dict[str, Any]] = airtable_to_csv(airtable_pets)

    animals = shelterluv_pets_list + airtable_pets_list

    send_csv_file(animals)


def get_shelterluv_pets(shelterluv_key: str) -> Dict[str, Any]:

    headers: Dict[str, str] = {"x-api-key": shelterluv_key}
    offset = 0
    total_count = 0
    animals = {}

    url = "https://www.shelterluv.com/api/v1/animals?status_type=publishable"

    while response := requests.get(url, headers=headers):

        # check http response code
        if response.status_code != 200:
            logger.error("invalid response code")
            raise requests.RequestException(response)

        response_json = response.json()

        if response_json["success"] != 1:
            logger.error(response_json.get("error_message"))
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


def get_airtable_pets(airtable_section: Any) -> Dict[str, Any]:
    """Get the new digs pets from Airtable."""
    url = "https://api.airtable.com/v0/" + airtable_section["BASE"] + "/Pets"
    headers = {"Authorization": "Bearer " + airtable_section["AIRTABLE_API_KEY"]}

    response = requests.get(url, headers=headers)
    if response.status_code != requests.codes.ok:
        logger.error("Airtable response: ")
        logger.error(response)
        logger.error("URL: %s", url)
        logger.error("Headers: %s", str(headers))
        raise requests.RequestException(
            "invalid airtable response {}".format(response.status_code)
        )

    airtable_response = response.json()

    airtable_pets = {}

    for pet in airtable_response.get("records", []):
        if "Published - Available" in pet.get("fields").get("Status"):
            airtable_pets[pet["id"]] = pet["fields"]

    return airtable_pets


def shelterluv_to_csv(shelterluv_pets: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert the shelterluv pets to a list of dicts formatted for CSV."""
    animals = []

    for id, fields in shelterluv_pets.items():

        if fields.get("Breed") is None:
            logger.error("no breed found for animal {}".format(id))
            continue

        first_breed, second_breed = get_breed_from_shelterluv(
            fields["Breed"], fields["Type"]
        )
        photos = get_photos_from_shelterluv(fields)
        needs, needs_notes = get_special_needs_from_shelterluv(fields)
        first_color, second_color = get_colors_from_shelterluv(
            fields["Color"], fields["Type"]
        )

        animal = {
            "ID": "DPA-A-" + id,
            "Internal": "",
            "AnimalName": fields["Name"],
            "PrimaryBreed": first_breed,
            "SecondaryBreed": "" if second_breed == "Mix" else second_breed,
            "Sex": "M" if fields["Sex"] == "Male" else "F",
            "Size": get_size_from_shelterluv(fields["Size"]),
            "Age": get_age_from_shelterluv(fields["Age"]),
            "Desc": fields["Description"].replace("\n", "&#10;"),
            "Type": get_type_from_shelterluv(fields["Type"]),
            "Status": "A",
            "Shots": "1",
            "Altered": "1" if fields["Altered"] == "Yes" else "",
            "NoDogs": get_no_dogs_from_shelterluv(fields),
            "NoCats": get_no_cats_from_shelterluv(fields),
            "NoKids": get_no_kids_from_shelterluv(fields),
            "Housetrained": get_housebroken_from_shelterluv(fields),
            "Declawed": get_declawed_from_shelterluv(fields),
            "specialNeeds": needs,
            "Mix": "1" if second_breed == "Mix" else "",
            "photo1": photos[0],
            "photo2": photos[1],
            "photo3": photos[2],
            "photo4": photos[3],
            "photo5": photos[4],
            "photo6": photos[5],
            "arrival_date": datetime.datetime.fromtimestamp(
                int(fields["LastIntakeUnixTime"])
            ).strftime("%Y-%m-%d"),
            "birth_date": datetime.datetime.fromtimestamp(
                int(fields["DOBUnixTime"])
            ).strftime("%Y-%m-%d"),
            "primaryColor": first_color,
            "secondaryColor": second_color,
            "tertiaryColor": "",
            "coat_length": "",
            "adoption_fee": int(fields.get("AdoptionFeeGroup", {}).get("Price")),
            "display_adoption_fee": "1",
            "adoption_fee_waived": "0",
            "special_needs_notes": needs_notes,
            "no_other": "",
            "no_other_note": "",
            "tags": "",
        }

        animals.append(animal)

    return animals


def airtable_to_csv(airtable_pets: Dict[str, Any]) -> List[Dict[str, Any]]:
    return []


def send_csv_file(pets: List[Dict[str, Any]]) -> None:
    pass


def get_colors_from_shelterluv(color: str, type: str) -> Tuple[str, str]:
    first_color = ""
    second_color = ""

    if color and "\\/" in color:
        first_color, second_color = color.split("\\/")
        if second_color == "None":
            second_color = ""
    elif color:
        first_color = color

    if type == "Cat":
        if first_color:
            if first_color in constants.SHELTERLUV_CAT_COLOR_MAPPING:
                first_color = constants.SHELTERLUV_CAT_COLOR_MAPPING[first_color]
            else:
                logger.error("no cat color mapping found for {}".format(first_color))
                first_color = ""
        if second_color:
            if second_color in constants.SHELTERLUV_CAT_COLOR_MAPPING:
                second_color = constants.SHELTERLUV_CAT_COLOR_MAPPING[second_color]
            else:
                logger.error("no cat color mapping found for {}".format(second_color))
                second_color = ""
    elif type == "Dog":
        if first_color:
            if first_color in constants.SHELTERLUV_DOG_COLOR_MAPPING:
                first_color = constants.SHELTERLUV_DOG_COLOR_MAPPING[first_color]
            else:
                logger.error("no dog color mapping found for {}".format(first_color))
                first_color = ""
        if second_color:
            if second_color in constants.SHELTERLUV_DOG_COLOR_MAPPING:
                second_color = constants.SHELTERLUV_DOG_COLOR_MAPPING[second_color]
            else:
                logger.error("no dog color mapping found for {}".format(second_color))
                second_color = ""
    else:
        logger.error("Unknown pet type {}".format(type))
        return "", ""

    return first_color, second_color


def get_photos_from_shelterluv(fields: Dict[str, Any]) -> List[str]:
    """Get the shelterluv photos for the animal."""
    photos = []

    if cover_photo := fields.get("CoverPhoto"):
        photos.append(cover_photo)

    for photo in fields["Photos"]:
        if photo == cover_photo:
            continue
        photos.append(photo)

    if len(photos) < 6:
        photos.extend(["", "", "", "", "", ""])

    return photos


def get_special_needs_from_shelterluv(fields: Dict[str, Any]) -> Tuple[str, str]:
    """Get the special needs value from the shelterluv fields."""
    needs = ""
    needs_notes = []

    special_needs_attributes = {
        "63371": "Blind",
        "63373": "Blind",
        "63372": "Deaf",
        "63374": "Deaf",
        "14854": "Medical Needs",
        "14832": "Medical Needs",
        "7320": "FIV+",
        "104077": "FIV+",
        "53439": "FIP+",
        "53438": "FeLV+",
        "14829": "Dietary Needs",
        "7317": "Dietary Needs",
        "18301": "Behavioral Needs",
        "18297": "Behavioral Needs",
        "67626": "Diabetic",
        "67627": "Diabetic",
        "14856": "Long Term Illness",
        "14834": "Long Term Illness",
        "14833": "Chronic Condition",
        "14855": "Chronic Condition",
        "14830": "Activity Needs",
        "14853": "Exercise/Activity Needs",
        "69442": "Hip Dysplasia",
    }

    attributes = fields["Attributes"]
    for attribute in attributes:
        if attribute["Internal-ID"] in special_needs_attributes:
            needs = "1"
            needs_notes.append(special_needs_attributes[attribute["Internal-ID"]])

    return needs, ", ".join(needs_notes) if needs_notes else ""


def get_declawed_from_shelterluv(fields: Dict[str, Any]) -> str:
    """Get the declawed value from the shelterluv fields."""
    attributes = fields["Attributes"]
    for attribute in attributes:
        if attribute["Internal-ID"] == "7319":
            return "1"
    return ""


def get_housebroken_from_shelterluv(fields: Dict[str, Any]) -> str:
    """Get the housebroken value from the shelterluv fields."""
    attributes = fields["Attributes"]
    for attribute in attributes:
        if attribute["Internal-ID"] in ("14835", "14839"):
            return "1"
    return ""


def get_no_dogs_from_shelterluv(fields: Dict[str, Any]) -> str:
    """Get the "good with dogs" value from the shelterluv fields."""
    attributes = fields["Attributes"]
    for attribute in attributes:
        if attribute["Internal-ID"] in ("14819", "14842"):
            # good with dogs
            return "0"
        if attribute["Internal-ID"] in ("52466", "14837"):
            # not good with dogs
            return "1"
    return ""


def get_no_cats_from_shelterluv(fields: Dict[str, Any]) -> str:
    """Get the "good with cats" value from the shelterluv fields."""
    attributes = fields["Attributes"]
    for attribute in attributes:
        if attribute["Internal-ID"] in ("14820", "14841"):
            # good with cats
            return "0"
        if attribute["Internal-ID"] in ("21523", "17159"):
            # not good with cats
            return "1"
    return ""


def get_no_kids_from_shelterluv(fields: Dict[str, Any]) -> str:
    """Get the "good with kids" value from the shelterluv fields."""
    attributes = fields["Attributes"]
    for attribute in attributes:
        if attribute["Internal-ID"] in ("14818", "14840"):
            # good with kids
            return "0"
        if attribute["Internal-ID"] in ("7316", "14836", "53437"):
            # not good with kids
            return "1"
    return ""


def get_age_from_shelterluv(age: int) -> str:
    """Convert the shelterluv age to a string."""
    if age < 6:
        return "Baby"
    elif age < 18:
        return "Young"
    elif age < 120:
        return "Adult"
    else:
        return "Senior"


def get_size_from_shelterluv(size: str) -> str:
    """Convert the shelterluv size to a Petfinder size."""
    if "Small" in size:
        return "S"
    elif "Medium" in size:
        return "M"
    elif "Extra" in size:
        return "XL"
    elif "Large" in size:
        return "L"
    else:
        logger.error("unknown size: {}".format(size))
        return "M"


def get_type_from_shelterluv(shelterluv_type: str) -> str:
    """Convert the shelterluv type to a type for Petfinder."""
    if shelterluv_type == "Small mammal":
        return "Small & Furry"
    if shelterluv_type == "Large mammal":
        return "Barnyard"
    if shelterluv_type == "Exotic/Other":
        return "Scales, Fins & Other"
    return shelterluv_type


def get_breed_from_shelterluv(breed: str, species: str) -> Tuple[str, str]:
    """Get the primary and secondary breed from the shelterluv breed."""
    primary, secondary = "", ""
    if breed.find("\\/") > -1:
        primary, secondary = breed.split("\\/")
    else:
        primary = breed

    if species == "Cat":
        if primary and primary in constants.SHELTERLUV_CAT_BREED_MAPPING:
            primary = constants.SHELTERLUV_CAT_BREED_MAPPING[primary]
        else:
            logger.error("no cat breed mapping found for {}".format(primary))
            primary = "Domestic Short Hair"
            secondary = "Mix"
        if secondary and secondary in constants.SHELTERLUV_CAT_BREED_MAPPING:
            secondary = constants.SHELTERLUV_CAT_BREED_MAPPING[secondary]
        elif secondary == "Mix":
            secondary = "Mix"
        elif not secondary:
            secondary = ""
        else:
            logger.error("no cat breed mapping found for {}".format(secondary))
            secondary = "Mix"
    elif species == "Dog":
        if primary and primary in constants.SHELTERLUV_DOG_BREED_MAPPING:
            primary = constants.SHELTERLUV_DOG_BREED_MAPPING[primary]
        else:
            logger.error("no dog breed mapping found for {}".format(primary))
            primary = "Mixed Breed"
            secondary = "Mix"
        if secondary and secondary in constants.SHELTERLUV_DOG_BREED_MAPPING:
            secondary = constants.SHELTERLUV_DOG_BREED_MAPPING[secondary]
            if secondary == "Mixed Breed":
                secondary = "Mix"
        elif secondary == "Mix":
            secondary = "Mix"
        elif not secondary:
            secondary = ""
        else:
            logger.error("no dog breed mapping found for {}".format(secondary))
            secondary = "Mix"

    return primary, secondary
