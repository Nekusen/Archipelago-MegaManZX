@ Go to Transerver from the pause menu.
@ Cave A replaces the pad read of the MISSION tab scroll handler: it returns the
@ held buttons and, when Y was just pressed, raises "warp requested" (client)
@ and "close menu" (cave B). Cave B replaces the menu-closing call: with the
@ close flag set it clears it and answers "close"; otherwise it tail-calls the
@ original. Caves at 0x020CB99C / 0x020CB438 (rom/ui.py MENU_WARP_CAVE_A / _B),
@ flags at 0x020CB9D0 (MENU_WARP_FLAGS_RAM), hooks in MENU_WARP_HOOKS.

        .thumb

.equ PAD_STATE,             0x020F2768  @ u16 held buttons; +2 u16 previous frame (bit 11 = Y)
.equ MENU_WARP_FLAGS,       0x020CB9D0  @ +0 u8 warp requested (client clears), +1 u8 close menu (cave B clears)
.equ pause_menu_close_check, 0x02022B0C @ FUN_02022b0c(menu): 1 = close the menu (START, or B at page level 0)
.equ menu_warp_cave_a,      0x020CB99C
.equ menu_warp_cave_b,      0x020CB438

        .org    0x020272B6
@ rom: MENU_WARP_HOOKS[0][2]
@ MISSION tab scroll handler FUN_020272ac.
@ was: ldr r1, =PAD_STATE; ldrh r1, [r1]
        bl      menu_warp_cave_a

        .org    0x02023240
@ rom: MENU_WARP_HOOKS[1][2]
@ Pause menu tick FUN_0202323c.
@ was: bl pause_menu_close_check
        bl      menu_warp_cave_b

        .org    0x020CB99C
@ rom: MENU_WARP_CAVE_A
        ldr     r2, lit_pad
        ldrh    r1, [r2]                @ held buttons: the displaced read (r1)
        ldrh    r3, [r2, #2]            @ previous frame
        mvns    r3, r3
        ands    r3, r1                  @ newly pressed
        lsls    r3, r3, #20             @ bit 11 (Y) into the sign
        bpl     a_ret
        ldr     r2, lit_flags_a
        movs    r3, #1
        strb    r3, [r2]                @ warp requested
        strb    r3, [r2, #1]            @ close the menu
a_ret:  bx      lr
lit_pad:        .word PAD_STATE
lit_flags_a:    .word MENU_WARP_FLAGS

        .org    0x020CB438
@ rom: MENU_WARP_CAVE_B
        ldr     r1, lit_flags_b
        ldrb    r2, [r1, #1]            @ close flag
        cmp     r2, #0
        beq     b_orig
        movs    r2, #0
        strb    r2, [r1, #1]            @ consume it
        movs    r0, #1                  @ answer "close", like START
        bx      lr
b_orig: ldr     r3, lit_close_fn
        bx      r3                      @ tail-call the original check
lit_flags_b:    .word MENU_WARP_FLAGS
lit_close_fn:   .word pause_menu_close_check + 1
