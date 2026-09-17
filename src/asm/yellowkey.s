@ Yellow Card Key dialogue.
@ The Operator's console re-ran the script that announces and grants the key
@ whenever Troop Reinforcement was reported and the key bit was clear. The key
@ is a pool item enforced by the client, so the script is skipped for good.
@ The console object has two dialogue routines with the same test, picked by
@ the entity's variant byte: the Transerver with Transport (state 2,
@ 0x02093B4C) and the plain computer of the DATA floors and Area C (state 8,
@ 0x020933A4). One-instruction patch in each (rom/pickups.py YELLOWKEY_PATCH);
@ no cave.

        .thumb

        .org    0x02093BE4
@ rom: YELLOWKEY_PATCH[0][2]
@ was: beq 0x02093C00   (YELLOWKEY_PATCH[0][1]): skip the grant script only when Troop is not reported
        b       0x02093C00              @ always skip the grant script

        .org    0x02093462
@ rom: YELLOWKEY_PATCH[1][2]
@ was: beq 0x02093480   (YELLOWKEY_PATCH[1][1]): same test in the computer console's dialogue
        b       0x02093480              @ always skip the grant script
