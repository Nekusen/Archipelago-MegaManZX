@ DATA SELECT biometal icons.
@ The save-slot screen tested raw victory bits for H/F/L/P; the four in-place
@ sequences read the first-half ownership flags instead (the free flags 462, 472,
@ 523 and 544, one past the end of each Secret Disk series: slot +0x38..+0x44).
@ The X/ZX branch calls the cave, which selects the X frame and hides the
@ sprite when the slot does not own Model X.
@ Patches in rom/pickups.py DATASELECT_ICON_PATCH, cave at 0x020CB980 (DATASELECT_CAVE).
@ r4 = icon sprite, r5 = slot block (copy of the progress block, +0 = 0x021045CC).

        .thumb

.equ entity_set_anim,       0x0200FE64  @ FUN_0200fe64(ent, anim)
.equ dataselect_switch_end, 0x020362B2  @ end of the icon switch in the slot drawer
.equ dataselect_cave,       0x020CB980

        .org    0x020361FC
@ rom: DATASELECT_ICON_PATCH[0][2]
@ was: ldrb r1, [r5, #4]; movs r0, #2; ands r1, r0; cmp r1, #0   (Hivolt victory bit)
        ldr     r1, [r5, #0x38]         @ H: flag 462 = 0x02104605 bit 6 = word bit 14
        lsrs    r1, r1, #14
        movs    r0, #1
        ands    r1, r0                  @ sets Z for the original bne

        .org    0x02036218
@ rom: DATASELECT_ICON_PATCH[1][2]
@ was: ldrb r1, [r5, #4]; movs r0, #0x20; ands r1, r0; cmp r1, #0
        ldr     r1, [r5, #0x38]         @ F: flag 472 = 0x02104607 bit 0 = word bit 24
        lsrs    r1, r1, #24
        movs    r0, #1
        ands    r1, r0

        .org    0x02036234
@ rom: DATASELECT_ICON_PATCH[2][2]
@ was: ldrb r1, [r5, #4]; movs r0, #8; ands r1, r0; cmp r1, #0
        ldr     r1, [r5, #0x40]         @ L: flag 523 = 0x0210460D bit 3 = word bit 11
        lsrs    r1, r1, #11
        movs    r0, #1
        ands    r1, r0

        .org    0x02036250
@ rom: DATASELECT_ICON_PATCH[3][2]
@ was: ldrb r1, [r5, #4]; movs r0, #0x80; ands r1, r0; cmp r1, #0
        ldr     r1, [r5, #0x44]         @ P: flag 544 = 0x02104610 bit 0
        movs    r0, #1
        ands    r1, r0
        mov     r8, r8

        .org    0x020361E2
@ rom: DATASELECT_ICON_PATCH[4][2]
@ X/ZX icon, branch taken when ZX is not owned.
@ was: adds r0, r4, #0; movs r1, #2; bl entity_set_anim
        bl      dataselect_cave
        b       dataselect_switch_end
        mov     r8, r8

        .org    0x020CB980
@ rom: DATASELECT_CAVE
        push    {r4, r5, lr}
        adds    r0, r4, #0              @ the displaced call: X frame on the icon sprite
        movs    r1, #2
        bl      entity_set_anim
        ldrb    r0, [r5, #3]            @ slot +3 = 0x021045CF: bit 7 = Model X owned
        lsls    r0, r0, #24
        bmi     ret
        ldrb    r1, [r4, #0xa]
        movs    r0, #0xfe
        ands    r1, r0                  @ clear bit 0: sprite hidden
        strb    r1, [r4, #0xa]
ret:    pop     {r4, r5, pc}
