"""BizHawkClient de Mega Man ZX (USA). Enfoque RAM-directa (no runtime ASM).

Direcciones y recetas: docs/client_integration.md + worlds/mmzx/data.py.
Dominio de memoria: "ARM9 System Bus" con direcciones absolutas 0x02xxxxxx
(verificar el mapeo del core melonDS al montar; ver playbook §1).
"""

from typing import TYPE_CHECKING, Any

import worlds._bizhawk as bizhawk
from worlds._bizhawk.client import BizHawkClient

from .data import LOCATIONS, ITEMS

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

CANON_OFF = CANON_BLOCK - LIVE_BLOCK  # 0x21602B4 - 0x21045CC

ROM_GAME_CODE = b"ARZE"       # MMZX USA


class MMZXClient(BizHawkClient):
    game = "Mega Man ZX"
    system = "NDS"
    patch_suffix = ".apmmzx"

    def __init__(self) -> None:
        super().__init__()
        self.local_checked: set[int] = set()
        self.applied_consumables = 0  # high-water de items consumibles aplicados

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        try:
            code = (await bizhawk.read(ctx.bizhawk_ctx, [(0x0C, 4, "ROM")]))[0]
        except bizhawk.RequestFailedError:
            return False
        if code != ROM_GAME_CODE:
            return False
        ctx.game = self.game
        # El parche NO pre-coloca items en la ROM: el cliente concede TODO
        # por RAM, incluidos los items locales y el start inventory.
        ctx.items_handling = 0b111
        ctx.want_slot_data = True
        ctx.watcher_timeout = 0.125
        self.local_checked = set()
        self.applied_consumables = 0
        return True

    async def set_auth(self, ctx: "BizHawkClientContext") -> None:
        # v0.1: el slot name se embebe en el parche (TODO rom.py); por
        # ahora el jugador lo teclea si no está.
        pass

    async def _in_game(self, ctx) -> bool:
        try:
            reads = await bizhawk.read(ctx.bizhawk_ctx, [
                (SUBAREA_STABLE, 1, DOM), (HP, 1, DOM), (GAME_STATE, 4, DOM)])
        except bizhawk.RequestFailedError:
            return False
        sub = reads[0][0]
        hp = reads[1][0]
        state = int.from_bytes(reads[2], "little")
        return sub != 0 and hp > 0 and state == STATE_INGAME

    async def game_watcher(self, ctx: "BizHawkClientContext") -> None:
        if ctx.server is None or ctx.slot_data is None:
            return
        if not await self._in_game(ctx):
            return

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

        checked = set()
        for name, v in LOCATIONS.items():
            det = v.get("detect")
            if not det or det[0] != "bit":
                continue
            addr, bit = det[1], det[2]
            if addr == LIFEUP_BYTE:
                val = lifeup
            elif addr == SUBTANK_BYTE:
                val = subtank
            elif LIVE_BLOCK <= addr < LIVE_BLOCK + LIVE_LEN:
                val = block[addr - LIVE_BLOCK]
            else:
                continue
            if val & (1 << bit):
                loc_id = v["id"]
                if loc_id in ctx.server_locations:
                    checked.add(loc_id)

        if checked != self.local_checked:
            newly = checked - self.local_checked
            if newly:
                await ctx.check_locations(list(checked))
            self.local_checked = checked

        # ---- conceder items recibidos (idempotente, re-aplicar todo) ----
        await self._grant_items(ctx)

        # ---- objetivo ----
        # (Serpent: pendiente de anclar el flag; se rellenará en Fase 3.)

    async def _grant_items(self, ctx) -> None:
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
        canon_bits: set[tuple[int, int]] = set()   # (canon_byte, bit) idempotentes
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
            elif kind in ("ecrystals", "oneup"):
                if i >= self.applied_consumables:
                    new_consumables.append(kind)
            # model / cardkey / transerver: TODO recetas exactas (bit de
            # posesión pendiente de RE — no se conceden aún para no
            # corromper flags). Ver docs/functions.md (biometales).

        writes: list[tuple[int, bytes, str]] = []

        # Life Ups (idempotente): bits 0..n-1 + HP máx
        if n_lifeup:
            n = min(4, n_lifeup)
            mask = (1 << n) - 1
            cur = (await bizhawk.read(ctx.bizhawk_ctx, [(LIFEUP_BYTE, 1, DOM)]))[0][0]
            if cur & mask != mask:
                writes.append((LIFEUP_BYTE, bytes([cur | mask]), DOM))
            # HP máx = 0x10 + 4*n (tope 0x20)
            hpmax = min(0x20, 0x10 + 4 * n)
            writes.append((0x0214FC76, bytes([hpmax]), DOM))

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
                lives = (await bizhawk.read(ctx.bizhawk_ctx, [(0x0214FC6C, 1, DOM)]))[0][0]
                writes.append((0x0214FC6C, bytes([min(99, lives + n1)]), DOM))
            self.applied_consumables = len(ctx.items_received)

        if writes:
            await bizhawk.write(ctx.bizhawk_ctx, writes)

    def on_package(self, ctx: "BizHawkClientContext", cmd: str, args: dict[str, Any]) -> None:
        super().on_package(ctx, cmd, args)
