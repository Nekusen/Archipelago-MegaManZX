"""Granting received items, and keeping model ownership equal to the items held."""

from typing import TYPE_CHECKING
import worlds._bizhawk as bizhawk

from ..data import (
    ACTIVE_MODEL_ADDR, EVENT_GATES, EVENT_GATES_ALL6, EVENT_GATES_OPEN, ITEMS, STARTING_MODELS)
from .addresses import (
    BOSS_LEVELS, CANON_OFF, CAPACITY_NIBBLE, CARDKEY_MASKS, COLLECTED_NIBBLE, CONS_KEY,
    CUTSCENE_FLAG, DOM, ECRYSTALS, ECRYSTALS_CAP, ECRYSTALS_HIGH_MASK, ECRYSTALS_MASK,
    ECRYSTALS_PER_ITEM, HPMAX, HP_BASE, HP_CAP, HP_PER_LIFEUP, ITEM_BY_ID, LIFEUP_BYTE,
    LIFEUP_SLOTS, LIVES, LIVES_CAP, MODEL_LEVEL_IDX, MODEL_POSSESSION, MODEL_SECOND_HALF,
    PLAYTIME, SIX_MODELS, SUBTANK_BYTE, SUBTANK_SLOTS, WE_BASE, WE_FULL)
from .ram import Tick, bits_by_byte, copies_writes, read_copies

if TYPE_CHECKING:
    from . import MMZXClient


def received_counts(ctx) -> dict[str, int]:
    """Copies of each item received so far, by name."""
    counts: dict[str, int] = {}
    for net in ctx.items_received:
        entry = ITEM_BY_ID.get(net.item)
        if entry:
            counts[entry[0]] = counts.get(entry[0], 0) + 1
    return counts


def wanted_progress_bits(counts: dict[str, int]) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """(idempotent bits, Card Key bits) the received items call for.

    Progressive items set one bit per copy. Some story gates open for everyone;
    the Slither gate (D-2 to D-4) once the six model items are held.
    """
    bits: set[tuple[int, int]] = set()
    cardkeys: set[tuple[int, int]] = set()
    for name, n in counts.items():
        grant = ITEMS[name]["grant"]
        kind = grant[0]
        if kind == "live_bit":
            (cardkeys if name.endswith("Card Key") else bits).add((grant[1], grant[2]))
        elif kind == "progressive":
            for k, (addr, bit) in enumerate(grant[1]):
                if n > k:
                    bits.add((addr, bit))
        elif kind == "transerver":
            bits.add((grant[1], grant[2]))
    for fl in EVENT_GATES_OPEN:
        bits.add(tuple(EVENT_GATES[fl]))
    if all(counts.get(n, 0) for n in SIX_MODELS):
        for fl in EVENT_GATES_ALL6:
            bits.add(tuple(EVENT_GATES[fl]))
    return bits, cardkeys


async def weapon_energy_writes(ctx, counts: dict[str, int]) -> list[tuple[int, bytes, str]]:
    """Victory levels and a full bar for models granted by item, once (see BOSS_LEVELS).

    With one half the first boss level is raised so the pair sums 4 and the
    bar is filled to 16; with both halves both levels become 4 and the bar 32.
    """
    owned = [m for m, (item, _a, _b) in MODEL_POSSESSION.items()
             if m in MODEL_LEVEL_IDX and counts.get(item, 0)]
    if not owned:
        return []
    lv = (await bizhawk.read(ctx.bizhawk_ctx, [(BOSS_LEVELS, 8, DOM)]))[0]
    writes: list[tuple[int, bytes, str]] = []
    for m in owned:
        i0, i1 = MODEL_LEVEL_IDX[m]
        full = counts.get(MODEL_POSSESSION[m][0], 0) >= 2
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
    return writes


async def capacity_writes(ctx, counts: dict[str, int]) -> list[tuple[int, bytes, str]]:
    """Life Up and Sub Tank capacity nibbles equal to the received counts; max HP follows.

    The physical pickup only marks its "collected" nibble (the check) and grants nothing.
    """
    writes: list[tuple[int, bytes, str]] = []
    nlu = min(LIFEUP_SLOTS, counts.get("Life Up", 0))
    lu_mask = (1 << nlu) - 1
    cur_lu, cur_hpmax = await bizhawk.read(ctx.bizhawk_ctx, [(LIFEUP_BYTE, 1, DOM), (HPMAX, 1, DOM)])
    if (cur_lu[0] & CAPACITY_NIBBLE) != lu_mask:
        writes.append((LIFEUP_BYTE, bytes([(cur_lu[0] & COLLECTED_NIBBLE) | lu_mask]), DOM))
    hpmax = min(HP_CAP, HP_BASE + HP_PER_LIFEUP * nlu)
    if cur_hpmax[0] != hpmax:
        writes.append((HPMAX, bytes([hpmax]), DOM))
    nst = min(SUBTANK_SLOTS, counts.get("Sub Tank", 0))
    st_mask = (1 << nst) - 1
    cur_st = (await bizhawk.read(ctx.bizhawk_ctx, [(SUBTANK_BYTE, 1, DOM)]))[0][0]
    if (cur_st & CAPACITY_NIBBLE) != st_mask:
        writes.append((SUBTANK_BYTE, bytes([(cur_st & COLLECTED_NIBBLE) | st_mask]), DOM))
    return writes


def consumables_present(log, playtime: int) -> int:
    """Consumables already present in a game state at the given play time.

    Batches stamped later than the play time were rewound by a reload.
    """
    return max([int(e[0]) for e in log if int(e[1]) <= playtime], default=0)


async def resolve_consumables_log(client: "MMZXClient", ctx) -> None:
    """Load the applied-consumables log from the datastore; None until it arrives.

    Nothing is granted meanwhile, so a reconnect never adds a batch twice.
    """
    if client.cons_key is None:
        client.cons_key = CONS_KEY % (ctx.team, ctx.slot)
    if not client.cons_requested:
        await ctx.send_msgs([
            {"cmd": "SetNotify", "keys": [client.cons_key]},
            {"cmd": "Get", "keys": [client.cons_key]},
        ])
        client.cons_requested = True
        return
    if client.cons_key not in ctx.stored_data:
        return
    val = ctx.stored_data[client.cons_key]
    log = []
    if isinstance(val, list):
        for e in val:
            if isinstance(e, list) and len(e) == 2 and all(isinstance(x, int) for x in e):
                log.append([e[0], e[1]])
    client.cons_log = log


async def consumable_writes(client: "MMZXClient", ctx, consumables: list[str]) -> tuple[list, int, list]:
    """E-Crystals and 1-Ups not yet applied to this game state.

    Returns (new consumables, play time, writes). Each batch is stamped with the
    play time, which grows every frame, never goes back on death and returns to
    the save's value on Continue or LOAD: a batch stamped later than the current
    play time was rewound and is granted again; a reconnect rewinds nothing.
    """
    if not consumables:
        return [], 0, []
    if client.cons_log is None:
        await resolve_consumables_log(client, ctx)
    if client.cons_log is None:
        return [], 0, []
    pt = int.from_bytes((await bizhawk.read(ctx.bizhawk_ctx, [(PLAYTIME, 4, DOM)]))[0], "little")
    if pt <= 0:
        return [], pt, []
    new = consumables[consumables_present(client.cons_log, pt):]
    if not new:
        return [], pt, []
    writes: list[tuple[int, bytes, str]] = []
    raw = int.from_bytes((await bizhawk.read(ctx.bizhawk_ctx, [(ECRYSTALS, 4, DOM)]))[0], "little")
    ec = min(ECRYSTALS_CAP, (raw & ECRYSTALS_MASK) + ECRYSTALS_PER_ITEM * new.count("ecrystals"))
    writes.append((ECRYSTALS, ((raw & ECRYSTALS_HIGH_MASK) | ec).to_bytes(4, "little"), DOM))
    n1 = new.count("oneup")
    if n1:
        lives = (await bizhawk.read(ctx.bizhawk_ctx, [(LIVES, 1, DOM)]))[0][0]
        writes.append((LIVES, bytes([min(LIVES_CAP, lives + n1)]), DOM))
    return new, pt, writes


async def grant_items(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Write the received items into the game.

    Idempotent grants (bits, capacities, levels) are recomputed from the
    whole list every tick and only the bytes that differ are written;
    consumables are applied once per game state and logged in the datastore.
    """
    counts = received_counts(ctx)
    consumables = [ITEM_BY_ID[net.item][1][0] for net in ctx.items_received
                   if net.item in ITEM_BY_ID and ITEM_BY_ID[net.item][1][0] in ("ecrystals", "oneup")]
    bits, cardkeys = wanted_progress_bits(counts)

    writes = await weapon_energy_writes(ctx, counts)
    # idempotent bits go to live (effect now) and canonical (persistence)
    if bits:
        masks = bits_by_byte(bits)
        addrs = sorted(masks)
        live, canon = await read_copies(ctx, addrs)
        writes += copies_writes(addrs, live, canon, set_masks=masks)
    # Card Keys: exactly the received set, since the game also hands them out
    # as mission rewards; the neighbouring bits are unrelated flags
    want = bits_by_byte(cardkeys)
    kaddrs = sorted(CARDKEY_MASKS)
    live, canon = await read_copies(ctx, kaddrs)
    writes += copies_writes(kaddrs, live, canon,
                            set_masks={a: want.get(a, 0) & CARDKEY_MASKS[a] for a in kaddrs},
                            clear_masks={a: CARDKEY_MASKS[a] & ~want.get(a, 0) for a in kaddrs})
    writes += await capacity_writes(ctx, counts)
    new_consumables, pt, cons_writes = await consumable_writes(client, ctx, consumables)
    writes += cons_writes
    if not writes:
        return
    ok = await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard])
    # consumables count as applied only if the write went through
    if ok and new_consumables:
        client.cons_log = [e for e in client.cons_log if e[1] <= pt] + [[len(consumables), pt]]
        await ctx.send_msgs([{
            "cmd": "Set", "key": client.cons_key, "default": [],
            "want_reply": False,
            "operations": [{"operation": "replace", "value": client.cons_log}],
        }])


def fallback_model(client: "MMZXClient", ctx, owned: dict[int, bool]) -> int:
    """Model to revert to: last legitimate, YAML start, any owned, else Hu."""
    if owned.get(client.last_legit_model, False):
        return client.last_legit_model
    rec = STARTING_MODELS.get(str(ctx.slot_data.get("starting_model", "model_zx")))
    if rec and owned.get(int(rec.get("active", 0)), False):
        return int(rec["active"])
    for m in sorted(owned):
        if m and owned[m]:
            return m
    return 0


async def revert_unowned_models(client: "MMZXClient", ctx, tick: Tick) -> None:
    """Revert an unowned active form and clear possession bits without their item.

    Boss victories, the Troop megamerge and the LOAD change the active model
    or set shared bits; ownership must come from items alone. Skipped during
    cutscenes and until the first ReceivedItems (the list is never empty).
    """
    if not ctx.items_received:
        return
    counts = received_counts(ctx)
    r = await bizhawk.read(ctx.bizhawk_ctx, [(ACTIVE_MODEL_ADDR, 1, DOM), (CUTSCENE_FLAG, 1, DOM)])
    if r[1][0] & 1:
        return   # cutscene running: leave the model alone
    active = r[0][0]
    owned = {m: counts.get(item, 0) >= 1 for m, (item, _a, _b) in MODEL_POSSESSION.items()}
    full = {m: counts.get(MODEL_POSSESSION[m][0], 0) >= 2 for m in MODEL_SECOND_HALF}
    # With hu_in_pool Hu is just another form. The game refuses to transform
    # with a single owned category, so a scene that ends in Hu (the M-1 seal
    # one does) would leave the player stuck in Hu for good.
    owned[0] = not ctx.slot_data.get("hu_in_pool") or counts.get("Model Hu", 0) >= 1
    writes: list[tuple[int, bytes, str]] = []
    notes: list[str] = []
    if owned.get(active, False):
        client.last_legit_model = active   # Hu, or form owned via AP: legitimate
    else:
        fallback = fallback_model(client, ctx, owned)
        if fallback != active:   # with nothing better (Hu gated and 0 biometals) leave it
            writes.append((ACTIVE_MODEL_ADDR, bytes([fallback]), DOM))
            notes.append("model %d not owned -> reverting to %d" % (active, fallback))
    # possession bits without their item are cleared in both copies
    addrs = sorted({a for _i, a, _b in MODEL_POSSESSION.values()}
                   | {a for a, _b in MODEL_SECOND_HALF.values()})
    live, canon = await read_copies(ctx, addrs)
    clear: dict[int, int] = {}
    for m, (item, a, bit) in MODEL_POSSESSION.items():
        if owned[m]:
            continue
        clear[a] = clear.get(a, 0) | (1 << bit)
        for cur, tag in ((live, ""), (canon, " (canonical)")):
            if cur[a] & (1 << bit):
                notes.append("%s owned without its item -> clearing 0x%08X.%d%s" % (item, a, bit, tag))
    for m, (a, bit) in MODEL_SECOND_HALF.items():
        if full[m]:
            continue
        clear[a] = clear.get(a, 0) | (1 << bit)
        for cur, tag in ((live, ""), (canon, " (canonical)")):
            if cur[a] & (1 << bit):
                notes.append("second half of %s without its second copy -> clearing 0x%08X.%d%s"
                             % (MODEL_POSSESSION[m][0], a, bit, tag))
    writes += copies_writes(addrs, live, canon, clear_masks=clear)
    if writes and await bizhawk.guarded_write(ctx.bizhawk_ctx, writes, [tick.guard]):
        for n in notes:
            client._debug("[mmzx] %s" % n)
