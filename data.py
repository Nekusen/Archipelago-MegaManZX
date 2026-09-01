"""GENERADO por tools/gen_ap_data.py — NO editar a mano.
Puente RE→apworld: locations (detección por RAM) e items
(receta de concesión). IDs append-only. Fuente: docs/
client_integration.md, disk_checks.md, entities.md."""

BASE_ID = 0xD00000
LIVE_BLOCK = 0x021045CC
CANON_BLOCK = 0x021602B4

# name -> {id, category, detect:[kind,addr,bit], room, pos, status}
LOCATIONS = {
    'Disk B-1': {'id': 13631488, 'category': 'disk', 'detect': ['bit', 34620931, 6], 'room': 'b02', 'pos': [4232, 456], 'status': 'verified'},
    'Disk B-2': {'id': 13631489, 'category': 'disk', 'detect': ['bit', 34620931, 7], 'room': 'n01', 'pos': [488, 648], 'status': 'verified'},
    'Disk B-3': {'id': 13631490, 'category': 'disk', 'detect': ['bit', 34620932, 0], 'room': 'a02', 'pos': [3168, 920], 'status': 'verified'},
    'Disk B-4': {'id': 13631491, 'category': 'disk', 'detect': ['bit', 34620932, 1], 'room': 'd02', 'pos': [8672, 536], 'status': 'verified'},
    'Disk B-5': {'id': 13631492, 'category': 'disk', 'detect': ['bit', 34620932, 2], 'room': 'd04', 'pos': [1136, 3864], 'status': 'verified'},
    'Disk B-6': {'id': 13631493, 'category': 'disk', 'detect': ['bit', 34620932, 3], 'room': 'd05', 'pos': [2584, 552], 'status': 'verified'},
    'Disk B-7': {'id': 13631494, 'category': 'disk', 'detect': ['bit', 34620932, 4], 'room': 'h04', 'pos': [1072, 248], 'status': 'verified'},
    'Disk B-8': {'id': 13631495, 'category': 'disk', 'detect': ['bit', 34620932, 5], 'room': 'e08', 'pos': [2220, 728], 'status': 'verified'},
    'Disk B-9': {'id': 13631496, 'category': 'disk', 'detect': ['bit', 34620932, 6], 'room': 'i03', 'pos': [280, 808], 'status': 'verified'},
    'Disk B-10': {'id': 13631497, 'category': 'disk', 'detect': ['bit', 34620932, 7], 'room': 'm03', 'pos': [792, 744], 'status': 'verified'},
    'Disk B-11': {'id': 13631498, 'category': 'disk', 'detect': ['bit', 34620933, 0], 'room': 'g05', 'pos': [3788, 452], 'status': 'verified'},
    'Disk B-12': {'id': 13631499, 'category': 'disk', 'detect': ['bit', 34620933, 1], 'room': 'k04', 'pos': [848, 1858], 'status': 'verified'},
    'Disk B-13': {'id': 13631500, 'category': 'disk', 'detect': ['bit', 34620933, 2], 'room': 'l04', 'pos': [1144, 606], 'status': 'verified'},
    'Disk B-14': {'id': 13631501, 'category': 'disk', 'detect': ['bit', 34620933, 3], 'room': 'o02', 'pos': [5224, 536], 'status': 'verified'},
    'Disk B-15': {'id': 13631502, 'category': 'disk', 'detect': ['bit', 34620933, 4], 'room': 'f04', 'pos': [1576, 306], 'status': 'verified'},
    'Disk B-16': {'id': 13631503, 'category': 'disk', 'detect': ['bit', 34620933, 5], 'room': 'j05', 'pos': [2008, 472], 'status': 'verified'},
    'Life Up - Area D01': {'id': 13631744, 'category': 'life_up', 'detect': ['bit', 34620884, 1], 'room': 'd01', 'pos': [3144, 728], 'status': 'verified'},
    'Life Up - Area F02': {'id': 13631745, 'category': 'life_up', 'detect': ['bit', 34620885, 7], 'room': 'f02', 'pos': [712, 544], 'status': 'verified'},
    'Life Up - Area J01': {'id': 13631746, 'category': 'life_up', 'detect': ['bit', 34620888, 1], 'room': 'j01', 'pos': [728, 872], 'status': 'verified'},
    'Life Up - Area I05': {'id': 13631747, 'category': 'life_up', 'detect': ['bit', 34620888, 0], 'room': 'i05', 'pos': [2800, 456], 'status': 'verified'},
    'Sub Tank - Area A02': {'id': 13631760, 'category': 'sub_tank', 'detect': ['bit', 34620809, 0], 'room': 'a02', 'pos': [488, 528], 'status': 'verified'},
    'Sub Tank - Area E04': {'id': 13631761, 'category': 'sub_tank', 'detect': ['bit', 34620885, 1], 'room': 'e04', 'pos': [2644, 840], 'status': 'verified'},
    'Sub Tank - Area K01': {'id': 13631762, 'category': 'sub_tank', 'detect': ['bit', 34620888, 6], 'room': 'k01', 'pos': [7216, 1314], 'status': 'verified'},
    'Obtain Biometal H': {'id': 13632001, 'category': 'biometal', 'detect': ['bit', 34620880, 1], 'room': 'E-7/I-3', 'pos': None, 'status': 'verified'},
    'Obtain Biometal L': {'id': 13632003, 'category': 'biometal', 'detect': ['bit', 34620880, 3], 'room': 'F-5/J-5', 'pos': None, 'status': 'verified'},
    'Obtain Biometal F': {'id': 13632005, 'category': 'biometal', 'detect': ['bit', 34620880, 5], 'room': 'G-5/K-4', 'pos': None, 'status': 'verified'},
    'Obtain Biometal P': {'id': 13632007, 'category': 'biometal', 'detect': ['bit', 34620880, 7], 'room': 'H-4/L-4', 'pos': None, 'status': 'verified'},
    'Mission - Catch The Maverick': {'id': 13632257, 'category': 'mission', 'detect': ['all', [[34620894, 3], [34620894, 4], [34620895, 0]]], 'room': 'A-2', 'pos': None, 'status': 'verified'},
    'Mission - Locate Giro': {'id': 13632258, 'category': 'mission', 'detect': ['all', [[34620894, 7]]], 'room': 'B-1B-2', 'pos': None, 'status': 'verified'},
    'Mission - Pass The Test': {'id': 13632259, 'category': 'mission', 'detect': ['all', [[34620896, 3]]], 'room': 'C-1C-2', 'pos': None, 'status': 'verified'},
    'Mission - Troop Reinforcement': {'id': 13632260, 'category': 'mission', 'detect': ['all', [[34620897, 1], [34620897, 2], [34620897, 5], [34620898, 0], [34620900, 0]]], 'room': 'D-2', 'pos': None, 'status': 'verified'},
    'Mission - Search The Plant': {'id': 13632261, 'category': 'mission', 'detect': ['all', [[34620897, 4]]], 'room': 'E-7', 'pos': None, 'status': 'verified'},
    'Mission - Find The Survivors': {'id': 13632262, 'category': 'mission', 'detect': ['all', [[34620897, 7], [34620901, 0]]], 'room': 'F', 'pos': None, 'status': 'verified'},
    'Mission - Fight The Mavericks': {'id': 13632263, 'category': 'mission', 'detect': ['all', [[34620899, 7], [34620901, 3]]], 'room': 'G', 'pos': None, 'status': 'verified'},
    'Mission - Secure The Biometal': {'id': 13632264, 'category': 'mission', 'detect': ['all', [[34620900, 3]]], 'room': 'H-4', 'pos': None, 'status': 'verified'},
    'Mission - Save The People': {'id': 13632265, 'category': 'mission', 'detect': ['all', [[34620900, 7]]], 'room': 'I-3', 'pos': None, 'status': 'verified'},
    'Mission - Recover The Disk': {'id': 13632266, 'category': 'mission', 'detect': ['all', [[34620901, 2]]], 'room': 'J-5', 'pos': None, 'status': 'verified'},
    'Mission - Attack The Excavators': {'id': 13632267, 'category': 'mission', 'detect': ['all', [[34620901, 6]]], 'room': 'K-4', 'pos': None, 'status': 'verified'},
    'Mission - Protect The Lab': {'id': 13632268, 'category': 'mission', 'detect': ['all', [[34620902, 1]]], 'room': 'L-4', 'pos': None, 'status': 'verified'},
    'Mission - Protect Hq': {'id': 13632269, 'category': 'mission', 'detect': None, 'room': 'X HQ', 'pos': None, 'status': 'detect_pending'},
    'Mission - Stop The Dig': {'id': 13632270, 'category': 'mission', 'detect': ['all', [[34620903, 3], [34620903, 4]]], 'room': 'M', 'pos': None, 'status': 'verified'},
    'Mission - Repel The Army': {'id': 13632271, 'category': 'mission', 'detect': ['all', [[34620903, 7], [34620904, 0]]], 'room': 'O', 'pos': None, 'status': 'verified'},
    'Mission - Destroy Model W': {'id': 13632272, 'category': 'mission', 'detect': None, 'room': 'D-4D-5', 'pos': None, 'status': 'detect_pending'},
    'Quest - Find The Flower': {'id': 13632340, 'category': 'quest', 'detect': None, 'room': 'A-1', 'pos': None, 'status': 'detect_pending'},
    'Quest - Trim The Weeds': {'id': 13632341, 'category': 'quest', 'detect': None, 'room': 'C-2', 'pos': None, 'status': 'detect_pending'},
    'Quest - Find The Boy': {'id': 13632342, 'category': 'quest', 'detect': None, 'room': 'G-1G-2', 'pos': None, 'status': 'detect_pending'},
    'Quest - Quiz Partner': {'id': 13632343, 'category': 'quest', 'detect': None, 'room': 'C-1C-3', 'pos': None, 'status': 'detect_pending'},
    'Quest - Another Quiz': {'id': 13632344, 'category': 'quest', 'detect': None, 'room': 'C-1C-3', 'pos': None, 'status': 'detect_pending'},
    'Quest - Purify The Lakes': {'id': 13632345, 'category': 'quest', 'detect': None, 'room': 'B-4', 'pos': None, 'status': 'detect_pending'},
    'Quest - Find Mushroom': {'id': 13632346, 'category': 'quest', 'detect': None, 'room': 'A-2', 'pos': None, 'status': 'detect_pending'},
    'Quest - Sending A Letter': {'id': 13632347, 'category': 'quest', 'detect': None, 'room': 'C-2', 'pos': None, 'status': 'detect_pending'},
    'Quest - Sending Another Letter': {'id': 13632348, 'category': 'quest', 'detect': None, 'room': 'C-2', 'pos': None, 'status': 'detect_pending'},
    'Quest - Yet Another Letter': {'id': 13632349, 'category': 'quest', 'detect': None, 'room': 'C-2', 'pos': None, 'status': 'detect_pending'},
    'Quest - Not Another Letter': {'id': 13632350, 'category': 'quest', 'detect': None, 'room': 'C-2', 'pos': None, 'status': 'detect_pending'},
    'Quest - Guess What A Letter': {'id': 13632351, 'category': 'quest', 'detect': None, 'room': 'C-2', 'pos': None, 'status': 'detect_pending'},
    'Quest - One More Letter': {'id': 13632352, 'category': 'quest', 'detect': None, 'room': 'C-2', 'pos': None, 'status': 'detect_pending'},
    'Quest - Deliver A Reply': {'id': 13632353, 'category': 'quest', 'detect': None, 'room': 'X-1 HQ', 'pos': None, 'status': 'detect_pending'},
    'Quest - Find The Purse': {'id': 13632354, 'category': 'quest', 'detect': None, 'room': 'B-2', 'pos': None, 'status': 'detect_pending'},
    'Quest - Find The Pearl': {'id': 13632355, 'category': 'quest', 'detect': None, 'room': 'F-2', 'pos': None, 'status': 'detect_pending'},
    'Quest - Find The Rock': {'id': 13632356, 'category': 'quest', 'detect': None, 'room': 'K-1', 'pos': None, 'status': 'detect_pending'},
    'Quest - Smash The Rock': {'id': 13632357, 'category': 'quest', 'detect': None, 'room': 'E-4', 'pos': None, 'status': 'detect_pending'},
    'Quest - Gather The Screws': {'id': 13632358, 'category': 'quest', 'detect': None, 'room': 'K-3K-4K-5', 'pos': None, 'status': 'detect_pending'},
    'Quest - Clean The Room': {'id': 13632359, 'category': 'quest', 'detect': None, 'room': 'C-1', 'pos': None, 'status': 'detect_pending'},
    'Quest - Deliver The Aid Kit': {'id': 13632360, 'category': 'quest', 'detect': None, 'room': 'L-1L-2L-3', 'pos': None, 'status': 'detect_pending'},
    'Disk M-1': {'id': 13632488, 'category': 'disk', 'detect': ['bit', 34620933, 7], 'room': 'i04', 'pos': [1528, 312], 'status': 'verified'},
    'Disk M-2': {'id': 13632489, 'category': 'disk', 'detect': ['bit', 34620934, 0], 'room': 'm01', 'pos': [5592, 280], 'status': 'verified'},
    'Disk M-3': {'id': 13632490, 'category': 'disk', 'detect': ['bit', 34620934, 1], 'room': 'o01', 'pos': [2544, 904], 'status': 'verified'},
    'Disk M-4': {'id': 13632491, 'category': 'disk', 'detect': ['bit', 34620934, 2], 'room': 'd02', 'pos': [3664, 744], 'status': 'verified'},
    'Disk M-5': {'id': 13632492, 'category': 'disk', 'detect': ['bit', 34620934, 3], 'room': 'e05', 'pos': [2192, 264], 'status': 'verified'},
    'Disk M-6': {'id': 13632493, 'category': 'disk', 'detect': ['bit', 34620934, 4], 'room': 'i05', 'pos': [1416, 648], 'status': 'verified'},
    'Disk M-7': {'id': 13632494, 'category': 'disk', 'detect': ['bit', 34620934, 5], 'room': 'j03', 'pos': [1704, 1000], 'status': 'verified'},
    'Disk M-8': {'id': 13632495, 'category': 'disk', 'detect': ['bit', 34620934, 6], 'room': 'h03', 'pos': [2248, 936], 'status': 'verified'},
    'Disk M-9': {'id': 13632496, 'category': 'disk', 'detect': ['bit', 34620934, 7], 'room': 'k03', 'pos': [560, 1102], 'status': 'verified'},
    'Disk E-1': {'id': 13633488, 'category': 'disk', 'detect': ['bit', 34620935, 1], 'room': 'a01', 'pos': [7632, 344], 'status': 'verified'},
    'Disk E-2': {'id': 13633489, 'category': 'disk', 'detect': ['bit', 34620935, 2], 'room': 'f03', 'pos': [1984, 628], 'status': 'verified'},
    'Disk E-3': {'id': 13633490, 'category': 'disk', 'detect': ['bit', 34620935, 3], 'room': 'i01', 'pos': [2592, 632], 'status': 'verified'},
    'Disk E-4': {'id': 13633491, 'category': 'disk', 'detect': ['bit', 34620935, 4], 'room': 'e01', 'pos': [1800, 728], 'status': 'verified'},
    'Disk E-5': {'id': 13633492, 'category': 'disk', 'detect': ['bit', 34620935, 5], 'room': 'l03', 'pos': [4032, 722], 'status': 'verified'},
    'Disk E-6': {'id': 13633493, 'category': 'disk', 'detect': ['bit', 34620935, 6], 'room': 'd03', 'pos': [2800, 920], 'status': 'verified'},
    'Disk E-7': {'id': 13633494, 'category': 'disk', 'detect': ['bit', 34620935, 7], 'room': 'j02', 'pos': [2448, 472], 'status': 'verified'},
    'Disk E-8': {'id': 13633495, 'category': 'disk', 'detect': ['bit', 34620936, 0], 'room': 'e04', 'pos': [3032, 264], 'status': 'verified'},
    'Disk E-9': {'id': 13633496, 'category': 'disk', 'detect': ['bit', 34620936, 1], 'room': 'g03', 'pos': [888, 546], 'status': 'verified'},
    'Disk E-10': {'id': 13633497, 'category': 'disk', 'detect': ['bit', 34620936, 2], 'room': 'h03', 'pos': [1824, 712], 'status': 'verified'},
    'Disk E-11': {'id': 13633498, 'category': 'disk', 'detect': ['bit', 34620936, 3], 'room': 'b04', 'pos': [2224, 664], 'status': 'verified'},
    'Disk E-12': {'id': 13633499, 'category': 'disk', 'detect': ['bit', 34620936, 4], 'room': 'd01', 'pos': [2832, 728], 'status': 'verified'},
    'Disk E-13': {'id': 13633500, 'category': 'disk', 'detect': ['bit', 34620936, 5], 'room': 'i05', 'pos': [3280, 520], 'status': 'verified'},
    'Disk E-14': {'id': 13633501, 'category': 'disk', 'detect': ['bit', 34620936, 6], 'room': 'i04', 'pos': [1928, 312], 'status': 'verified'},
    'Disk E-15': {'id': 13633502, 'category': 'disk', 'detect': ['bit', 34620936, 7], 'room': 'f02', 'pos': [992, 930], 'status': 'verified'},
    'Disk E-16': {'id': 13633503, 'category': 'disk', 'detect': ['bit', 34620937, 0], 'room': 'g02', 'pos': [348, 362], 'status': 'verified'},
    'Disk E-17': {'id': 13633504, 'category': 'disk', 'detect': ['bit', 34620937, 1], 'room': 'b02', 'pos': [2672, 472], 'status': 'verified'},
    'Disk E-18': {'id': 13633505, 'category': 'disk', 'detect': ['bit', 34620937, 2], 'room': 'l01', 'pos': [3280, 528], 'status': 'verified'},
    'Disk E-19': {'id': 13633506, 'category': 'disk', 'detect': ['bit', 34620937, 3], 'room': 'd01', 'pos': [3824, 632], 'status': 'verified'},
    'Disk E-20': {'id': 13633507, 'category': 'disk', 'detect': ['bit', 34620937, 4], 'room': 'a04', 'pos': [1224, 248], 'status': 'verified'},
    'Disk E-21': {'id': 13633508, 'category': 'disk', 'detect': ['bit', 34620937, 5], 'room': 'e04', 'pos': [3272, 1112], 'status': 'verified'},
    'Disk E-22': {'id': 13633509, 'category': 'disk', 'detect': ['bit', 34620937, 6], 'room': 'k01', 'pos': [3386, 622], 'status': 'verified'},
    'Disk E-23': {'id': 13633510, 'category': 'disk', 'detect': ['bit', 34620937, 7], 'room': 'i05', 'pos': [2536, 712], 'status': 'verified'},
    'Disk E-24': {'id': 13633511, 'category': 'disk', 'detect': ['bit', 34620938, 0], 'room': 'b01', 'pos': [4992, 888], 'status': 'verified'},
    'Disk E-25': {'id': 13633512, 'category': 'disk', 'detect': ['bit', 34620938, 1], 'room': 'k05', 'pos': [552, 1250], 'status': 'verified'},
    'Disk E-26': {'id': 13633513, 'category': 'disk', 'detect': ['bit', 34620938, 2], 'room': 'k04', 'pos': [352, 526], 'status': 'verified'},
    'Disk E-27': {'id': 13633514, 'category': 'disk', 'detect': ['bit', 34620938, 3], 'room': 'a02', 'pos': [5112, 568], 'status': 'verified'},
    'Disk E-28': {'id': 13633515, 'category': 'disk', 'detect': ['bit', 34620938, 4], 'room': 'b02', 'pos': [1712, 920], 'status': 'verified'},
    'Disk E-29': {'id': 13633516, 'category': 'disk', 'detect': ['bit', 34620938, 5], 'room': 'a02', 'pos': [4400, 920], 'status': 'verified'},
    'Disk E-30': {'id': 13633517, 'category': 'disk', 'detect': ['bit', 34620938, 6], 'room': 'c02', 'pos': [4992, 1128], 'status': 'verified'},
    'Disk E-31': {'id': 13633518, 'category': 'disk', 'detect': ['bit', 34620938, 7], 'room': 'a01', 'pos': [3208, 824], 'status': 'verified'},
    'Disk E-32': {'id': 13633519, 'category': 'disk', 'detect': ['bit', 34620939, 0], 'room': 'g05', 'pos': [1278, 676], 'status': 'verified'},
    'Disk E-33': {'id': 13633520, 'category': 'disk', 'detect': ['bit', 34620939, 1], 'room': 'i02', 'pos': [2192, 344], 'status': 'verified'},
    'Disk E-34': {'id': 13633521, 'category': 'disk', 'detect': ['bit', 34620939, 2], 'room': 'i02', 'pos': [1496, 632], 'status': 'verified'},
    'Disk E-35': {'id': 13633522, 'category': 'disk', 'detect': ['bit', 34620939, 3], 'room': 'k03', 'pos': [904, 688], 'status': 'verified'},
    'Disk E-36': {'id': 13633523, 'category': 'disk', 'detect': ['bit', 34620939, 4], 'room': 'j03', 'pos': [1960, 456], 'status': 'verified'},
    'Disk E-37': {'id': 13633524, 'category': 'disk', 'detect': ['bit', 34620939, 5], 'room': 'e05', 'pos': [2656, 264], 'status': 'verified'},
    'Disk E-38': {'id': 13633525, 'category': 'disk', 'detect': ['bit', 34620939, 6], 'room': 'g01', 'pos': [1278, 896], 'status': 'verified'},
    'Disk E-39': {'id': 13633526, 'category': 'disk', 'detect': ['bit', 34620939, 7], 'room': 'f01', 'pos': [894, 544], 'status': 'verified'},
    'Disk E-40': {'id': 13633527, 'category': 'disk', 'detect': ['bit', 34620940, 0], 'room': 'd02', 'pos': [3696, 536], 'status': 'verified'},
    'Disk E-41': {'id': 13633528, 'category': 'disk', 'detect': ['bit', 34620940, 1], 'room': 'l02', 'pos': [1608, 478], 'status': 'verified'},
    'Disk E-42': {'id': 13633529, 'category': 'disk', 'detect': ['bit', 34620940, 2], 'room': 'o01', 'pos': [2248, 728], 'status': 'verified'},
    'Disk E-43': {'id': 13633530, 'category': 'disk', 'detect': ['bit', 34620940, 3], 'room': 'k03', 'pos': [1560, 1088], 'status': 'verified'},
    'Disk E-44': {'id': 13633531, 'category': 'disk', 'detect': ['bit', 34620940, 4], 'room': 'f02', 'pos': [1416, 1026], 'status': 'verified'},
    'Disk E-45': {'id': 13633532, 'category': 'disk', 'detect': ['bit', 34620940, 5], 'room': 'f04', 'pos': [1522, 512], 'status': 'verified'},
    'Disk E-46': {'id': 13633533, 'category': 'disk', 'detect': ['bit', 34620940, 6], 'room': 'a03', 'pos': [1240, 792], 'status': 'verified'},
    'Disk E-48': {'id': 13633535, 'category': 'disk', 'detect': ['bit', 34620941, 0], 'room': 'f03', 'pos': [496, 468], 'status': 'verified'},
    'Disk E-49': {'id': 13633536, 'category': 'disk', 'detect': ['bit', 34620941, 1], 'room': 'c03', 'pos': [592, 552], 'status': 'verified'},
    'Disk E-50': {'id': 13633537, 'category': 'disk', 'detect': ['bit', 34620941, 2], 'room': 'm01', 'pos': [6104, 744], 'status': 'verified'},
    'Disk O-1': {'id': 13634488, 'category': 'disk', 'detect': ['bit', 34620941, 4], 'room': 'x01', 'pos': [2392, 1032], 'status': 'verified'},
    'Disk O-2': {'id': 13634489, 'category': 'disk', 'detect': ['bit', 34620941, 5], 'room': 'x01', 'pos': [504, 1112], 'status': 'verified'},
    'Disk O-3': {'id': 13634490, 'category': 'disk', 'detect': ['bit', 34620941, 6], 'room': 'x02', 'pos': [606, 504], 'status': 'verified'},
    'Disk O-4': {'id': 13634491, 'category': 'disk', 'detect': ['bit', 34620941, 7], 'room': 'x01', 'pos': [2080, 728], 'status': 'verified'},
    'Disk O-5': {'id': 13634492, 'category': 'disk', 'detect': ['bit', 34620942, 0], 'room': 'x01', 'pos': [2080, 344], 'status': 'verified'},
    'Disk O-6': {'id': 13634493, 'category': 'disk', 'detect': ['bit', 34620942, 1], 'room': 'x01', 'pos': [3032, 344], 'status': 'verified'},
    'Disk O-7': {'id': 13634494, 'category': 'disk', 'detect': ['bit', 34620942, 2], 'room': 'x01', 'pos': [1048, 1480], 'status': 'verified'},
    'Disk O-8': {'id': 13634495, 'category': 'disk', 'detect': ['bit', 34620942, 3], 'room': 'x01', 'pos': [760, 1112], 'status': 'verified'},
    'Disk O-9': {'id': 13634496, 'category': 'disk', 'detect': ['bit', 34620942, 4], 'room': 'a01', 'pos': [2416, 1128], 'status': 'verified'},
    'Disk O-10': {'id': 13634497, 'category': 'disk', 'detect': ['bit', 34620942, 5], 'room': 'x01', 'pos': [1278, 1112], 'status': 'verified'},
    'Disk O-11': {'id': 13634498, 'category': 'disk', 'detect': ['bit', 34620942, 6], 'room': 'x03', 'pos': [992, 520], 'status': 'verified'},
    'Disk O-12': {'id': 13634499, 'category': 'disk', 'detect': ['bit', 34620942, 7], 'room': 'd02', 'pos': [7026, 536], 'status': 'verified'},
    'Disk O-13': {'id': 13634500, 'category': 'disk', 'detect': ['bit', 34620943, 0], 'room': 'x01', 'pos': [1032, 952], 'status': 'verified'},
    'Disk O-14': {'id': 13634501, 'category': 'disk', 'detect': ['bit', 34620943, 1], 'room': 'x01', 'pos': [280, 728], 'status': 'verified'},
    'Disk O-15': {'id': 13634502, 'category': 'disk', 'detect': ['bit', 34620943, 2], 'room': 'x01', 'pos': [3544, 344], 'status': 'verified'},
    'Disk O-16': {'id': 13634503, 'category': 'disk', 'detect': ['bit', 34620943, 3], 'room': 'x02', 'pos': [1056, 536], 'status': 'verified'},
    'Disk O-17': {'id': 13634504, 'category': 'disk', 'detect': ['bit', 34620943, 4], 'room': 'c02', 'pos': [3912, 696], 'status': 'verified'},
    'Disk O-18': {'id': 13634505, 'category': 'disk', 'detect': ['bit', 34620943, 5], 'room': 'c02', 'pos': [1712, 776], 'status': 'verified'},
    'Disk O-19': {'id': 13634506, 'category': 'disk', 'detect': ['bit', 34620943, 6], 'room': 'x01', 'pos': [3032, 728], 'status': 'verified'},
    'Disk O-20': {'id': 13634507, 'category': 'disk', 'detect': ['bit', 34620943, 7], 'room': 'x01', 'pos': [1288, 952], 'status': 'verified'},
}

# name -> {id, classification, grant}
ITEMS = {
    'Model ZX': {'id': 13664256, 'classification': 'progression', 'grant': ['live_bit', 34620880, 0], 'pooled': True},
    'Biometal H': {'id': 13664257, 'classification': 'progression', 'grant': ['live_bit', 34620881, 1], 'pooled': True},
    'Biometal F': {'id': 13664258, 'classification': 'progression', 'grant': ['live_bit', 34620881, 5], 'pooled': True},
    'Biometal L': {'id': 13664259, 'classification': 'progression', 'grant': ['live_bit', 34620881, 3], 'pooled': True},
    'Biometal P': {'id': 13664260, 'classification': 'progression', 'grant': ['live_bit', 34620881, 7], 'pooled': True},
    'Biometal O': {'id': 13664261, 'classification': 'progression', 'grant': ['live_bit', 34620882, 1], 'pooled': True},
    'Model X': {'id': 13664262, 'classification': 'progression', 'grant': ['live_bit', 34620879, 7], 'pooled': True},
    'Yellow Card Key': {'id': 13664512, 'classification': 'progression', 'grant': ['live_bit', 34620925, 1], 'pooled': True},
    'Green Card Key': {'id': 13664513, 'classification': 'progression', 'grant': ['live_bit', 34620925, 0], 'pooled': True},
    'Red Card Key': {'id': 13664514, 'classification': 'progression', 'grant': ['live_bit', 34620924, 5], 'pooled': True},
    'Blue Card Key': {'id': 13664515, 'classification': 'progression', 'grant': ['live_bit', 34620924, 6], 'pooled': True},
    'White Card Key': {'id': 13664516, 'classification': 'progression', 'grant': ['live_bit', 34620925, 2], 'pooled': True},
    'Purple Card Key': {'id': 13664517, 'classification': 'progression', 'grant': ['live_bit', 34620924, 7], 'pooled': True},
    'Life Up': {'id': 13664528, 'classification': 'useful', 'grant': ['lifeup'], 'pooled': True},
    'Sub Tank': {'id': 13664529, 'classification': 'useful', 'grant': ['subtank'], 'pooled': True},
    'Transerver Access': {'id': 13664544, 'classification': 'progression', 'grant': ['todo'], 'pooled': False},
    'E-Crystals': {'id': 13664768, 'classification': 'filler', 'grant': ['ecrystals'], 'pooled': True},
    '1-Up': {'id': 13664769, 'classification': 'filler', 'grant': ['oneup'], 'pooled': True},
}

LOCATION_NAME_TO_ID = {n: v['id'] for n, v in LOCATIONS.items()}
ITEM_NAME_TO_ID = {n: v['id'] for n, v in ITEMS.items()}

# Objetivo (defeat Serpent): al completarse la misión final
# (estado 0xF8, id 19) mission_complete_on_report (0x02031028)
# pone AMBOS bits (derivado estático; validar en E2E):
GOAL_BITS = [(0x021045EB, 7), (0x021045EC, 0)]

# --- Modo AUTO force-accept de misiones (v0.2) ---
# Al entrar en la subárea destino de una misión, el cliente la
# fuerza como aceptada (replica FUN_02031f10, validado exp067):
# start flag (vivo+canónica) + estado en MISSION_STATE_ADDR +
# MISSION_ACTIVE_FLAG=1. Excluye Troop(4)/Protect HQ(13) (auto
# por hito). subárea -> {id, state, flag:[addr,bit], name}.
MISSION_STATE_ADDR = 0x021046AC
MISSION_ACTIVE_FLAG = 0x02160FA8
MISSION_ACCEPT = {
    2: {'id': 1, 'state': 146, 'flag': [34620894, 2], 'name': 'Catch The Maverick'},
    5: {'id': 2, 'state': 149, 'flag': [34620894, 5], 'name': 'Locate Giro'},
    6: {'id': 2, 'state': 149, 'flag': [34620894, 5], 'name': 'Locate Giro'},
    9: {'id': 3, 'state': 153, 'flag': [34620895, 1], 'name': 'Pass The Test'},
    10: {'id': 3, 'state': 153, 'flag': [34620895, 1], 'name': 'Pass The Test'},
    18: {'id': 16, 'state': 225, 'flag': [34620904, 1], 'name': 'Destroy Model W'},
    19: {'id': 16, 'state': 225, 'flag': [34620904, 1], 'name': 'Destroy Model W'},
    26: {'id': 5, 'state': 171, 'flag': [34620897, 3], 'name': 'Search The Plant'},
    28: {'id': 6, 'state': 174, 'flag': [34620897, 6], 'name': 'Find The Survivors'},
    29: {'id': 6, 'state': 174, 'flag': [34620897, 6], 'name': 'Find The Survivors'},
    30: {'id': 6, 'state': 174, 'flag': [34620897, 6], 'name': 'Find The Survivors'},
    31: {'id': 6, 'state': 174, 'flag': [34620897, 6], 'name': 'Find The Survivors'},
    32: {'id': 6, 'state': 174, 'flag': [34620897, 6], 'name': 'Find The Survivors'},
    33: {'id': 7, 'state': 177, 'flag': [34620898, 1], 'name': 'Fight The Mavericks'},
    34: {'id': 7, 'state': 177, 'flag': [34620898, 1], 'name': 'Fight The Mavericks'},
    35: {'id': 7, 'state': 177, 'flag': [34620898, 1], 'name': 'Fight The Mavericks'},
    36: {'id': 7, 'state': 177, 'flag': [34620898, 1], 'name': 'Fight The Mavericks'},
    37: {'id': 7, 'state': 177, 'flag': [34620898, 1], 'name': 'Fight The Mavericks'},
    41: {'id': 8, 'state': 193, 'flag': [34620900, 1], 'name': 'Secure The Biometal'},
    44: {'id': 9, 'state': 197, 'flag': [34620900, 5], 'name': 'Save The People'},
    51: {'id': 10, 'state': 201, 'flag': [34620901, 1], 'name': 'Recover The Disk'},
    55: {'id': 11, 'state': 204, 'flag': [34620901, 4], 'name': 'Attack The Excavators'},
    60: {'id': 12, 'state': 208, 'flag': [34620902, 0], 'name': 'Protect The Lab'},
    61: {'id': 14, 'state': 218, 'flag': [34620903, 2], 'name': 'Stop The Dig'},
    62: {'id': 14, 'state': 218, 'flag': [34620903, 2], 'name': 'Stop The Dig'},
    63: {'id': 14, 'state': 218, 'flag': [34620903, 2], 'name': 'Stop The Dig'},
    65: {'id': 15, 'state': 221, 'flag': [34620903, 5], 'name': 'Repel The Army'},
    66: {'id': 15, 'state': 221, 'flag': [34620903, 5], 'name': 'Repel The Army'},
}

# --- Modelo inicial (tutorial-skip, v0.2; exp171/176/178-180) ---
# Posesión de modelos = flags del bloque de progreso (tablas de
# categorías 0x020DE9AC/0x020DEB78; Hu hardcoded). El save dorado
# arranca con Model X: para otros arranques se REVOCA X (CF.7) y
# se pone la posesión + modelo activo (0x0214FC74) elegidos.
MODEL_X_POSSESSION = [0x021045CF, 7]
ACTIVE_MODEL_ADDR = 0x0214FC74
# starting_model key -> {grant:[[addr,bit]..], revoke_x, active}
STARTING_MODELS = {
    'model_x':  {'grant': [[0x021045CF, 7]], 'revoke_x': False, 'active': 1},
    'none':     {'grant': [], 'revoke_x': True, 'active': 0},
    'model_zx': {'grant': [[0x021045D0, 0]], 'revoke_x': True, 'active': 2},
    'model_hx': {'grant': [[0x021045D1, 1]], 'revoke_x': True, 'active': 3},
    'model_fx': {'grant': [[0x021045D1, 5]], 'revoke_x': True, 'active': 4},
    'model_lx': {'grant': [[0x021045D1, 3]], 'revoke_x': True, 'active': 5},
    'model_px': {'grant': [[0x021045D1, 7]], 'revoke_x': True, 'active': 6},
    'model_ox': {'grant': [[0x021045D2, 1]], 'revoke_x': True, 'active': 7},
}
# starting_model key -> item AP equivalente (para precollect)
STARTING_MODEL_ITEM = {
    'model_x': 'Model X', 'model_zx': 'Model ZX',
    'model_hx': 'Biometal H', 'model_fx': 'Biometal F',
    'model_lx': 'Biometal L', 'model_px': 'Biometal P',
    'model_ox': 'Biometal O',
}
# Transervers de arranque: key -> (subárea, x_px, y_px). v0.2:
# solo el hub (el save dorado ya deja ahí; sin teleport). Crecerá
# al cablear la lógica de regiones.
STARTING_TRANSERVERS = {
    'guardian_hub': (70, 288, 351),
}
