"""BizHawkClient de Mega Man ZX (USA). Enfoque RAM-directa (no runtime ASM).

Direcciones y recetas: docs/client_integration.md + worlds/mmzx/data.py.
Dominio de memoria: "ARM9 System Bus" con direcciones absolutas 0x02xxxxxx
(verificar el mapeo del core melonDS al montar; ver playbook §1).
"""

import collections
import time
from typing import TYPE_CHECKING, Any

import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

from .data import (LOCATIONS, ITEMS, GOAL_BITS, GOAL_BITS_ALT, MISSION_ACCEPT,
                   MISSION_STATE_ADDR, MISSION_ACTIVE_FLAG,
                   STARTING_MODELS, STARTING_MODEL_ITEM, STARTING_TRANSERVERS,
                   MODEL_X_POSSESSION, ACTIVE_MODEL_ADDR)
from .data import EVENT_GATES, EVENT_GATES_OPEN, EVENT_GATES_ALL6
from .data import HUB_FLOOR_BOSS, HUB_FLOOR_DOOR_X, HUB_FLOOR_Y, WARP_DESTINATIONS
from .data import PICKUP_MAILBOX_ADDR, PICKUP_MAILBOX_SLOTS
from .data import PICKUP_MARK_TABLE_ADDR, PICKUP_MARK_SLOT, NOTIFY_ADDR, NOTIFY_BUF_MAX, NOTIFY_POPUP_GLYPHS
from .golden import GOLDEN_IMAGE, GOLDEN_IMAGE_ADDR, build_image

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext

DOM = "ARM9 System Bus"

# Anclas (docs/client_integration.md)
LIVE_BLOCK = 0x021045CC       # copia viva del bloque de progreso
# Card Keys: bits de llave por dirección (derivados de ITEMS). El juego las
# REGALA por su cuenta en las recompensas de misión (exp505: al menos Verde
# en FUN_02031028 estado 0xAB, Azul en 0xAE y Amarilla en FUN_02094288), así
# que su posesión es AUTORITATIVA desde AP: se escribe exactamente el conjunto
# recibido, respetando el resto de bits del byte (que son otros flags).
CARDKEY_MASKS: dict[int, int] = {}
for _kn, _kv in ITEMS.items():
    if _kn.endswith("Card Key") and _kv["grant"][0] == "live_bit":
        CARDKEY_MASKS[_kv["grant"][1]] = CARDKEY_MASKS.get(_kv["grant"][1], 0) | (1 << _kv["grant"][2])
CANON_BLOCK = 0x021602B4      # copia canónica (conceder = set bit aquí)
LIVE_LEN = 0x60               # ventana viva a leer (cubre disks/misiones/keys)
PLAYER_POS = 0x0214FB64      # u32 x<<8 (0x0214FB64) y u32 y<<8 (0x0214FB68); px = >>8
                             # (exp342: la doc decía FB65/FB69, que da basura leído como u32)
POS_KEY = "mmzx_pos_%d"     # almacén de datos: [subárea, x, y] para UT (auto-tab/icono)
POS_INTERVAL = 1.0           # s entre envíos si no cambia la subárea
POS_MIN_DELTA = 48           # px de movimiento mínimo para reenviar
PLAYTIME = 0x021602A8        # u32 tiempo de juego en frames (cabecera de la imagen del save;
                             # exp497: +1/frame en juego, no retrocede al morir, vuelve al valor
                             # del save con Game Over→Continue/LOAD, 0 en partida nueva)
CONS_KEY = "mmzx_consumables_%s_%s"  # almacén de datos por (team, slot): [[aplicados, playtime], ...]


def _consumables_present(log, playtime: int) -> int:
    """Cuántos consumibles (en orden del servidor) están YA en el estado actual
    de la partida: el mayor acumulado de los lotes aplicados con playtime <=
    el actual (los posteriores se rebobinaron con Continue/LOAD/partida nueva)."""
    return max([int(e[0]) for e in log if int(e[1]) <= playtime], default=0)

# Weapon Energy (agente exp390-399): tope de WE de un modelo = 4 x (nivel de
# victoria del 1er jefe + del 2o jefe del par); los niveles (1-4) son 8 bytes
# del bloque de partida 0x02104634..3B (orden Hivolt, Lurerre, Fistleo,
# Purprill, Hurricaune, Leganchor, Flammole, Protectos) que solo escribe la
# victoria real (FUN_02009438). Con el biometal concedido por flag quedan a 0
# -> tope 0 -> barra vacia y los pickups no rellenan. Receta: al poseer el
# modelo, si lv0+lv1 < 4 poner lv0 = 4 - lv1 (vivo+canonica; tope 16 como
# tras el 1er jefe) y llenar la barra (u8[0x0214FC92 + modelo] = 16) UNA vez.
BOSS_LEVELS = 0x02104634
MODEL_LEVEL_IDX = {3: (0, 4), 4: (2, 6), 5: (1, 5), 6: (3, 7)}   # HX, FX, LX, PX
WE_BASE = 0x0214FC92          # + modelo activo (3..6) = WE actual del modelo
WE_FULL = 16
MSG_BANK = 0x02104588         # u32 índice del último banco de texto (0xFFFFFFFF = boot)
LIFEUP_BYTE = 0x0214FC77
SUBTANK_BYTE = 0x0214FC78
ECRYSTALS = 0x0214FC70        # u24
HP = 0x0214FBB2
MODEL = 0x0214FC74
SUBAREA_STABLE = 0x02108228
GAME_STATE = 0x0215E6D8       # 0x500 = en juego
STATE_INGAME = 0x500
STATE_LOAD = 0x400            # el juego carga la escena (teleport)
# Carrusel del título (objeto estático 0x0214CD6C, literal DAT_020160C4 de
# FUN_02015f98 / DAT_02017F54 de FUN_02017e68). Byte +4 = PASO (exp269n/q):
#   0..2 = logos/boot, 3 = título "Press START", 5 = menús del título (New
#   Game/Continue, Easy/Normal, Vent/Aile, y también el menú "Exit Game" de la
#   pantalla de Game Over, que re-entra en este carrusel), 4 = título/attract,
#   6 = partida lanzada (se pone en el MISMO frame en que se pide New Game
#   (modo 0x10000) o Continue (modo 3) y ya no vuelve a <6 hasta el próximo
#   Game Over/título). Mientras el paso es 3 o 5 nada escribe el bloque de
#   escena 0x021602A8 (exp262/269c: sin writers), así que es el momento
#   seguro para sembrar la imagen dorada.
TITLE_CAROUSEL_STEP = 0x0214CD70
TITLE_STEPS_SEEDABLE = (3, 5)
SCENE_DESC = 0x0216047C       # descriptor de escena (spawn X/Y + subárea)
LIVES = 0x0214FC6C
HPMAX = 0x0214FC76

CANON_OFF = CANON_BLOCK - LIVE_BLOCK  # 0x21602B4 - 0x21045CC

# #5 (exp240 + rom.py §1c) + posesión autoritativa (2026-09-03): modelo
# activo (0x0214FC74) -> (item AP, bit de posesión que SOLO pone ese item).
# Sirve para revertir una forma no recibida y para limpiar cualquier bit de
# posesión que aparezca sin su item (ZX de Troop D0.0, X del LOAD, etc.).
MODEL_POSSESSION = {
    # X: flag 31 (0x021045CF.7; la imagen dorada lo trae puesto o quitado
    # según el YAML). En el playtest 5 apareció X usable sin item -> se
    # trata como cualquier otro modelo (revertir + limpiar el bit).
    1: ("Model X", 0x021045CF, 7),
    2: ("Model ZX", 0x021045D0, 0),
    # H/F/L/P: flags LIBRES 0x02104627.0-3 (agente exp380-389); los bits
    # D0/D1 los escriben los jefes del par y ya no conceden nada.
    3: ("Progressive Model HX", 0x02104627, 0),
    4: ("Progressive Model FX", 0x02104627, 1),
    5: ("Progressive Model LX", 0x02104627, 2),
    6: ("Progressive Model PX", 0x02104627, 3),
    7: ("Model OX", 0x021045D2, 1),
}
# 2ª MITAD de H/F/L/P = 2ª copia del item progresivo (exp444-447c, 2026-09-03):
# flags LIBRES 0x02104626.0-3 (720-723) = list[1] de la categoría del modelo
# (rom.py BIOMETAL_CAT_PATCH, count vanilla 2). Con las dos mitades
# model_owned_count == 2 -> ataque cargado de nivel 2 (tope del contador de
# carga 0x78; HX: huracán soltando la carga en el aire con salto+ARRIBA,
# exp446k) y tope de WE 32 (niveles 4+4). Sin la 2ª copia el cliente limpia
# este bit (la tienda de niveles FUN_02045084 lo re-deriva de los niveles).
MODEL_PART2 = {
    3: (0x02104626, 0), 4: (0x02104626, 1), 5: (0x02104626, 2), 6: (0x02104626, 3),
}

# Byte "misión en curso" del bloque de partida (0x0210460C+0x1F): bit1 lo
# pone FUN_02031f10 al aceptar (id<17), bit2 para misiones de historia;
# FUN_02009184 ("¿misión X activa?") exige (&6). Lo limpia el Report.
# Canónica en +0x5BCE8. Sin él, la arena del jefe no se armaba (exp229/231).
MISSION_ACTIVE_BYTE = 0x0210462B
# Bloque de estado de HISTORIA (agente exp350-359): id de mision activa +
# objeto del handler por mision (tabla 0x020CF0F4). Sin instalarlo, el
# force-accept no dispara cutscenes ni flags por rectangulo (verjas).
STORY_BLOCK = 0x0214F6BC           # bloque de historia (0x11C B: +4 id, +8 objeto del handler)
STORY_BLOCK_CANON = 0x02160554     # su copia de checkpoint (la restaura la muerte)
# INSTANTÁNEA DE INICIO DE MISIÓN (exp452, 2026-09-03): al aceptar una misión en la
# consola, FUN_02022744 copia canónica A → espejo B, descriptor 1 → descriptor 2 y
# cola 1 → cola 2. "Abort Mission" (FUN_020946f0 → FUN_02022630 → estado 0x300)
# restaura ESOS espejos (bloque de progreso, posición/escena y guion de historia).
# Con la aceptación forzada del cliente nunca se refrescaban y el Abort volvía al
# contenido de la imagen dorada / del tutorial (A-1, modelo humano, bloque en
# blanco). El cliente los replica al auto-aceptar (antes de escribir la misión).
BLOCK_MIRROR = 0x02160398          # espejo B del bloque de progreso (0xE4 B; = canónica + 0xE4)
SCENE_DESC_MIRROR = 0x021604E8     # descriptor 2 (0x6C B; = descriptor 1 + 0x6C)
STORY_BLOCK_MIRROR = 0x02160670    # cola 2 (0x11C B; = cola 1 + 0x11C)
SCENE_DESC_LEN, STORY_BLOCK_LEN, LIVE_BLOCK_LEN = 0x6C, 0x11C, 0xE4
CUTSCENE_FLAG = 0x0214F502         # bit0 = cutscene/guion de historia en curso
# Troop Reinforcement: la escena de Giro del final de D-2 (y con ella el jefe
# Model Z) solo se dispara si 0x02104602.1 = 0 (VERIFICADO exp507d: con el bit
# puesto no ocurre NADA a ninguna altura ni en toda la sala). Ese bit lo pone
# el juego en el megamerge; si el jugador muere después sin que la misión
# llegue a reportarse, D-2 se queda vacía PARA SIEMPRE y Troop es
# incompletable. El cliente lo limpia mientras Troop sea la misión activa y no
# esté completada (ver _troop_unstick).
TROOP_STATE = 162                  # 0xA2 = estado "Troop Reinforcement aceptada"
TROOP_MERGE = (0x02104602, 1)      # flag "megamerge de Troop hecho"
STORY_HANDLER_ID = 0x0214F6C0
STORY_HANDLER_OBJ = 0x0214F6C4     # 0x114 B; +9 = id de cutscene (0xFF = ninguna)

# Subáreas de JEFE (y de fin de misión) donde NO se auto-acepta al entrar
# (exp212/213): e07 26, f05 32, g05 37, i03 44, k04 55, l04 60, m03 63,
# o02 66; h04 41, j05 51, d05 19.
BOSS_SUBAREAS = {26, 32, 37, 44, 55, 60, 63, 66, 41, 51, 19}   # informativo; ya no excluye (agente exp379: sin corrupción con la guarda OAM)

ROM_GAME_CODE = b"ARZE"       # MMZX USA

# Hub por defecto del anti-softlock (z01 = subárea 70): ENCIMA del pad de la
# consola del Transerver (plataforma elevada en x=384, y=335; el spawn del
# skip (288,351) queda fuera de su hitbox y UP no hace nada — exp251-259/272).
# (384,351) NO vale: queda dentro de la plataforma y el jugador cae al piso
# de abajo.
HUB_SUBAREA, HUB_X, HUB_Y = 70, 384, 335

# "Go to Transerver" DESDE EL MENÚ (2026-09-03, exp432-442): en la pestaña
# MISSION (mapa) del menú de pausa, Y ("Y Button:Go to Transerver", texto
# parcheado) hace que el parche de ROM (rom.py §1g) ponga WARP_REQ = 1 y
# cierre el menú. El cliente, ya en juego, consume la petición y abre la
# lista "Target Area" DEL JUEGO (la misma que ofrece la consola del
# Transerver: solo destinos con su bit de acceso, sea por item o por haber
# pisado el piso), pidiendo el estado 0x50700 como hace la consola
# (FUN_02021070(0x0215D7F8, 0x50700)) con la "estación actual" a -1 para que
# no excluya ninguna. Al cerrarse la lista el juego deja en TRANSPORT_SEL el
# índice elegido (0..12; -1 = cancelada con B) y vuelve a gameplay sin
# moverse (en la consola es el guion del Operator quien recoloca al
# jugador y pide el estado 0x600): el cliente teletransporta entonces al
# piso del hub de ese destino, (384, y_piso-17), exactamente donde deja el
# Transport vanilla. Índices: 0 A-2, 1 B-2, 2 C-2, 3 D-2, 4 E-7, 5 F-5,
# 6 G-5, 7 I-3, 8 K-4, 9 L-4, 10 M-3, 11 O-2, 12 X-1 (tabla 0x020DB0A4).
# Estado de botones (exp432/433): u16 0x020F2768 = mantenidos este frame
# (máscara NitroSDK: A 1, B 2, SELECT 4, START 8, →/←/↑/↓ 0x10..0x80,
# R 0x100, L 0x200, X 0x400, Y 0x800), 0x020F276A = frame anterior.
WARP_REQ = 0x020CB9D0          # u8: 1 = petición pendiente (la pone el cave A, la borra el cliente)
PAD_HELD = 0x020F2768
TRANSPORT_SEL = 0x021046A8     # u32: selección de la lista "Target Area" (0x0210464C+0x5C); -1 = ninguna
STATE_TARGET_AREA = 0x00050700 # petición de estado que abre la lista (la consola: DAT_02093E64)
STATION_ROOMS = list(WARP_DESTINATIONS) + ["x01"]   # índice de estación -> sala del Transerver
HUB_PAD_DY = 17                # la consola de cada piso está 17 px por encima del piso

# Diagnóstico de flags: ventana ancha del bloque de progreso (cubre
# misiones/quests/historia/HQ) para trazar qué bits cambian al completar
# una misión en vivo.
FLAG_WATCH_BASE, FLAG_WATCH_LEN = 0x021045C0, 0x84

# Pickups respawneables como checks (v0.2, agente exp360-369): el parche
# rom.py PICKUP_MAILBOX_* escribe en un BUZÓN de RAM (u32 contador + anillo
# de PICKUP_MAILBOX_SLOTS entradas [sub, idx, role, 0]) cada refill de
# layout recogido. Opciones de slot_data que activan el sondeo.
PICKUP_OPTION_KEYS = ("pickup_checks_1up", "pickup_checks_energy",
                      "pickup_checks_weapon", "pickup_checks_crystals")


# --- Avisos en pantalla (parche rom.py NOTIFY_*; agente exp473-480,
# docs/v02_notes.md §2a) ---
# El cave abre el popup pequeño del juego (el de "Found a Life Up!", no
# bloquea) con el texto que el cliente deja en NOTIFY_ADDR: u8 REQ (1 = texto
# en BUF; el cave lo pone a 0 al cerrarse el aviso), u8 STATE (del cave), u16
# DUR (frames con el texto entero), BUF en +4 (fuente del juego = ASCII-0x20,
# fin 0xFE). Una línea de NOTIFY_POPUP_GLYPHS glifos; los controles de color
# (F1 03 verde / F1 00 blanco) no cuentan. Umbrales por clase de item con
# /mmzx_notify (received/sent: off, progression, useful = progresión+útil, all).
NOTIFY_DUR = 90
NOTIFY_LEVELS = ("off", "progression", "useful", "all")
NOTIFY_PUNCT = {"!": 0x01, "'": 0x07, ",": 0x0C, "-": 0x0D, ".": 0x0E, ":": 0x1A, "?": 0x1F}
NOTIFY_GREEN, NOTIFY_WHITE = b"\xf1\x03", b"\xf1\x00"
NOTIFY_QUEUE_MAX = 16


def encode_text(text: str, terminate: bool = True) -> bytes:
    """Codifica con la fuente de MMZX (ASCII-0x20; verificado en pantalla para
    espacio, dígitos, A-Z, a-z y la puntuación de NOTIFY_PUNCT; el resto -> espacio)."""
    out = bytearray()
    for ch in text:
        if ch == " ":
            out.append(0x00)
        elif "0" <= ch <= "9":
            out.append(0x10 + ord(ch) - 0x30)
        elif "A" <= ch <= "Z":
            out.append(0x21 + ord(ch) - 0x41)
        elif "a" <= ch <= "z":
            out.append(0x41 + ord(ch) - 0x61)
        elif ch in NOTIFY_PUNCT:
            out.append(NOTIFY_PUNCT[ch])
        else:
            out.append(0x00)
    if terminate:
        out.append(0xFE)
    return bytes(out)


def notify_bytes(head: str, item: str, tail: str) -> bytes:
    """head + item (en verde) + tail, en una línea de NOTIFY_POPUP_GLYPHS glifos:
    si no cabe se sacrifica primero tail (' from Alice') y luego se recorta el item."""
    n = NOTIFY_POPUP_GLYPHS
    if len(head) + len(item) + len(tail) > n:
        tail = ""
    if len(head) + len(item) > n:
        item = item[:max(0, n - len(head) - 1)] + "."
    data = (encode_text(head, False) + NOTIFY_GREEN + encode_text(item, False)
            + NOTIFY_WHITE + encode_text(tail, False) + b"\xfe")
    if len(data) > NOTIFY_BUF_MAX:
        data = data[:NOTIFY_BUF_MAX - 1] + b"\xfe"
    return data


def item_level(flags: int) -> int:
    """Nivel de un item para el umbral de avisos: 1 progression, 2 useful, 3 resto."""
    if flags & 0b001:
        return 1
    if flags & 0b010:
        return 2
    return 3


class MMZXClient(BizHawkClient):
    game = "Mega Man ZX"
    system = "NDS"
    patch_suffix = ".apmmzx"

    def __init__(self) -> None:
        super().__init__()
        self.local_checked: set[int] = set()
        self.cons_log = None          # consumibles aplicados: [[n acumulado, playtime]] (datastore); None = sin resolver
        self.cons_key = None
        self.cons_requested = False
        self.death_link_enabled = False
        self.death_link_setup = False
        self.mission_auto_accept = False   # modo open-world (slot_data)
        self.mission_setup = False
        self.last_accept_sub = None        # última subárea auto-aceptada
        self.force_accept = False          # /mmzx_accept: forzar en el próximo tick
        self._stage_failed: set[str] = set()   # etapas con excepción ya trazada
        self.pending_where = False         # /mmzx_where: volcar posición/estado al log
        self.prev_hp = None
        self.prev_death_link = None
        self.pending_death = False
        self.pending_teleport = None   # (subárea, x, y) o None
        self.transport_wait = False    # lista "Target Area" abierta por el cliente: leer la selección al volver
        self.added_commands = False
        self._win: tuple[int, int] | None = None   # ventana de detección (cache)
        # diagnóstico de flags (para mapear "misión completada" en vivo)
        self.flag_watch = False
        self.flag_snap: bytes | None = None
        self.pending_dump = False   # /mmzx_dump: volcar estado del Transerver
        # tutorial-skip: aplicación one-shot del estado inicial (modelo YAML
        # + Transerver). 0=sin pedir, 1=esperando datastore, 2=aplicar
        # cuando sea elegible, 3=hecho. /mmzx_start fuerza el estado 2.
        self.start_state = 0
        self.start_key: str | None = None
        # el LOAD fuerza el modelo activo a X (0x0214FC74=1) durante la
        # entrada a la escena, PISANDO el que fija el cliente si llega antes.
        # Se re-aserta hasta que el valor deseado se mantenga N ticks.
        self.start_confirm = 0
        self.start_retries = 0
        # #5: último modelo activo "legítimo" (poseído por item AP, o Hu/X)
        # visto, para revertir si un megamerge de jefe / Troop fuerza una forma
        # que el jugador aún no ha recibido.
        self.last_legit_model = 1
        # buzón de pickups respawneables: contador visto, ids ya enviados
        # (las repeticiones por respawn se filtran aquí), mapa (sub, idx) ->
        # id de location y si el slot activa alguna categoría (slot_data).
        self.mailbox_count: int | None = None
        self.mailbox_checked: set[int] = set()
        self.mailbox_map: dict[tuple[int, int], int] | None = None
        self.mailbox_enabled: bool | None = None
        self.pos_last = None          # (sub, x, y, t) del último envío de posición
        # avisos en pantalla (parche NOTIFY): cola de textos ya codificados,
        # índice de items ya avisados (None = sincronizar sin backlog al
        # conectar), umbrales de /mmzx_notify, scouts pedidos (avisos 'Sent')
        self.notify_queue: collections.deque = collections.deque()
        self.notified_items: int | None = None
        self.notify_cfg = {"received": 2, "sent": 2}      # índices en NOTIFY_LEVELS
        self.scout_requested: set[int] = set()
        # marcador gris de pickups ya enviados (parche PICKUP_MARK)
        self.marks_enabled = True
        self.mark_written: tuple[int, bytes] | None = None
        self.mark_by_sub: dict[int, dict[int, int]] | None = None

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        from CommonClient import logger
        try:
            reads = await bizhawk.read(ctx.bizhawk_ctx, [
                (0x0C, 4, "ROM"),      # game code ARZE
                (0x1000, 6, "ROM"),    # magia AP (rom.py)
                (0x1010, 64, "ROM"),   # slot name
            ])
        except bizhawk.RequestFailedError:
            return False
        if reads[0] != ROM_GAME_CODE:
            return False
        if reads[1] != b"MZXAP\x00":
            logger.info("ERROR: esta ROM de Mega Man ZX no está parcheada "
                        "para Archipelago. Genera el parche .apmmzx y ábrelo "
                        "con el launcher para crear la ROM parcheada.")
            return False
        raw = reads[2]
        end = raw.find(b"\x00")
        try:
            self.slot_name = raw[:end if end >= 0 else 64].decode("utf-8")
        except UnicodeDecodeError:
            self.slot_name = None
        ctx.game = self.game
        # El parche NO pre-coloca items en la ROM: el cliente concede TODO
        # por RAM, incluidos los items locales y el start inventory.
        ctx.items_handling = 0b111
        ctx.want_slot_data = True
        ctx.watcher_timeout = 0.125
        self.local_checked = set()
        self.cons_log = None
        self.cons_key = None
        self.cons_requested = False
        self.death_link_setup = False
        self.prev_hp = None
        self.prev_death_link = None
        self.pending_death = False
        self.mailbox_count = None
        self.mailbox_checked = set()
        self.mailbox_enabled = None
        self.pos_last = None
        self.notify_queue.clear()
        self.notified_items = None
        self.scout_requested = set()
        self.mark_written = None
        return True

    async def set_auth(self, ctx: "BizHawkClientContext") -> None:
        if getattr(self, "slot_name", None):
            ctx.auth = self.slot_name

    def _detect_window(self) -> tuple[int, int]:
        """Rango [lo, hi) que cubre las direcciones de detect DEL BLOQUE de
        progreso (+ GOAL_BITS). Las direcciones lejanas (Life Ups/Sub Tanks:
        bytes de capacidad 0x0214FC77/78, nibble alto = recogido fisico) se
        leen aparte (self._extra_addrs) para no leer 190 KiB por tick."""
        if self._win is not None:
            return self._win
        addrs: list[int] = [a for a, _ in GOAL_BITS] + [a for a, _ in GOAL_BITS_ALT]
        for v in LOCATIONS.values():
            det = v.get("detect")
            if not det:
                continue
            if det[0] == "bit":
                addrs.append(det[1])
            elif det[0] in ("all", "any"):
                addrs += [a for a, _ in det[1]]
        near = [a for a in addrs if abs(a - LIVE_BLOCK) < 0x1000]
        self._extra_addrs = sorted({a for a in addrs if abs(a - LIVE_BLOCK) >= 0x1000})
        lo, hi = min(near), max(near) + 1
        self._win = (lo, hi)
        return self._win

    async def _in_game(self, ctx):
        """Devuelve (en_juego, state_bytes). state_bytes sirve de GUARD para
        que las escrituras solo se apliquen si el juego SIGUE en gameplay
        (no en menú/transición) — evita corromper una carga de escena."""
        try:
            reads = await bizhawk.read(ctx.bizhawk_ctx, [
                (SUBAREA_STABLE, 1, DOM), (HP, 1, DOM), (GAME_STATE, 4, DOM),
                (TITLE_CAROUSEL_STEP, 1, DOM)])
        except bizhawk.RequestFailedError:
            return False, None
        sub = reads[0][0]
        hp = reads[1][0]
        state_bytes = reads[2]
        state = int.from_bytes(state_bytes, "little")
        # El TÍTULO y sus menús también tienen gs=0x500, sub=1 y hp=16
        # (exp260-269): solo es gameplay real si el carrusel del título está
        # en "partida lanzada" (paso 6).
        launched = reads[3][0] == 6
        return (launched and sub != 0 and hp > 0 and state == STATE_INGAME), state_bytes

    async def _stage(self, name: str, coro) -> None:
        """Ejecuta una etapa del watcher capturando cualquier excepción: el
        framework de BizHawk no las captura y una sola mataría el bucle en
        silencio. Se traza en el log (una vez por etapa hasta que vuelva a
        funcionar)."""
        try:
            await coro
            self._stage_failed.discard(name)
        except bizhawk.RequestFailedError:
            raise
        except Exception:
            if name not in self._stage_failed:
                self._stage_failed.add(name)
                from CommonClient import logger
                logger.exception("[mmzx] etapa '%s' falló (se sigue con el resto)" % name)

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        if ctx.server is None or ctx.slot_data is None:
            return

        # DeathLink: activar tag una vez según slot_data
        if not self.death_link_setup:
            self.death_link_setup = True
            self.death_link_enabled = bool(ctx.slot_data.get("death_link", False))
            if self.death_link_enabled:
                await ctx.update_death_link(True)

        # Modo open-world: leer la opción una vez
        if not self.mission_setup:
            self.mission_setup = True
            self.mission_auto_accept = bool(ctx.slot_data.get("mission_auto_accept", False))

        # comandos de cliente (anti-softlock + diagnóstico de flags)
        if not self.added_commands:
            self.added_commands = True
            ctx.command_processor.commands["mmzx_teleport"] = _cmd_teleport
            ctx.command_processor.commands["mmzx_flags"] = _cmd_flags
            ctx.command_processor.commands["mmzx_dump"] = _cmd_dump
            ctx.command_processor.commands["mmzx_start"] = _cmd_start
            ctx.command_processor.commands["mmzx_accept"] = _cmd_accept
            ctx.command_processor.commands["mmzx_where"] = _cmd_where
            ctx.command_processor.commands["mmzx_notify"] = _cmd_notify
            ctx.command_processor.commands["mmzx_marks"] = _cmd_marks

        # ---- tutorial-skip: estado one-shot (datastore) + imagen dorada ----
        # Resolver PRONTO (también en menús) la máquina one-shot del modelo
        # YAML (0→1→2/3); solo la fase de APLICAR (2) requiere gameplay.
        await self._start_state_resolve(ctx)
        # Sembrar la imagen dorada en 0x021602A8 SIEMPRE que el título/menús
        # estén activos (independiente de start_state): "New Game" (redirigido
        # por el parche al handler de LOAD) entra a la escena con este bloque
        # -> hub post-tutorial, también tras un Game Over. Nunca durante una
        # carga ni en gameplay (ver _seed_golden_image).
        await self._seed_golden_image(ctx)

        in_game, state_bytes = await self._in_game(ctx)
        if not in_game:
            self.prev_hp = None
            self.ingame_ticks = 0
            return
        guard = (GAME_STATE, state_bytes, DOM)   # solo escribir si sigue en juego
        # Debounce de arranque (agente exp310-319): al lanzar la partida hay
        # ~37 frames en los que _in_game ya es True pero estructuras fuera del
        # bloque siguen con el relleno de boot 0xFF (p.ej. el struct de
        # mensajes 0x02104588). Ningún check ni escritura hasta que el juego
        # lleve varios ticks estable y el struct de mensajes esté inicializado.
        self.ingame_ticks = getattr(self, "ingame_ticks", 0) + 1
        if self.ingame_ticks < 3:
            return
        try:
            msg = (await bizhawk.read(ctx.bizhawk_ctx, [(MSG_BANK, 4, DOM)]))[0]
        except bizhawk.RequestFailedError:
            return
        if msg == bytes([0xFF] * 4):
            return

        if self.pending_where:
            self.pending_where = False
            await self._stage("where", self._log_where(ctx))

        # ---- posición del jugador -> almacén de datos (UT: auto-tab e icono) ----
        await self._stage("posicion", self._send_position(ctx))

        # ---- detectar checks ----
        # Ventana de lectura calculada de TODAS las direcciones de detect
        # (+ GOAL_BITS). Cubre el bloque de progreso 0x021045CC y tambien
        # el flag del Sub Tank A-2 (0x02104589, por debajo del bloque).
        lo, hi = self._detect_window()
        extra = self._extra_addrs
        try:
            reads = await bizhawk.read(ctx.bizhawk_ctx,
                                       [(lo, hi - lo, DOM)] + [(a, 1, DOM) for a in extra])
        except bizhawk.RequestFailedError:
            return
        block = reads[0]
        extra_val = {a: reads[1 + i][0] for i, a in enumerate(extra)}

        def bit_set(addr: int, bit: int) -> bool:
            if lo <= addr < hi:
                return bool(block[addr - lo] & (1 << bit))
            if addr in extra_val:
                return bool(extra_val[addr] & (1 << bit))
            return False

        checked = set()
        for name, v in LOCATIONS.items():
            det = v.get("detect")
            if not det:
                continue
            if det[0] == "bit":
                ok = bit_set(det[1], det[2])
            elif det[0] == "all":   # todos los bits (misión completada)
                ok = all(bit_set(a, b) for a, b in det[1])
            elif det[0] == "any":   # cualquiera (biometal: 1º o 2º jefe del par)
                ok = any(bit_set(a, b) for a, b in det[1])
            else:
                continue
            if ok:
                loc_id = v["id"]
                if loc_id in ctx.server_locations:
                    checked.add(loc_id)

        # ---- pickups respawneables: sondear el buzón (solo si el slot los
        #      activa); los ids ya vistos persisten en mailbox_checked ----
        await self._stage("buzon de pickups", self._poll_pickup_mailbox(ctx))
        checked |= self.mailbox_checked

        if checked != self.local_checked:
            newly = checked - self.local_checked
            if newly:
                await ctx.check_locations(list(checked))
                self._notify_sent(ctx, newly)
            self.local_checked = checked

        # ---- marcador gris de pickups ya enviados (parche PICKUP_MARK) ----
        await self._stage("marcas de pickups", self._sync_pickup_marks(ctx))

        # ---- Troop: desatascar la escena de Giro si quedó a medias ----
        await self._stage("troop", self._troop_unstick(ctx, guard))

        # ---- diagnóstico: trazar bits que cambian (mapear misión completada) ----
        if self.flag_watch:
            await self._stage("flags", self._flag_watch_tick(ctx))

        # ---- diagnóstico: volcar estado del Transerver (a petición) ----
        if self.pending_dump:
            self.pending_dump = False
            await self._stage("dump", self._dump_transerver(ctx))

        # ---- tutorial-skip: aplicar el estado inicial (one-shot) ----
        await self._stage("estado inicial", self._start_state_tick(ctx, guard))

        # ---- conceder items recibidos (idempotente, re-aplicar todo) ----
        await self._stage("items", self._grant_items(ctx, guard))

        # ---- avisos en pantalla: items recibidos nuevos + bomba de la cola ----
        await self._stage("avisos", self._notify_tick(ctx))

        # ---- #5: revertir formas de jefe / Troop no poseídas por item AP ----
        await self._stage("modelos", self._revert_unowned_models(ctx, guard))

        # ---- open-world: auto-aceptar la misión de la zona actual ----
        if self.mission_auto_accept:
            await self._stage("auto-accept", self._auto_accept_mission(ctx, guard))

        # ---- DeathLink ----
        if self.death_link_enabled:
            await self._stage("deathlink", self._handle_death_link(ctx, guard))

        # ---- "Go to Transerver" (pestaña MISSION del menú) + último Transerver ----
        await self._stage("warp", self._warp_request_tick(ctx, guard))

        # ---- anti-softlock: teleport pedido por comando ----
        if self.pending_teleport is not None:
            sub, x, y = self.pending_teleport
            self.pending_teleport = None
            await self._stage("teleport", self._teleport(ctx, sub, x, y, guard))

        # ---- objetivo: Serpent derrotado (misión final completada) ----
        if not ctx.finished_game:
            # Serpent (forma 2) vencido: evento del epílogo 0x021045CA.5 o, de
            # respaldo, ambos bits del guion de D-5 (formas 1 y 2). exp298f/275.
            done = (all(bit_set(a, b) for (a, b) in GOAL_BITS)
                    or all(bit_set(a, b) for (a, b) in GOAL_BITS_ALT))
            if done:
                from NetUtils import ClientStatus
                ctx.finished_game = True
                await ctx.send_msgs([{"cmd": "StatusUpdate",
                                      "status": ClientStatus.CLIENT_GOAL}])

    async def _log_where(self, ctx) -> None:
        """/mmzx_where: subárea, posición, estado y misión al log."""
        from CommonClient import logger
        r = await bizhawk.read(ctx.bizhawk_ctx, [
            (SUBAREA_STABLE, 1, DOM), (PLAYER_POS, 8, DOM), (GAME_STATE, 4, DOM),
            (HP, 1, DOM), (TITLE_CAROUSEL_STEP, 1, DOM), (MISSION_STATE_ADDR, 4, DOM),
            (MISSION_ACTIVE_BYTE, 1, DOM), (0x0214F6C0, 4, DOM), (0x0214FC74, 1, DOM),
            (0x0214F6CF, 1, DOM), (TROOP_MERGE[0], 1, DOM), (CUTSCENE_FLAG, 1, DOM)])
        x = int.from_bytes(r[1][0:4], "little") >> 8
        y = int.from_bytes(r[1][4:8], "little") >> 8
        logger.info("[mmzx] where: sub=%d pos=(%d,%d) gs=%06X hp=%d paso=%d mision(estado)=%d 462B=%02X handler=%d modelo=%d auto_accept=%s items=%d"
                    % (r[0][0], x, y, int.from_bytes(r[2], "little"), r[3][0], r[4][0],
                       int.from_bytes(r[5], "little"), r[6][0], int.from_bytes(r[7], "little"), r[8][0],
                       self.mission_auto_accept, len(ctx.items_received)))
        logger.info("[mmzx] where+: handler_estado=%02X megamerge(0x02104602.1)=%d cutscene=%d"
                    % (r[9][0], (r[10][0] >> TROOP_MERGE[1]) & 1, r[11][0] & 1))

    async def _send_position(self, ctx) -> None:
        """Escribe [subárea, x, y] en la clave mmzx_pos_<slot> del almacén de
        datos para el auto-tab y el icono del mapa de Universal Tracker.
        UT recarga la pestaña de mapa en cada cambio de la clave (sin
        limitación por su parte), así que se limita aquí: al cambiar de
        subárea (inmediato) o, como mucho, cada POS_INTERVAL s y solo si el
        jugador se ha movido >= POS_MIN_DELTA px."""
        if not getattr(ctx, "slot", None):
            return
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [(SUBAREA_STABLE, 1, DOM), (PLAYER_POS, 8, DOM)])
        except bizhawk.RequestFailedError:
            return
        sub = r[0][0]
        x = int.from_bytes(r[1][0:4], "little") >> 8
        y = int.from_bytes(r[1][4:8], "little") >> 8
        now = time.monotonic()
        last = self.pos_last
        if last is not None and sub == last[0]:
            if now - last[3] < POS_INTERVAL:
                return
            if abs(x - last[1]) < POS_MIN_DELTA and abs(y - last[2]) < POS_MIN_DELTA:
                return
        self.pos_last = (sub, x, y, now)
        await ctx.send_msgs([{
            "cmd": "Set", "key": POS_KEY % ctx.slot, "default": [0, 0, 0],
            "want_reply": False,
            "operations": [{"operation": "replace", "value": [int(sub), int(x), int(y)]}],
        }])

    async def _poll_pickup_mailbox(self, ctx) -> None:
        """Pickups respawneables (v0.2): lee el buzón que rellena el parche
        (u32 contador + anillo de PICKUP_MAILBOX_SLOTS entradas u32
        [u8 subárea, u8 índice de coords, u8 role, 0]; la entrada k del
        contador vive en +4 + (k % SLOTS)*4). Cada (sub, idx) nuevo se mapea a
        su location (detect ['mailbox', sub, idx]) y se acumula en
        mailbox_checked; las repeticiones (el pickup respawnea al reentrar) no
        hacen nada. Si el contador RETROCEDE (reset del emulador: el buzón
        vive en RAM y arranca a 0) o es el primer tick, se procesan como
        mucho las últimas SLOTS entradas y se re-sincroniza. Sin opción
        pickup_checks_* activa en el slot no se lee nada."""
        if self.mailbox_enabled is None:
            self.mailbox_enabled = any(bool(ctx.slot_data.get(k, False))
                                       for k in PICKUP_OPTION_KEYS)
        if not self.mailbox_enabled:
            return
        if self.mailbox_map is None:
            self.mailbox_map = {}
            for v in LOCATIONS.values():
                det = v.get("detect")
                if det and det[0] == "mailbox":
                    self.mailbox_map[(int(det[1]), int(det[2]))] = v["id"]
        try:
            raw = (await bizhawk.read(ctx.bizhawk_ctx, [
                (PICKUP_MAILBOX_ADDR, 4 + 4 * PICKUP_MAILBOX_SLOTS, DOM)]))[0]
        except bizhawk.RequestFailedError:
            return
        count = int.from_bytes(raw[:4], "little")
        if self.mailbox_count is None or count < self.mailbox_count:
            start = max(0, count - PICKUP_MAILBOX_SLOTS)      # re-sincronizar
        else:
            start = max(self.mailbox_count, count - PICKUP_MAILBOX_SLOTS)
        new_ids = []
        for k in range(start, count):
            off = 4 + 4 * (k % PICKUP_MAILBOX_SLOTS)
            sub, idx = raw[off], raw[off + 1]
            loc_id = self.mailbox_map.get((sub, idx))
            if loc_id is None or loc_id not in ctx.server_locations:
                continue
            if loc_id not in self.mailbox_checked:
                self.mailbox_checked.add(loc_id)
                new_ids.append(loc_id)
        self.mailbox_count = count
        if new_ids:
            from CommonClient import logger
            names = []
            for i in new_ids:
                try:
                    names.append(ctx.location_names.lookup_in_game(i, "Mega Man ZX"))
                except Exception:
                    names.append(str(i))
            logger.info("[mmzx] pickup recogido: %s" % ", ".join(names))

    async def _sync_pickup_marks(self, ctx) -> None:
        """Escribe en la ROM (tabla PICKUP_MARK) el bitmap de pickups
        respawneables YA ENVIADOS de la subárea actual: el cave los pinta en
        gris al spawnear (o en <= 2 frames si la sala ya está cargada). Se
        reescribe al cambiar de sub, al enviar un check de pickup, al recibir
        checked_locations del servidor y si la ROM perdió la tabla (reset:
        slot 0). Con /mmzx_marks off se apaga (slot 0)."""
        if not self.mailbox_enabled:
            return
        if self.mark_by_sub is None:
            self.mark_by_sub = {}
            for v in LOCATIONS.values():
                det = v.get("detect")
                if det and det[0] == "mailbox" and int(det[2]) < 256:
                    self.mark_by_sub.setdefault(int(det[1]), {})[v["id"]] = int(det[2])
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [(SUBAREA_STABLE, 1, DOM),
                                                     (PICKUP_MARK_TABLE_ADDR, 4, DOM)])
        except bizhawk.RequestFailedError:
            return
        sub, head = r[0][0], r[1]
        if not self.marks_enabled:
            if head[1] != 0:
                await bizhawk.write(ctx.bizhawk_ctx, [(PICKUP_MARK_TABLE_ADDR, bytes(36), DOM)])
                self.mark_written = None
            return
        done = set(ctx.checked_locations) | self.mailbox_checked
        bm = bytearray(32)
        for loc_id, idx in self.mark_by_sub.get(sub, {}).items():
            if loc_id in done:
                bm[idx >> 3] |= 1 << (idx & 7)
        want = (sub, bytes(bm))
        if want == self.mark_written and head[0] == sub and head[1] == PICKUP_MARK_SLOT:
            return
        await bizhawk.write(ctx.bizhawk_ctx, [
            (PICKUP_MARK_TABLE_ADDR, bytes([sub, PICKUP_MARK_SLOT, 0, 0]) + bytes(bm), DOM)])
        self.mark_written = want

    def _ensure_scouts(self, ctx) -> list:
        """Pide LocationScouts (sin crear hints) de las locations pendientes
        para saber qué item de qué jugador hay en cada una (avisos 'Sent')."""
        if self.notify_cfg["sent"] == 0:
            return []
        info = getattr(ctx, "locations_info", None) or {}
        if not info and self.scout_requested:
            self.scout_requested = set()        # el servidor limpió la info (reconexión)
        pending = set(getattr(ctx, "missing_locations", ())) - set(info) - self.scout_requested
        if not pending:
            return []
        self.scout_requested |= pending
        return [{"cmd": "LocationScouts", "locations": sorted(pending), "create_as_hint": 0}]

    def _notify_sent(self, ctx, newly: set) -> None:
        """Encola 'Sent <item> to <jugador>' por cada check nuevo cuyo item es
        de OTRO jugador (según el umbral 'sent')."""
        lvl = self.notify_cfg["sent"]
        if lvl == 0:
            return
        infos = getattr(ctx, "locations_info", None) or {}
        names = getattr(ctx, "player_names", {})
        for loc in sorted(newly):
            info = infos.get(loc)
            if info is None or info.player == ctx.slot or item_level(info.flags) > lvl:
                continue
            if len(self.notify_queue) >= NOTIFY_QUEUE_MAX:
                break
            try:
                item = ctx.item_names.lookup_in_slot(info.item, info.player)
            except Exception:
                item = str(info.item)
            who = names.get(info.player, str(info.player))
            self.notify_queue.append(notify_bytes("Sent ", item, " to " + who))

    async def _notify_tick(self, ctx) -> None:
        """Encola 'Got <item> [from <jugador>]' por cada item recibido nuevo
        (según el umbral 'received'; el backlog al conectar no se avisa) y, si
        el popup está libre (REQ == 0), escribe el siguiente aviso de la cola."""
        msgs = self._ensure_scouts(ctx)
        if msgs and hasattr(ctx, "send_msgs"):
            await ctx.send_msgs(msgs)
        n = len(ctx.items_received)
        if self.notified_items is None:
            self.notified_items = n
        lvl = self.notify_cfg["received"]
        while self.notified_items < n:
            net = ctx.items_received[self.notified_items]
            self.notified_items += 1
            if lvl == 0 or item_level(net.flags) > lvl or len(self.notify_queue) >= NOTIFY_QUEUE_MAX:
                continue
            try:
                item = ctx.item_names.lookup_in_game(net.item, getattr(ctx, "game", "Mega Man ZX"))
            except Exception:
                item = str(net.item)
            tail = ""
            if net.player != ctx.slot:
                tail = " from " + getattr(ctx, "player_names", {}).get(net.player, str(net.player))
            self.notify_queue.append(notify_bytes("Got ", item, tail))
        if not self.notify_queue:
            return
        try:
            req = (await bizhawk.read(ctx.bizhawk_ctx, [(NOTIFY_ADDR, 1, DOM)]))[0][0]
        except bizhawk.RequestFailedError:
            return
        if req != 0:
            return                              # el aviso anterior sigue en pantalla
        data = self.notify_queue.popleft()
        await bizhawk.write(ctx.bizhawk_ctx, [
            (NOTIFY_ADDR + 4, data, DOM),
            (NOTIFY_ADDR + 2, NOTIFY_DUR.to_bytes(2, "little"), DOM)])
        await bizhawk.write(ctx.bizhawk_ctx, [(NOTIFY_ADDR, b"\x01", DOM)])   # REQ el último

    async def _flag_watch_tick(self, ctx) -> None:
        """Lee la ventana ancha del bloque de progreso y reporta en el log
        qué bits cambian respecto al snapshot anterior. Sirve para mapear la
        rutina de 'misión completada' en vivo: activar con /mmzx_flags, hacer
        el snapshot, entregar la misión, y ver qué bit(s) se encienden."""
        from CommonClient import logger
        try:
            cur = (await bizhawk.read(
                ctx.bizhawk_ctx, [(FLAG_WATCH_BASE, FLAG_WATCH_LEN, DOM)]))[0]
        except bizhawk.RequestFailedError:
            return
        if self.flag_snap is None:
            self.flag_snap = cur
            return
        changes = []
        for i in range(FLAG_WATCH_LEN):
            diff = cur[i] ^ self.flag_snap[i]
            if diff:
                for b in range(8):
                    if diff & (1 << b):
                        on = bool(cur[i] & (1 << b))
                        changes.append("0x%08X.%d %s" % (
                            FLAG_WATCH_BASE + i, b, "ON" if on else "off"))
        if changes:
            logger.info("[mmzx_flags] cambios: " + ", ".join(changes))
            self.flag_snap = cur

    async def _dump_transerver(self, ctx) -> None:
        """Vuelca el estado relevante para el gating del listado de misiones
        del Transerver: región de flags de misión (0x021045DE..), región del
        Transerver (0x02104620.., incluye el índice 0x02104630) y decodifica
        qué misiones tienen su flag de INICIO puesto. Para correlacionar con
        lo que aparece ofertado en el menú (RE de disponibilidad, v0.2)."""
        from CommonClient import logger
        MISSIONS = [  # id -> (byte, bit, nombre) — flag de inicio (mission_table)
            (0x021045DE, 2, "Catch The Maverick"), (0x021045DE, 5, "Locate Giro"),
            (0x021045DF, 1, "Pass The Test"), (0x021045E0, 2, "Troop Reinforcement"),
            (0x021045E1, 3, "Search The Plant"), (0x021045E1, 6, "Find The Survivors"),
            (0x021045E2, 1, "Fight The Mavericks"), (0x021045E4, 1, "Secure The Biometal"),
            (0x021045E4, 5, "Save The People"), (0x021045E5, 1, "Recover The Disk"),
            (0x021045E5, 4, "Attack The Excavators"), (0x021045E6, 0, "Protect The Lab"),
            (0x021045E6, 3, "Protect HQ"), (0x021045E7, 2, "Stop The Dig"),
            (0x021045E7, 5, "Repel The Army"), (0x021045E8, 1, "Destroy Model W"),
        ]
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [
                (0x021045DE, 0x0C, DOM), (0x02104620, 0x14, DOM)])
        except bizhawk.RequestFailedError:
            return
        mis_region, ts_region = r[0], r[1]

        def bit_of(addr, bit):
            base = 0x021045DE
            return bool(mis_region[addr - base] & (1 << bit)) if 0 <= addr - base < len(mis_region) else False

        started = [name for (a, b, name) in MISSIONS if bit_of(a, b)]
        logger.info("[mmzx_dump] mision(0x021045DE): " + mis_region.hex(" "))
        logger.info("[mmzx_dump] transerver(0x02104620): " + ts_region.hex(" "))
        logger.info("[mmzx_dump] idx 0x02104630 = 0x%02X | acceso 0x02104627/28 = %02X %02X" % (
            ts_region[0x10], ts_region[0x07], ts_region[0x08]))
        logger.info("[mmzx_dump] misiones con FLAG de inicio puesto: "
                    + (", ".join(started) if started else "ninguna"))

    @staticmethod
    def _mission_done_bits(name: str):
        """Bits de 'completada' de una misión (detect 'all' de su location)."""
        v = LOCATIONS.get("Mission - " + name) or {}
        det = v.get("detect")
        if det and det[0] == "all":
            return [(a, b) for a, b in det[1]]
        return []

    async def _troop_unstick(self, ctx, guard) -> None:
        """Troop Reinforcement: el jefe del final de D-2 solo aparece si el
        flag de megamerge 0x02104602.1 está a 0 (exp507d). El juego lo pone al
        megamergear con Model ZX; si el jugador muere ahí sin que la misión se
        reporte, la sala queda vacía y la misión no se puede terminar (se
        recorre D-2 entera sin combate). Mientras Troop sea la misión ACTIVA y
        NO esté completada, se limpia el bit (vivo + canónica), nunca durante
        una cutscene de historia."""
        addr, bit = TROOP_MERGE
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [
                (MISSION_STATE_ADDR, 4, DOM), (addr, 1, DOM),
                (addr + CANON_OFF, 1, DOM), (CUTSCENE_FLAG, 1, DOM)])
        except bizhawk.RequestFailedError:
            return
        if int.from_bytes(r[0], "little") != TROOP_STATE or r[3][0] & 1:
            return
        mask = 1 << bit
        if not ((r[1][0] | r[2][0]) & mask):
            return
        done = self._mission_done_bits("Troop Reinforcement")
        if done:
            try:
                vals = await bizhawk.read(ctx.bizhawk_ctx, [(a, 1, DOM) for a, _ in done])
            except bizhawk.RequestFailedError:
                return
            if all(vals[i][0] & (1 << b) for i, (_, b) in enumerate(done)):
                return       # ya completada: el bit es legítimo, no tocarlo
        writes = []
        if r[1][0] & mask:
            writes.append((addr, bytes([r[1][0] & ~mask]), DOM))
        if r[2][0] & mask:
            writes.append((addr + CANON_OFF, bytes([r[2][0] & ~mask]), DOM))
        if writes and await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard]):
            from CommonClient import logger
            logger.info("[mmzx] Troop Reinforcement estaba a medias (megamerge hecho sin reportar): "
                        "limpiado 0x02104602.1 para que la escena de Giro vuelva a dispararse")

    async def _auto_accept_mission(self, ctx, guard) -> None:
        """Open-world: al ENTRAR en la subárea destino de una misión, la
        fuerza como aceptada (replica FUN_02031f10, validado exp067): start
        flag (vivo+canónica) + estado en MISSION_STATE_ADDR + MISSION_ACTIVE_
        FLAG=1. Solo al CAMBIAR de zona (no cada frame) y si no es ya la
        misión activa. Excluye Troop/Protect HQ (no están en MISSION_ACCEPT;
        se auto-lanzan por historia). Antes de escribir la misión toma la
        instantánea de inicio de misión (espejos B/descriptor 2/cola 2) para
        que "Abort Mission" devuelva al jugador a este punto sin misión y con
        el progreso intacto (exp452); después, commit del checkpoint."""
        try:
            sub = (await bizhawk.read(ctx.bizhawk_ctx, [(SUBAREA_STABLE, 1, DOM)]))[0][0]
        except bizhawk.RequestFailedError:
            return
        if sub == HUB_SUBAREA:
            # Piso del hub con puerta hacia una sala de JEFE: la puerta del
            # piso (G-5/K-4/L-4) y los shutters de la arena exigen la misión
            # del área aceptada o completada (agente exp370-379). Se acepta
            # al acercarse a la puerta izquierda (x <= HUB_FLOOR_DOOR_X) para
            # no convertir la consola del piso en "Abort the mission?".
            try:
                r = await bizhawk.read(ctx.bizhawk_ctx, [(PLAYER_POS, 8, DOM)])
            except bizhawk.RequestFailedError:
                return
            x = int.from_bytes(r[0][0:4], "little") >> 8
            y = int.from_bytes(r[0][4:8], "little") >> 8
            floor = next((fy for fy in HUB_FLOOR_BOSS if abs(y - (fy - 17)) <= 64), None)
            if floor is None or (x > HUB_FLOOR_DOOR_X and not self.force_accept):
                self.last_accept_sub = None
                return
            if self.last_accept_sub == ("hub", floor) and not self.force_accept:
                return
            key = ("hub", floor)
            rec = MISSION_ACCEPT.get(HUB_FLOOR_BOSS[floor])
            from CommonClient import logger
            logger.info("[mmzx] piso del hub y=%d (jugador %d,%d): misión %s"
                        % (floor, x, y, rec["name"] if rec else "?"))
        else:
            if sub == self.last_accept_sub and not self.force_accept:
                return
            key = sub
            # (Las salas de JEFE ya no se excluyen: con la guarda OAM de la ROM
            # forzar la misión dentro no corrompe la sala; agente exp379/379b.)
            rec = MISSION_ACCEPT.get(sub)
        self.force_accept = False
        if not rec:
            self.last_accept_sub = key
            return
        # misión ya COMPLETADA (bits de "completada" = detección de su
        # location): no re-aceptarla (evitaría un segundo Report/recompensa)
        done_bits = self._mission_done_bits(rec["name"])
        if done_bits:
            try:
                vals = await bizhawk.read(ctx.bizhawk_ctx, [(a, 1, DOM) for a, _ in done_bits])
            except bizhawk.RequestFailedError:
                return
            if all(vals[i][0] & (1 << b) for i, (_, b) in enumerate(done_bits)):
                self.last_accept_sub = key
                from CommonClient import logger
                logger.info("[mmzx] %s ya completada: no se re-acepta" % rec["name"])
                return
        try:
            cur_state = int.from_bytes((await bizhawk.read(
                ctx.bizhawk_ctx, [(MISSION_STATE_ADDR, 4, DOM)]))[0], "little")
        except bizhawk.RequestFailedError:
            return
        if cur_state == rec["state"]:
            self.last_accept_sub = key
            return   # ya es la misión activa
        addr, bit = rec["flag"]
        canon = addr + (CANON_BLOCK - LIVE_BLOCK)
        act, act_c = MISSION_ACTIVE_BYTE, MISSION_ACTIVE_BYTE + (CANON_BLOCK - LIVE_BLOCK)
        cur = await bizhawk.read(ctx.bizhawk_ctx, [
            (addr, 1, DOM), (canon, 1, DOM), (act, 1, DOM), (act_c, 1, DOM),
            (LIVE_BLOCK, LIVE_BLOCK_LEN, DOM), (SCENE_DESC, SCENE_DESC_LEN, DOM),
            (STORY_BLOCK, STORY_BLOCK_LEN, DOM)])
        writes = [
            # Instantánea de inicio de misión (FUN_02022744) con el estado PREVIO a la
            # misión: es lo que restaura "Abort Mission" (exp452k/452l): bloque vivo →
            # espejo B, descriptor 1 (spawn de la sala/piso actual) → descriptor 2,
            # bloque de historia vivo → cola 2.
            (BLOCK_MIRROR, cur[4], DOM),
            (SCENE_DESC_MIRROR, cur[5], DOM),
            (STORY_BLOCK_MIRROR, cur[6], DOM),
            (addr, bytes([cur[0][0] | (1 << bit)]), DOM),
            (canon, bytes([cur[1][0] | (1 << bit)]), DOM),
            (MISSION_STATE_ADDR, rec["state"].to_bytes(4, "little"), DOM),
            (MISSION_ACTIVE_FLAG, b"\x01", DOM),
            # "misión en curso" (bit1): lo pone FUN_02031f10; lo exige FUN_02009184
            (act, bytes([cur[2][0] | 0x02]), DOM),
            (act_c, bytes([cur[3][0] | 0x02]), DOM),
        ]
        # Handler de HISTORIA de la mision (receta FUN_0201b5ec, validada por
        # el agente exp350-359 para las misiones 6/14/16): objeto a cero, sin
        # cutscene activa (+9 = 0xFF) e id de mision. Con el se ejecutan las
        # cutscenes por rectangulo y los flags de la mision como en vanilla.
        obj = bytearray(0x114)
        obj[9] = 0xFF
        obj[0xB] = int(rec.get("hstate", 0))   # estado inicial del handler (Troop: 3)
        writes.append((STORY_HANDLER_OBJ, bytes(obj), DOM))
        writes.append((STORY_HANDLER_ID, int(rec["id"]).to_bytes(4, "little"), DOM))
        # bits extra de la misión (p.ej. Troop: 0x021045E0.7 = "ya lanzada" para
        # que la sala de mando X-2 no la relance por historia), vivo+canónica
        for ea, eb in rec.get("extra", []):
            ecur = await bizhawk.read(ctx.bizhawk_ctx, [(ea, 1, DOM), (ea + CANON_OFF, 1, DOM)])
            writes.append((ea, bytes([ecur[0][0] | (1 << eb)]), DOM))
            writes.append((ea + CANON_OFF, bytes([ecur[1][0] | (1 << eb)]), DOM))
        ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
        from CommonClient import logger
        if ok:
            # COMMIT del checkpoint (lo que hace el juego en los pads,
            # FUN_0201b384): bloque de progreso vivo -> canónica y bloque de
            # historia (id + handler) -> su copia. Sin esto, una muerte antes
            # del primer hito restaura el checkpoint y borra el handler y el
            # estado de misión (agente exp410-416).
            try:
                cur = await bizhawk.read(ctx.bizhawk_ctx, [
                    (LIVE_BLOCK, 0xE4, DOM), (STORY_BLOCK, 0x11C, DOM)])
                await bizhawk.guarded_write(ctx.bizhawk_ctx, [
                    (CANON_BLOCK, cur[0], DOM), (STORY_BLOCK_CANON, cur[1], DOM)], [guard])
            except bizhawk.RequestFailedError:
                pass
            self.last_accept_sub = key      # solo se marca si la escritura entró
            logger.info("[mmzx] open-world: misión auto-aceptada → %s" % rec["name"])
        else:
            logger.info("[mmzx] aceptación de %s no aplicada (guarda de estado); se reintenta" % rec["name"])

    async def _start_state_resolve(self, ctx) -> None:
        """Avanza la máquina one-shot del skip usando el datastore del
        servidor (clave `mmzx_start_applied_<team>_<slot>`), corra o no el
        juego. 0=pedir, 1=esperando Get, 2=aplicar (requiere gameplay+hub),
        3=hecho. /mmzx_start salta directo a 2."""
        if self.start_state >= 2:
            return
        self.start_key = "mmzx_start_applied_%s_%s" % (ctx.team, ctx.slot)
        if self.start_state == 0:
            await ctx.send_msgs([
                {"cmd": "SetNotify", "keys": [self.start_key]},
                {"cmd": "Get", "keys": [self.start_key]},
            ])
            self.start_state = 1
            return
        if self.start_state == 1:
            if self.start_key not in ctx.stored_data:
                return
            self.start_state = 3 if ctx.stored_data[self.start_key] else 2

    async def _seed_golden_image(self, ctx) -> None:
        """Escribe la imagen dorada en 0x021602A8 mientras el TÍTULO/MENÚS
        estén activos, en cada tick e independientemente de start_state, para
        que cualquier "New Game" (modo 0x10000, redirigido por el parche al
        handler de LOAD) entre SIEMPRE al hub post-tutorial — también tras un
        Game Over, cuyo "Exit Game" re-entra en el mismo carrusel del título
        (exp260-269, work/nav/exp260/NOTES.md).

        Estados medidos (game_state 0x0215E6D8 / paso del carrusel 0x0214CD70):
          logos/boot ............ gs=0x000000, paso 0-2 (no se siembra; el
                                  título re-inicializa el bloque al cargar)
          carga del título ...... 0xB00 (1 frame) → 0x200 → 0x400, paso 3
                                  (init del bloque por DMA: no sembrar)
          título "Press START" .. gs=0x500, paso 3, sub estable=1  ← SEMBRAR
          menús del título ...... gs=0x500, paso 5                 ← SEMBRAR
          New Game pedido ....... gs=0x010000 (1 frame; Aile: 0x000000) y
                                  paso=6 en ese mismo frame → 0x200 → 0x400
                                  (LOAD lee el bloque) → 0x500
          Continue pedido ....... gs=0x000003 → 0x000103 → 0x0203xx (data
                                  select), paso=6 desde 0x000003; DMA de
                                  restauración SRAM→0x021602A8 en 0x140203/
                                  0x150203 → 0x820203 → 0x840203 → 0x840303
                                  → 0x100 → 0x200 → 0x400 → 0x500
          gameplay .............. gs=0x500, paso 6 (0x021602A8 = buffer de
                                  escena vivo → NUNCA escribir)
          pausa ................. 0x1000700 → 0x1 → 0x10001 → 0x1010001 →
                                  0x101; despausa 0x800 → 0x1000800 → 0x500
          muerte → Game Over .... 0x900 → 0x000007 → 0x000107 → 0x010107
                                  (paso 6); al pulsar: 0x0x0107 → 0x0x0207 y
                                  paso 6 → 1 → 5 (menú Exit Game/Continue =
                                  carrusel del título)             ← SEMBRAR
          Exit Game ............. = New Game (0x10000 → LOAD del bloque)
          Continue desde GO ..... 0x010003 → data select (paso 6) → DMA → LOAD
        Regla: paso ∈ {3,5} Y (gs == 0x500 o gs&0xFF == 0x07). Excluye por
        construcción 0x100/0x200/0x400 y los estados 0x..03 del data select
        (el DMA del Continue precede al LOAD: sembrar ahí pisaría el save),
        y el gameplay (paso 6). El paso 4 (título/attract con demo,
        gs 0x090700) se excluye: todo New Game pasa por el paso 5 antes.
        Escritura GUARDADA por (paso, gs) para que no entre si el carrusel
        avanzó a 6 entre la lectura y la escritura."""
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [
                (GAME_STATE, 4, DOM), (TITLE_CAROUSEL_STEP, 1, DOM)])
        except bizhawk.RequestFailedError:
            return
        gs = int.from_bytes(r[0], "little")
        step = r[1][0]
        if step not in TITLE_STEPS_SEEDABLE:
            return
        if not (gs == STATE_INGAME or (gs & 0xFF) == 0x07):
            return
        try:
            # La imagen dorada lleva dificultad/personaje en +0x70/+0x71
            # (exp273d: +0x70 = 1 Easy / 0 Normal; +0x71 = 0 Vent / 1 Aile).
            # El dorado es Normal/Vent; se aplica el personaje del YAML.
            # Imagen v2 parcheada por YAML (golden.build_image): modelo activo y
            # posesión desde el primer frame (el LOAD no fuerza X), personaje
            # (0x0214FC75), dificultad Normal, WE del modelo inicial, sin
            # briefing, spawn (384,335). _start_state_tick queda de respaldo.
            img = build_image(str(ctx.slot_data.get("starting_model", "model_x")),
                              int(ctx.slot_data.get("character", 0) or 0), STARTING_MODELS)
            await bizhawk.guarded_write(
                ctx.bizhawk_ctx,
                [(GOLDEN_IMAGE_ADDR, bytes(img), DOM)],
                [(TITLE_CAROUSEL_STEP, r[1], DOM), (GAME_STATE, r[0], DOM)])
        except bizhawk.RequestFailedError:
            return

    async def _start_state_tick(self, ctx, guard) -> None:
        """Tutorial-skip (v0.2): fase de APLICAR (start_state==2). Aplica UNA
        VEZ el estado inicial del YAML (starting_model + starting_transerver)
        sobre el estado dorado post-tutorial, cuando el juego esté EN JUEGO,
        en el hub (subárea 70) y con acceso al Transerver (0x02104627 bit4) —
        la firma del estado post-tutorial. Marca el datastore al terminar.
        (Los estados 0/1/3 los gestiona _start_state_resolve.)"""
        if self.start_state == 3:
            # Partida NUEVA tras una ya aplicada (playtest 4: "new save" dejaba
            # Model X disponible y no forzaba el modelo del YAML). Firma del
            # estado dorado crudo: X poseído (0x021045CF.7 lo trae la imagen)
            # sin haber recibido el item "Model X" y modelo inicial != model_x
            # -> re-armar la aplicación (idempotente: al aplicar se revoca X).
            key = str(ctx.slot_data.get("starting_model", "model_x"))
            rec = STARTING_MODELS.get(key)
            if rec and rec.get("revoke_x"):
                id_to_name = {v["id"]: n for n, v in ITEMS.items()}
                got_x = any(id_to_name.get(net.item) == "Model X" for net in ctx.items_received)
                if not got_x:
                    try:
                        xa, xb = MODEL_X_POSSESSION
                        cf = (await bizhawk.read(ctx.bizhawk_ctx, [(xa, 1, DOM), (SUBAREA_STABLE, 1, DOM)]))
                    except bizhawk.RequestFailedError:
                        return
                    if (cf[0][0] & (1 << xb)) and cf[1][0] == HUB_SUBAREA:
                        from CommonClient import logger
                        logger.info("[mmzx] partida nueva detectada (Model X del estado dorado): re-aplicando el estado inicial")
                        self.start_state = 2
                        self.start_confirm = 0
                        self.start_retries = 0
        if self.start_state != 2:
            return
        # aplicar cuando el juego esté en el estado elegible
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [
                (SUBAREA_STABLE, 1, DOM), (0x02104627, 1, DOM)])
        except bizhawk.RequestFailedError:
            return
        sub, ts_access = r[0][0], r[1][0]
        if sub != HUB_SUBAREA or not (ts_access & 0x10):
            return
        desired_active = await self._apply_start_state(ctx, guard)
        if desired_active is None:
            return   # escritura no entró (guarda) — reintentar próximo tick
        if desired_active == -1:      # modelo desconocido: nada que confirmar
            self.start_confirm = 4
        # confirmar que el modelo activo se MANTIENE (el load lo pisa con X
        # una vez durante la entrada; re-asertamos hasta que aguante).
        try:
            active_now = (await bizhawk.read(ctx.bizhawk_ctx, [(MODEL, 1, DOM)]))[0][0]
        except bizhawk.RequestFailedError:
            return
        self.start_retries += 1
        self.start_confirm = self.start_confirm + 1 if active_now == desired_active else 0
        if self.start_confirm >= 4 or self.start_retries > 600:
            self.start_state = 3
            await ctx.send_msgs([{
                "cmd": "Set", "key": self.start_key, "default": False,
                "want_reply": False,
                "operations": [{"operation": "replace", "value": True}],
            }])

    async def _apply_start_state(self, ctx, guard):
        """Escribe el modelo inicial (posesión vivo+canónica + modelo activo)
        y, si el Transerver inicial no es el hub, teleporta. Devuelve el valor
        del modelo activo DESEADO (int) si las escrituras entraron, o None si
        la guarda de gameplay las rechazó (para reintentar)."""
        from CommonClient import logger
        key = str(ctx.slot_data.get("starting_model", "model_x"))
        rec = STARTING_MODELS.get(key)
        if rec is None:
            logger.info("[mmzx] starting_model desconocido: %r (ignorado)" % key)
            return -1   # nada que confirmar; se dará por hecho

        # posesiones: revocar X si toca + conceder las del modelo elegido
        bit_ops: list[tuple[int, int, bool]] = []   # (addr, bit, on)
        if rec["revoke_x"]:
            xa, xb = MODEL_X_POSSESSION
            bit_ops.append((xa, xb, False))
        for addr, bit in rec["grant"]:
            bit_ops.append((addr, bit, True))

        addrs = sorted({a for a, _, _ in bit_ops})
        writes: list[tuple[int, bytes, str]] = []
        if addrs:
            cur = await bizhawk.read(
                ctx.bizhawk_ctx,
                [(a, 1, DOM) for a in addrs] + [(a + CANON_OFF, 1, DOM) for a in addrs])
            vals = {a: [cur[i][0], cur[len(addrs) + i][0]] for i, a in enumerate(addrs)}
            for addr, bit, on in bit_ops:
                for k in (0, 1):
                    v = vals[addr][k]
                    vals[addr][k] = (v | (1 << bit)) if on else (v & ~(1 << bit))
            for i, a in enumerate(addrs):
                if vals[a][0] != cur[i][0]:
                    writes.append((a, bytes([vals[a][0]]), DOM))
                if vals[a][1] != cur[len(addrs) + i][0]:
                    writes.append((a + CANON_OFF, bytes([vals[a][1]]), DOM))
        writes.append((ACTIVE_MODEL_ADDR, bytes([rec["active"]]), DOM))

        ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
        if not ok:
            return None

        # Transerver inicial distinto del hub -> teleport (v0.2: solo hub)
        ts_key = str(ctx.slot_data.get("starting_transerver", "guardian_hub"))
        dest = STARTING_TRANSERVERS.get(ts_key)
        if dest and dest[0] != HUB_SUBAREA:
            await self._teleport(ctx, dest[0], dest[1], dest[2], guard)

        if self.start_confirm == 0 and self.start_retries == 0:
            logger.info("[mmzx] estado inicial aplicado: modelo=%s, transerver=%s"
                        % (key, ts_key))
        return rec["active"]

    async def _warp_request_tick(self, ctx, guard) -> None:
        """Atiende "Go to Transerver" (pestaña MISSION + Y): (1) WARP_REQ = 1
        (puesta por el cave del parche; el menú ya se ha cerrado) → la
        consume y abre la lista "Target Area" del juego; (2) al volver a
        gameplay tras la lista, lee la selección y teletransporta al piso
        del hub de ese destino (−1 = cancelada: nada)."""
        from CommonClient import logger
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [(WARP_REQ, 1, DOM), (TRANSPORT_SEL, 4, DOM)])
        except bizhawk.RequestFailedError:
            return
        req = r[0][0]
        sel = int.from_bytes(r[1], "little", signed=True)
        if self.transport_wait:
            self.transport_wait = False
            if 0 <= sel < len(STATION_ROOMS):
                letter = STATION_ROOMS[sel][0].upper()
                y = HUB_FLOOR_Y.get(letter)
                if y is not None:
                    self.pending_teleport = (HUB_SUBAREA, HUB_X, y - HUB_PAD_DY)
                    logger.info("[mmzx] Go to Transerver → Area %s (piso %s del hub)"
                                % (STATION_ROOMS[sel][0].upper() + "-" + STATION_ROOMS[sel][1:].lstrip("0"), letter))
            else:
                logger.info("[mmzx] Go to Transerver: lista cancelada")
            return
        if req != 1:
            return
        # abrir la lista del juego: sin estación actual (-1) y petición de estado,
        # todo bajo la guarda de gameplay (si no entra, se reintenta el próximo tick)
        ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, [
            (WARP_REQ, b"\x00", DOM),
            (TRANSPORT_SEL, (0xFFFFFFFF).to_bytes(4, "little"), DOM),
            (GAME_STATE, STATE_TARGET_AREA.to_bytes(4, "little"), DOM),
            (GAME_STATE + 4, b"\x00\x00\x00\x00", DOM),
            (GAME_STATE + 8, b"\x00\x00\x00\x00", DOM),
        ], [guard])
        if ok:
            self.transport_wait = True
            logger.info("[mmzx] Go to Transerver: abriendo la lista Target Area")

    async def _teleport(self, ctx, sub, x, y, guard) -> None:
        """Teleport limpio (7 escrituras; docs/client_integration.md §6).
        Con guarda de estado 0x500 para no dispararlo en menú/transición."""
        writes = [
            (SCENE_DESC + 0x00, (x << 8).to_bytes(4, "little"), DOM),
            (SCENE_DESC + 0x04, (y << 8).to_bytes(4, "little"), DOM),
            (SCENE_DESC + 0x08, sub.to_bytes(4, "little"), DOM),
            (SCENE_DESC + 0x11, b"\x01", DOM),
            (GAME_STATE, STATE_LOAD.to_bytes(4, "little"), DOM),
            (GAME_STATE + 4, b"\x00\x00\x00\x00", DOM),
            (GAME_STATE + 8, b"\x00\x00\x00\x00", DOM),
        ]
        await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])

    async def _grant_items(self, ctx, guard) -> None:
        """Aplica los items recibidos.

        Dos familias:
          - IDEMPOTENTES (bits que persisten o se reconstruyen): se
            recalcula el estado deseado desde el conteo total y se
            escribe (OR / set de máximo). Barato y seguro re-aplicar.
          - CONSUMIBLES (E-Crystals, 1-Up): se aplican UNA vez por partida
            (registro en el almacén de datos fechado con el tiempo de juego,
            ver `_consumables_resolve`), nunca re-sumar al reconectar.
        """
        id_to_item = {v["id"]: (name, v["grant"]) for name, v in ITEMS.items()}
        # copias recibidas por nombre (progresivos: 1 = 1ª mitad, 2 = las dos)
        name_count: dict[str, int] = {}
        for net in ctx.items_received:
            entry = id_to_item.get(net.item)
            if entry:
                name_count[entry[0]] = name_count.get(entry[0], 0) + 1

        # contar recibidos por tipo de concesión
        n_lifeup = n_subtank = 0
        live_bits: set[tuple[int, int]] = set()    # (live_addr, bit) idempotentes
        consumables: list[str] = []    # E-Crystals / 1-Up recibidos, en orden del servidor
        cardkeys: set[tuple[int, int]] = set()     # (addr, bit) de las llaves recibidas
        for net in ctx.items_received:
            entry = id_to_item.get(net.item)
            if not entry:
                continue
            name, grant = entry
            kind = grant[0]
            if kind == "lifeup":
                n_lifeup += 1
            elif kind == "subtank":
                n_subtank += 1
            elif kind == "live_bit":
                if name.endswith("Card Key"):
                    cardkeys.add((grant[1], grant[2]))   # posesión autoritativa
                else:
                    live_bits.add((grant[1], grant[2]))
            elif kind == "progressive":
                # la copia k pone el bit k (mitad 1, mitad 2...)
                for k, (addr, bit) in enumerate(grant[1]):
                    if name_count.get(name, 0) > k:
                        live_bits.add((addr, bit))
            elif kind == "transerver":
                # acceso a la red de Transervers: si el bit del destino es
                # conocido (exp230) se enciende en el bitfield 0x02104627/28
                # (vivo+canónica) para que aparezca en la lista de Transport
                # del juego; si no, el item gatea solo la lógica (el warp del
                # cliente /mmzx_teleport cubre el desplazamiento).
                if len(grant) >= 3:
                    live_bits.add((grant[1], grant[2]))
            elif kind in ("ecrystals", "oneup"):
                consumables.append(kind)
            # kind == "todo": item sin receta aún (no en pool v0.1)

        # Verjas de EVENTO (puertas con bit 1 del rol; exp341): las de
        # EVENT_GATES_OPEN se abren siempre (open world) y las de
        # EVENT_GATES_ALL6 al tener los 6 biometales por items AP (requisito
        # de diseño del goal: HQ de Slither D-2 -> D-4, sello de M-1).
        for fl in EVENT_GATES_OPEN:
            live_bits.add(tuple(EVENT_GATES[fl]))
        received = {id_to_item[net.item][0] for net in ctx.items_received if net.item in id_to_item}
        if all(n in received for n in ("Model X", "Model ZX", "Progressive Model HX",
                                       "Progressive Model FX", "Progressive Model LX",
                                       "Progressive Model PX")):
            for fl in EVENT_GATES_ALL6:
                live_bits.add(tuple(EVENT_GATES[fl]))

        writes: list[tuple[int, bytes, str]] = []

        # Weapon Energy de los biometales poseidos por item (ver BOSS_LEVELS):
        # 1 mitad: nivel del 1er jefe del par >= 4 - nivel del 2o (tope >= 16);
        # 2 mitades: niveles 4+4 (tope 32, como dos victorias perfectas). Barra
        # llena una vez. Idempotente: no toca nada si la suma ya alcanza el tope.
        owned_models = [m for m, (item, _a, _b) in MODEL_POSSESSION.items()
                        if m in MODEL_LEVEL_IDX and item in received]
        if owned_models:
            lv = await bizhawk.read(ctx.bizhawk_ctx, [(BOSS_LEVELS, 8, DOM)])
            lv = lv[0]
            for m in owned_models:
                i0, i1 = MODEL_LEVEL_IDX[m]
                full = name_count.get(MODEL_POSSESSION[m][0], 0) >= 2
                if full and lv[i0] + lv[i1] < 8:
                    for i in (i0, i1):
                        writes.append((BOSS_LEVELS + i, b"\x04", DOM))
                        writes.append((BOSS_LEVELS + i + CANON_OFF, b"\x04", DOM))
                    writes.append((WE_BASE + m, bytes([WE_FULL * 2]), DOM))
                elif not full and lv[i0] + lv[i1] < 4:
                    v = bytes([4 - lv[i1]])
                    writes.append((BOSS_LEVELS + i0, v, DOM))
                    writes.append((BOSS_LEVELS + i0 + CANON_OFF, v, DOM))
                    writes.append((WE_BASE + m, bytes([WE_FULL]), DOM))

        # Bits idempotentes (biometales 0x021045D0, card keys 0x021045FC/FD):
        # set en VIVO (efecto inmediato) y en CANÓNICA (persistencia)
        if live_bits:
            by_addr: dict[int, int] = {}
            for addr, bit in live_bits:
                by_addr[addr] = by_addr.get(addr, 0) | (1 << bit)
            addrs = sorted(by_addr)
            cur = await bizhawk.read(ctx.bizhawk_ctx,
                                     [(a, 1, DOM) for a in addrs]
                                     + [(a + CANON_OFF, 1, DOM) for a in addrs])
            for k, a in enumerate(addrs):
                mask = by_addr[a]
                live_v, canon_v = cur[k][0], cur[len(addrs) + k][0]
                if live_v & mask != mask:
                    writes.append((a, bytes([live_v | mask]), DOM))
                if canon_v & mask != mask:
                    writes.append((a + CANON_OFF, bytes([canon_v | mask]), DOM))

        # Card Keys: posesión AUTORITATIVA. El juego las concede al reportar
        # ciertas misiones (bug del playtest del usuario: la Azul aparecía sin
        # haberla recibido por AP). Se escribe EXACTAMENTE el conjunto recibido
        # en los 6 bits de llave de 0x021045FC/FD (vivo + canónica), dejando
        # intactos los demás bits de esos bytes (cutscenes vistas, verjas...).
        want_keys = {a: 0 for a in CARDKEY_MASKS}
        for a, b in cardkeys:
            want_keys[a] = want_keys.get(a, 0) | (1 << b)
        kaddrs = sorted(CARDKEY_MASKS)
        kcur = await bizhawk.read(ctx.bizhawk_ctx,
                                  [(a, 1, DOM) for a in kaddrs]
                                  + [(a + CANON_OFF, 1, DOM) for a in kaddrs])
        for k, a in enumerate(kaddrs):
            mask = CARDKEY_MASKS[a]
            for off, cur in ((0, kcur[k][0]), (CANON_OFF, kcur[len(kaddrs) + k][0])):
                new = (cur & ~mask) | (want_keys[a] & mask)
                if new != cur:
                    writes.append((a + off, bytes([new]), DOM))

        # Life Ups: capacidad AUTORITATIVA — solo los items AP, NUNCA la
        # recogida NATIVA del mundo. Se escribe EXACTAMENTE el conteo recibido
        # en los bits 0..3 (limpiando lo que conceda el pickup físico): el
        # check se dispara por su flag persistente (aparte) pero el Life Up no
        # se otorga como capacidad. Corrige el doble-grant del playtest #2.
        nlu = min(4, n_lifeup)
        lu_mask = (1 << nlu) - 1
        cur_lu, cur_hpmax = (await bizhawk.read(
            ctx.bizhawk_ctx, [(LIFEUP_BYTE, 1, DOM), (HPMAX, 1, DOM)]))
        if (cur_lu[0] & 0x0F) != lu_mask:
            writes.append((LIFEUP_BYTE, bytes([(cur_lu[0] & 0xF0) | lu_mask]), DOM))
        hpmax = min(0x20, 0x10 + 4 * nlu)   # HP máx sigue al conteo AP
        if cur_hpmax[0] != hpmax:
            writes.append((HPMAX, bytes([hpmax]), DOM))

        # Sub Tanks: capacidad AUTORITATIVA (idéntico criterio)
        nst = min(4, n_subtank)
        st_mask = (1 << nst) - 1
        cur_st = (await bizhawk.read(ctx.bizhawk_ctx, [(SUBTANK_BYTE, 1, DOM)]))[0][0]
        if (cur_st & 0x0F) != st_mask:
            writes.append((SUBTANK_BYTE, bytes([(cur_st & 0xF0) | st_mask]), DOM))

        # Consumibles (UNA vez por partida): el registro de aplicados vive en el
        # almacén de datos del servidor, cada lote fechado con el tiempo de juego
        # (PLAYTIME) en que se aplicó. Ese contador es el reloj de la partida:
        # crece 1/frame, no retrocede al morir y vuelve al valor del save con
        # Game Over→Continue o LOAD (exp497), y es 0 en partida nueva. Lotes con
        # playtime > actual = el estado se rebobinó a antes de aplicarlos → se
        # vuelven a conceder; reconectar el cliente no rebobina nada → no re-suma.
        new_consumables: list[str] = []
        pt = 0
        if consumables:
            if self.cons_log is None:
                await self._consumables_resolve(ctx)
            if self.cons_log is not None:
                pt = int.from_bytes((await bizhawk.read(ctx.bizhawk_ctx, [(PLAYTIME, 4, DOM)]))[0], "little")
                if pt > 0:
                    new_consumables = consumables[_consumables_present(self.cons_log, pt):]
        if new_consumables:
            raw = int.from_bytes((await bizhawk.read(ctx.bizhawk_ctx, [(ECRYSTALS, 4, DOM)]))[0], "little")
            ec = raw & 0xFFFFFF
            add = sum(50 for k in new_consumables if k == "ecrystals")
            ec = min(99999, ec + add)
            writes.append((ECRYSTALS, ((raw & 0xFF000000) | ec).to_bytes(4, "little"), DOM))
            # 1-Up: sumar vidas (0x0214FC6C), tope 99
            n1 = sum(1 for k in new_consumables if k == "oneup")
            if n1:
                lives = (await bizhawk.read(ctx.bizhawk_ctx, [(LIVES, 1, DOM)]))[0][0]
                writes.append((LIVES, bytes([min(99, lives + n1)]), DOM))

        if writes:
            # guarda de estado: solo si el juego sigue en gameplay
            ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
            # los consumibles solo se marcan como aplicados si la escritura entró:
            # fuera los lotes rebobinados, dentro el nuevo con su playtime; persistir
            if ok and new_consumables:
                self.cons_log = [e for e in self.cons_log if e[1] <= pt] + [[len(consumables), pt]]
                await ctx.send_msgs([{
                    "cmd": "Set", "key": self.cons_key, "default": [],
                    "want_reply": False,
                    "operations": [{"operation": "replace", "value": self.cons_log}],
                }])

    async def _consumables_resolve(self, ctx) -> None:
        """Carga del almacén de datos el registro de consumibles aplicados de
        este slot (clave mmzx_consumables_<team>_<slot>): la 1ª llamada pide
        SetNotify+Get; las siguientes esperan la respuesta. Hasta entonces
        cons_log es None y no se concede ningún consumible (evita duplicar
        en la ventana de la reconexión)."""
        if self.cons_key is None:
            self.cons_key = CONS_KEY % (ctx.team, ctx.slot)
        if not self.cons_requested:
            await ctx.send_msgs([
                {"cmd": "SetNotify", "keys": [self.cons_key]},
                {"cmd": "Get", "keys": [self.cons_key]},
            ])
            self.cons_requested = True
            return
        if self.cons_key not in ctx.stored_data:
            return
        val = ctx.stored_data[self.cons_key]
        log = []
        if isinstance(val, list):
            for e in val:
                if isinstance(e, list) and len(e) == 2 and all(isinstance(x, int) for x in e):
                    log.append([e[0], e[1]])
        self.cons_log = log

    def _fallback_model(self, ctx, owned: dict) -> int:
        """Modelo activo al que revertir una forma no poseída: el último
        legítimo visto si sigue poseído; si no, el modelo inicial del YAML;
        si no, cualquier modelo poseído; si no, Hu (0)."""
        if owned.get(self.last_legit_model, False):
            return self.last_legit_model
        key = str((ctx.slot_data or {}).get("starting_model", "model_x"))
        rec = STARTING_MODELS.get(key)
        if rec and owned.get(int(rec.get("active", 0)), False):
            return int(rec["active"])
        for m in sorted(owned):
            if m and owned[m]:
                return m
        return 0

    async def _revert_unowned_models(self, ctx, guard) -> None:
        """#5 + posesión AUTORITATIVA (2026-09-03): la forma activa y los bits
        de posesión de TODOS los modelos deben venir SOLO del item AP (el
        modelo inicial llega pre-concedido como item). La victoria de un jefe
        o la misión Troop hacen un megamerge que cambia el modelo activo (y,
        para ZX, pone el bit compartido D0.0); el LOAD puede forzar X activo;
        y en el playtest 5 el menú ofrecía X y PX sin item. Cada tick:
          1) modelo activo no poseído -> revertir (último legítimo / modelo
             inicial / cualquiera poseído / Hu);
          2) bit de posesión puesto sin item -> limpiarlo (vivo+canónica)
             para que el menú no lo ofrezca y el save no lo muestre.
        No toca nada durante una cutscene de historia (0x0214F502.0) ni
        antes de recibir el primer ReceivedItems (siempre hay al menos el
        Transerver Access pre-concedido: lista vacía = aún sin sincronizar).
        Idempotente."""
        if not ctx.items_received:
            return
        counts: dict[int, int] = {}
        for net in ctx.items_received:
            counts[net.item] = counts.get(net.item, 0) + 1
        try:
            r = await bizhawk.read(ctx.bizhawk_ctx, [(MODEL, 1, DOM), (CUTSCENE_FLAG, 1, DOM)])
        except bizhawk.RequestFailedError:
            return
        if r[1][0] & 1:
            return   # cutscene de historia en curso (megamerge de Troop, etc.): no tocar el modelo
        active = r[0][0]
        owned = {m: counts.get(ITEMS.get(item, {}).get("id"), 0) >= 1
                 for m, (item, _a, _b) in MODEL_POSSESSION.items()}
        # 2ª mitad (progresivos): solo con 2 copias recibidas
        full = {m: counts.get(ITEMS.get(MODEL_POSSESSION[m][0], {}).get("id"), 0) >= 2
                for m in MODEL_PART2}
        owned[0] = True   # Hu: hardcoded (o gateada por su propio parche Hu-gate)
        writes: list[tuple[int, bytes, str]] = []
        notes: list[str] = []
        if owned.get(active, False):
            self.last_legit_model = active   # Hu, o forma poseída por AP: legítima
        else:
            fallback = self._fallback_model(ctx, owned)
            writes.append((MODEL, bytes([fallback]), DOM))
            notes.append("modelo %d no poseído -> revierto a %d" % (active, fallback))
        # bits de posesión sin item -> limpiar (vivo + canónica); ídem la 2ª
        # mitad sin la 2ª copia (p.ej. re-derivada por la tienda de niveles)
        addrs = sorted({a for _i, a, _b in MODEL_POSSESSION.values()}
                       | {a for a, _b in MODEL_PART2.values()})
        try:
            cur = await bizhawk.read(
                ctx.bizhawk_ctx,
                [(a, 1, DOM) for a in addrs] + [(a + CANON_OFF, 1, DOM) for a in addrs])
        except bizhawk.RequestFailedError:
            return
        vals = {a: [cur[i][0], cur[len(addrs) + i][0]] for i, a in enumerate(addrs)}
        for m, (item, a, bit) in MODEL_POSSESSION.items():
            if owned[m]:
                continue
            for k in (0, 1):
                if vals[a][k] & (1 << bit):
                    vals[a][k] &= ~(1 << bit) & 0xFF
                    notes.append("posesión de %s sin item -> limpio 0x%08X.%d%s"
                                 % (item, a, bit, "" if k == 0 else " (canónica)"))
        for m, (a, bit) in MODEL_PART2.items():
            if full.get(m, False):
                continue
            for k in (0, 1):
                if vals[a][k] & (1 << bit):
                    vals[a][k] &= ~(1 << bit) & 0xFF
                    notes.append("2ª mitad de %s sin 2ª copia -> limpio 0x%08X.%d%s"
                                 % (MODEL_POSSESSION[m][0], a, bit, "" if k == 0 else " (canónica)"))
        for i, a in enumerate(addrs):
            if vals[a][0] != cur[i][0]:
                writes.append((a, bytes([vals[a][0]]), DOM))
            if vals[a][1] != cur[len(addrs) + i][0]:
                writes.append((a + CANON_OFF, bytes([vals[a][1]]), DOM))
        if not writes:
            return
        ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
        if ok:
            from CommonClient import logger
            for n in notes:
                logger.info("[mmzx] %s" % n)

    async def _handle_death_link(self, ctx, guard) -> None:
        """SEND: observa la muerte del juego (HP >0 → 0) y la envía.
        RECEIVE: poll de ctx.last_death_link (lo actualiza CommonContext al
        recibir un DeathLink) → best-effort pone HP=0. ⚠️ El poke a 0 puede
        no matar al instante (exp105/106: el disparador de muerte real está
        en el think del jugador, RE pendiente); mata en el siguiente daño.
        """
        try:
            hp = (await bizhawk.read(ctx.bizhawk_ctx, [(HP, 1, DOM)]))[0][0]
        except bizhawk.RequestFailedError:
            return

        if self.prev_death_link is None:
            self.prev_death_link = ctx.last_death_link

        # SEND: transición >0 -> 0 (muerte real del juego)
        if self.prev_hp is not None and self.prev_hp > 0 and hp == 0:
            await ctx.send_death(f"{ctx.player_names[ctx.slot]} se quedó sin energía.")
            self.prev_death_link = ctx.last_death_link  # no auto-recibir el propio
        self.prev_hp = hp

        # RECEIVE: last_death_link avanzó por otro jugador
        if ctx.last_death_link > self.prev_death_link:
            self.prev_death_link = ctx.last_death_link
            self.pending_death = True

        if self.pending_death and hp > 0:
            self.pending_death = False
            await bizhawk.guarded_write(ctx.bizhawk_ctx, [(HP, b"\x00", DOM)], [guard])


def _cmd_teleport(self, *args) -> None:
    """Anti-softlock: teletransporta a una subárea. Sin argumentos → hub
    (z01). Uso: /mmzx_teleport [subárea] [x_px] [y_px]  ·  /mmzx_teleport K
    (letra de área → piso de esa área en el hub, junto a la consola)"""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    if len(args) >= 1 and str(args[0]).strip().upper() in HUB_FLOOR_Y:
        # letra de área -> piso del hub (sub 70) de esa área, junto a la consola
        letter = str(args[0]).strip().upper()
        # (384, y_piso-17) = encima de la consola del piso, como el Transport
        # vanilla y "Go to Transerver"; con y_piso-1 el jugador aterrizaba dentro
        # del piso y caía al de abajo (exp451: piso M → piso O).
        y = HUB_FLOOR_Y[letter] - HUB_PAD_DY
        handler.pending_teleport = (HUB_SUBAREA, HUB_X, y)
        logger.info(f"Teleport encolado → hub, piso {letter} ({HUB_X},{y}).")
        return
    try:
        sub = int(args[0]) if len(args) >= 1 else HUB_SUBAREA
        x = int(args[1]) if len(args) >= 2 else HUB_X
        y = int(args[2]) if len(args) >= 3 else HUB_Y
    except ValueError:
        logger.error("mmzx_teleport: argumentos no numéricos (o letra de área A..X)")
        return
    handler.pending_teleport = (sub, x, y)
    logger.info(f"Teleport encolado → subárea {sub} ({x},{y}).")


def _cmd_where(self, *args) -> None:
    """Diagnóstico: escribe en el log la subárea, posición y estado actuales."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    handler.pending_where = True
    logger.info("mmzx_where: encolado (se vuelca en el próximo tick en juego).")


def _cmd_accept(self, *args) -> None:
    """Fuerza la aceptación de la misión de la zona actual (o del piso del hub
    en el que estás) en el próximo tick, aunque ya se hubiera intentado."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    handler.force_accept = True
    handler.last_accept_sub = None
    logger.info("mmzx_accept: encolado (se aplica en el próximo tick en juego).")


def _cmd_start(self, *args) -> None:
    """Tutorial-skip: fuerza la (re)aplicación del estado inicial del YAML
    (modelo + Transerver). Úsalo si reinicias la partida del cartucho a mitad
    de seed (la aplicación automática es one-shot por seed)."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    handler.start_state = 2   # aplicar en el próximo tick elegible
    handler.start_confirm = 0
    handler.start_retries = 0
    logger.info("mmzx_start: encolado (se aplica al estar en el hub, en juego).")


def _cmd_flags(self, *args) -> None:
    """Diagnóstico: traza los bits del bloque de progreso que cambian.
    Uso: /mmzx_flags on  (toma snapshot y empieza a trazar) · /mmzx_flags off.
    Para mapear 'misión completada': /mmzx_flags on ANTES de entregar en el
    Transerver; entrega la misión; los bits que salgan 'ON' son la firma."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    arg = (args[0].lower() if args else "on")
    if arg in ("off", "0", "stop"):
        handler.flag_watch = False
        handler.flag_snap = None
        logger.info("mmzx_flags: OFF")
    else:
        handler.flag_watch = True
        handler.flag_snap = None   # se re-toma en el próximo tick
        logger.info("mmzx_flags: ON (snapshot en el próximo frame de juego; "
                    "ahora entrega la misión y observa los bits 'ON')")


def _cmd_dump(self, *args) -> None:
    """Diagnóstico: vuelca el estado del Transerver (flags de misión +
    índice de disponibilidad 0x02104630). Úsalo EN el menú del Transerver,
    con la lista de misiones a la vista, y dime qué misiones salen ofertadas
    para correlacionar el gating del listado."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    handler.pending_dump = True
    logger.info("mmzx_dump: encolado (se vuelca en el próximo frame de juego).")


def _cmd_notify(self, *args) -> None:
    """Avisos en pantalla al recibir/enviar items: /mmzx_notify [received|sent]
    [off|progression|useful|all] ('useful' = progresión + útiles). Sin
    argumentos muestra la configuración actual."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    if len(args) >= 2 and str(args[0]).lower() in ("received", "sent") \
            and str(args[1]).lower() in NOTIFY_LEVELS:
        handler.notify_cfg[str(args[0]).lower()] = NOTIFY_LEVELS.index(str(args[1]).lower())
    elif args:
        logger.error("uso: /mmzx_notify [received|sent] [off|progression|useful|all]")
        return
    logger.info("[mmzx] avisos en pantalla: received=%s, sent=%s" % (
        NOTIFY_LEVELS[handler.notify_cfg["received"]], NOTIFY_LEVELS[handler.notify_cfg["sent"]]))


def _cmd_marks(self, *args) -> None:
    """Marcador gris de los pickups respawneables ya enviados: /mmzx_marks [on|off]."""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    if args and str(args[0]).lower() in ("on", "off"):
        handler.marks_enabled = str(args[0]).lower() == "on"
        handler.mark_written = None
    elif args:
        logger.error("uso: /mmzx_marks [on|off]")
        return
    logger.info("[mmzx] marcador de pickups enviados: %s" % ("on" if handler.marks_enabled else "off"))
