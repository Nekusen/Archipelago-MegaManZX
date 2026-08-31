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
        self.granted_count = 0

    async def validate_rom(self, ctx: "BizHawkClientContext") -> bool:
        try:
            code = (await bizhawk.read(ctx.bizhawk_ctx, [(0x0C, 4, "ROM")]))[0]
        except bizhawk.RequestFailedError:
            return False
        if code != ROM_GAME_CODE:
            return False
        ctx.game = self.game
        ctx.items_handling = 0b001  # el cliente aplica los items recibidos
        ctx.want_slot_data = True
        ctx.watcher_timeout = 0.125
        self.local_checked = set()
        self.granted_count = 0
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
        id_to_grant = {v["id"]: v["grant"] for v in ITEMS.values()}
        writes: list[tuple[int, bytes, str]] = []
        for net_item in ctx.items_received:
            grant = id_to_grant.get(net_item.item)
            if not grant:
                continue
            kind = grant[0]
            if kind == "lifeup":
                # OR de un bit libre en 0x0214FC77 lo hace el juego al
                # recoger; para conceder remoto: set bit 0 como mínimo
                # (refinamiento por-conteo en Fase 3).
                pass
            # disks/misiones/keys/biometales: set bit en canónica.
            # (Recetas concretas por tipo → Fase 3 con validación.)
        if writes:
            await bizhawk.write(ctx.bizhawk_ctx, writes)

    def on_package(self, ctx: "BizHawkClientContext", cmd: str, args: dict[str, Any]) -> None:
        super().on_package(ctx, cmd, args)
