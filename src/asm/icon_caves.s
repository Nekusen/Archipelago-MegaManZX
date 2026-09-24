@ Icon caves.
@ LOOKUP returns the icon code of a pickup entity, or -1: the search itself
@ lives in the pickup table section (pickup_table.s), so LOOKUP only jumps
@ there. ATTACH replaces the graphics-attach call of the three pickup inits:
@ with a code it attaches set 261 and clears the entity's "dynamic set" and
@ "foreign palette" bits. ANIM replaces the following animation call: an
@ entity carrying set 261 uses the LOOKUP code.
@ Cave at 0x020C81C4 (rom/sprites.py ICON_CAVES; ATTACH at ICON_ATTACH_CAVE_RAM, ANIM at
@ ICON_ANIM_CAVE_RAM), hooks in ICON_ATTACH_HOOKS and ICON_ANIM_HOOKS.

        .thumb

.equ AP_SET,                261         @ the AP icon set (data.py ICON_SET)
.equ pickup_lookup,         0x02191B00  @ pickup_table.s lookup(ent) -> code or -1 (PICKUP_TABLE_ADDR + PICKUP_TABLE_ENTRIES["lookup"])
.equ entity_attach_set,     0x02010624  @ FUN_02010624(ent, set): stores the set in u16 ent+0x22
.equ entity_set_anim,       0x0200FE64  @ FUN_0200fe64(ent, anim)
.equ icon_attach,           0x020C8212  @ ICON_ATTACH_CAVE_RAM
.equ icon_anim,             0x020C823C  @ ICON_ANIM_CAVE_RAM

        .org    0x020C81C4
@ rom: ICON_CAVES
lookup:                                 @ +0x00 lookup(ent) -> r0 = icon code, or -1
        ldr     r3, lit_lookup
        bx      r3                      @ the pickup table's lookup returns to our caller
lit_lookup:     .word pickup_lookup + 1
        .word   0                       @ the per-room table search that lived here (70 bytes)
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .short  0

attach:                                 @ +0x4E attach(ent, set): replaces `bl entity_attach_set`
        push    {r4, r5, lr}
        movs    r4, r0
        movs    r5, r1
        bl      lookup
        cmp     r0, #0
        blt     attach_call             @ no code: vanilla set
        ldrb    r1, [r4, #0xb]
        movs    r2, #8
        bics    r1, r2                  @ ent+0xB bit 3: dynamic set
        strb    r1, [r4, #0xb]
        ldrb    r1, [r4, #0xc]
        movs    r2, #1
        bics    r1, r2                  @ ent+0xC bit 0: palette of another set
        strb    r1, [r4, #0xc]
        ldr     r5, lit_attach_set
attach_call:
        movs    r0, r4
        movs    r1, r5
        ldr     r2, lit_attach_fn
        blx     r2
        pop     {r4, r5, pc}

anim:                                   @ +0x78 anim(ent, anim): replaces `bl entity_set_anim`
        push    {r4, r5, lr}
        movs    r4, r0
        movs    r5, r1
        ldrh    r2, [r0, #0x22]         @ attached set
        ldr     r3, lit_anim_set
        cmp     r2, r3
        bne     anim_call               @ not the AP set: vanilla animation
        bl      lookup
        cmp     r0, #0
        blt     anim_call
        movs    r5, r0                  @ the code is the animation
anim_call:
        movs    r0, r4
        movs    r1, r5
        ldr     r2, lit_anim_fn
        blx     r2
        pop     {r4, r5, pc}
        nop                             @ pad to a word
        .word   0                       @ the three words of the old lookup's pool
        .word   0
        .word   0
lit_attach_set: .word AP_SET
lit_attach_fn:  .word entity_attach_set + 1
lit_anim_set:   .word AP_SET
lit_anim_fn:    .word entity_set_anim + 1

        .org    0x020A3BC4
@ rom: thumb_bl(ICON_ATTACH_HOOKS[0][0], ICON_ATTACH_CAVE_RAM)
@ Disk init FUN_020a3b6c.  was: bl entity_attach_set
        bl      icon_attach

        .org    0x020A3EEE
@ rom: thumb_bl(ICON_ATTACH_HOOKS[1][0], ICON_ATTACH_CAVE_RAM)
@ Life Up / Sub Tank init FUN_020a3dd4.  was: bl entity_attach_set
        bl      icon_attach

        .org    0x020A36F4
@ rom: thumb_bl(ICON_ATTACH_HOOKS[2][0], ICON_ATTACH_CAVE_RAM)
@ Refill graphics attach.  was: bl entity_attach_set
        bl      icon_attach

        .org    0x020A3BCC
@ rom: thumb_bl(ICON_ANIM_HOOKS[0][0], ICON_ANIM_CAVE_RAM)
@ Disk init.  was: bl entity_set_anim
        bl      icon_anim

        .org    0x020A3EF6
@ rom: thumb_bl(ICON_ANIM_HOOKS[1][0], ICON_ANIM_CAVE_RAM)
@ Life Up / Sub Tank init.  was: bl entity_set_anim
        bl      icon_anim

        .org    0x020A3706
@ rom: thumb_bl(ICON_ANIM_HOOKS[2][0], ICON_ANIM_CAVE_RAM)
@ Refill graphics attach.  was: bl entity_set_anim
        bl      icon_anim
