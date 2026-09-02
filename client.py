"""BizHawkClient de Mega Man ZX (USA). Enfoque RAM-directa (no runtime ASM).

Direcciones y recetas: docs/client_integration.md + worlds/mmzx/data.py.
Dominio de memoria: "ARM9 System Bus" con direcciones absolutas 0x02xxxxxx
(verificar el mapeo del core melonDS al montar; ver playbook §1).
"""

import time
from typing import TYPE_CHECKING, Any

import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

from .data import (LOCATIONS, ITEMS, GOAL_BITS, GOAL_BITS_ALT, MISSION_ACCEPT,
                   MISSION_STATE_ADDR, MISSION_ACTIVE_FLAG,
                   STARTING_MODELS, STARTING_MODEL_ITEM, STARTING_TRANSERVERS,
                   MODEL_X_POSSESSION, ACTIVE_MODEL_ADDR)
from .data import EVENT_GATES, EVENT_GATES_OPEN, EVENT_GATES_ALL6
from .data import HUB_FLOOR_BOSS, HUB_FLOOR_DOOR_X, HUB_FLOOR_Y
from .data import PICKUP_MAILBOX_ADDR, PICKUP_MAILBOX_SLOTS
from .golden import GOLDEN_IMAGE, GOLDEN_IMAGE_ADDR

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext

DOM = "ARM9 System Bus"

# Anclas (docs/client_integration.md)
LIVE_BLOCK = 0x021045CC       # copia viva del bloque de progreso
CANON_BLOCK = 0x021602B4      # copia canónica (conceder = set bit aquí)
LIVE_LEN = 0x60               # ventana viva a leer (cubre disks/misiones/keys)
PLAYER_POS = 0x0214FB65      # u32 x<<8 y u32 y<<8 (8 bytes; px = >>8)
POS_KEY = "mmzx_pos_%d"     # almacén de datos: [subárea, x, y] para UT (auto-tab/icono)
POS_INTERVAL = 1.0           # s entre envíos si no cambia la subárea
POS_MIN_DELTA = 48           # px de movimiento mínimo para reenviar
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

# #5 Troop sin ZX (exp197-199): posesión de Model ZX = 0x021045D0 bit0;
# modelo activo ZX = 2.
ZX_POSSESSION_BYTE = 0x021045D0
ZX_POSSESSION_BIT = 0
ZX_ACTIVE = 2

# #5 (exp240 + rom.py §1c): modelo activo (0x0214FC74) -> (item AP, bit de
# posesión que SOLO pone ese item). Tras el parche de categorías, poseer
# H/F/L/P depende del bit D1 (0x021045D1); ZX del D0.0; OX del D2.1. Sirve
# para revertir una forma que el jugador aún no ha recibido.
MODEL_POSSESSION = {
    2: ("Model ZX", 0x021045D0, 0),
    # H/F/L/P: flags LIBRES 0x02104627.0-3 (agente exp380-389); los bits
    # D0/D1 los escriben los jefes del par y ya no conceden nada.
    3: ("Biometal H", 0x02104627, 0),
    4: ("Biometal F", 0x02104627, 1),
    5: ("Biometal L", 0x02104627, 2),
    6: ("Biometal P", 0x02104627, 3),
    7: ("Biometal O", 0x021045D2, 1),
}

# Byte "misión en curso" del bloque de partida (0x0210460C+0x1F): bit1 lo
# pone FUN_02031f10 al aceptar (id<17), bit2 para misiones de historia;
# FUN_02009184 ("¿misión X activa?") exige (&6). Lo limpia el Report.
# Canónica en +0x5BCE8. Sin él, la arena del jefe no se armaba (exp229/231).
MISSION_ACTIVE_BYTE = 0x0210462B
# Bloque de estado de HISTORIA (agente exp350-359): id de mision activa +
# objeto del handler por mision (tabla 0x020CF0F4). Sin instalarlo, el
# force-accept no dispara cutscenes ni flags por rectangulo (verjas).
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


class MMZXClient(BizHawkClient):
    game = "Mega Man ZX"
    system = "NDS"
    patch_suffix = ".apmmzx"

    def __init__(self) -> None:
        super().__init__()
        self.local_checked: set[int] = set()
        self.applied_consumables = 0  # high-water de items consumibles aplicados
        self.death_link_enabled = False
        self.death_link_setup = False
        self.mission_auto_accept = False   # modo open-world (slot_data)
        self.mission_setup = False
        self.last_accept_sub = None        # última subárea auto-aceptada
        self.prev_hp = None
        self.prev_death_link = None
        self.pending_death = False
        self.pending_teleport = None   # (subárea, x, y) o None
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
        self.applied_consumables = 0
        self.death_link_setup = False
        self.prev_hp = None
        self.prev_death_link = None
        self.pending_death = False
        self.mailbox_count = None
        self.mailbox_checked = set()
        self.mailbox_enabled = None
        self.pos_last = None
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

        # ---- posición del jugador -> almacén de datos (UT: auto-tab e icono) ----
        await self._send_position(ctx)

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
        await self._poll_pickup_mailbox(ctx)
        checked |= self.mailbox_checked

        if checked != self.local_checked:
            newly = checked - self.local_checked
            if newly:
                await ctx.check_locations(list(checked))
            self.local_checked = checked

        # ---- diagnóstico: trazar bits que cambian (mapear misión completada) ----
        if self.flag_watch:
            await self._flag_watch_tick(ctx)

        # ---- diagnóstico: volcar estado del Transerver (a petición) ----
        if self.pending_dump:
            self.pending_dump = False
            await self._dump_transerver(ctx)

        # ---- tutorial-skip: aplicar el estado inicial (one-shot) ----
        await self._start_state_tick(ctx, guard)

        # ---- conceder items recibidos (idempotente, re-aplicar todo) ----
        await self._grant_items(ctx, guard)

        # ---- #5: revertir formas de jefe / Troop no poseídas por item AP ----
        await self._revert_unowned_models(ctx, guard)

        # ---- open-world: auto-aceptar la misión de la zona actual ----
        if self.mission_auto_accept:
            await self._auto_accept_mission(ctx, guard)

        # ---- DeathLink ----
        if self.death_link_enabled:
            await self._handle_death_link(ctx, guard)

        # ---- anti-softlock: teleport pedido por comando ----
        if self.pending_teleport is not None:
            sub, x, y = self.pending_teleport
            self.pending_teleport = None
            await self._teleport(ctx, sub, x, y, guard)

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
            names = [ctx.location_names.lookup_in_game(i) for i in new_ids]
            logger.info("[mmzx] pickup recogido: %s" % ", ".join(names))

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

    async def _auto_accept_mission(self, ctx, guard) -> None:
        """Open-world: al ENTRAR en la subárea destino de una misión, la
        fuerza como aceptada (replica FUN_02031f10, validado exp067): start
        flag (vivo+canónica) + estado en MISSION_STATE_ADDR + MISSION_ACTIVE_
        FLAG=1. Solo al CAMBIAR de zona (no cada frame) y si no es ya la
        misión activa. Excluye Troop/Protect HQ (no están en MISSION_ACCEPT;
        se auto-lanzan por historia)."""
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
            floor = next((fy for fy in HUB_FLOOR_BOSS if abs(y - (fy - 17)) <= 48), None)
            if floor is None or x > HUB_FLOOR_DOOR_X:
                self.last_accept_sub = None
                return
            if self.last_accept_sub == ("hub", floor):
                return
            self.last_accept_sub = ("hub", floor)
            rec = MISSION_ACCEPT.get(HUB_FLOOR_BOSS[floor])
        else:
            if sub == self.last_accept_sub:
                return
            self.last_accept_sub = sub
            # (Las salas de JEFE ya no se excluyen: con la guarda OAM de la ROM
            # forzar la misión dentro no corrompe la sala; agente exp379/379b.)
            rec = MISSION_ACCEPT.get(sub)
        if not rec:
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
                return
        try:
            cur_state = int.from_bytes((await bizhawk.read(
                ctx.bizhawk_ctx, [(MISSION_STATE_ADDR, 4, DOM)]))[0], "little")
        except bizhawk.RequestFailedError:
            return
        if cur_state == rec["state"]:
            return   # ya es la misión activa
        addr, bit = rec["flag"]
        canon = addr + (CANON_BLOCK - LIVE_BLOCK)
        act, act_c = MISSION_ACTIVE_BYTE, MISSION_ACTIVE_BYTE + (CANON_BLOCK - LIVE_BLOCK)
        cur = await bizhawk.read(ctx.bizhawk_ctx, [
            (addr, 1, DOM), (canon, 1, DOM), (act, 1, DOM), (act_c, 1, DOM)])
        writes = [
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
        writes.append((STORY_HANDLER_OBJ, bytes(obj), DOM))
        writes.append((STORY_HANDLER_ID, int(rec["id"]).to_bytes(4, "little"), DOM))
        # bits extra de la misión (p.ej. Troop: 0x021045E0.7 = "ya lanzada" para
        # que la sala de mando X-2 no la relance por historia), vivo+canónica
        for ea, eb in rec.get("extra", []):
            ecur = await bizhawk.read(ctx.bizhawk_ctx, [(ea, 1, DOM), (ea + CANON_OFF, 1, DOM)])
            writes.append((ea, bytes([ecur[0][0] | (1 << eb)]), DOM))
            writes.append((ea + CANON_OFF, bytes([ecur[1][0] | (1 << eb)]), DOM))
        ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
        if ok:
            from CommonClient import logger
            logger.info("[mmzx] open-world: misión auto-aceptada → %s" % rec["name"])

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
            img = bytearray(GOLDEN_IMAGE)
            img[0x71] = 1 if int(ctx.slot_data.get("character", 0) or 0) == 1 else 0
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
          - CONSUMIBLES (E-Crystals, 1-Up): se aplican UNA vez por item
            nuevo (high-water `applied_consumables`), nunca re-sumar.
        """
        id_to_item = {v["id"]: (name, v["grant"]) for name, v in ITEMS.items()}

        # contar recibidos por tipo de concesión
        n_lifeup = n_subtank = 0
        live_bits: set[tuple[int, int]] = set()    # (live_addr, bit) idempotentes
        new_consumables: list[str] = []
        for i, net in enumerate(ctx.items_received):
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
                live_bits.add((grant[1], grant[2]))
            elif kind == "transerver":
                # acceso a la red de Transervers: si el bit del destino es
                # conocido (exp230) se enciende en el bitfield 0x02104627/28
                # (vivo+canónica) para que aparezca en la lista de Transport
                # del juego; si no, el item gatea solo la lógica (el warp del
                # cliente /mmzx_teleport cubre el desplazamiento).
                if len(grant) >= 3:
                    live_bits.add((grant[1], grant[2]))
            elif kind in ("ecrystals", "oneup"):
                if i >= self.applied_consumables:
                    new_consumables.append(kind)
            # kind == "todo": item sin receta aún (no en pool v0.1)

        # Verjas de EVENTO (puertas con bit 1 del rol; exp341): las de
        # EVENT_GATES_OPEN se abren siempre (open world) y las de
        # EVENT_GATES_ALL6 al tener los 6 biometales por items AP (requisito
        # de diseño del goal: HQ de Slither D-2 -> D-4, sello de M-1).
        for fl in EVENT_GATES_OPEN:
            live_bits.add(tuple(EVENT_GATES[fl]))
        received = {id_to_item[net.item][0] for net in ctx.items_received if net.item in id_to_item}
        if all(n in received for n in ("Model X", "Model ZX", "Biometal H",
                                       "Biometal F", "Biometal L", "Biometal P")):
            for fl in EVENT_GATES_ALL6:
                live_bits.add(tuple(EVENT_GATES[fl]))

        writes: list[tuple[int, bytes, str]] = []

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

        # Consumibles (una vez)
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
            # los consumibles solo se marcan como aplicados si la escritura entró
            if ok and new_consumables:
                self.applied_consumables = len(ctx.items_received)

    async def _revert_unowned_models(self, ctx, guard) -> None:
        """#5: la VICTORIA de un jefe (o la misión Troop) hace un megamerge que
        cambia el modelo activo y, en vanilla, concede la posesión. En el
        randomizer el modelo debe venir SOLO del item AP:
          - H/F/L/P: el parche de ROM (rom.py §1c) hace que la posesión
            dependa solo del bit D1 (item AP); la victoria pone el bit D0
            (= detección del check "Obtain Biometal X"), que NO concede
            posesión. Aquí solo hay que REVERTIR el modelo activo si el jugador
            no ha recibido el item -> juega con su modelo hasta recibirlo.
          - ZX: comparte el bit D0.0 entre posesión y grant de Troop, así que
            además de revertir el modelo hay que LIMPIAR ese bit (vivo+canónica)
            para que el menú no ofrezca ZX (validado exp198/199).
        Idempotente. Si el item AP se ha recibido, la forma es legítima y no se
        toca (se registra como 'último modelo legítimo')."""
        received = {net.item for net in ctx.items_received}
        try:
            active = (await bizhawk.read(ctx.bizhawk_ctx, [(MODEL, 1, DOM)]))[0][0]
        except bizhawk.RequestFailedError:
            return
        rec = MODEL_POSSESSION.get(active)
        if rec is None:
            self.last_legit_model = active   # 0 Hu / 1 X: siempre legítimos
            return
        item_name, pos_addr, pos_bit = rec
        owns = ITEMS.get(item_name, {}).get("id") in received
        if owns:
            self.last_legit_model = active   # forma poseída por AP: legítima
            return
        # forma NO poseída: revertir el modelo activo al último legítimo
        writes = [(MODEL, bytes([self.last_legit_model]), DOM)]
        note = "modelo %d no poseído -> revierto a %d" % (active, self.last_legit_model)
        # ZX: además limpiar el bit compartido D0.0 (menú)
        if active == ZX_ACTIVE:
            canon = ZX_POSSESSION_BYTE + CANON_OFF
            cur = await bizhawk.read(ctx.bizhawk_ctx,
                                     [(ZX_POSSESSION_BYTE, 1, DOM), (canon, 1, DOM)])
            mask = ~(1 << ZX_POSSESSION_BIT) & 0xFF
            if cur[0][0] & (1 << ZX_POSSESSION_BIT):
                writes.append((ZX_POSSESSION_BYTE, bytes([cur[0][0] & mask]), DOM))
            if cur[1][0] & (1 << ZX_POSSESSION_BIT):
                writes.append((canon, bytes([cur[1][0] & mask]), DOM))
            note = "Troop: ZX no concedido (mantengo el modelo %d)" % self.last_legit_model
        ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [guard])
        if ok:
            from CommonClient import logger
            logger.info("[mmzx] %s" % note)

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
        handler.pending_teleport = (HUB_SUBAREA, HUB_X, HUB_FLOOR_Y[letter] - 1)
        logger.info(f"Teleport encolado → hub, piso {letter} ({HUB_X},{HUB_FLOOR_Y[letter] - 1}).")
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
