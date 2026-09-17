@ AP icon set.
@ Set 261 (the AP icons) is made resident like the item atlas, set 58: the
@ resident list gains a fourth entry, its two length constants become four and
@ the boot cave replaces the VRAM upload of set 58 with that upload, the static
@ registration of set 261 without a palette of its own and its upload; it exits
@ through palshare.s. Patches in rom/sprites.py ICON_RESIDENT_LIST_PATCH, hook at
@ 0x0200BDA8 (ICON_BOOT_HOOK_RAM), cave at 0x020C8150 (ICON_BOOT_CAVE).

        .thumb

.equ AP_SET,                261         @ the AP icon set (data.py ICON_SET)
.equ ITEM_SET,              58          @ the item atlas, resident in vanilla
.equ GFX_MGR,               0x02105740  @ object graphics manager
.equ FNT_BLOCK_TABLE,       0x020F3520  @ u32[set]: obj_fnt block of the set in RAM
.equ gfx_upload_set,        0x02006164  @ FUN_02006164(mgr, set, 0, 0, 0, 0, 1, 0): tiles to VRAM
.equ gfx_register_static,   0x02006A88  @ FUN_02006a88(mgr, fnt_block, set, 3, alloc_vram, alloc_pal)
.equ palshare_cave,         0x020C8288  @ shares the palette slot and runs this cave's epilogue
.equ icon_boot_cave,        0x020C8150

        .org    0x020C9C36
@ rom: ICON_RESIDENT_LIST_PATCH[0][2]
@ Data, not code: the u16 after the resident list [0, 1, 58] (FUN_0200bd04).
@ was: .hword 0   (alignment padding)
        .hword  AP_SET                  @ fourth resident set

        .org    0x0200BD16
@ rom: ICON_RESIDENT_LIST_PATCH[1][2]
@ was: movs r2, #3
        movs    r2, #4                  @ resident list length (obj_fnt)

        .org    0x0200BDB6
@ rom: ICON_RESIDENT_LIST_PATCH[2][2]
@ was: movs r2, #3
        movs    r2, #4                  @ resident list length (obj_dat)

        .org    0x0200BDA8
@ rom: thumb_bl(ICON_BOOT_HOOK_RAM, ICON_BOOT_CAVE_RAM)
@ Global set loader FUN_0200bd04.
@ was: bl gfx_upload_set   (ICON_BOOT_HOOK_ORIG: the upload of set 58)
        bl      icon_boot_cave

        .org    0x020C8150
@ rom: ICON_BOOT_CAVE
        push    {r4, lr}
        sub     sp, #0x10               @ four stack arguments
        movs    r4, #0
        str     r4, [sp]
        str     r4, [sp, #4]
        movs    r4, #1
        str     r4, [sp, #8]
        movs    r4, #0
        str     r4, [sp, #0xc]
        ldr     r0, lit_mgr_1
        movs    r1, #ITEM_SET
        movs    r2, #0
        movs    r3, #0
        ldr     r4, lit_upload_1
        blx     r4                      @ gfx_upload_set(mgr, 58, 0, 0, 0, 0, 1, 0): the displaced call
        movs    r4, #1
        str     r4, [sp]                @ alloc_vram = 1
        mov     r8, r8                  @ was `str r4, [sp, #4]` (alloc_pal = 1): no palette of its own
        ldr     r0, lit_mgr_2
        ldr     r1, lit_fnt_block_261
        ldr     r1, [r1]                @ obj_fnt block of set 261
        ldr     r2, lit_ap_set_1
        movs    r3, #3
        ldr     r4, lit_register
        blx     r4                      @ gfx_register_static(mgr, fnt[261], 261, 3, 1, 0)
        movs    r4, #0
        str     r4, [sp]
        str     r4, [sp, #4]
        movs    r4, #1
        str     r4, [sp, #8]
        movs    r4, #0
        str     r4, [sp, #0xc]
        ldr     r0, lit_mgr_3
        ldr     r1, lit_ap_set_2
        movs    r2, #0
        movs    r3, #0
        ldr     r4, lit_upload_2
        blx     r4                      @ gfx_upload_set(mgr, 261, 0, 0, 0, 0, 1, 0)
        bl      palshare_cave           @ never returns here: it pops this frame
lit_mgr_1:          .word GFX_MGR
lit_upload_1:       .word gfx_upload_set + 1
lit_mgr_2:          .word GFX_MGR
lit_fnt_block_261:  .word FNT_BLOCK_TABLE + AP_SET * 4
lit_ap_set_1:       .word AP_SET
lit_register:       .word gfx_register_static + 1
lit_mgr_3:          .word GFX_MGR
lit_ap_set_2:       .word AP_SET
lit_upload_2:       .word gfx_upload_set + 1
