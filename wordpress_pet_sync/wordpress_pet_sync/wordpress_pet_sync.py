import base64
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
logging.getLogger("botocore").setLevel(logging.INFO)

secrets_client = boto3.client("secretsmanager")
dynamodb_client = boto3.client("dynamodb")
dynamodb_resource = boto3.resource("dynamodb")
photos_table = dynamodb_resource.Table("FeaturedPhotos")


def handler(event: Dict[str, Any], _: Any) -> None:
    logging.info("sync received event: {}".format(event))

    wordpress_sync = WordpressSync()

    wordpress_sync.get_dynamodb_pets()
    wordpress_sync.get_dynamodb_featured_photos()
    wordpress_sync.get_wordpress_pets()
    wordpress_sync.delete_pets()
    wordpress_sync.create_pets()
    wordpress_sync.update_pets()
    wordpress_sync.post_to_slack()


class WordpressSync:
    dynamodb_pets: List[Dict[str, any]]
    wordpress_pets: List[Dict[str, any]]
    dynamodb_ids: List[str]
    wordpress_ids: List[str]
    featured_photos: Dict[str, str]
    duplicate_wordpress_pets: List[Dict[str, any]]

    deleted_pets: List[str]
    added_pets: List[str]

    wordpress_header: Dict[str, str]

    def __init__(self):
        self.deleted_pets = []
        self.added_pets = []
        self.featured_photos = {}
        self.duplicate_wordpress_pets = []

        credentials = json.loads(secrets_client.get_secret_value(SecretId="wordpress_credentials")["SecretString"])
        username = credentials["username"]
        password = credentials["password"]

        wordpress_credentials = username + ":" + password
        token = base64.b64encode(wordpress_credentials.encode())
        self.wordpress_header = {"Authorization": "Basic " + token.decode("utf-8")}

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

    def get_dynamodb_featured_photos(self) -> None:
        photos = []
        try:
            response = dynamodb_client.scan(
                TableName="FeaturedPhotos",
            )

            if "Items" not in response:
                logger.error("No featured photos found")
                return None

            photos = response["Items"]

            while lastKey := response.get("LastEvaluatedKey"):
                response = dynamodb_client.scan(
                    TableName="FeaturedPhotos",
                    ExclusiveStartKey=lastKey,
                )
                photos.extend(response["Items"])
        except botocore.exceptions.ClientError:
            logger.exception("client error")
            raise

        for photo in photos:
            photo_formatted = from_dynamodb_json(photo)
            self.featured_photos[photo_formatted["id"]] = photo_formatted["photo"]

    def get_wordpress_pets(self):
        pets = []
        self.wordpress_ids = []

        offset = 0
        while response := requests.get(
            "https://dallaspetsalive.org/wp-json/wp/v2/pet?offset={}&order=asc".format(offset),
            headers=self.wordpress_header,
        ).json():
            if "status" in response and response["status"] == "error":
                raise Exception(
                    "Error fetching pets from Wordpress: {}".format(response.get("error_description", "Unknown error"))
                )
            pets.extend(response)
            offset += len(response)

        for pet in pets:
            id = pet.get("acf", {}).get("id")
            if id in self.wordpress_ids:
                self.duplicate_wordpress_pets.append(pet)
            self.wordpress_ids.append(id)

        logger.info("got {} pets from wordpress".format(len(pets)))

        self.wordpress_pets = pets

    def delete_pets(self):
        # delete any wordpress pets that are no longer in dynamodb
        deleted_pets = [pet for pet in self.wordpress_ids if pet not in self.dynamodb_ids]

        # delete any duplicate pets
        for pet in self.duplicate_wordpress_pets:
            logger.info("deleting duplicate pet {}".format(pet.get("slug")))

            response = requests.delete(
                "https://dallaspetsalive.org/wp-json/wp/v2/pet/{}?force=true".format(pet["id"]),
                headers=self.wordpress_header,
            )
            if response.status_code != 200:
                logger.error("could not delete pet post {}: {}".format(pet["id"], response.text))
                continue
            self.deleted_pets.append(pet["title"]["rendered"])

        if not deleted_pets:
            logger.info("no pets to delete")
            return

        logger.info("deleting {} pets".format(len(deleted_pets)))
        for pet in self.wordpress_pets:
            if pet.get("acf", {}).get("id") in deleted_pets:
                logger.debug("deleting {}".format(pet.get("acf", {}).get("id")))

                response = requests.delete(
                    "https://dallaspetsalive.org/wp-json/wp/v2/pet/{}?force=true".format(pet["id"]),
                    headers=self.wordpress_header,
                )
                if response.status_code != 200:
                    logger.error("could not delete pet post {}: {}".format(pet["id"], response.text))
                    continue
                self.deleted_pets.append(pet["title"]["rendered"])

    def create_pets(self):
        # create pets in wordpress that are in dynamodb but not wordpress
        pets_to_add = [pet for pet in self.dynamodb_ids if pet not in self.wordpress_ids]

        logger.info("creating {} pets".format(len(pets_to_add)))

        with photos_table.batch_writer() as batch:
            for pet in self.dynamodb_pets:
                if pet["id"] in pets_to_add:
                    logger.debug("creating {}".format(pet["id"]))

                    # get the cover photo
                    cover_photo_id = None
                    if coverPhoto := pet.get("coverPhoto"):
                        cover_photo_id = self.upload_featured_photo(coverPhoto)
                        if cover_photo_id == -1:
                            continue
                        batch.put_item(
                            Item={
                                "id": pet["id"],
                                "photo": coverPhoto,
                            }
                        )

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
                            "video": pet.get("video"),
                        },
                        "pet-attributes": attributes,
                    }

                    for photo_num, photo in enumerate(pet.get("photos", [])):
                        pet_data["acf"]["photos_{}".format(photo_num)] = photo

                    response = requests.post(
                        "https://dallaspetsalive.org/wp-json/wp/v2/pet",
                        headers=self.wordpress_header,
                        json=pet_data,
                    )

                    if response.status_code != 201:
                        logger.error("could not create pet {}: {}".format(pet_data, response.text))
                        continue
                    self.added_pets.append(pet["name"])

    def update_pets(self):
        pets_to_maybe_update = [pet for pet in self.wordpress_ids if pet in self.dynamodb_ids]

        with photos_table.batch_writer() as batch:
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

                    wordpress_description = self.strip_description(
                        self.convert_wordpress_content(wordpress_pet.get("content", {}).get("rendered"))
                    )

                    if dynamodb_pet["description"] and wordpress_description != self.strip_description(
                        dynamodb_pet["description"].strip()
                    ):
                        logger.debug(
                            "updating description from {}".format(wordpress_pet.get("content", {}).get("rendered"))
                        )
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

                    current_featured_photo = self.featured_photos.get(dynamodb_pet["id"])
                    incoming_current_photo = dynamodb_pet.get("coverPhoto")
                    if current_featured_photo != incoming_current_photo:
                        logger.debug("updating featured photo for id {}".format(dynamodb_pet["id"]))

                        photo_id = self.upload_featured_photo(incoming_current_photo)
                        if photo_id != -1:
                            new_pet_data["featured_media"] = photo_id
                            batch.put_item(
                                Item={
                                    "id": dynamodb_pet["id"],
                                    "photo": incoming_current_photo,
                                }
                            )

                    while wordpress_pet.get("acf", {}).get(f"photos_{last_index + 1}"):
                        logger.debug(
                            "removing photo {}".format(wordpress_pet.get("acf", {}).get(f"photos_{last_index + 1}"))
                        )
                        if "acf" not in new_pet_data:
                            new_pet_data["acf"] = {}
                        new_pet_data["acf"][f"photos_{last_index + 1}"] = ""
                        last_index += 1

                    if dynamodb_pet.get("coverPhoto") and not wordpress_pet.get("featured_media"):
                        logger.debug("updating featured photo {}".format(dynamodb_pet.get("coverPhoto")))

                        photo_id = self.upload_featured_photo(dynamodb_pet.get("coverPhoto"))
                        if photo_id != -1:
                            new_pet_data["featured_media"] = photo_id

                    for attribute in wordpress_pet.get("acf", {}):
                        if "photo" in attribute or attribute in [
                            "description",
                            "coverPhoto",
                        ]:
                            continue

                        wordpress_attribute = wordpress_pet["acf"].get(attribute)
                        dynamodb_attribute = dynamodb_pet.get(attribute)

                        if not wordpress_attribute and not dynamodb_attribute:
                            continue

                        if wordpress_attribute != dynamodb_attribute:
                            logger.debug(
                                "updating attribute {} for {}".format(
                                    attribute,
                                    wordpress_pet.get("title", {}).get("rendered"),
                                )
                            )
                            if "acf" not in new_pet_data:
                                new_pet_data["acf"] = {}
                            new_pet_data["acf"][attribute] = dynamodb_pet.get(attribute)

                    break

                if new_pet_data:
                    logger.info("updating ID {} data {}".format(dynamodb_pet["id"], new_pet_data))

                    response = requests.post(
                        "https://dallaspetsalive.org/wp-json/wp/v2/pet/{}".format(wordpress_pet["id"]),
                        headers=self.wordpress_header,
                        json=new_pet_data,
                    )

                    if response.status_code != 200:
                        logger.error("could not update pet {}: {}".format(new_pet_data, response.text))
                        continue

    @staticmethod
    def convert_wordpress_content(content: str) -> str:
        content = html.unescape(content)
        content = content.replace("”", '"')
        content = content.replace("“", '"')
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
        description = re.sub(r"\W+", "", description)
        return description

    def upload_featured_photo(self, photoUrl: str) -> int:
        if not photoUrl:
            return -1

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
                "Content-Disposition": "attachment; filename={}".format(filename),
                "Content-Type": content_type[0],
                **self.wordpress_header,
            },
            data=cover_photo,
        )

        if response.status_code != 201:
            logger.error("could not upload cover photo {}: {}".format(photoUrl, response.text))
            return -1

        return response.json()["id"]

    def post_to_slack(self):
        if not self.added_pets and not self.deleted_pets:
            return

        message = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "The following changes were sent to Wordpress:",
                    },
                },
                {
                    "type": "divider",
                },
            ],
        }

        if self.added_pets:
            message["blocks"].append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Added Pets*\n{}".format("\n".join(self.added_pets)),
                    },
                }
            )
            if self.deleted_pets:
                message["blocks"].append(
                    {
                        "type": "divider",
                    }
                )
        if self.deleted_pets:
            message["blocks"].append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Deleted Pets*\n{}".format("\n".join(self.deleted_pets)),
                    },
                }
            )

        webhook = json.loads(secrets_client.get_secret_value(SecretId="slack_alerts_webhook")["SecretString"])
        url = webhook.get("url")

        requests.post(
            url,
            json=message,
        )
