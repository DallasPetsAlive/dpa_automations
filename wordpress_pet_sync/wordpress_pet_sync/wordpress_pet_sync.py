import boto3
import botocore
import html
import json
import logging
import mimetypes
import re
from typing import Any, Dict, List

import requests
from cerealbox.dynamo import from_dynamodb_json

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

secrets_client = boto3.client("secretsmanager")
dynamodb_client = boto3.client("dynamodb")


def handler(event: Dict[str, Any], _: Any) -> None:
    logging.info("sync received event: {}".format(event))

    wordpress_sync = WordpressSync()

    wordpress_sync.get_token()
    wordpress_sync.get_dynamodb_pets()
    wordpress_sync.get_wordpress_pets()
    wordpress_sync.delete_pets()
    wordpress_sync.create_pets()
    wordpress_sync.update_pets()

class WordpressSync:
    token: str
    dynamodb_pets: List[Dict[str, any]]
    wordpress_pets: List[Dict[str, any]]
    dynamodb_ids: List[str]
    wordpress_ids: List[str]

    def get_token(self) -> None:
        credentials = json.loads(secrets_client.get_secret_value(SecretId="wordpress_credentials")["SecretString"])
        username = credentials["username"]
        password = credentials["password"]

        response = requests.post(
            "https://dallaspetsalive.org/wp-json/api/v1/token",
            data={"username": username, "password": password},
        )
        if response.status_code != 200:
            raise Exception("Could not get token: {}".format(response.text))
        self.token = response.json()["jwt_token"]

    def get_dynamodb_pets(self) -> None:
        pets = []
        self.dynamodb_ids = []

        try:
            response = dynamodb_client.scan(
                TableName="Pets",
            )

            if "Items" not in response:
                logger.error("No pets found")
                return None

            pets = response["Items"]

            while lastKey := response.get("LastEvaluatedKey"):
                response = dynamodb_client.scan(
                    TableName="Pets",
                    ExclusiveStartKey=lastKey,
                )
                pets.extend(response["Items"])
        except botocore.exceptions.ClientError:
            logger.exception("client error")
            raise

        formatted_pets = []
        for pet in pets:
            pet_formatted = from_dynamodb_json(pet)
            formatted_pets.append(pet_formatted)
            self.dynamodb_ids.append(pet_formatted["id"])

        if not formatted_pets:
            raise Exception("No pets found")

        logger.info("got {} pets from dynamodb".format(len(formatted_pets)))

        self.dynamodb_pets = formatted_pets

    def get_wordpress_pets(self):
        pets = []
        self.wordpress_ids = []

        offset = 0
        while response := requests.get(
            "https://dallaspetsalive.org/wp-json/wp/v2/pet?offset={}".format(offset),
            headers={"Authorization": "Bearer {}".format(self.token)}
        ).json():
            pets.extend(response)
            offset += len(response)

        for pet in pets:
            self.wordpress_ids.append(pet.get("acf", {}).get("id"))

        logger.info("got {} pets from wordpress".format(len(pets)))

        self.wordpress_pets = pets
        
    def delete_pets(self):
        # delete any wordpress pets that are no longer in dynamodb
        deleted_pets = [pet for pet in self.wordpress_ids if pet not in self.dynamodb_ids]

        if not deleted_pets:
            logger.info("no pets to delete")
            return
        
        logger.info("deleting {} pets".format(len(deleted_pets)))
        for pet in self.wordpress_pets:
            if pet.get("acf", {}).get("id") in deleted_pets:
                logger.debug("deleting {}".format(pet.get("acf", {}).get("id")))
                response = requests.delete(
                    "https://dallaspetsalive.org/wp-json/wp/v2/pet/{}?force=true".format(pet["id"]),
                    headers={"Authorization": "Bearer {}".format(self.token)},
                )
                if response.status_code != 200:
                    logger.error("could not delete pet post {}: {}".format(pet["id"], response.text))

    def create_pets(self):
        # create pets in wordpress that are in dynamodb but not wordpress
        pets_to_add = [pet for pet in self.dynamodb_ids if pet not in self.wordpress_ids]

        logger.info("creating {} pets".format(len(pets_to_add)))

        for pet in self.dynamodb_pets:
            if pet["id"] in pets_to_add:
                logger.debug("creating {}".format(pet["id"]))

                # get the cover photo
                cover_photo_id = None
                if coverPhoto := pet.get("coverPhoto"):
                    cover_photo_id = self.upload_featured_photo(coverPhoto)
                    if cover_photo_id == -1:
                        continue

                attributes = []

                age_attributes = {
                    "Baby": 264,
                    "Young": 267,
                    "Adult": 260,
                    "Senior": 261,
                }

                if pet.get("age") and pet.get("age") in age_attributes:
                    attributes.append(age_attributes[pet.get("age")])

                sex_attributes = {
                    "Female": 262,
                    "Male": 265,
                }

                if pet.get("sex") and pet.get("sex") in sex_attributes:
                    attributes.append(sex_attributes[pet.get("sex")])

                size_attributes = {
                    "Small": 268,
                    "Medium": 266,
                    "Large": 263,
                    "Extra-Large": 269,
                }

                if pet.get("size") and pet.get("size") in size_attributes:
                    attributes.append(size_attributes[pet.get("size")])

                pet_data = {
                    "status": "publish",
                    "title": pet["name"],
                    "content": pet["description"],
                    "featured_media": cover_photo_id,
                    "acf": {
                        "id": pet.get("id"),
                        "age": pet.get("age"),
                        "breed": pet.get("breed"),
                        "color": pet.get("color"),
                        "adoptLink": pet.get("adoptLink"),
                        "internalId": pet.get("internalId"),
                        "name": pet.get("name"),
                        "sex": pet.get("sex"),
                        "size": pet.get("size"),
                        "species": pet.get("species"),
                        "source": pet.get("source"),
                        "status": pet.get("status"),
                    },
                    "pet-attributes": attributes,
                }

                for photo_num, photo in enumerate(pet.get("photos", [])):
                    pet_data["acf"]["photos_{}".format(photo_num)] = photo

                response = requests.post(
                    "https://dallaspetsalive.org/wp-json/wp/v2/pet",
                    headers={
                        "Authorization": "Bearer {}".format(self.token),
                    },
                    json=pet_data,
                )

                if response.status_code != 201:
                    logger.error("could not create pet {}: {}".format(pet_data, response.text))
                    continue

    def update_pets(self):
        pets_to_maybe_update = [pet for pet in self.wordpress_ids if pet in self.dynamodb_ids]

        for dynamodb_pet in self.dynamodb_pets:
            if dynamodb_pet["id"] not in pets_to_maybe_update:
                continue

            new_pet_data = {}

            for wordpress_pet in self.wordpress_pets:
                if wordpress_pet.get("acf", {}).get("id") != dynamodb_pet["id"]:
                    continue

                wordpress_title = self.convert_wordpress_content(wordpress_pet.get("title", {}).get("rendered"))

                if wordpress_title != dynamodb_pet["name"].strip():
                    logger.debug("renaming from {}".format(wordpress_title))
                    new_pet_data["title"] = dynamodb_pet["name"].strip()

                wordpress_description = self.strip_description(self.convert_wordpress_content(wordpress_pet.get("content", {}).get("rendered")))

                if wordpress_description != self.strip_description(dynamodb_pet["description"].strip()):
                    logger.debug("updating description from {}".format(wordpress_pet.get("content", {}).get("rendered")))
                    new_pet_data["content"] = dynamodb_pet["description"].strip()

                last_index = 0
                for index, photo in enumerate(dynamodb_pet.get("photos", [])):
                    last_index += 1
                    if index > 19:
                        break
                    if f"photos_{index}" not in wordpress_pet.get("acf", {}):
                        logger.debug("adding photo {}".format(photo))
                        if "acf" not in new_pet_data:
                            new_pet_data["acf"] = {}
                        new_pet_data["acf"][f"photos_{index}"] = photo
                    elif wordpress_pet.get("acf", {}).get(f"photos_{index}") != photo:
                        logger.debug("updating photo {}".format(photo))
                        if "acf" not in new_pet_data:
                            new_pet_data["acf"] = {}
                        new_pet_data["acf"][f"photos_{index}"] = photo

                        if index == 0:
                            logger.debug("updating featured photo {}".format(photo))

                            photo_id = self.upload_featured_photo(photo)
                            if photo_id != -1:
                                new_pet_data["featured_media"] = photo_id

                while wordpress_pet.get("acf", {}).get(f"photos_{last_index + 1}"):
                    logger.debug("removing photo {}".format(wordpress_pet.get("acf", {}).get(f"photos_{last_index + 1}")))
                    if "acf" not in new_pet_data:
                        new_pet_data["acf"] = {}
                    new_pet_data["acf"][f"photos_{last_index + 1}"] = ""
                    last_index += 1

                break
            
            if new_pet_data:
                logger.info("updating ID {} data {}".format(dynamodb_pet["id"], new_pet_data))

                response = requests.post(
                    "https://dallaspetsalive.org/wp-json/wp/v2/pet/{}".format(wordpress_pet["id"]),
                    headers={
                        "Authorization": "Bearer {}".format(self.token),
                    },
                    json=new_pet_data,
                )

                if response.status_code != 200:
                    logger.error("could not update pet {}: {}".format(new_pet_data, response.text))
                    continue

    @staticmethod
    def convert_wordpress_content(content: str) -> str:
        content = html.unescape(content)
        content = content.replace("”", "\"")
        content = content.replace("“", "\"")
        content = content.replace("’", "'")
        content = content.replace("</p>\n<p>", "\\n\\n")
        content = content.replace("<p>", "")
        content = content.replace("</p>", "")
        content = content.replace("– ", "- ")
        return content

    @staticmethod
    def strip_description(description: str) -> str:
        description = description.replace("\\n", "")
        description = description.replace("\\r", "")
        description = description.replace("<br", "")
        description = re.sub(r'\W+', '', description)
        return description

    def upload_featured_photo(self, photoUrl: str) -> int:
        response = requests.get(photoUrl, stream=True)
        if response.status_code != 200:
            logger.error("could not get cover photo {}: {}".format(photoUrl, response.text))
            return -1

        cover_photo = response.raw.read()

        filename = photoUrl.split("/")[-1]
        content_type = mimetypes.guess_type(filename)

        # create the media for the cover photo
        response = requests.post(
            "https://dallaspetsalive.org/wp-json/wp/v2/media",
            headers={
                "Authorization": "Bearer {}".format(self.token),
                "Content-Disposition": "attachment; filename={}".format(filename),
                "Content-Type": content_type[0],
            },
            data=cover_photo,
        )

        if response.status_code != 201:
            logger.error("could not upload cover photo {}: {}".format(photoUrl, response.text))
            return -1
    
        return response.json()["id"]
