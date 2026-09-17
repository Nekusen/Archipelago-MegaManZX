@ Icons for a carried disk.
@ The balloon of H-1 creates Disk E-47 when it spawns and holds it: a kind 3
@ entity whose +0x30 points at the carrier. The disk has no spawn record of
@ its own, so these three routines, the counterparts of ATTACH, ANIM and
@ RETRY, run LOOKUP on the carrier and dress the disk with the result.
@ Cave at 0x020C82E8 (rom/sprites.py ICON_CARRIED_CAVE; ANIM at ICON_CARRIED_ANIM_CAVE_RAM,
@ RETRY at ICON_CARRIED_RETRY_CAVE_RAM), hooks in ICON_CARRIED_HOOKS.

        .thumb

.equ AP_SET,                261         @ the AP icon set (data.py ICON_SET)
.equ icon_lookup,           0x020C81C4  @ icon_caves.s lookup(ent) -> code or -1
.equ entity_attach_set,     0x02010624  @ FUN_02010624(ent, set)
.equ entity_set_anim,       0x0200FE64  @ FUN_0200fe64(ent, anim)
.equ entity_anim_tick,      0x0200FC0C  @ FUN_0200fc0c(ent): per-frame animation advance
.equ icon_carried_attach,   0x020C82E8  @ ICON_CARRIED_CAVE_RAM
.equ icon_carried_anim,     0x020C8308  @ ICON_CARRIED_ANIM_CAVE_RAM
.equ icon_carried_retry,    0x020C832C  @ ICON_CARRIED_RETRY_CAVE_RAM

        .org    0x020C82E8
@ rom: ICON_CARRIED_CAVE
attach:                                 @ +0x00 attach(disk, set): replaces `bl entity_attach_set`
        push    {r4, r5, lr}
        movs    r4, r0
        movs    r5, r1
        ldr     r0, [r4, #0x30]         @ carrier
        bl      icon_lookup
        cmp     r0, #0
        blt     attach_call             @ no code: vanilla set
        bl      adopt
        ldr     r5, lit_set
attach_call:
        movs    r0, r4
        movs    r1, r5
        bl      entity_attach_set
        pop     {r4, r5, pc}

anim:                                   @ +0x20 anim(disk, anim): replaces `bl entity_set_anim`
        push    {r4, r5, lr}
        movs    r4, r0
        movs    r5, r1
        ldrh    r2, [r4, #0x22]         @ attached set
        ldr     r3, lit_set
        cmp     r2, r3
        bne     anim_call               @ not the AP set: vanilla animation
        ldr     r0, [r4, #0x30]
        bl      icon_lookup
        cmp     r0, #0
        blt     anim_call
        movs    r5, r0                  @ the code is the animation
anim_call:
        movs    r0, r4
        movs    r1, r5
        bl      entity_set_anim
        pop     {r4, r5, pc}

retry:                                  @ +0x44 retry(disk): replaces `bl entity_anim_tick`
        push    {r4, r5, lr}
        movs    r4, r0
        ldrh    r2, [r4, #0x22]
        ldr     r3, lit_set
        cmp     r2, r3
        beq     tick                    @ already the AP set
        ldr     r0, [r4, #0x30]
        bl      icon_lookup
        cmp     r0, #0
        blt     tick                    @ still no code
        movs    r5, r0
        bl      adopt
        movs    r0, r4
        ldr     r1, lit_set
        bl      entity_attach_set
        movs    r0, r4
        movs    r1, r5
        bl      entity_set_anim
tick:   movs    r0, r4
        bl      entity_anim_tick        @ the displaced call, always
        pop     {r4, r5, pc}

adopt:                                  @ r4 = disk: drop the flags of a dynamic set
        ldrb    r1, [r4, #0xb]
        movs    r2, #8
        bics    r1, r2                  @ ent+0xB bit 3: dynamic set
        strb    r1, [r4, #0xb]
        ldrb    r1, [r4, #0xc]
        movs    r2, #1
        bics    r1, r2                  @ ent+0xC bit 0: palette of another set
        strb    r1, [r4, #0xc]
        bx      lr
        nop                             @ pad to a word
lit_set:        .word AP_SET

        .org    0x020A40C6
@ rom: thumb_bl(ICON_CARRIED_HOOKS[0][0], ICON_CARRIED_CAVE_RAM)
@ Carried disk init FUN_020a40c0.  was: bl entity_attach_set
        bl      icon_carried_attach

        .org    0x020A40CE
@ rom: thumb_bl(ICON_CARRIED_HOOKS[1][0], ICON_CARRIED_ANIM_CAVE_RAM)
@ Carried disk init.  was: bl entity_set_anim
        bl      icon_carried_anim

        .org    0x020A3FF8
@ rom: thumb_bl(ICON_CARRIED_HOOKS[2][0], ICON_CARRIED_RETRY_CAVE_RAM)
@ Carried disk think FUN_020a3ff4.  was: bl entity_anim_tick
        bl      icon_carried_retry
