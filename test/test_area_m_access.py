"""area_m_access: the seal of Area M open, behind the biometal checks or behind the Passwords."""
import unittest
from collections import Counter

from Options import OptionError
from test.general import setup_multiworld

from .bases import MMZXTestBase, WITNESS, window_with
from .test_goal import collect_pool_but
from .. import MMZXWorld
from ..client.seal import BIOMETAL_CHECKS, CLOSED_BITS, GATE_BIT, Seal as ClientSeal
from ..data import ITEMS, LOCATIONS
from ..seal import BIOMETAL_EVENTS, BIOMETAL_LOCATIONS, PASSWORD_ITEM

TRANSERVER = "Transerver Access - Area M"
BIOMETAL_Z = "Obtain Biometal Z"
PAST_THE_SEAL = ["m01/a-4-entrance", "m01/main-area", "m03/boss-room", "n01/main-area"]
BIOMETALS = {"area_m_access": "biometals"}
PASSWORDS = {"area_m_access": "passwords", "required_passwords": 4, "total_passwords": 6}


class TestOpen(MMZXTestBase):
    def test_no_passwords_in_the_pool(self) -> None:
        self.assertEqual(Counter(item.name for item in self.multiworld.itempool)[PASSWORD_ITEM], 0)

    def test_transerver_gets_around_the_door(self) -> None:
        """With the seal open the Transerver of Area M is a way in of its own."""
        self.collect_by_name([TRANSERVER, "Progressive Model LX", "Progressive Model HX"])
        self.assertTrue(self.can_reach_region("m03/boss-room"))

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["area_m_access"]["mode"], "open")


class TestBiometalZ(MMZXTestBase):
    options = {"boss_logic": {"Model Z": WITNESS}}

    def test_five_biometal_locations(self) -> None:
        self.assertEqual(sorted(BIOMETAL_LOCATIONS), sorted("Obtain Biometal " + b for b in "FHLPZ"))
        self.assertEqual(len({LOCATIONS[n]["id"] for n in BIOMETAL_LOCATIONS}), 5)

    def test_sits_in_the_arena_of_giro(self) -> None:
        """The check is beating Giro, so a requirement on his fight is a requirement on it."""
        self.assertEqual(self.multiworld.get_location(BIOMETAL_Z, self.player).parent_region.name,
                         "d02/boss-room")
        collect_pool_but(self, [WITNESS])
        self.assertFalse(self.can_reach_location(BIOMETAL_Z))
        self.collect_by_name(WITNESS)
        self.assertTrue(self.can_reach_location(BIOMETAL_Z))


class TestPasswords(MMZXTestBase):
    options = PASSWORDS

    def test_pool(self) -> None:
        passwords = self.get_items_by_name(PASSWORD_ITEM)
        self.assertEqual(len(passwords), 6)
        self.assertTrue(all(item.advancement for item in passwords))

    def test_required_count(self) -> None:
        """Three Passwords leave every room past the seal closed; the fourth opens them."""
        collect_pool_but(self, [PASSWORD_ITEM])
        passwords = self.get_items_by_name(PASSWORD_ITEM)
        self.collect(passwords[:3])
        for region in PAST_THE_SEAL:
            self.assertFalse(self.can_reach_region(region), region)
        self.collect(passwords[3])
        for region in PAST_THE_SEAL:
            self.assertTrue(self.can_reach_region(region), region)

    def test_transerver_leaves_the_pool(self) -> None:
        """Nothing gets around the seal, and the pool still fills every location."""
        self.assertEqual(self.get_items_by_name(TRANSERVER), [])
        real = [loc for loc in self.multiworld.get_locations(self.player) if loc.address is not None]
        self.assertEqual(len(self.multiworld.itempool), len(real))
        collect_pool_but(self, [PASSWORD_ITEM])
        self.assertFalse(self.can_reach_location("Mission - Stop The Dig"))

    def test_goal_does_not_need_them(self) -> None:
        collect_pool_but(self, [PASSWORD_ITEM])
        self.assertBeatable(True)

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["area_m_access"],
                         {"mode": "passwords", "passwords": 4, "passwords_total": 6})


class TestBiometals(MMZXTestBase):
    options = BIOMETALS

    def test_no_passwords_nor_transerver_in_the_pool(self) -> None:
        names = Counter(item.name for item in self.multiworld.itempool)
        self.assertEqual((names[PASSWORD_ITEM], names[TRANSERVER]), (0, 0))

    def test_every_biometal_has_its_event(self) -> None:
        events = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is None}
        self.assertLessEqual(set(BIOMETAL_EVENTS), events)

    def test_opens_with_the_whole_pool(self) -> None:
        self.collect(self.multiworld.itempool)
        for region in PAST_THE_SEAL:
            self.assertTrue(self.can_reach_region(region), region)

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["area_m_access"]["mode"], "biometals")


class TestBiometalsOnePseudoroidIsEnough(MMZXTestBase):
    options = {**BIOMETALS, "boss_logic": {"Lurerre": WITNESS}}

    def test_the_other_of_the_pair_gives_the_check(self) -> None:
        """Lurerre out of reach, Biometal L still comes from Leganchor and the seal opens."""
        collect_pool_but(self, [WITNESS])
        for region in PAST_THE_SEAL:
            self.assertTrue(self.can_reach_region(region), region)


class TestBiometalsNeedBothOutOfReach(MMZXTestBase):
    options = {**BIOMETALS, "boss_logic": {"Lurerre": WITNESS, "Leganchor": WITNESS}}

    def test_a_biometal_out_of_reach_keeps_it_closed(self) -> None:
        collect_pool_but(self, [WITNESS])
        for region in PAST_THE_SEAL:
            self.assertFalse(self.can_reach_region(region), region)
        self.collect_by_name(WITNESS)
        for region in PAST_THE_SEAL:
            self.assertTrue(self.can_reach_region(region), region)


class TestBiometalsNeedGiro(MMZXTestBase):
    options = {**BIOMETALS, "boss_logic": {"Model Z": WITNESS}}

    def test_biometal_z_counts(self) -> None:
        collect_pool_but(self, [WITNESS])
        self.assertFalse(self.can_reach_region("m01/main-area"))
        self.collect_by_name(WITNESS)
        self.assertTrue(self.can_reach_region("m01/main-area"))


class TestTranserverHeldAnyway(MMZXTestBase):
    options = PASSWORDS

    def test_warp_waits_for_the_seal(self) -> None:
        """Held all the same (a start inventory), the Transerver Access does not get around a closed seal."""
        collect_pool_but(self, [PASSWORD_ITEM])
        self.collect(self.world.create_item(TRANSERVER))
        for region in PAST_THE_SEAL:
            self.assertFalse(self.can_reach_region(region), region)
        self.collect(self.get_items_by_name(PASSWORD_ITEM))
        for region in PAST_THE_SEAL:
            self.assertTrue(self.can_reach_region(region), region)


class TestClamps(unittest.TestCase):
    def test_total_raised_to_required(self) -> None:
        multiworld = setup_multiworld(MMZXWorld, options={
            "area_m_access": "passwords", "required_passwords": 5, "total_passwords": 2})
        world = multiworld.worlds[1]
        self.assertEqual((world.seal.passwords_required, world.seal.passwords_total), (5, 5))
        self.assertEqual(sum(1 for i in multiworld.itempool if i.name == PASSWORD_ITEM), 5)

    def test_passwords_leave_room_for_the_disks(self) -> None:
        """Both hunts share the free slots: the disks give way, never the Passwords."""
        multiworld = setup_multiworld(MMZXWorld, options={
            "area_m_access": "passwords", "goal_requirements": ["Secret Disks"],
            "required_secret_disks": 50, "total_secret_disks": 95})
        world = multiworld.worlds[1]
        real = sum(1 for loc in multiworld.get_locations(1) if loc.address is not None)
        free = real - len(world.fixed_items()[0])
        self.assertEqual(world.seal.passwords_total, 6)
        self.assertEqual(world.goal.disks_total, free - 6)
        self.assertEqual(len(multiworld.itempool), real)

    def test_no_room_fails(self) -> None:
        with self.assertRaises(OptionError):
            setup_multiworld(MMZXWorld, options={
                "area_m_access": "passwords", "goal_requirements": ["Secret Disks"],
                "required_secret_disks": 95, "total_secret_disks": 95})


class TestClientSeal(unittest.TestCase):
    def test_old_seed_is_open(self) -> None:
        seal = ClientSeal({})
        self.assertFalse(seal.gated)
        self.assertEqual(seal.closed_bits({}), frozenset())
        self.assertEqual(seal.report({}), [])

    def test_passwords(self) -> None:
        seal = ClientSeal({"area_m_access": {"mode": "passwords", "passwords": 4, "passwords_total": 6}})
        self.assertEqual(seal.closed_bits({PASSWORD_ITEM: 3}), CLOSED_BITS)
        self.assertEqual(seal.progress({PASSWORD_ITEM: 3}), (3, 4))
        self.assertEqual(seal.closed_bits({PASSWORD_ITEM: 4}), frozenset())
        self.assertIn("closed", seal.report({PASSWORD_ITEM: 3})[0])
        self.assertIn("open", seal.report({PASSWORD_ITEM: 5})[0])

    def test_biometals_from_the_flags(self) -> None:
        """Either Pseudoroid of a pair gives its biometal; Z comes with the megamerge after Giro."""
        seal = ClientSeal({"area_m_access": {"mode": "biometals"}})
        self.assertEqual(seal.closed_bits({}), CLOSED_BITS)      # nothing read yet: closed
        second_of_each_pair = [(0x021045D1, bit) for bit in (1, 3, 5, 7)]
        seal.read_biometals(window_with(second_of_each_pair), set())
        self.assertEqual(seal.progress({}), (4, 5))
        self.assertIn("missing: Z", seal.report({})[0])
        seal.read_biometals(window_with(second_of_each_pair + [(0x02104602, 1)]), set())
        self.assertEqual(seal.closed_bits({}), frozenset())

    def test_biometals_already_checked(self) -> None:
        """A check the server already has counts, whatever the flags of this save say."""
        seal = ClientSeal({"area_m_access": {"mode": "biometals"}})
        seal.read_biometals(window_with([]), {LOCATIONS[n]["id"] for n in BIOMETAL_LOCATIONS})
        self.assertEqual(seal.progress({}), (5, 5))

    def test_closed_bits(self) -> None:
        """The gate flag and the Transport destination of Area M, nothing else."""
        grant = ITEMS[TRANSERVER]["grant"]
        self.assertEqual(CLOSED_BITS, {GATE_BIT, (grant[1], grant[2])})
        self.assertEqual(sorted(BIOMETAL_CHECKS), list("FHLPZ"))
