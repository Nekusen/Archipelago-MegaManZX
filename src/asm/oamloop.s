@ OAM drawer guards (rom_patches.md "OAM drawer guards").
@ Two sprite drawers leave their loop only through `subs r5, #1; beq exit`; with
@ a count of zero the counter wraps and the loop sprays RAM. `bls` also leaves
@ when the subtraction borrowed, so a zero count exits after one bounded pass.
@ Two one-instruction patches (rom.py OAM_LOOP_A_BR_NEW, OAM_LOOP_B_BR_NEW); no cave.

        .thumb

        .org    0x02009C30
@ rom.py: OAM_LOOP_A_BR_NEW
@ was: beq 0x02009C36   (OAM_LOOP_A_BR_ORIG)
        bls     0x02009C36              @ first drawer: exit of the sprite loop

        .org    0x02009D7C
@ rom.py: OAM_LOOP_B_BR_NEW
@ was: beq 0x02009D82   (OAM_LOOP_B_BR_ORIG)
        bls     0x02009D82              @ second drawer (FUN_02009c5c): same loop, same fix
