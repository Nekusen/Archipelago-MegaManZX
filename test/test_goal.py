"""The goal: Serpent behind the six biometals, boss_logic and skip_boss_rush."""
from .bases import MMZXTestBase, WITNESS


def collect_pool_but(test, names) -> None:
    """Collect every item of the pool except the named ones (events are swept, never collected)."""
    test.collect([item for item in test.multiworld.itempool if item.name not in names])


class TestGoal(MMZXTestBase):
    def test_nothing_is_not_enough(self) -> None:
        """The starting inventory alone does not beat the game."""
        self.assertBeatable(False)

    def test_everything_wins(self) -> None:
        """The whole pool beats the game."""
        self.collect(self.multiworld.itempool)
        self.assertBeatable(True)

    def test_six_biometals_seal(self) -> None:
        """Serpent needs every biometal: without Model X the goal stays closed."""
        collect_pool_but(self, ["Model X"])
        self.assertBeatable(False)
        self.collect_by_name("Model X")
        self.assertBeatable(True)

    def test_one_half_opens_the_seal(self) -> None:
        """One half of a progressive biometal counts as owning it for the seal."""
        collect_pool_but(self, ["Progressive Model HX"])
        self.assertBeatable(False)
        self.collect(self.get_items_by_name("Progressive Model HX")[0])
        self.assertBeatable(True)


class TestGoalWithBossLogic(MMZXTestBase):
    options = {"boss_logic": {"Serpent": WITNESS}}

    def test_serpent_requirement(self) -> None:
        """A requirement on Serpent closes the goal until it is met."""
        collect_pool_but(self, [WITNESS])
        self.assertBeatable(False)
        self.collect_by_name(WITNESS)
        self.assertBeatable(True)


class TestGoalNeedsTheBossRush(MMZXTestBase):
    options = {"boss_logic": {"Hivolt": WITNESS}}

    def test_pseudoroid_requirement_reaches_the_tower(self) -> None:
        """A Pseudoroid requirement also applies to its rematch, so the goal needs it."""
        collect_pool_but(self, [WITNESS])
        self.assertBeatable(False)
        self.collect_by_name(WITNESS)
        self.assertBeatable(True)


class TestGoalWithSkipBossRush(MMZXTestBase):
    options = {"boss_logic": {"Hivolt": WITNESS}, "skip_boss_rush": True}

    def test_only_the_story_fight_asks(self) -> None:
        """With the rush skipped the goal ignores the Pseudoroid, whose story arena stays closed."""
        collect_pool_but(self, [WITNESS])
        self.assertBeatable(True)
        self.assertFalse(self.can_reach_region("e07/boss-room"))
        self.collect_by_name(WITNESS)
        self.assertTrue(self.can_reach_region("e07/boss-room"))
