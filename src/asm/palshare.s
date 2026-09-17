@ PALSHARE.
@ Set 261 borrows the OBJ palette slot of set 58 instead of taking one of the
@ 15 the registrar hands out. The cave is the tail of icon_boot.s: it copies
@ the slot table entry and then runs the boot cave's epilogue.
@ Cave at 0x020C8288 (rom/sprites.py PALSHARE_CAVE); entered by `bl` from icon_boot.s.

        .thumb

.equ AP_SET,            261             @ the AP icon set (data.py ICON_SET)
.equ ITEM_SET,          58              @ the item atlas
.equ PAL_SLOT_TABLE,    0x02105EE4      @ u8[set]: palette slot of the set

        .org    0x020C8288
@ rom: PALSHARE_CAVE
        ldr     r0, lit_pal_table
        movs    r1, #ITEM_SET
        ldrb    r1, [r0, r1]            @ palette slot of set 58
        ldr     r0, lit_pal_261
        strb    r1, [r0]                @ becomes the slot of set 261
        add     sp, #0x10               @ epilogue of icon_boot_cave
        pop     {r4, pc}
        mov     r8, r8                  @ pad to a word
lit_pal_table:  .word PAL_SLOT_TABLE
lit_pal_261:    .word PAL_SLOT_TABLE + AP_SET
