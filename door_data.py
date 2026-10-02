"""Door constraint sites: the pairs of doors a seed may lock behind a Card Key, and where each door lives in the ROM.

Generated; do not edit. A site is the two faces of one way between two rooms. Each face
names its room, the RAM address of its entry in the room's coordinates table, the
index of its 12-byte entity template, the template itself, and whether other entities
use that template too. `weight` and `weight_pickups` rank the sites for the draw, without
and with the pickup checks."""

# room -> overlay, RAM address of the ARM9 pointer to its template table, the table, its
# length in templates, and the overlay's code and bss sizes
ROOMS = {
    "a01": {"overlay": 44, "slots_pointer": 0x020C9FE0, "slots": 0x02194758, "slot_count": 22, "size": 5344, "bss": 0},
    "a02": {"overlay": 45, "slots_pointer": 0x020C9FE4, "slots": 0x021953C0, "slot_count": 27, "size": 8800, "bss": 0},
    "a03": {"overlay": 46, "slots_pointer": 0x020C9FE8, "slots": 0x02194520, "slot_count": 14, "size": 3296, "bss": 0},
    "a04": {"overlay": 47, "slots_pointer": 0x020C9FEC, "slots": 0x02194100, "slot_count": 13, "size": 1792, "bss": 0},
    "b03": {"overlay": 50, "slots_pointer": 0x020C9FF8, "slots": 0x02194718, "slot_count": 16, "size": 4576, "bss": 0},
    "d01": {"overlay": 58, "slots_pointer": 0x020CA018, "slots": 0x02194C08, "slot_count": 24, "size": 5824, "bss": 0},
    "d02": {"overlay": 59, "slots_pointer": 0x020CA01C, "slots": 0x02195278, "slot_count": 22, "size": 9536, "bss": 0},
    "d03": {"overlay": 60, "slots_pointer": 0x020CA020, "slots": 0x02194430, "slot_count": 17, "size": 2592, "bss": 0},
    "e01": {"overlay": 63, "slots_pointer": 0x020CA02C, "slots": 0x021943E8, "slot_count": 14, "size": 2496, "bss": 0},
    "e02": {"overlay": 64, "slots_pointer": 0x020CA030, "slots": 0x02194E70, "slot_count": 26, "size": 5280, "bss": 0},
    "e04": {"overlay": 66, "slots_pointer": 0x020CA038, "slots": 0x02195A60, "slot_count": 27, "size": 9056, "bss": 32},
    "e05": {"overlay": 67, "slots_pointer": 0x020CA03C, "slots": 0x02194F70, "slot_count": 38, "size": 6592, "bss": 0},
    "e07": {"overlay": 69, "slots_pointer": 0x020CA044, "slots": 0x021949D8, "slot_count": 11, "size": 5088, "bss": 0},
    "e08": {"overlay": 70, "slots_pointer": 0x020CA048, "slots": 0x02194490, "slot_count": 13, "size": 2496, "bss": 0},
    "f01": {"overlay": 71, "slots_pointer": 0x020CA04C, "slots": 0x02194458, "slot_count": 18, "size": 2496, "bss": 0},
    "f02": {"overlay": 72, "slots_pointer": 0x020CA050, "slots": 0x021949A8, "slot_count": 18, "size": 4736, "bss": 0},
    "f03": {"overlay": 73, "slots_pointer": 0x020CA054, "slots": 0x02194A98, "slot_count": 19, "size": 6176, "bss": 0},
    "f04": {"overlay": 74, "slots_pointer": 0x020CA058, "slots": 0x021941F0, "slot_count": 14, "size": 1952, "bss": 0},
    "f05": {"overlay": 75, "slots_pointer": 0x020CA05C, "slots": 0x021949E0, "slot_count": 8, "size": 4672, "bss": 0},
    "g01": {"overlay": 76, "slots_pointer": 0x020CA060, "slots": 0x02194908, "slot_count": 20, "size": 4704, "bss": 0},
    "g02": {"overlay": 77, "slots_pointer": 0x020CA064, "slots": 0x021946D8, "slot_count": 36, "size": 4832, "bss": 0},
    "g03": {"overlay": 78, "slots_pointer": 0x020CA068, "slots": 0x021945D8, "slot_count": 16, "size": 2624, "bss": 0},
    "g04": {"overlay": 79, "slots_pointer": 0x020CA06C, "slots": 0x02194310, "slot_count": 15, "size": 2080, "bss": 0},
    "g05": {"overlay": 80, "slots_pointer": 0x020CA070, "slots": 0x02194D30, "slot_count": 28, "size": 6880, "bss": 0},
    "h01": {"overlay": 81, "slots_pointer": 0x020CA074, "slots": 0x0219843C, "slot_count": 27, "size": 19328, "bss": 32},
    "h02": {"overlay": 82, "slots_pointer": 0x020CA078, "slots": 0x02194924, "slot_count": 7, "size": 3200, "bss": 0},
    "h03": {"overlay": 83, "slots_pointer": 0x020CA07C, "slots": 0x02196A38, "slot_count": 22, "size": 12160, "bss": 32},
    "h04": {"overlay": 84, "slots_pointer": 0x020CA080, "slots": 0x02194E0C, "slot_count": 25, "size": 5152, "bss": 32},
    "i01": {"overlay": 85, "slots_pointer": 0x020CA084, "slots": 0x02194FD8, "slot_count": 35, "size": 6304, "bss": 32},
    "i02": {"overlay": 86, "slots_pointer": 0x020CA088, "slots": 0x02194AC0, "slot_count": 23, "size": 4736, "bss": 0},
    "i03": {"overlay": 87, "slots_pointer": 0x020CA08C, "slots": 0x02195A70, "slot_count": 16, "size": 10624, "bss": 32},
    "i05": {"overlay": 89, "slots_pointer": 0x020CA094, "slots": 0x021945B0, "slot_count": 28, "size": 3424, "bss": 0},
    "j01": {"overlay": 90, "slots_pointer": 0x020CA098, "slots": 0x02194360, "slot_count": 17, "size": 1920, "bss": 0},
    "j02": {"overlay": 91, "slots_pointer": 0x020CA09C, "slots": 0x02194A88, "slot_count": 18, "size": 4768, "bss": 0},
    "j03": {"overlay": 92, "slots_pointer": 0x020CA0A0, "slots": 0x02194B60, "slot_count": 19, "size": 4928, "bss": 0},
    "j04": {"overlay": 93, "slots_pointer": 0x020CA0A4, "slots": 0x02194550, "slot_count": 16, "size": 2336, "bss": 0},
    "j05": {"overlay": 94, "slots_pointer": 0x020CA0A8, "slots": 0x02194C70, "slot_count": 18, "size": 6272, "bss": 0},
    "k01": {"overlay": 95, "slots_pointer": 0x020CA0AC, "slots": 0x021962C8, "slot_count": 29, "size": 13280, "bss": 32},
    "k03": {"overlay": 97, "slots_pointer": 0x020CA0B4, "slots": 0x021946B8, "slot_count": 21, "size": 3008, "bss": 0},
    "k04": {"overlay": 98, "slots_pointer": 0x020CA0B8, "slots": 0x021958E0, "slot_count": 33, "size": 14816, "bss": 0},
    "k05": {"overlay": 99, "slots_pointer": 0x020CA0BC, "slots": 0x02194AE8, "slot_count": 20, "size": 4288, "bss": 0},
    "l01": {"overlay": 100, "slots_pointer": 0x020CA0C0, "slots": 0x021958E0, "slot_count": 19, "size": 6976, "bss": 0},
    "l02": {"overlay": 101, "slots_pointer": 0x020CA0C4, "slots": 0x021951B0, "slot_count": 24, "size": 5248, "bss": 0},
    "l03": {"overlay": 102, "slots_pointer": 0x020CA0C8, "slots": 0x02195154, "slot_count": 30, "size": 5344, "bss": 0},
    "l04": {"overlay": 103, "slots_pointer": 0x020CA0CC, "slots": 0x021950C8, "slot_count": 24, "size": 6624, "bss": 0},
    "m01": {"overlay": 104, "slots_pointer": 0x020CA0D0, "slots": 0x021948C0, "slot_count": 25, "size": 5088, "bss": 0},
    "m02": {"overlay": 105, "slots_pointer": 0x020CA0D4, "slots": 0x021945F8, "slot_count": 16, "size": 3744, "bss": 0},
    "m03": {"overlay": 106, "slots_pointer": 0x020CA0D8, "slots": 0x02194BF8, "slot_count": 15, "size": 6400, "bss": 0},
    "o01": {"overlay": 110, "slots_pointer": 0x020CA0E0, "slots": 0x021954D0, "slot_count": 20, "size": 11552, "bss": 0},
    "o02": {"overlay": 111, "slots_pointer": 0x020CA0E4, "slots": 0x02194CF0, "slot_count": 16, "size": 5856, "bss": 0},
}

SITES = {
    "A-1 / A-2": {
        "doors": ("a01 door (6368,1104)", "a02 door (288,912)"), "key": None, "border": False, "weight": 30, "weight_pickups": 30,
        "faces": (
            {"room": "a01", "coord": 0x021949B8, "slot": 5, "template": "010513010000ffffff000000", "shared": False},
            {"room": "a02", "coord": 0x021952F0, "slot": 0, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
    "A-3 / H-1": {
        "doors": ("a03 door (1632,576)", "h01 door (288,928)"), "key": None, "border": True, "weight": 15, "weight_pickups": 30,
        "faces": (
            {"room": "a03", "coord": 0x02194640, "slot": 3, "template": "010513000600ffffff000000", "shared": False},
            {"room": "h01", "coord": 0x02198588, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "A-4 / M-1": {
        "doors": ("a04 door (864,320)", "m01 door (288,704)"), "key": None, "border": True, "weight": 15, "weight_pickups": 30,
        "faces": (
            {"room": "a04", "coord": 0x021940A8, "slot": 2, "template": "010513000600ffffff000000", "shared": False},
            {"room": "m01", "coord": 0x021949F4, "slot": 1, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "B-3 / F-1": {
        "doors": ("b03 door (2272,704)", "f01 door (288,544)"), "key": None, "border": True, "weight": 45, "weight_pickups": 30,
        "faces": (
            {"room": "b03", "coord": 0x021948D8, "slot": 3, "template": "010513010000ffffff000000", "shared": False},
            {"room": "f01", "coord": 0x021943A8, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "D-1 / D-2": {
        "doors": ("d01 door (4320,544)", "d02 door (288,544)"), "key": None, "border": False, "weight": 20, "weight_pickups": 20,
        "faces": (
            {"room": "d01", "coord": 0x02194BF8, "slot": 4, "template": "010513010000ffffff000000", "shared": False},
            {"room": "d02", "coord": 0x02195388, "slot": 4, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
    "D-3 / G-1": {
        "doors": ("d03 door (3296,736)", "g01 door (288,1120)"), "key": None, "border": True, "weight": 15, "weight_pickups": 15,
        "faces": (
            {"room": "d03", "coord": 0x02194420, "slot": 1, "template": "010513010000ffffff000000", "shared": True},
            {"room": "g01", "coord": 0x02194A00, "slot": 0, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
    "D-3 / O-1": {
        "doors": ("d03 door (2224,544)", "o01 door (288,736)"), "key": None, "border": True, "weight": 15, "weight_pickups": 15,
        "faces": (
            {"room": "d03", "coord": 0x021943F0, "slot": 0, "template": "010513000800ffffff000000", "shared": False},
            {"room": "o01", "coord": 0x02195440, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "E-1 / E-2": {
        "doors": ("e01 door (3040,704)", "e02 door (288,320)"), "key": None, "border": False, "weight": 10, "weight_pickups": 10,
        "faces": (
            {"room": "e01", "coord": 0x02194528, "slot": 2, "template": "010513010000ffffff000000", "shared": False},
            {"room": "e02", "coord": 0x02194DC0, "slot": 7, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "E-2 / E-4": {
        "doors": ("e02 door (1248,1088)", "e04 door (288,704)"), "key": None, "border": False, "weight": 10, "weight_pickups": 10,
        "faces": (
            {"room": "e02", "coord": 0x02194E60, "slot": 7, "template": "010513010000ffffff000000", "shared": True},
            {"room": "e04", "coord": 0x02195940, "slot": 1, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
    "E-4 / E-5": {
        "doors": ("e04 door (2736,928)", "e05 door (288,928)"), "key": None, "border": False, "weight": 20, "weight_pickups": 20,
        "faces": (
            {"room": "e04", "coord": 0x02195A00, "slot": 0, "template": "010513000a00ffffff000000", "shared": True},
            {"room": "e05", "coord": 0x02194DD0, "slot": 0, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
    "E-5 / E-7": {
        "doors": ("e05 door (3040,528)", "e07 door (288,720)"), "key": None, "border": False, "weight": 20, "weight_pickups": 20,
        "faces": (
            {"room": "e05", "coord": 0x02194F60, "slot": 27, "template": "010513010600ffffff000000", "shared": False},
            {"room": "e07", "coord": 0x021949B8, "slot": 1, "template": "010513010600ffffff000000", "shared": True},
        ),
    },
    "E-7 / E-8": {
        "doors": ("e08 door (320,720)", "e07 door (1760,720)"), "key": None, "border": False, "weight": 5, "weight_pickups": 5,
        "faces": (
            {"room": "e08", "coord": 0x02194418, "slot": 2, "template": "010513000a00ffffff000000", "shared": False},
            {"room": "e07", "coord": 0x021949C8, "slot": 1, "template": "010513010600ffffff000000", "shared": True},
        ),
    },
    "F-1 / F-2": {
        "doors": ("f01 door (2016,736)", "f02 door (288,544)"), "key": None, "border": False, "weight": 30, "weight_pickups": 20,
        "faces": (
            {"room": "f01", "coord": 0x02194448, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
            {"room": "f02", "coord": 0x02194A88, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "F-2 / F-3": {
        "doors": ("f02 door (2528,544)", "f03 door (288,1696)"), "key": None, "border": False, "weight": 20, "weight_pickups": 20,
        "faces": (
            {"room": "f02", "coord": 0x02194BA8, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
            {"room": "f03", "coord": 0x02194B84, "slot": 2, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "F-4 / F-5": {
        "doors": ("f04 door (1760,528)", "f05 door (288,736)"), "key": None, "border": False, "weight": 10, "weight_pickups": 5,
        "faces": (
            {"room": "f04", "coord": 0x021943A0, "slot": 1, "template": "010513010600ffffff000000", "shared": False},
            {"room": "f05", "coord": 0x021949B8, "slot": 1, "template": "010513010600ffffff000000", "shared": False},
        ),
    },
    "G-1 / G-2": {
        "doors": ("g01 door (3808,768)", "g02 door (288,1152)"), "key": None, "border": False, "weight": 10, "weight_pickups": 10,
        "faces": (
            {"room": "g01", "coord": 0x02194BB8, "slot": 8, "template": "010513810000ffffff000000", "shared": False},
            {"room": "g02", "coord": 0x02194890, "slot": 7, "template": "010513810000ffffff000000", "shared": False},
        ),
    },
    "G-2 / G-3": {
        "doors": ("g02 door (656,1552)", "g03 door (288,544)"), "key": None, "border": False, "weight": 5, "weight_pickups": 5,
        "faces": (
            {"room": "g02", "coord": 0x02194B68, "slot": 8, "template": "010513000c00ffffff000000", "shared": True},
            {"room": "g03", "coord": 0x021946A0, "slot": 1, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "G-4 / G-5": {
        "doors": ("g04 door (1504,352)", "g05 door (288,544)"), "key": None, "border": False, "weight": 10, "weight_pickups": 10,
        "faces": (
            {"room": "g04", "coord": 0x021944AC, "slot": 1, "template": "010513010000ffffff000000", "shared": True},
            {"room": "g05", "coord": 0x02194E88, "slot": 3, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
    "H-1 / H-2": {
        "doors": ("h01 door (4832,896)", "h02 door (288,704)"), "key": None, "border": False, "weight": 10, "weight_pickups": 10,
        "faces": (
            {"room": "h01", "coord": 0x021986D0, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
            {"room": "h02", "coord": 0x02194904, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "H-2 / H-3": {
        "doors": ("h02 door (1504,704)", "h03 door (288,896)"), "key": None, "border": False, "weight": 5, "weight_pickups": 10,
        "faces": (
            {"room": "h02", "coord": 0x02194914, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
            {"room": "h03", "coord": 0x02196B48, "slot": 0, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
    "H-3 / H-4": {
        "doors": ("h03 door (3808,368)", "h04 door (288,944)"), "key": None, "border": False, "weight": 5, "weight_pickups": 5,
        "faces": (
            {"room": "h03", "coord": 0x02196CE0, "slot": 1, "template": "010513010600ffffff000000", "shared": False},
            {"room": "h04", "coord": 0x02194D4C, "slot": 4, "template": "010513010600ffffff000000", "shared": False},
        ),
    },
    "I-1 / I-3": {
        "doors": ("i01 door (3488,736)", "i03 door (352,944)"), "key": None, "border": False, "weight": 10, "weight_pickups": 10,
        "faces": (
            {"room": "i01", "coord": 0x02194FB8, "slot": 1, "template": "010513000f00ffffff000000", "shared": True},
            {"room": "i03", "coord": 0x02195A00, "slot": 0, "template": "010513000f00ffffff000000", "shared": True},
        ),
    },
    "I-2 / I-5": {
        "doors": ("i02 door (2208,736)", "i05 door (288,736)"), "key": None, "border": False, "weight": 20, "weight_pickups": 10,
        "faces": (
            {"room": "i02", "coord": 0x02194AA8, "slot": 0, "template": "010513000f00ffffff000000", "shared": True},
            {"room": "i05", "coord": 0x02194500, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "I-3 / I-5": {
        "doors": ("i03 door (928,544)", "i05 door (3296,736)"), "key": None, "border": False, "weight": 5, "weight_pickups": 5,
        "faces": (
            {"room": "i03", "coord": 0x02195A30, "slot": 0, "template": "010513000f00ffffff000000", "shared": True},
            {"room": "i05", "coord": 0x021945A0, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "J-1 / J-2": {
        "doors": ("j01 door (1248,560)", "j02 door (288,752)"), "key": None, "border": False, "weight": 20, "weight_pickups": 20,
        "faces": (
            {"room": "j01", "coord": 0x02194350, "slot": 4, "template": "010513010000ffffff000000", "shared": False},
            {"room": "j02", "coord": 0x02194B68, "slot": 1, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "J-2 / J-3": {
        "doors": ("j02 door (3296,752)", "j03 door (288,736)"), "key": None, "border": False, "weight": 20, "weight_pickups": 20,
        "faces": (
            {"room": "j02", "coord": 0x02194CA8, "slot": 1, "template": "010513010000ffffff000000", "shared": True},
            {"room": "j03", "coord": 0x02194AA8, "slot": 0, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
    "J-2 / J-4": {
        "doors": ("j02 door (3008,1056)", "j04 door (288,656)"), "key": None, "border": False, "weight": 5, "weight_pickups": 5,
        "faces": (
            {"room": "j02", "coord": 0x02194C90, "slot": 0, "template": "010513000b00ffffff000000", "shared": False},
            {"room": "j04", "coord": 0x02194508, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "J-3 / J-5": {
        "doors": ("j03 door (2272,752)", "j05 door (288,752)"), "key": None, "border": False, "weight": 10, "weight_pickups": 10,
        "faces": (
            {"room": "j03", "coord": 0x02194B50, "slot": 1, "template": "010513010600ffffff000000", "shared": False},
            {"room": "j05", "coord": 0x02194BF0, "slot": 1, "template": "010513010600ffffff000000", "shared": False},
        ),
    },
    "J-4 / J-5": {
        "doors": ("j05 door (2000,608)", "j04 door (1248,416)"), "key": None, "border": False, "weight": 5, "weight_pickups": 5,
        "faces": (
            {"room": "j05", "coord": 0x02194C50, "slot": 0, "template": "010513000b00ffffff000000", "shared": True},
            {"room": "j04", "coord": 0x02194540, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "K-1 / K-5": {
        "doors": ("k01 door (7296,752)", "k05 door (560,272)"), "key": None, "border": False, "weight": 5, "weight_pickups": 10,
        "faces": (
            {"room": "k01", "coord": 0x021965FC, "slot": 4, "template": "010513001000ffffff000000", "shared": True},
            {"room": "k05", "coord": 0x02194A40, "slot": 0, "template": "010513001000ffffff000000", "shared": False},
        ),
    },
    "K-3 / K-4": {
        "doors": ("k04 door (640,528)", "k03 door (1760,1104)"), "key": None, "border": False, "weight": 20, "weight_pickups": 20,
        "faces": (
            {"room": "k04", "coord": 0x02195AA4, "slot": 5, "template": "010513001000ffffff000000", "shared": True},
            {"room": "k03", "coord": 0x021946A8, "slot": 1, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "K-3 / K-5": {
        "doors": ("k03 door (1504,528)", "k05 door (288,2640)"), "key": None, "border": False, "weight": 10, "weight_pickups": 20,
        "faces": (
            {"room": "k03", "coord": 0x02194680, "slot": 1, "template": "010513010000ffffff000000", "shared": True},
            {"room": "k05", "coord": 0x02194A20, "slot": 1, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
    "L-1 / L-2": {
        "doors": ("l01 door (4320,752)", "l02 door (288,752)"), "key": None, "border": False, "weight": 10, "weight_pickups": 10,
        "faces": (
            {"room": "l01", "coord": 0x02195AF4, "slot": 0, "template": "010513010000ffffff000000", "shared": False},
            {"room": "l02", "coord": 0x021952D8, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "L-2 / L-3": {
        "doors": ("l02 door (4320,752)", "l03 door (288,752)"), "key": None, "border": False, "weight": 10, "weight_pickups": 10,
        "faces": (
            {"room": "l02", "coord": 0x02195460, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
            {"room": "l03", "coord": 0x021952C4, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "L-3 / L-4": {
        "doors": ("l03 door (4320,736)", "l04 door (288,736)"), "key": None, "border": False, "weight": 10, "weight_pickups": 10,
        "faces": (
            {"room": "l03", "coord": 0x021954B4, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
            {"room": "l04", "coord": 0x02194FE8, "slot": 2, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
    "M-1 / M-2": {
        "doors": ("m01 door (5088,736)", "m02 door (288,352)"), "key": None, "border": False, "weight": 5, "weight_pickups": 10,
        "faces": (
            {"room": "m01", "coord": 0x02194AD4, "slot": 1, "template": "010513010000ffffff000000", "shared": True},
            {"room": "m02", "coord": 0x021946C0, "slot": 1, "template": "010513010000ffffff000000", "shared": True},
        ),
    },
    "M-2 / M-3": {
        "doors": ("m02 door (3296,1088)", "m03 door (288,320)"), "key": None, "border": False, "weight": 5, "weight_pickups": 5,
        "faces": (
            {"room": "m02", "coord": 0x02194768, "slot": 1, "template": "010513010000ffffff000000", "shared": True},
            {"room": "m03", "coord": 0x02194B80, "slot": 3, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
    "O-1 / O-2": {
        "doors": ("o01 door (4320,736)", "o02 door (288,544)"), "key": None, "border": False, "weight": 10, "weight_pickups": 5,
        "faces": (
            {"room": "o01", "coord": 0x021954C0, "slot": 0, "template": "010513010000ffffff000000", "shared": True},
            {"room": "o02", "coord": 0x02194DB8, "slot": 0, "template": "010513010000ffffff000000", "shared": False},
        ),
    },
}
