@ Yellow Card Key dialogue.
@ The Operator's console re-ran the script that announces and grants the key
@ whenever Troop Reinforcement was reported and the key bit was clear. The key
@ is a pool item enforced by the client, so the script is skipped for good.
@ One-instruction patch at 0x02093BE4 (rom.py YELLOWKEY_BR_NEW); no cave.

        .thumb

        .org    0x02093BE4
@ rom.py: YELLOWKEY_BR_NEW
@ was: beq 0x02093C00   (YELLOWKEY_BR_ORIG): skip the grant script only when the key is owned
        b       0x02093C00              @ always skip the grant script
