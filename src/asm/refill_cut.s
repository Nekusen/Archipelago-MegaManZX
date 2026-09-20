@ Refill cut guard.
@ A weapon hit breaks a large refill into small pieces (the refill think's
@ cut block: break sound, one drop per piece, release). A refill standing for
@ a pending location would vanish without its check, so the block's first
@ call goes through the cave: for a pending location the hit is forgotten
@ and the think continues on its no-hit path; otherwise the sound plays and
@ the vanilla cut follows.
@ Cave at 0x020CB4D0 (rom/pickups.py REFILL_CUT_CAVE), hook at 0x020A3236.

        .thumb

.equ pickup_gate,           0x02191B30  @ pickup_table.s gate(ent) -> 1 if pending (PICKUP_TABLE_ADDR + PICKUP_TABLE_ENTRIES["gate"])
.equ play_sfx,              0x020058DC  @ FUN_020058dc(id)
.equ refill_no_hit,         0x020A3336  @ FUN_020a309c: the path taken when the refill was not hit
.equ SFX_BREAK,             0x21
.equ refill_cut_cave,       0x020CB4D0

        .org    0x020A3236
@ rom: thumb_bl(REFILL_CUT_HOOK_RAM, REFILL_CUT_CAVE_RAM)
@ Refill think FUN_020a309c, first instruction of the cut block after `movs r0, #0x21`; r5 = entity.
@ was: bl play_sfx
        bl      refill_cut_cave

        .org    0x020CB4D0
@ rom: REFILL_CUT_CAVE
cut:                                    @ replaces `bl play_sfx` (r5 = entity)
        push    {lr}
        movs    r0, r5
        ldr     r1, lit_gate
        blx     r1                      @ gate(ent): 1 while the location is pending
        cmp     r0, #0
        bne     pending
        movs    r0, #SFX_BREAK
        ldr     r1, lit_sfx
        blx     r1                      @ the displaced call: vanilla cut follows
        pop     {pc}
pending:
        movs    r0, #0
        movs    r1, #0x94
        str     r0, [r5, r1]            @ forget the hit, as the block does before releasing
        movs    r1, #0x98
        str     r0, [r5, r1]
        movs    r1, #0x9c
        strb    r0, [r5, r1]
        pop     {r0}                    @ drop the return address
        ldr     r0, lit_no_hit
        bx      r0                      @ continue as if nothing had touched the refill
lit_gate:       .word pickup_gate + 1
lit_sfx:        .word play_sfx + 1
lit_no_hit:     .word refill_no_hit + 1
