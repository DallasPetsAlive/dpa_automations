"""Test Shelterluv attribute mapping."""

from sync_to_rescue_groups.sync_to_rescue_groups import (
    CSV_HEADERS,
    clean_text,
    normalize_attribute_name,
    parse_sl_pet,
)


def make_pet(attributes):
    return {
        "ID": "47498",
        "Name": "Wally",
        "Type": "Dog",
        "Sex": "Male",
        "Breed": "Terrier, Jack Russell",
        "Photos": [],
        "Attributes": attributes,
    }


def attribute(internal_id, name, publish="Yes"):
    return {"Internal-ID": internal_id, "AttributeName": name, "Publish": publish}


def column(row, name):
    return row[CSV_HEADERS.index(name)]


def test_current_attribute_names():
    """Attributes recreated with new IDs are matched by name."""
    row, _ = parse_sl_pet(
        make_pet(
            [
                attribute("448580", "Dog: Good with Dogs"),
                attribute("122097", "Good with Cats"),
                attribute("448578", "Dog: Good with Kids"),
                attribute("448577", "Dog: Housebroken"),
            ]
        ),
        [],
    )

    assert column(row, "okwithdogs") == "Yes"
    assert column(row, "okwithcats") == "Yes"
    assert column(row, "okwithkids") == "Yes"
    assert column(row, "housebroken") == "Yes"


def test_current_attribute_ids():
    """Current Shelterluv IDs match even if the attribute gets renamed."""
    row, _ = parse_sl_pet(
        make_pet([attribute("448580", "Pup pal"), attribute("122172", "Potty pro")]),
        [],
    )

    assert column(row, "okwithdogs") == "Yes"
    assert column(row, "housebroken") == "Yes"


def test_unpublished_attribute_ids_ignored():
    row, _ = parse_sl_pet(make_pet([attribute("448580", "x", publish="No")]), [])

    assert column(row, "okwithdogs") == ""


def test_unpublished_and_partial_attributes_ignored():
    """Unpublished attributes and "some dogs" don't count."""
    row, _ = parse_sl_pet(
        make_pet(
            [
                attribute("122096", "Good with Dogs", publish="No"),
                attribute("31816", "Dog: Good with some Dogs"),
                attribute("122098", "Not Good with Cats"),
            ]
        ),
        [],
    )

    assert column(row, "okwithdogs") == ""
    assert column(row, "okwithcats") == ""


def test_no_attributes():
    row, _ = parse_sl_pet({**make_pet(None)}, [])

    assert column(row, "okwithdogs") == ""


def breeds_for(breed):
    row, _ = parse_sl_pet({**make_pet([]), "Breed": breed}, [])
    return column(row, "priBreed"), column(row, "secBreed"), column(row, "mix")


def test_secondary_breed():
    assert breeds_for("Husky/Bulldog, American") == ("Husky", "American Bulldog", "Yes")


def test_generic_mix_is_not_a_secondary_breed():
    assert breeds_for("Terrier, Pit Bull/Mix")[1:] == ("", "Yes")
    assert breeds_for("Shepherd, German/Mixed Breed (Medium)")[1:] == ("", "Yes")


def test_real_breed_preferred_as_primary():
    assert breeds_for("Mixed Breed (Large)/Mastiff")[:2] == ("Mastiff", "")


def test_single_breed():
    assert breeds_for("Domestic Shorthair") == ("Domestic Short Hair", "", "No")
    assert breeds_for("Mixed Breed (Medium)")[:2] == ("Mixed Breed", "")


def coat_for(species, breed):
    row, _ = parse_sl_pet({**make_pet([]), "Type": species, "Breed": breed}, [])
    return column(row, "coatLength")


def test_cat_coat_length_from_breed():
    assert coat_for("Cat", "Domestic Shorthair") == "Short"
    assert coat_for("Cat", "Domestic Medium Hair") == "Medium"
    assert coat_for("Cat", "Domestic Longhair") == "Long"
    assert coat_for("Cat", "Domestic Long Hair") == "Long"
    assert coat_for("Cat", "Siamese") == ""


def test_no_coat_length_for_dogs():
    assert coat_for("Dog", "Retriever, Labrador") == ""


def test_clean_text_removes_emojis():
    assert clean_text("Hi! 🐾🐾 I’m Wally ✨") == "Hi! I'm Wally"
    assert clean_text("Love ❤️ and 👍🏻 and 👨‍👩‍👧") == "Love and and"
    assert clean_text("Home 🏡\r\n\r\nSweet 💛") == "Home\r\n\r\nSweet"


def test_clean_text_replaces_curly_punctuation():
    assert clean_text("“Good boy” – sits—stays…") == '"Good boy" - sits - stays...'


def test_clean_text_makes_plain_ascii():
    assert clean_text("Kreme Brûlée, 90° © DPA") == "Kreme Brulee, 90 DPA"
    assert clean_text(None) == ""


def test_clean_text_emoji_bullets():
    assert clean_text("✅ Crate trained\n  🐾🐾 Loves walks\nNo emoji") == (
        "- Crate trained\n- Loves walks\nNo emoji"
    )
    assert clean_text("✨ The Highlights:\r\n✅ Chill\r") == "The Highlights:\r\n- Chill"


def test_clean_text_lone_emoji_line_is_not_a_bullet():
    assert clean_text("🐾 Meet Bambi!\n\nShe is sweet.\n\n💛 Adopt her today") == (
        "Meet Bambi!\n\nShe is sweet.\n\nAdopt her today"
    )


def test_clean_text_cotton_bio():
    """The bio that showed up garbled on Petfinder."""
    bio = (
        "Meet Cotton – Your Ultimate Snuggle Buddy! 🐾\n\n"
        "Cotton isn’t just a dog—she’s a warm hug.\n\n"
        "✨ The Highlights:\n"
        "✅ Super chill—naps are her jam.\n\n"
        "Adopt Cotton—because that’s just who she is. 🩷🐾"
    )

    assert clean_text(bio) == (
        "Meet Cotton - Your Ultimate Snuggle Buddy!\n\n"
        "Cotton isn't just a dog - she's a warm hug.\n\n"
        "The Highlights:\n"
        "- Super chill - naps are her jam.\n\n"
        "Adopt Cotton - because that's just who she is."
    )


def test_description_and_name_cleaned():
    row, _ = parse_sl_pet(
        {**make_pet([]), "Name": "Wally 🐶", "Description": "Sweet 💕 boy\nLoves walks"},
        [],
    )

    assert column(row, "name") == "Wally"
    assert column(row, "dsc") == "Sweet boy&#10;Loves walks"


def test_normalize_attribute_name():
    assert normalize_attribute_name("Dog:  Good with Dogs ") == "good with dogs"
    assert normalize_attribute_name("Cat: House-Trained") == "housetrained"
    assert normalize_attribute_name("Housetrained") == "housetrained"
    assert normalize_attribute_name(None) == ""
