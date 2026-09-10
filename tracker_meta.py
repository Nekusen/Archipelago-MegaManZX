"""GENERADO por tools/gen_tracker_pack.py — no editar a mano.

Índices de maps.json y transformaciones (ox, oy, escala) de cada sala
dentro de su mapa de área y de su mapa de sala, para convertir la
posición del jugador (subárea, x, y) en píxeles del mapa (UT: auto-tab
e icono; worlds/mmzx/tracker_pos.py)."""

MAP_INDEX = {'area_a': 0, 'area_b': 1, 'area_c': 2, 'area_d': 3, 'area_e': 4, 'area_f': 5, 'area_g': 6, 'area_h': 7, 'area_i': 8, 'area_j': 9, 'area_k': 10, 'area_l': 11, 'area_m': 12, 'area_n': 13, 'area_o': 14, 'area_x': 15, 'room_a01': 16, 'room_a02': 17, 'room_a03': 18, 'room_a04': 19, 'room_b01': 20, 'room_b02': 21, 'room_b03': 22, 'room_b04': 23, 'room_c01': 24, 'room_c02': 25, 'room_c03': 26, 'room_d01': 27, 'room_d02': 28, 'room_d03': 29, 'room_d04': 30, 'room_d05': 31, 'room_e01': 32, 'room_e02': 33, 'room_e03': 34, 'room_e04': 35, 'room_e05': 36, 'room_e06': 37, 'room_e07': 38, 'room_e08': 39, 'room_f01': 40, 'room_f02': 41, 'room_f03': 42, 'room_f04': 43, 'room_f05': 44, 'room_g01': 45, 'room_g02': 46, 'room_g03': 47, 'room_g04': 48, 'room_g05': 49, 'room_h01': 50, 'room_h02': 51, 'room_h03': 52, 'room_h04': 53, 'room_i01': 54, 'room_i02': 55, 'room_i03': 56, 'room_i04': 57, 'room_i05': 58, 'room_j01': 59, 'room_j02': 60, 'room_j03': 61, 'room_j04': 62, 'room_j05': 63, 'room_k01': 64, 'room_k03': 65, 'room_k04': 66, 'room_k05': 67, 'room_l01': 68, 'room_l02': 69, 'room_l03': 70, 'room_l04': 71, 'room_m01': 72, 'room_m02': 73, 'room_m03': 74, 'room_n01': 75, 'room_o01': 76, 'room_o02': 77, 'room_x01': 78, 'room_x02': 79, 'room_x03': 80, 'room_z01': 81, 'room_z02': 82}

SUB_TO_ROOM = {1: 'a01', 2: 'a02', 3: 'a03', 4: 'a04', 5: 'b01', 6: 'b02', 7: 'b03', 8: 'b04', 9: 'c01', 10: 'c02', 11: 'c03', 15: 'd01', 16: 'd02', 17: 'd03', 18: 'd04', 19: 'd05', 20: 'e01', 21: 'e02', 22: 'e03', 23: 'e04', 24: 'e05', 25: 'e06', 26: 'e07', 27: 'e08', 28: 'f01', 29: 'f02', 30: 'f03', 31: 'f04', 32: 'f05', 33: 'g01', 34: 'g02', 35: 'g03', 36: 'g04', 37: 'g05', 38: 'h01', 39: 'h02', 40: 'h03', 41: 'h04', 42: 'i01', 43: 'i02', 44: 'i03', 45: 'i04', 46: 'i05', 47: 'j01', 48: 'j02', 49: 'j03', 50: 'j04', 51: 'j05', 52: 'k01', 54: 'k03', 55: 'k04', 56: 'k05', 57: 'l01', 58: 'l02', 59: 'l03', 60: 'l04', 61: 'm01', 62: 'm02', 63: 'm03', 64: 'n01', 65: 'o01', 66: 'o02', 67: 'x01', 68: 'x02', 69: 'x03', 70: 'z01', 71: 'z02'}

ROOMS = {
    'a01': {'area_map': 0, 'area_xf': [0, 124, 0.25], 'room_map': 16, 'room_xf': [0, 34, 0.25], 'sub': 1},
    'a02': {'area_map': 0, 'area_xf': [0, 500, 0.25], 'room_map': 17, 'room_xf': [0, 34, 0.25], 'sub': 2},
    'a03': {'area_map': 0, 'area_xf': [0, 828, 0.25], 'room_map': 18, 'room_xf': [0, 34, 0.5], 'sub': 3},
    'a04': {'area_map': 0, 'area_xf': [0, 1156, 0.25], 'room_map': 19, 'room_xf': [0, 34, 0.5], 'sub': 4},
    'b01': {'area_map': 1, 'area_xf': [0, 124, 0.25], 'room_map': 20, 'room_xf': [0, 34, 0.25], 'sub': 5},
    'b02': {'area_map': 1, 'area_xf': [0, 500, 0.25], 'room_map': 21, 'room_xf': [0, 34, 0.25], 'sub': 6},
    'b03': {'area_map': 1, 'area_xf': [0, 828, 0.25], 'room_map': 22, 'room_xf': [0, 34, 0.5], 'sub': 7},
    'b04': {'area_map': 1, 'area_xf': [0, 1348, 0.25], 'room_map': 23, 'room_xf': [0, 34, 0.5], 'sub': 8},
    'c01': {'area_map': 2, 'area_xf': [0, 196, 0.25], 'room_map': 24, 'room_xf': [0, 34, 0.25], 'sub': 9},
    'c02': {'area_map': 2, 'area_xf': [0, 668, 0.25], 'room_map': 25, 'room_xf': [0, 34, 0.25], 'sub': 10},
    'c03': {'area_map': 2, 'area_xf': [0, 1044, 0.25], 'room_map': 26, 'room_xf': [0, 34, 0.5], 'sub': 11},
    'd01': {'area_map': 3, 'area_xf': [0, 124, 0.188235], 'room_map': 27, 'room_xf': [0, 34, 0.25], 'sub': 15},
    'd02': {'area_map': 3, 'area_xf': [0, 381, 0.188235], 'room_map': 28, 'room_xf': [0, 34, 0.235294], 'sub': 16},
    'd03': {'area_map': 3, 'area_xf': [0, 602, 0.188235], 'room_map': 29, 'room_xf': [0, 34, 0.5], 'sub': 17},
    'd04': {'area_map': 3, 'area_xf': [777, 602, 0.188235], 'room_map': 30, 'room_xf': [0, 34, 0.437066], 'sub': 18},
    'd05': {'area_map': 3, 'area_xf': [0, 1509, 0.188235], 'room_map': 31, 'room_xf': [0, 34, 0.25], 'sub': 19},
    'e01': {'area_map': 4, 'area_xf': [0, 124, 0.285714], 'room_map': 32, 'room_xf': [0, 34, 0.5], 'sub': 20},
    'e02': {'area_map': 4, 'area_xf': [1176, 124, 0.285714], 'room_map': 33, 'room_xf': [0, 34, 1.0], 'sub': 21},
    'e03': {'area_map': 4, 'area_xf': [0, 548, 0.285714], 'room_map': 34, 'room_xf': [0, 34, 0.5], 'sub': 22},
    'e04': {'area_map': 4, 'area_xf': [0, 807, 0.285714], 'room_map': 35, 'room_xf': [0, 34, 0.5], 'sub': 23},
    'e05': {'area_map': 4, 'area_xf': [0, 1231, 0.285714], 'room_map': 36, 'room_xf': [0, 34, 0.5], 'sub': 24},
    'e06': {'area_map': 4, 'area_xf': [1176, 1231, 0.285714], 'room_map': 37, 'room_xf': [0, 34, 1.0], 'sub': 25},
    'e07': {'area_map': 4, 'area_xf': [0, 1710, 0.285714], 'room_map': 38, 'room_xf': [0, 34, 1.0], 'sub': 26},
    'e08': {'area_map': 4, 'area_xf': [591, 1710, 0.285714], 'room_map': 39, 'room_xf': [0, 34, 0.5], 'sub': 27},
    'f01': {'area_map': 5, 'area_xf': [0, 124, 0.285714], 'room_map': 40, 'room_xf': [0, 34, 0.5], 'sub': 28},
    'f02': {'area_map': 5, 'area_xf': [0, 438, 0.285714], 'room_map': 41, 'room_xf': [0, 34, 0.5], 'sub': 29},
    'f03': {'area_map': 5, 'area_xf': [0, 917, 0.285714], 'room_map': 42, 'room_xf': [0, 34, 0.5], 'sub': 30},
    'f04': {'area_map': 5, 'area_xf': [0, 1506, 0.285714], 'room_map': 43, 'room_xf': [0, 34, 0.5], 'sub': 31},
    'f05': {'area_map': 5, 'area_xf': [1176, 1506, 0.285714], 'room_map': 44, 'room_xf': [0, 34, 1.0], 'sub': 32},
    'g01': {'area_map': 6, 'area_xf': [0, 124, 0.2], 'room_map': 45, 'room_xf': [0, 34, 0.5], 'sub': 33},
    'g02': {'area_map': 6, 'area_xf': [825, 124, 0.2], 'room_map': 46, 'room_xf': [0, 34, 0.308517], 'sub': 34},
    'g03': {'area_map': 6, 'area_xf': [1036, 124, 0.2], 'room_map': 47, 'room_xf': [0, 34, 1.0], 'sub': 35},
    'g04': {'area_map': 6, 'area_xf': [1452, 124, 0.2], 'room_map': 48, 'room_xf': [0, 34, 1.0], 'sub': 36},
    'g05': {'area_map': 6, 'area_xf': [0, 1470, 0.2], 'room_map': 49, 'room_xf': [0, 34, 0.5], 'sub': 37},
    'h01': {'area_map': 7, 'area_xf': [0, 124, 0.25], 'room_map': 50, 'room_xf': [0, 34, 0.25], 'sub': 38},
    'h02': {'area_map': 7, 'area_xf': [0, 548, 0.25], 'room_map': 51, 'room_xf': [0, 34, 0.5], 'sub': 39},
    'h03': {'area_map': 7, 'area_xf': [0, 972, 0.25], 'room_map': 52, 'room_xf': [0, 34, 0.5], 'sub': 40},
    'h04': {'area_map': 7, 'area_xf': [0, 1300, 0.25], 'room_map': 53, 'room_xf': [0, 34, 0.5], 'sub': 41},
    'i01': {'area_map': 8, 'area_xf': [0, 124, 0.2], 'room_map': 54, 'room_xf': [0, 34, 0.5], 'sub': 42},
    'i02': {'area_map': 8, 'area_xf': [825, 124, 0.2], 'room_map': 55, 'room_xf': [0, 34, 0.5], 'sub': 43},
    'i03': {'area_map': 8, 'area_xf': [0, 471, 0.2], 'room_map': 56, 'room_xf': [0, 34, 0.5], 'sub': 44},
    'i04': {'area_map': 8, 'area_xf': [825, 471, 0.2], 'room_map': 57, 'room_xf': [0, 34, 0.5], 'sub': 45},
    'i05': {'area_map': 8, 'area_xf': [0, 1049, 0.2], 'room_map': 58, 'room_xf': [0, 34, 0.5], 'sub': 46},
    'j01': {'area_map': 9, 'area_xf': [0, 124, 0.285714], 'room_map': 59, 'room_xf': [0, 34, 1.0], 'sub': 47},
    'j02': {'area_map': 9, 'area_xf': [591, 124, 0.285714], 'room_map': 60, 'room_xf': [0, 34, 0.5], 'sub': 48},
    'j03': {'area_map': 9, 'area_xf': [0, 548, 0.285714], 'room_map': 61, 'room_xf': [0, 34, 0.5], 'sub': 49},
    'j04': {'area_map': 9, 'area_xf': [1176, 548, 0.285714], 'room_map': 62, 'room_xf': [0, 34, 1.0], 'sub': 50},
    'j05': {'area_map': 9, 'area_xf': [0, 972, 0.285714], 'room_map': 63, 'room_xf': [0, 34, 0.5], 'sub': 51},
    'k01': {'area_map': 10, 'area_xf': [0, 124, 0.25], 'room_map': 64, 'room_xf': [0, 34, 0.25], 'sub': 52},
    'k03': {'area_map': 10, 'area_xf': [0, 548, 0.25], 'room_map': 65, 'room_xf': [0, 34, 1.0], 'sub': 54},
    'k04': {'area_map': 10, 'area_xf': [518, 548, 0.25], 'room_map': 66, 'room_xf': [0, 34, 0.444444], 'sub': 55},
    'k05': {'area_map': 10, 'area_xf': [1676, 548, 0.25], 'room_map': 67, 'room_xf': [0, 34, 0.655599], 'sub': 56},
    'l01': {'area_map': 11, 'area_xf': [0, 124, 0.25], 'room_map': 68, 'room_xf': [0, 34, 0.25], 'sub': 57},
    'l02': {'area_map': 11, 'area_xf': [0, 452, 0.25], 'room_map': 69, 'room_xf': [0, 34, 0.444444], 'sub': 58},
    'l03': {'area_map': 11, 'area_xf': [0, 1020, 0.25], 'room_map': 70, 'room_xf': [0, 34, 0.444444], 'sub': 59},
    'l04': {'area_map': 11, 'area_xf': [0, 1588, 0.25], 'room_map': 71, 'room_xf': [0, 34, 0.5], 'sub': 60},
    'm01': {'area_map': 12, 'area_xf': [0, 124, 0.25], 'room_map': 72, 'room_xf': [0, 34, 0.25], 'sub': 61},
    'm02': {'area_map': 12, 'area_xf': [0, 404, 0.25], 'room_map': 73, 'room_xf': [0, 34, 0.5], 'sub': 62},
    'm03': {'area_map': 12, 'area_xf': [0, 828, 0.25], 'room_map': 74, 'room_xf': [0, 34, 0.5], 'sub': 63},
    'n01': {'area_map': 13, 'area_xf': [0, 34, 0.5], 'room_map': 75, 'room_xf': [0, 34, 0.5], 'sub': 64},
    'o01': {'area_map': 14, 'area_xf': [0, 124, 0.25], 'room_map': 76, 'room_xf': [0, 34, 0.25], 'sub': 65},
    'o02': {'area_map': 14, 'area_xf': [0, 596, 0.25], 'room_map': 77, 'room_xf': [0, 34, 0.25], 'sub': 66},
    'x01': {'area_map': 15, 'area_xf': [0, 124, 0.4], 'room_map': 78, 'room_xf': [0, 34, 0.5], 'sub': 67},
    'x02': {'area_map': 15, 'area_xf': [0, 932, 0.4], 'room_map': 79, 'room_xf': [0, 34, 1.0], 'sub': 68},
    'x03': {'area_map': 15, 'area_xf': [825, 932, 0.4], 'room_map': 80, 'room_xf': [0, 34, 1.0], 'sub': 69},
    'z01': {'area_map': None, 'area_xf': None, 'room_map': 81, 'room_xf': [0, 34, 0.338374], 'sub': 70},
    'z02': {'area_map': None, 'area_xf': None, 'room_map': 82, 'room_xf': [0, 34, 0.349653], 'sub': 71},
}

# Mapa general (interordi): índice y punto (x, y) del marcador de cada área
OVERALL_MAP = None
OVERALL_POINTS = {}
# Mapa general: punto (x, y) de la caja de cada sala (icono de posición fuera del hub)
OVERALL_ROOM_POINTS = {}
