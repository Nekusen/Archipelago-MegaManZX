"""area_m_access: the seal of Area M open, behind the bosses or behind the Passwords."""
import unittest
from collections import Counter

from Options import OptionError
from test.general import setup_multiworld

from .bases import MMZXTestBase, WITNESS
from .test_goal import collect_pool_but
from .. import MMZXWorld
from ..client.goal import GoalRequirement as ClientGoal
from ..client.seal import BOSS_BITS, CLOSED_BITS, GATE_BIT, Seal as ClientSeal
from ..data import ITEMS, SEAL_BOSS_BITS
from ..logic import document as F, load_document
from ..seal import BOSS_EVENTS, PASSWORD_ITEM, defeated_event

TRANSERVER = "Transerver Access - Area M"
PAST_THE_SEAL = ["m01/a-4-entrance", "m01/main-area", "m03/boss-room", "n01/main-area"]
BOSSES = {"area_m_access": "bosses"}
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

    def test_transerver_does_not_get_around_it(self) -> None:
        collect_pool_but(self, [PASSWORD_ITEM])
        self.assertTrue(self.multiworld.state.has(TRANSERVER, self.player))
        self.assertFalse(self.can_reach_location("Mission - Stop The Dig"))

    def test_goal_does_not_need_them(self) -> None:
        collect_pool_but(self, [PASSWORD_ITEM])
        self.assertBeatable(True)

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["area_m_access"],
                         {"mode": "passwords", "passwords": 4, "passwords_total": 6})


class TestBosses(MMZXTestBase):
    options = BOSSES

    def test_no_passwords_in_the_pool(self) -> None:
        self.assertEqual(Counter(item.name for item in self.multiworld.itempool)[PASSWORD_ITEM], 0)

    def test_every_boss_has_its_event(self) -> None:
        events = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is None}
        self.assertLessEqual(set(BOSS_EVENTS), events)

    def test_opens_with_the_whole_pool(self) -> None:
        self.collect(self.multiworld.itempool)
        for region in PAST_THE_SEAL:
            self.assertTrue(self.can_reach_region(region), region)

    def test_one_boss_out_of_reach_keeps_it_closed(self) -> None:
        """Leganchor sits behind the Blue Card Key: without it the seal stays closed."""
        collect_pool_but(self, ["Blue Card Key"])
        self.assertFalse(self.multiworld.state.has(defeated_event("leganchor"), self.player))
        for region in PAST_THE_SEAL:
            self.assertFalse(self.can_reach_region(region), region)
        self.collect_by_name("Blue Card Key")
        for region in PAST_THE_SEAL:
            self.assertTrue(self.can_reach_region(region), region)



class TestBossesWithBossLogic(MMZXTestBase):
    options = {"area_m_access": "bosses", "boss_logic": {"Model Z": WITNESS}}

    def test_giro_counts(self) -> None:
        """A requirement on Giro's fight is a requirement on the seal."""
        collect_pool_but(self, [WITNESS])
        self.assertFalse(self.multiworld.state.has("Cleared: Troop Reinforcement", self.player))
        self.assertFalse(self.can_reach_region("m01/main-area"))
        self.collect_by_name(WITNESS)
        self.assertTrue(self.can_reach_region("m01/main-area"))


class TestDocument(unittest.TestCase):
    def test_every_seal_boss_has_an_arena(self) -> None:
        """`bosses` places one event in the arena of each Pseudoroid."""
        arenas = set(F.boss_regions(load_document()).values())
        self.assertLessEqual(set(SEAL_BOSS_BITS), arenas)
        self.assertEqual(set(SEAL_BOSS_BITS), set(F.PSEUDOROIDS))


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
        self.assertIsNone(seal.progress_part({}))
        self.assertEqual(seal.report({}), [])

    def test_passwords(self) -> None:
        seal = ClientSeal({"area_m_access": {"mode": "passwords", "passwords": 4, "passwords_total": 6}})
        self.assertEqual(seal.closed_bits({PASSWORD_ITEM: 3}), CLOSED_BITS)
        self.assertEqual(seal.progress_part({PASSWORD_ITEM: 3}), "Passwords 3/4")
        self.assertEqual(seal.closed_bits({PASSWORD_ITEM: 4}), frozenset())
        self.assertIn("closed", seal.report({PASSWORD_ITEM: 3})[0])
        self.assertIn("open", seal.report({PASSWORD_ITEM: 5})[0])

    def test_bosses(self) -> None:
        seal = ClientSeal({"area_m_access": {"mode": "bosses"}})
        self.assertEqual(seal.closed_bits({}), CLOSED_BITS)      # nothing read yet: closed
        seal.beaten = set(BOSS_BITS) - {"Giro"}
        self.assertEqual(seal.progress_part({}), "Bosses 8/9")
        self.assertIn("missing: Giro", seal.report({})[0])
        seal.beaten = set(BOSS_BITS)
        self.assertEqual(seal.closed_bits({}), frozenset())

    def test_pause_menu_lines(self) -> None:
        """The seal's part follows the goal requirements and moves to the second line when it does not fit."""
        goal = ClientGoal({"goal_requirements": {"models": ["Model X"], "models_count": 1}})
        self.assertEqual(goal.progress_lines({}, 0, ("Passwords 2/6",)), ("", "Models 0/1  Passwords 2/6"))
        goal = ClientGoal({"goal_requirements": {
            "models": ["Model X"], "models_count": 1, "secret_disks": 20, "secret_disks_total": 30,
            "missions": 14}})
        self.assertEqual(goal.progress_lines({}, 3, ("Passwords 6/6",)),
                         ("Disks 00/20  Models 0/1", "Missions 03/14  Passwords 6/6"))

    def test_closed_bits(self) -> None:
        """The gate flag and the Transport destination of Area M, nothing else."""
        grant = ITEMS[TRANSERVER]["grant"]
        self.assertEqual(CLOSED_BITS, {GATE_BIT, (grant[1], grant[2])})
        self.assertEqual(len(BOSS_BITS), 9)
