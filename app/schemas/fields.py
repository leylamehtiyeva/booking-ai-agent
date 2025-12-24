from enum import Enum


class Field(str, Enum):
    """
    Canonical amenity / constraint fields.
    This is a CLOSED set. LLM is allowed to choose ONLY from this list.
    """

    # --- Cooking / Kitchen ---
    KITCHEN = "kitchen"
    KITCHENETTE = "kitchenette"
    STOVE_OR_HOB = "stove_or_hob"
    OVEN = "oven"
    MICROWAVE = "microwave"
    REFRIGERATOR = "refrigerator"
    COOKWARE = "cookware"
    KETTLE = "kettle"
    COFFEE_MACHINE = "coffee_machine"

    # --- Bathroom ---
    PRIVATE_BATHROOM = "private_bathroom"
    BATHTUB = "bathtub"
    SHOWER = "shower"
    HOT_WATER = "hot_water"
    TOWELS = "towels"
    HAIR_DRYER = "hair_dryer"
    TOILETRIES = "toiletries"

    # --- Comfort / Living ---
    WIFI = "wifi"
    AIR_CONDITIONING = "air_conditioning"
    HEATING = "heating"
    WASHING_MACHINE = "washing_machine"
    DRYER = "dryer"
    IRON = "iron"
    WORKSPACE = "workspace"
    ELEVATOR = "elevator"
    BALCONY = "balcony"

    # --- Policies ---
    NON_SMOKING = "non_smoking"
    PET_FRIENDLY = "pet_friendly"
    FREE_CANCELLATION = "free_cancellation"
    PAY_AT_PROPERTY = "pay_at_property"

    # --- Property type ---
    PROPERTY_APARTMENT = "property_apartment"
    PROPERTY_HOTEL = "property_hotel"
    PROPERTY_HOSTEL = "property_hostel"
    PROPERTY_HOUSE = "property_house"
