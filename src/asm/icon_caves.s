@ Icon caves (rom_patches.md "Icon caves").
@ LOOKUP finds a pickup entity in the spawn list and returns the icon code the
@ client wrote for its coords index, or -1. ATTACH replaces the graphics-attach
@ call of the three pickup inits: with a code it attaches set 261 and clears the
@ entity's "dynamic set" and "foreign palette" bits. ANIM replaces the following
@ animation call: an entity carrying set 261 uses the LOOKUP code.
@ Cave at 0x020C81C4 (rom.py ICON_CAVES; ATTACH at ICON_ATTACH_CAVE_RAM, ANIM at
@ ICON_ANIM_CAVE_RAM), hooks in ICON_ATTACH_HOOKS and ICON_ANIM_HOOKS.

        .thumb

.equ AP_SET,                261         @ the AP icon set (data.py ICON_SET)
.equ ICON_TABLE,            0x02191460  @ client table (data.py ICON_TABLE_ADDR): +0 u8 subarea, +1 u8 flags (bit 0 valid), +4 u8 code[128], +0x84 u8 checked[32]
.equ SUBAREA,               0x02108228  @ u8 current subarea id
.equ SPAWN_LIST_HEAD,       0x021081F4  @ ptr: active spawn records [+0 next, +4 entity, +8 u16 coords index]
.equ entity_attach_set,     0x02010624  @ FUN_02010624(ent, set): stores the set in u16 ent+0x22
.equ entity_set_anim,       0x0200FE64  @ FUN_0200fe64(ent, anim)
.equ icon_attach,           0x020C8212  @ ICON_ATTACH_CAVE_RAM
.equ icon_anim,             0x020C823C  @ ICON_ANIM_CAVE_RAM

        .org    0x020C81C4
@ rom.py: ICON_CAVES
lookup:                                 @ +0x00 lookup(ent) -> r0 = icon code, or -1
        push    {r4, r5, lr}
        ldr     r4, lit_table
        ldrb    r1, [r4]                @ table subarea
        ldr     r2, lit_subarea
        ldrb    r2, [r2]
        cmp     r1, r2
        bne     none                    @ table is for another room
        ldrb    r1, [r4, #1]
        lsls    r1, r1, #31
        beq     none                    @ table not valid
        ldr     r1, lit_spawn_list
        ldr     r1, [r1]
loop:   cmp     r1, #0
        beq     none                    @ entity has no spawn record
        ldr     r2, [r1, #4]
        cmp     r2, r0
        beq     found
        ldr     r1, [r1]
        b       loop
found:  ldrh    r2, [r1, #8]            @ coords index
        cmp     r2, #0x80
        bhs     none
        lsrs    r3, r2, #3
        adds    r3, #0x84
        ldrb    r3, [r4, r3]            @ checked[index >> 3]
        movs    r5, #7
        ands    r5, r2
        lsrs    r3, r5
        lsls    r3, r3, #31
        bne     none                    @ location already sent: vanilla look
        adds    r3, r4, #4
        ldrb    r0, [r3, r2]            @ code[index]
        cmp     r0, #0
        beq     none                    @ 0 = no override
        subs    r0, #1                  @ code - 1 = animation of the AP set
        pop     {r4, r5, pc}
none:   movs    r0, #0
        mvns    r0, r0                  @ -1
        pop     {r4, r5, pc}

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
lit_table:      .word ICON_TABLE
lit_subarea:    .word SUBAREA
lit_spawn_list: .word SPAWN_LIST_HEAD
lit_attach_set: .word AP_SET
lit_attach_fn:  .word entity_attach_set + 1
lit_anim_set:   .word AP_SET
lit_anim_fn:    .word entity_set_anim + 1

        .org    0x020A3BC4
@ rom.py: thumb_bl(ICON_ATTACH_HOOKS[0][0], ICON_ATTACH_CAVE_RAM)
@ Disk init FUN_020a3b6c.  was: bl entity_attach_set
        bl      icon_attach

        .org    0x020A3EEE
@ rom.py: thumb_bl(ICON_ATTACH_HOOKS[1][0], ICON_ATTACH_CAVE_RAM)
@ Life Up / Sub Tank init FUN_020a3dd4.  was: bl entity_attach_set
        bl      icon_attach

        .org    0x020A36F4
@ rom.py: thumb_bl(ICON_ATTACH_HOOKS[2][0], ICON_ATTACH_CAVE_RAM)
@ Refill graphics attach.  was: bl entity_attach_set
        bl      icon_attach

        .org    0x020A3BCC
@ rom.py: thumb_bl(ICON_ANIM_HOOKS[0][0], ICON_ANIM_CAVE_RAM)
@ Disk init.  was: bl entity_set_anim
        bl      icon_anim

        .org    0x020A3EF6
@ rom.py: thumb_bl(ICON_ANIM_HOOKS[1][0], ICON_ANIM_CAVE_RAM)
@ Life Up / Sub Tank init.  was: bl entity_set_anim
        bl      icon_anim

        .org    0x020A3706
@ rom.py: thumb_bl(ICON_ANIM_HOOKS[2][0], ICON_ANIM_CAVE_RAM)
@ Refill graphics attach.  was: bl entity_set_anim
        bl      icon_anim
