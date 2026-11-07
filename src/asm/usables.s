@ ITEM A usables as locations.
@ The pause menu's category 0 lists eight flags of the progress block that the
@ game sets when it hands the object over (a townsperson, a Guardian, the tree of
@ A-3, the crane of H-3, the hanging doll of X-2) and clears when the player uses
@ it. Those flags are the locations now, so the menu list is pointed at the
@ possession byte of the pickup table section (rom/table.py USABLES_OFF), which
@ only the items received fill. The cake needs no birthday, and the two Guardians
@ who sell usables stay in the base while Protect HQ is under way. The missions
@ that the game asks for stay required: the child who gives the cake moves to
@ town once Save The People is reported (flag 199), and the salts are on sale
@ once Troop Reinforcement is reported (flag 169); the game only ever sets those
@ two flags, so neither source goes away afterwards.
@ The "You got X" popup of a hand-over would name an object the player does not
@ get, and the client's notice already says what was sent, so the popup routine
@ returns at once for the eight messages of the usables (USABLE_POPUP_CAVE); every
@ other popup goes through its displaced prologue and on.

        .thumb

.equ progress_block,        0x021045CC
.equ usables_byte,          0x02191C44  @ PICKUP_TABLE_ADDR + USABLES_OFF
.equ usable_flag_base,      (usables_byte - progress_block) * 8
.equ show_pickup_msg,       0x020122D4  @ (message id, frames): opens the small popup with a message
.equ show_pickup_msg_body,  0x020122DC  @ its first instruction after the prologue the hook displaces
.equ popup_object,          0x027E02CC  @ the popup the routine fills, its literal at 0x02012348
.equ first_usable_popup,    0x448       @ "You got Cake!", then the other seven in menu order
.equ usable_popup_cave,     0x020CB910  @ USABLE_POPUP_CAVE_RAM

        .org    0x020D96DC
@ rom: USABLE_TABLE_NEW
@ was: the flags 651, 646, 647, 648, 649, 644, 645, 650 (USABLE_TABLE_ORIG): Cake, Orange,
@ Candy, Bread, Apple, E Tank, W Tank, Smelling Salts; bit = flag - 644
        .word   usable_flag_base + 7
        .word   usable_flag_base + 2
        .word   usable_flag_base + 3
        .word   usable_flag_base + 4
        .word   usable_flag_base + 5
        .word   usable_flag_base + 0
        .word   usable_flag_base + 1
        .word   usable_flag_base + 6

        .org    0x0209C5F2
@ rom: CAKE_BIRTHDAY_PATCH[0][2]
@ was: beq 0x0209C606   (CAKE_BIRTHDAY_PATCH[0][1]): no cake unless today is the console owner's birthday
        mov     r8, r8                  @ the cake dialogue whenever the flag is clear

        .org    0x020122D4
@ rom: USABLE_POPUP_ENTRY_NEW
@ was: push {r4, r5, r6, lr}; adds r5, r0, #0; adds r6, r1, #0; ldr r4, [pc, #0x6c]   (USABLE_POPUP_ENTRY_ORIG): the prologue of show_pickup_msg
        ldr     r3, lit_popup_cave
        bx      r3
lit_popup_cave: .word usable_popup_cave + 1

        .org    0x020CB910
@ rom: USABLE_POPUP_CAVE
usable_popup:                           @ r0 = message id, r1 = frames, as show_pickup_msg takes them
        ldr     r3, lit_first_popup
        subs    r3, r0, r3
        cmp     r3, #8
        blo     usable_popup_quiet      @ one of the eight usables: no popup
        push    {r4, r5, r6, lr}        @ the prologue the hook displaced
        adds    r5, r0, #0
        adds    r6, r1, #0
        ldr     r4, lit_popup_object
        ldr     r3, lit_popup_body
        bx      r3
usable_popup_quiet:
        bx      lr
        .align  2
lit_first_popup:  .word first_usable_popup
lit_popup_object: .word popup_object
lit_popup_body:   .word show_pickup_msg_body + 1

        .org    0x0209C40C
@ rom: GUARDIAN_KEEP_PATCH[0][2]
@ Guardian init FUN_0209c3fc, with the Protect HQ start flag set (r4 = entity): the
@ vanilla block keeps only the three operators (role 4, modifiers 0 to 2). The refill
@ operator of the hub (role 5, modifier 7; subtank_npc.s) stays too.
@ was: ldrb r1, [r4, #0x14]; cmp r1, #4; bne; ldrb r0, [r4, #0x15]; cmp r0, #0; beq normal (three times, modifiers 0, 1, 2)
        ldrb    r1, [r4, #0x14]         @ role
        ldrb    r0, [r4, #0x15]         @ modifier
        cmp     r1, #4
        bne     not_operator
        cmp     r0, #3
        blo     0x0209C442              @ operators: normal init
not_operator:
        cmp     r1, #1
        bne     not_cedre
        cmp     r0, #3
        beq     0x0209C442              @ Cedre (1, 3) sells the E Tank
not_cedre:
        cmp     r1, #5
        bne     0x0209C42C              @ everyone else leaves
        cmp     r0, #4
        beq     0x0209C442              @ Scombresoce (5, 4) sells the Smelling Salts
        cmp     r0, #7
        beq     0x0209C442              @ the refill operator of the hub

@ Room overlays (rom/pickups.py OVERLAY_USABLE_PATCH; the patch decompresses the
@ overlay file, edits it and stores it again). Overlay 46 is A-3, overlay 113 is X-2.

        .org    0x021942F4
@ rom: OVERLAY_USABLE_PATCH[46][0][2]
@ was: .word 0x00020000   (OVERLAY_USABLE_PATCH[46][0][1]): the hit-flag mask the tree waits for, the punch class (Model FX)
        .word   0x00FFFF00              @ every attack class

        .org    0x0219422E
@ rom: OVERLAY_USABLE_PATCH[46][1][2]
@ was: bne 0x02194236   (OVERLAY_USABLE_PATCH[46][1][1]): fifteen times in sixteen the fruit is a random refill
        mov     r8, r8                  @ the first fruit is the apple while its flag is clear

        .org    0x02194F54
@ rom: OVERLAY_USABLE_PATCH[113][0][2]
@ was: .word 0x00000200   (OVERLAY_USABLE_PATCH[113][0][1]): the doll's hit points reached zero
        .word   0x00FFFF00              @ every attack class
