@ RETRY.
@ A pickup born during the room load, before the client's table or the item
@ scouts arrive, keeps its vanilla look. The per-frame animation-advance call
@ of the three pickup thinks goes through the cave: if the entity does not
@ carry set 261 yet and LOOKUP now resolves a code, it repeats the init's
@ attach and animation; it always calls the original routine.
@ Cave at 0x020C82A0 (rom/sprites.py ICON_RETRY_CAVE), hooks in ICON_RETRY_HOOKS.

        .thumb

.equ AP_SET,                261         @ the AP icon set (data.py ICON_SET)
.equ icon_lookup,           0x020C81C4  @ icon_caves.s lookup(ent) -> code or -1
.equ entity_attach_set,     0x02010624  @ FUN_02010624(ent, set)
.equ entity_set_anim,       0x0200FE64  @ FUN_0200fe64(ent, anim)
.equ entity_anim_tick,      0x0200FC0C  @ FUN_0200fc0c(ent): per-frame animation advance
.equ icon_retry_cave,       0x020C82A0

        .org    0x020C82A0
@ rom: ICON_RETRY_CAVE
        push    {r4, r5, lr}
        movs    r4, r0
        ldrh    r2, [r4, #0x22]         @ attached set
        ldr     r3, lit_set_1
        cmp     r2, r3
        beq     tick                    @ already the AP set
        bl      icon_lookup
        cmp     r0, #0
        blt     tick                    @ still no code
        movs    r5, r0
        ldrb    r1, [r4, #0xb]
        movs    r2, #8
        bics    r1, r2                  @ ent+0xB bit 3: dynamic set
        strb    r1, [r4, #0xb]
        ldrb    r1, [r4, #0xc]
        movs    r2, #1
        bics    r1, r2                  @ ent+0xC bit 0: palette of another set
        strb    r1, [r4, #0xc]
        movs    r0, r4
        ldr     r1, lit_set_2
        bl      entity_attach_set       @ attach set 261
        movs    r0, r4
        movs    r1, r5
        bl      entity_set_anim         @ animation = the code
tick:   movs    r0, r4
        bl      entity_anim_tick        @ the displaced call, always
        pop     {r4, r5, pc}
        nop                             @ pad to a word
lit_set_1:      .word AP_SET
lit_set_2:      .word AP_SET

        .org    0x020CB4A2
@ rom: thumb_bl(ICON_RETRY_HOOKS[0][0], ICON_RETRY_CAVE_RAM)
@ Inside pickup_mailbox.s: the refill think's own site belongs to the mailbox hook.
@ was: bl entity_anim_tick
        bl      icon_retry_cave

        .org    0x020A3A7E
@ rom: thumb_bl(ICON_RETRY_HOOKS[1][0], ICON_RETRY_CAVE_RAM)
@ Disk think FUN_020a3a6c.  was: bl entity_anim_tick
        bl      icon_retry_cave

        .org    0x020A3CAA
@ rom: thumb_bl(ICON_RETRY_HOOKS[2][0], ICON_RETRY_CAVE_RAM)
@ Life Up / Sub Tank think FUN_020a3c98.  was: bl entity_anim_tick
        bl      icon_retry_cave
