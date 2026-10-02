"""Door constraints: the catalogue of sites, the draw of a seed, its logic and its ROM edits."""
import os
import random
import struct
import unittest
from collections import Counter

from BaseClasses import CollectionState
from test.general import setup_multiworld
from worlds.AutoWorld import call_all

from .bases import MMZXTestBase
from .test_rom import ROM_PATH
from .. import MMZXWorld, door_constraints
from ..data import DOORS
from ..door_data import ROOMS, SITES
from ..logic.rules import SITE_DOORS
from ..options import DoorConstraintsMax, DoorConstraintsMin
from ..rom import arm9, doors, nds
from ..rom.ui import ROOM_OVERLAY_SLOT_RAM

DOOR_BY_NAME = {d["name"]: d for d in DOORS}
ENTITY_KIND_OFF = 1
ENTITY_SUBKIND_OFF = 2
DOOR_KIND = 5
DOOR_SUBKINDS = (0x12, 0x13)
ROLE_NO_DOOR = 0x80                 # a way with no door drawn; a locked one is always drawn
ROLE_NOT_PLAIN = 0x7E               # a key, an event or a mission lock
LOCKED = 10
RELEASE_PALETTE_RAM = 0x0200EE4C    # the call the closed-door hook displaces


class TestSites(unittest.TestCase):
    """The catalogue only holds doors a seed can lock and show."""

    def test_a_site_is_a_way_between_two_rooms(self) -> None:
        for name, site in SITES.items():
            with self.subTest(site=name):
                there, back = (DOOR_BY_NAME[d] for d in site["doors"])
                self.assertEqual((there["src"], there["dst"]), (back["dst"], back["src"]))
                self.assertNotEqual(there["src"], there["dst"])
                for door in (there, back):
                    self.assertIsNone(door["key"])
                    self.assertIsNone(door["gate"])
                    self.assertNotIn(door["src"][0], "xnz")
                self.assertEqual(site["border"], there["src"][0] != there["dst"][0])
                self.assertEqual([f["room"] for f in site["faces"]], [there["src"], back["src"]])

    def test_a_door_belongs_to_one_site(self) -> None:
        self.assertEqual(len(SITE_DOORS), 2 * len(SITES))

    def test_faces_are_plain_doors(self) -> None:
        for name, site in SITES.items():
            for face in site["faces"]:
                with self.subTest(site=name, room=face["room"]):
                    template = bytes.fromhex(face["template"])
                    self.assertEqual(len(template), doors.TEMPLATE_LEN)
                    self.assertEqual(template[ENTITY_KIND_OFF], DOOR_KIND)
                    self.assertIn(template[ENTITY_SUBKIND_OFF], DOOR_SUBKINDS)
                    self.assertEqual(template[doors.TEMPLATE_ROLE] & ROLE_NOT_PLAIN, 0)
                    self.assertLess(face["slot"], ROOMS[face["room"]]["slot_count"])

    def test_every_site_carries_weight(self) -> None:
        for name, site in SITES.items():
            self.assertGreater(site["weight"], 0, name)
            self.assertGreater(site["weight_pickups"], 0, name)

    def test_rooms_fit_their_longer_tables(self) -> None:
        """With every site locked at once, no room grows past what the room slot holds."""
        every = {name: door_constraints.KEYS[0] for name in SITES}
        for room, edit in doors.room_edits(every).items():
            if edit["templates"]:
                end = doors.grown_table_ram(room) - ROOM_OVERLAY_SLOT_RAM
                end += (ROOMS[room]["slot_count"] + len(edit["templates"])) * doors.TEMPLATE_LEN
                self.assertLessEqual(end, nds.OVERLAY_CODE_MAX, room)

    def test_option_range_is_what_the_keys_allow(self) -> None:
        self.assertEqual(door_constraints.MAX_SITES, door_constraints.MAX_PER_KEY * len(door_constraints.KEYS))
        self.assertEqual(DoorConstraintsMin.range_end, door_constraints.MAX_SITES)
        self.assertEqual(DoorConstraintsMax.range_end, door_constraints.MAX_SITES)
        self.assertLessEqual(door_constraints.MAX_SITES, len(SITES))
        self.assertEqual(set(door_constraints.KEYS), set(doors.KEY_TYPES))


class TestDraw(unittest.TestCase):
    def test_count_and_key_cap(self) -> None:
        for count in (1, 7, door_constraints.MAX_SITES):
            for seed in range(20):
                chosen = door_constraints.draw(random.Random(seed), count, pickups=bool(seed % 2))
                self.assertEqual(len(chosen), count)
                self.assertLessEqual(max(Counter(chosen.values()).values()), door_constraints.MAX_PER_KEY)

    def test_same_seed_same_doors(self) -> None:
        a = door_constraints.draw(random.Random(7), 9, pickups=False)
        b = door_constraints.draw(random.Random(7), 9, pickups=False)
        self.assertEqual(a, b)
        self.assertNotEqual(a, door_constraints.draw(random.Random(8), 9, pickups=False))

    def test_both_faces_take_the_key(self) -> None:
        chosen = door_constraints.draw(random.Random(1), 5, pickups=False)
        keys = door_constraints.door_keys(chosen)
        self.assertEqual(len(keys), 10)
        for name, key in chosen.items():
            self.assertEqual({keys[d] for d in SITES[name]["doors"]}, {key})


class TestTemplates(unittest.TestCase):
    def test_locked_template(self) -> None:
        for key, kind in doors.KEY_TYPES.items():
            for role in (0x00, 0x01, 0x81):
                template = bytes([1, DOOR_KIND, 0x13, role, 6, 0, 0xFF, 0xFF, 0xFF, 0, 0, 0])
                out = doors.locked_template(template, key)
                self.assertEqual(out[doors.TEMPLATE_ROLE], (role & doors.ROLE_WALKED) | kind << 4)
                self.assertEqual(out[doors.TEMPLATE_ROLE] & ROLE_NO_DOOR, 0)
                self.assertEqual(out[doors.TEMPLATE_MODIFIER], kind)
                self.assertEqual(out[:3] + out[5:], template[:3] + template[5:])

    def test_shared_templates_get_a_copy(self) -> None:
        every = {name: door_constraints.KEYS[1] for name in SITES}
        edits = doors.room_edits(every)
        shared = sum(1 for site in SITES.values() for face in site["faces"] if face["shared"])
        self.assertEqual(sum(len(e["templates"]) for e in edits.values()), shared)
        self.assertEqual(sum(len(e["writes"]) for e in edits.values()), 2 * len(SITES) - shared)
        for room, edit in edits.items():
            indexes = [new for _addr, _old, new in edit["moves"]]
            first = ROOMS[room]["slot_count"]
            self.assertEqual(indexes, list(range(first, first + len(indexes))), room)

    def test_locks_file_round_trip(self) -> None:
        chosen = door_constraints.draw(random.Random(3), 6, pickups=False)
        self.assertEqual(doors.read_locks(doors.pack_locks(chosen)), chosen)
        self.assertEqual(doors.read_locks(None), {})
        with self.assertRaises(ValueError):
            doors.read_locks(b'{"Nowhere / Else": "Red Card Key"}')
        with self.assertRaises(ValueError):
            doors.read_locks(doors.pack_locks({next(iter(SITES)): "White Card Key"}))

    def test_closed_sprite_only_for_doors_opened_with_up(self) -> None:
        walked = [n for n, s in SITES.items()
                  if all(bytes.fromhex(f["template"])[doors.TEMPLATE_ROLE] & doors.ROLE_WALKED for f in s["faces"])]
        other = [n for n in SITES if n not in walked]
        self.assertTrue(walked and other)
        self.assertFalse(doors.has_up_door({walked[0]: door_constraints.KEYS[0]}))
        self.assertTrue(doors.has_up_door({other[0]: door_constraints.KEYS[0]}))

    def test_closed_sprite_section(self) -> None:
        self.assertEqual(len(doors.DOOR_CAVES) % 4, 0)
        self.assertLessEqual(doors.DOOR_CLOSED_CAVE_RAM + len(doors.DOOR_CAVES), ROOM_OVERLAY_SLOT_RAM)
        self.assertEqual(arm9.thumb_bl(doors.DOOR_CLOSED_HOOK_RAM, RELEASE_PALETTE_RAM), doors.DOOR_CLOSED_HOOK_ORIG)


class TestDoorConstraintsOff(MMZXTestBase):
    def test_nothing_is_locked(self) -> None:
        world = self.multiworld.worlds[1]
        self.assertEqual(world.door_sites, {})
        self.assertEqual(world.door_keys, {})
        self.assertEqual(world.fill_slot_data()[door_constraints.SLOT_DATA_KEY], {})


class TestDoorConstraints(MMZXTestBase):
    options = {"door_constraints_min": LOCKED, "door_constraints_max": LOCKED}

    def test_the_seed_locks_its_sites(self) -> None:
        world = self.multiworld.worlds[1]
        self.assertTrue(1 <= len(world.door_sites) <= LOCKED)
        self.assertEqual(world.door_keys, door_constraints.door_keys(world.door_sites))
        self.assertLessEqual(max(Counter(world.door_sites.values()).values()), door_constraints.MAX_PER_KEY)
        self.assertEqual(world.fill_slot_data()[door_constraints.SLOT_DATA_KEY], world.door_sites)

    def test_a_locked_door_needs_its_key(self) -> None:
        world = self.multiworld.worlds[1]
        for door, key in world.door_keys.items():
            with self.subTest(door=door):
                entrance = self.multiworld.get_entrance(door, 1)
                state = CollectionState(self.multiworld)
                for item in self.multiworld.itempool:
                    if item.name != key:
                        state.collect(item, prevent_sweep=True)
                self.assertFalse(entrance.access_rule(state))
                state.collect(world.create_item(key), prevent_sweep=True)
                self.assertTrue(entrance.access_rule(state))

    def test_a_new_game_keeps_something_to_do(self) -> None:
        world = self.multiworld.worlds[1]
        self.assertGreaterEqual(door_constraints.sphere_zero(world), door_constraints.MIN_SPHERE_ZERO)

    def test_tracker_regeneration_sees_the_same_doors(self) -> None:
        world = self.multiworld.worlds[1]
        slot_data = world.fill_slot_data()
        again = setup_multiworld(MMZXWorld, steps=(), seed=12345)
        again.re_gen_passthrough = {MMZXWorld.game: MMZXWorld.interpret_slot_data(slot_data)}
        for step in ("generate_early", "create_regions"):
            call_all(again, step)
        self.assertEqual(again.worlds[1].door_sites, world.door_sites)
        self.assertEqual(again.worlds[1].door_keys, world.door_keys)


class TestDoorConstraintsRange(MMZXTestBase):
    options = {"door_constraints_min": 12, "door_constraints_max": 3, "starting_transerver": "guardian_base",
               "pickup_checks_energy": True}

    def test_a_maximum_below_the_minimum_counts_as_the_minimum(self) -> None:
        world = self.multiworld.worlds[1]
        self.assertTrue(1 <= len(world.door_sites) <= 12)
        self.assertGreater(len(world.door_sites), 3)


@unittest.skipUnless(os.path.isfile(ROM_PATH), "set MMZX_ROM to the vanilla Mega Man ZX (USA) ROM")
class TestDoorsOfTheRom(unittest.TestCase):
    """The catalogue describes the real ROM, and a patched ROM carries the locked doors."""

    @classmethod
    def setUpClass(cls) -> None:
        with open(ROM_PATH, "rb") as f:
            cls.rom = f.read()
        arm9_off, _entry, arm9_ram, arm9_len = struct.unpack_from("<4I", cls.rom, nds.NDS_HDR_ARM9)
        cls.code = arm9.Arm9(cls.rom[arm9_off:arm9_off + arm9_len], arm9_ram)

    def test_rooms_and_faces_match_the_rom(self) -> None:
        rom = bytearray(self.rom)
        for room, info in ROOMS.items():
            with self.subTest(room=room):
                ram, code = nds.overlay_code(rom, info["overlay"])
                self.assertEqual((ram, len(code)), (ROOM_OVERLAY_SLOT_RAM, info["size"]))
                self.assertEqual(nds.overlay_bss_size(rom, info["overlay"]), info["bss"])
                self.assertEqual(self.code.read(info["slots_pointer"], 4), struct.pack("<I", info["slots"]))
        for name, site in SITES.items():
            for face in site["faces"]:
                with self.subTest(site=name, room=face["room"]):
                    info = ROOMS[face["room"]]
                    ram, code = nds.overlay_code(rom, info["overlay"])
                    template = info["slots"] - ram + face["slot"] * doors.TEMPLATE_LEN
                    self.assertEqual(code[template:template + doors.TEMPLATE_LEN].hex(), face["template"])
                    slot = face["coord"] + doors.COORD_SLOT_OFF - ram
                    self.assertEqual(struct.unpack_from("<H", code, slot)[0], face["slot"])

    def test_hook_sites(self) -> None:
        self.assertEqual(self.code.read(doors.DOOR_CLOSED_HOOK_RAM, 4), doors.DOOR_CLOSED_HOOK_ORIG)
        self.assertEqual(self.code.read(doors.DOOR_OPENING_HOOK_RAM, 4), doors.DOOR_OPENING_HOOK_ORIG)

    def test_no_locks_no_edits(self) -> None:
        rom = bytearray(self.rom)
        code = arm9.Arm9(self.rom[self.code_off():self.code_off() + self.code_len()], self.code.ram)
        doors.patch_door_tables(code, {})
        doors.patch_door_overlays(rom, {})
        self.assertEqual(bytes(rom), self.rom)
        self.assertEqual([(ram, bytes(buf)) for ram, buf in code.sections],
                         [(ram, bytes(buf)) for ram, buf in self.code.sections])

    def test_patched_rom_carries_the_locks(self) -> None:
        locks = door_constraints.draw(random.Random(5), 8, pickups=False)
        rom = bytearray(self.rom)
        code = arm9.Arm9(self.rom[self.code_off():self.code_off() + self.code_len()], self.code.ram)
        doors.patch_door_tables(code, locks)
        doors.patch_door_overlays(rom, locks)
        for name, key in locks.items():
            for face in SITES[name]["faces"]:
                with self.subTest(site=name, room=face["room"]):
                    info = ROOMS[face["room"]]
                    ram, overlay = nds.overlay_code(rom, info["overlay"])
                    table = struct.unpack("<I", code.read(info["slots_pointer"], 4))[0] - ram
                    slot = struct.unpack_from("<H", overlay, face["coord"] + doors.COORD_SLOT_OFF - ram)[0]
                    got = overlay[table + slot * doors.TEMPLATE_LEN:table + (slot + 1) * doors.TEMPLATE_LEN]
                    self.assertEqual(got, doors.locked_template(bytes.fromhex(face["template"]), key))
                    if face["shared"]:
                        # the entities that shared the template still find it untouched
                        old = overlay[table + face["slot"] * doors.TEMPLATE_LEN:
                                      table + (face["slot"] + 1) * doors.TEMPLATE_LEN]
                        self.assertEqual(old.hex(), face["template"])
                        self.assertEqual(nds.overlay_bss_size(rom, info["overlay"]), 0)
                    self.assertLessEqual(len(overlay), nds.OVERLAY_CODE_MAX)

    def code_off(self) -> int:
        return struct.unpack_from("<I", self.rom, nds.NDS_HDR_ARM9)[0]

    def code_len(self) -> int:
        return struct.unpack_from("<I", self.rom, nds.NDS_HDR_ARM9_SIZE)[0]
