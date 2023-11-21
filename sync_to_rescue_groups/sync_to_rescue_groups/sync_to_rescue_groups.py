"""
AWS lambda handler.

Airtable New Digs and Shelterluv to RescueGroups.org sync.
"""
import configparser
import csv
import ftplib
import logging
from typing import Any, Dict, List, Optional

import boto3
import requests

logger: logging.Logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

config = configparser.ConfigParser()
config.read("config.ini")

secrets_client = boto3.client("secretsmanager")

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

    try:
        # get the pets from Airtable
        airtable_pets: List[Dict[str, Any]] = get_airtable_pets()

        # create CSV file of available pets
        csv_file: str = create_new_digs_csv_file(airtable_pets)

        # upload CSV file to rescuegroups.org
        upload_to_rescue_groups(csv_file)

        # get the pets from Shelterluv
        shelterluv_pets: Dict[str, Any] = get_shelterluv_pets()

        # create CSV of Shelterluv pets
        csv_file_sl: str = create_sl_csv_file(shelterluv_pets)

        # upload to rescuegroups.org
        upload_to_rescue_groups(csv_file_sl)
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


def create_new_digs_csv_file(airtable_pets: List[Dict[str, Any]]) -> str:
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
            description = description.replace("\r", "&#10;")
            description = description.replace("\n", "&#10;")
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


def get_shelterluv_pets() -> List[Dict[str, Any]]:
    response = secrets_client.get_secret_value(SecretId="shelterluv_api_key")
    shelterluv_api_key = response["SecretString"]

    headers = {"x-api-key": shelterluv_api_key}
    offset = 0
    animals = []

    while 1:
        url = (
            "https://www.shelterluv.com/api/v1/"
            + "animals?status_type=publishable&offset="
            + str(offset)
        )
        response = requests.get(url, headers=headers)

        # check http response code
        if response.status_code != 200:
            logger.error(
                "Invalid response code from Shelterluv {}".format(response.status_code)
            )
            raise ValueError("Invalid response code from Shelterluv")

        response_json = response.json()

        if response_json["success"] != 1:
            logger.error("Invalid response from Shelterluv {}".format(response_json))
            raise ValueError("Invalid response from Shelterluv")

        total_count = response_json["total_count"]

        if total_count == "0":
            logger.error("No animals found from Shelterluv")
            raise ValueError("No animals found from Shelterluv")

        # add each animal to the dict
        for animal in response_json["animals"]:
            animals.append(animal)

        # check for more animals
        if response_json["has_more"]:
            offset += 100
        else:
            break

    # we should have all the animals now
    if str(len(animals)) != str(total_count):
        logger.error("something went wrong, missing animals from shelterluv")

    return animals


def create_sl_csv_file(pets: List[Dict[str, Any]]) -> str:
    """Create a CSV file of shelterluv pets."""
    # pylint: disable=too-many-statements
    filename: str = "pets.csv"
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
            "house": CSV_HEADERS.index("housebroken"),
            "age": CSV_HEADERS.index("age"),
            "needs": CSV_HEADERS.index("specialNeeds"),
            "fixed": CSV_HEADERS.index("altered"),
            "size": CSV_HEADERS.index("size"),
            "utd": CSV_HEADERS.index("uptodate"),
            "color": CSV_HEADERS.index("color"),
            "courtesy": CSV_HEADERS.index("courtesy"),
            "dsc": CSV_HEADERS.index("dsc"),
            "found": CSV_HEADERS.index("found"),
            "photo1": CSV_HEADERS.index("photo1"),
            "photo2": CSV_HEADERS.index("photo2"),
            "photo3": CSV_HEADERS.index("photo3"),
            "photo4": CSV_HEADERS.index("photo4"),
            "videoUrl": CSV_HEADERS.index("videoUrl"),
            "housebroken": CSV_HEADERS.index("housebroken"),
        }

        dog_count = 0
        cat_count = 0
        other_count = 0
        for pet in pets:
            pet_row: List[Optional[str]] = ["" for _ in range(len(CSV_HEADERS))]

            # grab the standard fields
            pet_row[indexes["id"]] = pet["ID"]
            pet_row[indexes["name"]] = pet.get("Name", "")
            pet_row[indexes["status"]] = "Available"
            pet_row[indexes["sex"]] = pet.get("Sex", "")
            pet_row[indexes["courtesy"]] = "No"
            pet_row[indexes["utd"]] = "Yes"

            # deal with fields that are more annoying
            description: str = pet.get("Description", "")
            description = description.replace("\r", "&#10;")
            description = description.replace("\n", "&#10;")
            pet_row[indexes["dsc"]] = description

            breed = pet.get("Breed", "")
            if breed is None:
                breed = ""
            breeds = breed.split("/")
            first_breed = breeds[0]
            pet_row[indexes["breed"]] = sl_breed_to_rg_breed(first_breed)
            if len(breeds) > 1:
                pet_row[indexes["mix"]] = "Yes"
            else:
                pet_row[indexes["mix"]] = "No"

            species = pet.get("Type")
            if species == "Dog":
                color = pet.get("Color", "")
                color = sl_color_to_rg_color(color, "Dog")
                pet_row[indexes["color"]] = color
                dog_count += 1
            elif species == "Cat":
                color = pet.get("Color", "")
                color = sl_color_to_rg_color(color, "Cat")
                pet_row[indexes["color"]] = color
                cat_count += 1
            elif species == "Pig":
                pet_row[indexes["breed"]] = "Pig"
                other_count += 1
            elif species == "Rabbit, Domestic":
                species = "Rabbit"
                other_count += 1
            else:
                other_count += 1

            pet_row[indexes["species"]] = species

            age_in_months = pet.get("Age")
            if age_in_months is not None:
                if age_in_months < 6:
                    pet_row[indexes["age"]] = "Baby"
                elif age_in_months < 18:
                    pet_row[indexes["age"]] = "Young"
                elif age_in_months < 84:
                    pet_row[indexes["age"]] = "Adult"
                else:
                    pet_row[indexes["age"]] = "Senior"

            size = pet.get("Size")
            if size is not None:
                if "small" in size.lower():
                    pet_row[indexes["size"]] = "Small"
                elif "medium" in size.lower():
                    pet_row[indexes["size"]] = "Medium"
                elif "large" in size.lower():
                    if "x" in size.lower():
                        pet_row[indexes["size"]] = "X-Large"
                    else:
                        pet_row[indexes["size"]] = "Large"

            if pet.get("Altered") == "Yes":
                pet_row[indexes["fixed"]] = "Yes"

            photos = pet.get("Photos", [])
            if len(photos) > 0:
                pet_row[indexes["photo1"]] = photos[0]
            if len(photos) > 1:
                pet_row[indexes["photo2"]] = photos[1]
            if len(photos) > 2:
                pet_row[indexes["photo3"]] = photos[2]
            if len(photos) > 3:
                pet_row[indexes["photo4"]] = photos[3]

            videos = pet.get("Videos", [])

            if len(videos) > 0:
                video = videos[0]
                pet_row[indexes["videoUrl"]] = video.get("YoutubeUrl", "")

            attributes = pet.get("Attributes", [])
            attributes = [attribute.get("Internal-ID") for attribute in attributes]

            if "14835" in attributes or "14839" in attributes:
                pet_row[indexes["housebroken"]] = "Yes"

            if "14842" in attributes:
                pet_row[indexes["ok_dog"]] = "Yes"
            
            if "14841" in attributes:
                pet_row[indexes["ok_cat"]] = "Yes"

            if "14840" in attributes:
                pet_row[indexes["ok_kid"]] = "Yes"

            writer.writerow(pet_row)

        logger.info(
            "Found %d dogs, %d cats, %d other adoptable", 
            dog_count, cat_count, other_count,
        )

        return filename
    

def sl_breed_to_rg_breed(breed: str) -> str:
    breed_map = {
        # DOGS
        "American Blue Heeler": "Australian Cattle Dog/Blue Heeler",
        "Brasileiro, Fila": "Fila Brasileiro",
        "Buhund, Norwegian": "Norwegian Buhund",
        "Bulldog": "American Bulldog",
        "Bulldog, American": "American Bulldog",
        "Bulldog, English": "English Bulldog",
        "Bulldog, French": "French Bulldog",
        "Bulldog, Old English": "English Bulldog",
        "Canario, Presa": "Presa Canario",
        "Cattle Dog, Australian (Blue Heeler)": "Australian Cattle Dog / Blue Heeler",
        "Cattle Dog, Australian (Red Heeler)": "Australian Cattle Dog / Blue Heeler",
        "Chihuahua, Long Coat": "Chihuahua",
        "Chihuahua, Short Coat": "Chihuahua",
        "Chinese Shar-Pei": "Shar-Pei",
        "Collie, Bearded": "Bearded Collie",
        "Collie, Border": "Border Collie",
        "Collie, Rough": "Rough Collie",
        "Collie, Smooth": "Collie",
        "Coonhound, Bluetick": "Bluetick Coonhound",
        "Coonhound, English": "English Coonhound",
        "Coonhound, Redbone": "Redbone Coonhound",
        "Coonhound, Treeing Walker": "Treeing Walker Coonhound",
        "Corgi, Pembroke": "Corgi",
        "Corgi, Pembroke Welsh": "Corgi",
        "Corgi, Welsh": "Corgi",
        "Coton De Tulear": "Coton de Tulear",
        "Dachshund, Miniature Long Haired": "Miniature Dachshund",
        "Dachshund, Miniature Smooth Haired": "Miniature Dachshund",
        "Dachshund, Miniature Wire Haired": "Miniature Dachshund",
        "Dachshund, Standard Long Haired": "Dachshund",
        "Dachshund, Standard Smooth Haired": "Dachshund",
        "Dachshund, Standard Wire Haired": "Dachshund",
        "Elkhound, Norwegian": "Norwegian Elkhound",
        "Eskimo, American": "American Eskimo Dog",
        "Flanders, Bouvier Des": "Bouvier des Flandres",
        "Foxhound, American": "American Foxhound",
        "Foxhound, English": "English Foxhound",
        "Greyhound, Italian": "Italian Greyhound",
        "Griffon, Brussels": "Brussels Griffon",
        "Griffon, Petit Basset Vendeen": "Petit Basset Griffon Vendeen",
        "Griffon, Wire-Haired Pointing": "Wirehaired Pointing Griffon",
        "Hound, Afghan": "Afghan Hound",
        "Hound, Basset": "Basset Hound",
        "Hound, Black and Tan Coonhound": "Black and Tan Coonhound",
        "Hound, Bloodhound": "Bloodhound",
        "Hound, Halden (Haldenstover)": "Hound",
        "Hound, Ibizan": "Ibizan Hound",
        "Hound, Irish Wolfhound": "Irish Wolfhound",
        "Hound, Pharaoh": "Pharaoh Hound",
        "Hound, Plott": "Plott Hound",
        "Hound, Scottish Deerhound": "Scottish Deerhound",
        "Husky, Alaskan": "Husky",
        "Husky, Siberian": "Siberian Husky",
        "Kelpie, Australian": "Australian Kelpie",
        "Korean Jindo": "Jindo",
        "Lapphund, Finnish": "Finnish Lapphund",
        "Löwchen": "Lowchen",
        "Lundehund, Norwegian": "Norwegian Lundehund",
        "Malamute, Alaskan": "Alaskan Malamute",
        "Malinois, Belgian": "Belgian Shepherd / Malinois",
        "Mastiff, Bullmastiff": "Bullmastiff",
        "Mastiff, Cane Corso": "Cane Corso",
        "Mastiff, Neapolitan": "Neapolitan Mastiff",
        "Mastiff, Tibetan": "Tibetan Mastiff",
        "Mixed Breed (Large)": "Mixed Breed",
        "Mixed Breed (Medium)": "Mixed Breed",
        "Mixed Breed (Small)": "Mixed Breed",
        "Newfoundland": "Newfoundland Dog",
        "Pei, Shar": "Shar-Pei",
        "Pinscher, Doberman": "Doberman Pinscher",
        "Pinscher, German": "German Pinscher",
        "Pinscher, Miniature": "Miniature Pinscher",
        "Pointer, English": "English Pointer",
        "Pointer, German Shorthaired": "German Shorthaired Pointer",
        "Pointer, German Wirehaired": "German Wirehaired Pointer",
        "Poodle, Miniature": "Miniature Poodle",
        "Poodle, Standard": "Standard Poodle",
        "Poodle, Toy": "Poodle",
        "Pyrenees, Great": "Great Pyrenees",
        "Retriever, Black Labrador": "Black Labrador Retriever",
        "Retriever, Chesapeake Bay": "Chesapeake Bay Retriever",
        "Retriever, Chocolate Labrador": "Chocolate Labrador Retriever",
        "Retriever, Curly-Coated": "Curly-Coated Retriever",
        "Retriever, Flat-Coated": "Flat-Coated Retriever",
        "Retriever, Golden": "Golden Retriever",
        "Retriever, Labrador": "Labrador Retriever",
        "Retriever, Nova Scotia Duck-Tolling": "Nova Scotia Duck Tolling Retriever",
        "Retriever, Yellow Labrador": "Yellow Labrador Retriever",
        "Ridgeback, Rhodesian": "Rhodesian Ridgeback",
        "Ridgeback, Thai": "Thai Ridgeback",
        "Schnauzer, Giant": "Giant Schnauzer",
        "Schnauzer, Miniature": "Miniature Schnauzer",
        "Schnauzer, Standard": "Standard Schnauzer",
        "Scottish Terrier": "Scottish Terrier Scottie",
        "Setter, English": "English Setter",
        "Setter, Gordon": "Gordon Setter",
        "Setter, Irish": "Irish Setter",
        "Sheepdog, Caucasian Ovtcharka": "Caucasian Sheepdog / Caucasian Ovtcharka",
        "Sheepdog, Mcnab": "McNab",
        "Sheepdog, Old English": "Old English Sheepdog",
        "Sheepdog, Polish Lowland": "Polish Lowland Sheepdog",
        "Sheepdog, Shetland": "Shetland Sheepdog / Sheltie",
        "Shepherd, Anatolian": "Anatolian Shepherd",
        "Shepherd, Australian": "Australian Shepherd",
        "Shepherd, Belgian Malinois": "Belgian Shepherd / Malinois",
        "Shepherd, Belgian Sheepdog": "Belgian Shepherd / Sheepdog",
        "Shepherd, Belgian Tervuren": "Belgian Shepherd / Tervuren",
        "Shepherd, Dutch": "Dutch Shepherd",
        "Shepherd, English": "English Shepherd",
        "Shepherd, German": "German Shepherd Dog",
        "Shepherd, German King": "German Shepherd Dog",
        "Shepherd, White German": "White German Shepherd",
        "Spaniel, American Cocker": "Cocker Spaniel",
        "Spaniel, American Water": "American Water Spaniel",
        "Spaniel, Brittany": "Brittany Spaniel",
        "Spaniel, Cavalier King Charles": "Cavalier King Charles Spaniel",
        "Spaniel, Clumber": "Clumber Spaniel",
        "Spaniel, Cocker": "Cocker Spaniel",
        "Spaniel, English Cocker": "English Cocker Spaniel",
        "Spaniel, English Springer": "English Springer Spaniel",
        "Spaniel, English Toy": "English Toy Spaniel",
        "Spaniel, Irish Water": "Irish Water Spaniel",
        "Spaniel, Sussex": "Sussex Spaniel",
        "Spaniel, Tibetan": "Tibetan Spaniel",
        "Spaniel, Welsh Springer": "Welsh Springer Spaniel",
        "Spinone, Italian": "Spinone Italiano",
        "Spitz, Finnish": "Finnish Spitz",
        "Spitz, German": "German Spitz",
        "Taiwanese Mountain Dog": "Mountain Dog",
        "Terrier, Airedale": "Airedale Terrier",
        "Terrier, American Hairless": "American Hairless Terrier",
        "Terrier, American Pit Bull": "Pit Bull Terrier",
        "Terrier, American Staffordshire": "American Staffordshire Terrier",
        "Terrier, Australian": "Australian Terrier",
        "Terrier, Bedlington": "Bedlington Terrier",
        "Terrier, Black Russian": "Black Russian Terrier",
        "Terrier, Border": "Border Terrier",
        "Terrier, Boston": "Boston Terrier",
        "Terrier, Bull": "Bull Terrier",
        "Terrier, Cairn": "Cairn Terrier",
        "Terrier, Dandi Dinmont": "Dandie Dinmont Terrier",
        "Terrier, Fox": "Fox Terrier",
        "Terrier, Fox, Smooth": "Fox Terrier",
        "Terrier, Glen of Imaal": "Glen of Imaal Terrier",
        "Terrier, Irish": "Irish Terrier",
        "Terrier, Jack Russell": "Jack Russell Terrier",
        "Terrier, Kerry Blue": "Kerry Blue Terrier",
        "Terrier, Lakeland": "Lakeland Terrier",
        "Terrier, Manchester": "Manchester Terrier",
        "Terrier, Norfolk": "Norfolk Terrier",
        "Terrier, Norwich": "Norwich Terrier",
        "Terrier, Parson Jack Russell": "Parson Russell Terrier",
        "Terrier, Patterdale (Fell)": "Patterdale Terrier / Fell Terrier",
        "Terrier, Pit Bull": "Pit Bull Terrier",
        "Terrier, Rat": "Rat Terrier",
        "Terrier, Scottish Scottie": "Scottish Terrier Scottie",
        "Terrier, Sealyham": "Sealyham Terrier",
        "Terrier, Silky": "Silky Terrier",
        "Terrier, Skye": "Skye Terrier",
        "Terrier, Smooth Fox": "Fox Terrier",
        "Terrier, Soft Coated Wheaten": "Wheaten Terrier",
        "Terrier, Staffordshire Bull": "Staffordshire Bull Terrier",
        "Terrier, Tibetan": "Tibetan Terrier",
        "Terrier, Toy Fox": "Toy Fox Terrier",
        "Terrier, Welsh": "Welsh Terrier",
        "Terrier, West Highland White Westie": "West Highland White Terrier / Westie",
        "Terrier, Wheaten": "Wheaten Terrier",
        "Terrier, Wire Fox": "Wire Fox Terrier",
        "Terrier, Wirehaired": "Wirehaired Terrier",
        "Terrier, Yorkshire, Yorkie": "Yorkshire Terrier",
        "Unknown": "Mixed Breed",
        "Vallhund, Swedish": "Swedish Vallhund",
        "Vizsla, Smooth Haired": "Vizsla",
        "Water Dog, Portuguese": "Portuguese Water Dog",
        "Wolfhound, Irish": "Irish Wolfhound",
        "Xoloitzcuintle (Mexican Hairless)": "Xoloitzcuintli / Mexican Hairless",

        # CATS      
        "American Bobtail": "Bobtail",
        "Domestic Longhair": "Domestic Long Hair",       
        "Domestic Shorthair": "Domestic Short Hair",  
        "Havana Brown": "Havana",
        "Laperm": "LaPerm",
        "Sphynx": "Sphynx (hairless cat)",
    }

    return breed_map.get(breed, breed)


def sl_color_to_rg_color(color: str, species: str) -> str:
    colors = color.split("/")
    color = colors[0]

    dog_colors = {
        "Apricot": "Golden/Chestnut",
        "Beige": "Tan",
        "Blond": "Fawn",
        "Blue": "Blue/Silver/Salt & Pepper",
        "Blue Black": "Blue/Silver/Salt & Pepper",
        "Brown": "Brown/Chocolate",
        "Chocolate": "Brown/Chocolate",
        "Cream": "Fawn",
        "Golden": "Golden/Chestnut",
        "Grey": "Gray",
        "Red/Mahogany": "Red",
        "Sandy": "Tan",
        "Silver": "Gray",
        "Wheaten": "Golden/Chestnut",
    }

    cat_colors = {
        "Albino": "White",
        "Apricot": "Tan",
        "Blonde": "Cream",
        "Blue Black": "Blue (Mostly)",
        "Buff": "Cream",
        "Calico": "Calico or Dilute Calico",
        "Charcoal": "Gray",
        "Copper": "Orange",
        "Ebony": "Black",
        "Flame": "Orange",
        "Grey": "Gray",
        "Lilac": "Cream",
        "Liver": "Brown",
        "Lynx": "Gray",
        "Mahogany": "Brown",
        "Ruddy": "Red",
        "Rust": "Red",
        "Sable": "Fawn",
        "Salt & Pepper": "Black and White",
        "Seal": "White (Mostly)",
        "Shaded Blue Cream Cameo": "Blue (Mostly)",
        "Silver Black": "Gray and White",
        "Silver": "Gray",
        "Smoke": "Gray",
        "Torbie": "Red Tabby",
        "Tortoise": "Tortoiseshell",
        "Wheaten": "Tan",
        "Yellow": "Fawn",
    }

    if species == "Dog" and color in dog_colors:
        return dog_colors[color]
    elif species == "Cat" and color in cat_colors:
        return cat_colors[color]
    else:
        return color
