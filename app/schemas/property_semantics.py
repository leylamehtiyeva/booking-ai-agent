from __future__ import annotations

from enum import Enum


class PropertyType(str, Enum):
    APARTMENT = "apartment"
    HOTEL = "hotel"
    HOSTEL = "hostel"
    HOUSE = "house"
    APARTHOTEL = "aparthotel"
    GUESTHOUSE = "guesthouse"


class OccupancyType(str, Enum):
    ENTIRE_PLACE = "entire_place"
    PRIVATE_ROOM = "private_room"
    SHARED_ROOM = "shared_room"
    HOTEL_ROOM = "hotel_room"