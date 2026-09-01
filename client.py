"""BizHawkClient de Mega Man ZX (USA). Enfoque RAM-directa (no runtime ASM).

Direcciones y recetas: docs/client_integration.md + worlds/mmzx/data.py.
Dominio de memoria: "ARM9 System Bus" con direcciones absolutas 0x02xxxxxx
(verificar el mapeo del core melonDS al montar; ver playbook §1).
"""

import time
from typing import TYPE_CHECKING, Any

import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

from .data import LOCATIONS, ITEMS, GOAL_BITS

if TYPE_CHECKING:
    from worlds._bizhawk.context import BizHawkClientContext

DOM = "ARM9 System Bus"

# Anclas (docs/client_integration.md)
LIVE_BLOCK = 0x021045CC       # copia viva del bloque de progreso
CANON_BLOCK = 0x021602B4      # copia canónica (conceder = set bit aquí)
LIVE_LEN = 0x60               # ventana viva a leer (cubre disks/misiones/keys)
LIFEUP_BYTE = 0x0214FC77
SUBTANK_BYTE = 0x0214FC78
ECRYSTALS = 0x0214FC70        # u24
HP = 0x0214FBB2
MODEL = 0x0214FC74
SUBAREA_STABLE = 0x02108228
GAME_STATE = 0x0215E6D8       # 0x500 = en juego
STATE_INGAME = 0x500
STATE_LOAD = 0x400            # el juego carga la escena (teleport)
SCENE_DESC = 0x0216047C       # descriptor de escena (spawn X/Y + subárea)
LIVES = 0x0214FC6C
HPMAX = 0x0214FC76

CANON_OFF = CANON_BLOCK - LIVE_BLOCK  # 0x21602B4 - 0x21045CC

ROM_GAME_CODE = b"ARZE"       # MMZX USA

# Hub por defecto del anti-softlock (z01 = subárea 70)
HUB_SUBAREA, HUB_X, HUB_Y = 70, 288, 351


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
        self.prev_hp = None
        self.prev_death_link = None
        self.pending_death = False
        self.pending_teleport = None   # (subárea, x, y) o None
        self.added_commands = False

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
        return True

    async def set_auth(self, ctx: "BizHawkClientContext") -> None:
        if getattr(self, "slot_name", None):
            ctx.auth = self.slot_name

    async def _in_game(self, ctx):
        """Devuelve (en_juego, state_bytes). state_bytes sirve de GUARD para
        que las escrituras solo se apliquen si el juego SIGUE en gameplay
        (no en menú/transición) — evita corromper una carga de escena."""
        try:
            reads = await bizhawk.read(ctx.bizhawk_ctx, [
                (SUBAREA_STABLE, 1, DOM), (HP, 1, DOM), (GAME_STATE, 4, DOM)])
        except bizhawk.RequestFailedError:
            return False, None
        sub = reads[0][0]
        hp = reads[1][0]
        state_bytes = reads[2]
        state = int.from_bytes(state_bytes, "little")
        return (sub != 0 and hp > 0 and state == STATE_INGAME), state_bytes

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        if ctx.server is None or ctx.slot_data is None:
            return

        # DeathLink: activar tag una vez según slot_data
        if not self.death_link_setup:
            self.death_link_setup = True
            self.death_link_enabled = bool(ctx.slot_data.get("death_link", False))
            if self.death_link_enabled:
                await ctx.update_death_link(True)

        # comandos de cliente (anti-softlock)
        if not self.added_commands:
            self.added_commands = True
            ctx.command_processor.commands["mmzx_teleport"] = _cmd_teleport

        in_game, state_bytes = await self._in_game(ctx)
        if not in_game:
            self.prev_hp = None
            return
        guard = (GAME_STATE, state_bytes, DOM)   # solo escribir si sigue en juego

        # ---- detectar checks ----
        try:
            live = (await bizhawk.read(ctx.bizhawk_ctx, [
                (LIVE_BLOCK, LIVE_LEN, DOM),
                (LIFEUP_BYTE, 2, DOM)])
            )
        except bizhawk.RequestFailedError:
            return
        block = live[0]
        lifeup = live[1][0]
        subtank = live[1][1]

        def bit_set(addr: int, bit: int) -> bool:
            if addr == LIFEUP_BYTE:
                val = lifeup
            elif addr == SUBTANK_BYTE:
                val = subtank
            elif LIVE_BLOCK <= addr < LIVE_BLOCK + LIVE_LEN:
                val = block[addr - LIVE_BLOCK]
            else:
                return False
            return bool(val & (1 << bit))

        checked = set()
        for name, v in LOCATIONS.items():
            det = v.get("detect")
            if not det:
                continue
            if det[0] == "bit":
                ok = bit_set(det[1], det[2])
            elif det[0] == "all":   # todos los bits (misión completada)
                ok = all(bit_set(a, b) for a, b in det[1])
            else:
                continue
            if ok:
                loc_id = v["id"]
                if loc_id in ctx.server_locations:
                    checked.add(loc_id)

        if checked != self.local_checked:
            newly = checked - self.local_checked
            if newly:
                await ctx.check_locations(list(checked))
            self.local_checked = checked

        # ---- conceder items recibidos (idempotente, re-aplicar todo) ----
        await self._grant_items(ctx, guard)

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
            done = all(
                (block[a - LIVE_BLOCK] if LIVE_BLOCK <= a < LIVE_BLOCK + LIVE_LEN else 0)
                & (1 << b) for (a, b) in GOAL_BITS)
            if done:
                from NetUtils import ClientStatus
                ctx.finished_game = True
                await ctx.send_msgs([{"cmd": "StatusUpdate",
                                      "status": ClientStatus.CLIENT_GOAL}])

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
            elif kind in ("ecrystals", "oneup"):
                if i >= self.applied_consumables:
                    new_consumables.append(kind)
            # kind == "todo": item sin receta aún (no en pool v0.1)

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

        # Life Ups (idempotente): bits 0..n-1 + HP máx
        if n_lifeup:
            n = min(4, n_lifeup)
            mask = (1 << n) - 1
            cur = (await bizhawk.read(ctx.bizhawk_ctx, [(LIFEUP_BYTE, 1, DOM)]))[0][0]
            if cur & mask != mask:
                writes.append((LIFEUP_BYTE, bytes([cur | mask]), DOM))
            # HP máx = 0x10 + 4*n (tope 0x20)
            hpmax = min(0x20, 0x10 + 4 * n)
            writes.append((HPMAX, bytes([hpmax]), DOM))

        # Sub Tanks (idempotente): bits 0..n-1
        if n_subtank:
            n = min(4, n_subtank)
            mask = (1 << n) - 1
            cur = (await bizhawk.read(ctx.bizhawk_ctx, [(SUBTANK_BYTE, 1, DOM)]))[0][0]
            if cur & mask != mask:
                writes.append((SUBTANK_BYTE, bytes([cur | mask]), DOM))

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
    (z01). Uso: /mmzx_teleport [subárea] [x_px] [y_px]"""
    from CommonClient import logger
    handler = self.ctx.client_handler
    if not isinstance(handler, MMZXClient):
        return
    try:
        sub = int(args[0]) if len(args) >= 1 else HUB_SUBAREA
        x = int(args[1]) if len(args) >= 2 else HUB_X
        y = int(args[2]) if len(args) >= 3 else HUB_Y
    except ValueError:
        logger.error("mmzx_teleport: argumentos no numéricos")
        return
    handler.pending_teleport = (sub, x, y)
    logger.info(f"Teleport encolado → subárea {sub} ({x},{y}).")
