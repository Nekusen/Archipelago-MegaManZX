"""Infinite lives: a death never costs a life and never ends in a Game Over."""
from .arm9 import Arm9

# The death state first turns to Game Over when no life is left, then takes one
GAMEOVER_BRANCH_RAM = 0x02021610
GAMEOVER_BRANCH_ORIG = bytes.fromhex("05d1")      # bne respawn
GAMEOVER_BRANCH_NEW = bytes.fromhex("05e0")       # b respawn
LIVES_DECREMENT_RAM = 0x02021620
LIVES_DECREMENT_ORIG = bytes.fromhex("23f04afc")  # bl take a life
LIVES_DECREMENT_NEW = bytes.fromhex("c046c046")   # nop; nop


def patch_infinite_lives(arm9: Arm9) -> None:
    """Respawn after every death with the lives count untouched."""
    arm9.write(GAMEOVER_BRANCH_RAM, GAMEOVER_BRANCH_NEW, GAMEOVER_BRANCH_ORIG)
    arm9.write(LIVES_DECREMENT_RAM, LIVES_DECREMENT_NEW, LIVES_DECREMENT_ORIG)
