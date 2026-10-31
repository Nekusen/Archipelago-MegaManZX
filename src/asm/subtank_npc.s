@ Sub Tank refill: an operator beside the starting Transerver.
@ The hub room gets a new Guardian entity (class 5.48, role 5 = the plain Guardians,
@ modifier 7) to the right of the Transerver of the Area A floor and of the Guardian
@ base floor. The game picks a Guardian's init and update from two tables indexed by
@ role and modifier, and role 5 has seven modifiers, so the section carries both
@ tables of role 5 one entry longer and the two role pointers of the ARM9 point here.
@ The init is the game's own shared Guardian init, which also gives the role's sprite;
@ the update is the routine below, a state
@ machine shaped like the two Guardians who sell usables (Cedre, Scombresoce): UP in
@ front of the operator opens the offer, a YES fills every Sub Tank held through the
@ game's own routine and charges the price, and the three other answers (not enough
@ E-Crystals, nothing to fill, no) only talk. No flag is touched: the operator asks
@ no first-talk flag and gives nothing the game remembers. The texts are five
@ messages appended to the system talk file (rom/npc.py NPC_TEXTS).

        .thumb

.equ message,               0x027E02C4  @ the message system; +0x0A u16 state (0 idle, 4 last page shown)
.equ message_choice,        0x027E02D7  @ the option chosen, in the high nibble: 1 first line, 3 second
.equ message_side,          0x027E033A  @ u16: 1 when the speaker stands to the player's right
.equ up_pressed,            0x02108B70  @ non-zero while the player activates with UP
.equ interact_hitbox,       0x02108B58  @ the hitbox the player overlaps, as the consoles and NPCs test it
.equ player_entity,         0x02108B9C  @ pointer to the player's entity
.equ player_control,        0x0214F669  @ bit 0 gives the player's control back
.equ open_dialog,           0x0201221C  @ (message id)
.equ dialog_done,           0x0209C104  @ r0 = 1 once the open message has been read, and asks it to close
.equ talk_release,          0x0209C0D8  @ r0 = 1 once the message system is idle; gives the control back
.equ set_animation,         0x0200FE64  @ (entity, animation)
.equ sprite_update,         0x0200FC0C  @ (entity)
.equ count_tanks,           0x02044C78  @ (player): how many Sub Tanks are held, the low nibble of +0x170
.equ play_sound,            0x020058DC  @ (sound id)
.equ take_crystals,         0x02044D80  @ (player, amount)
.equ guardian_init,         0x0209C304  @ the shared Guardian init: sprite set of the role, hitbox, pose
.equ crystals_offset,       0x168       @ E-Crystals in the player's entity
.equ price,                 200
.equ tank_energy_offset,    0x171       @ the energy of each tank held, one byte per tank, packed
.equ tank_cap,              30
.equ sound_got_item,        0x26
.equ entity_x,              0x5C
.equ entity_flags,          0x0A        @ bit 4: faces right
.equ entity_state,          0x12
.equ entity_hitbox,         0x7C
.equ entity_faced,          0xC9        @ the way the Guardian faced before the talk
.equ msg_offer,             0x481       @ talk_sys_en.bin messages 129 to 133 (NPC_TEXTS)
.equ msg_done,              0x482
.equ msg_poor,              0x483
.equ msg_nothing,           0x484
.equ msg_no,                0x485
.equ section,               0x02193A00  @ NPC_SECTION_RAM

        .org    0x02193A00
@ rom: NPC_SECTION_CODE
npc_update:                             @ r0 = the operator's entity
        push    {r4, lr}
        adds    r4, r0, #0
        ldrb    r1, [r4, #entity_state]
        cmp     r1, #1
        beq     wait_for_up
        cmp     r1, #2
        beq     answer
        cmp     r1, #5
        beq     wait_for_read
        cmp     r1, #6
        beq     release
        cmp     r1, #0
        bne     update_done
        movs    r1, #0                  @ state 0: standing pose, turned to the player
        bl      set_animation
        bl      face_player
        movs    r0, #1
        strb    r0, [r4, #entity_state]
        b       update_done
wait_for_up:                            @ state 1: UP in front of the operator opens the offer
        bl      talk_trigger
        cmp     r0, #0
        beq     update_done
        ldr     r0, lit_msg_offer
        bl      say
        movs    r0, #2
        strb    r0, [r4, #entity_state]
        b       update_done
answer:                                 @ state 2: the offer was read; the first line is yes
        bl      dialog_done
        cmp     r0, #0
        beq     update_done
        ldr     r0, lit_message_choice
        ldrb    r0, [r0]
        lsrs    r0, r0, #4
        ldr     r1, lit_msg_no
        cmp     r0, #1
        bne     reply
        ldr     r2, lit_player_entity
        ldr     r2, [r2]
        ldr     r0, lit_crystals_offset
        ldr     r0, [r2, r0]
        ldr     r1, lit_msg_poor
        cmp     r0, #price
        blo     reply
        adds    r0, r2, #0
        bl      fill_every_tank
        ldr     r1, lit_msg_nothing
        cmp     r0, #0
        beq     reply                   @ no tank, or every tank full: no charge
        movs    r0, #sound_got_item
        bl      play_sound
        ldr     r0, lit_player_entity
        ldr     r0, [r0]
        movs    r1, #price
        bl      take_crystals
        ldr     r1, lit_msg_done
reply:
        adds    r0, r1, #0
        bl      say
        movs    r0, #5
        strb    r0, [r4, #entity_state]
        b       update_done
wait_for_read:                          @ state 5: the reply was read
        bl      dialog_done
        cmp     r0, #0
        beq     update_done
        movs    r0, #6
        strb    r0, [r4, #entity_state]
        b       update_done
release:                                @ state 6: the box is gone, the player moves again
        bl      talk_release
        cmp     r0, #0
        beq     update_done
        movs    r0, #1
        strb    r0, [r4, #entity_state]
update_done:
        adds    r0, r4, #0
        bl      sprite_update
        pop     {r4, pc}

say:                                    @ r0 = message id: turn to the player and open the box on their side
        push    {r5, lr}
        adds    r5, r0, #0
        bl      face_player
        adds    r0, r5, #0
        bl      open_dialog
        pop     {r5, pc}

talk_trigger:                           @ r0 = 1 when UP is pressed on our hitbox and no message is open
        push    {lr}
        ldr     r0, lit_message
        ldrh    r0, [r0, #0xA]
        cmp     r0, #0
        bne     no_trigger
        ldr     r0, lit_up_pressed
        ldrb    r0, [r0]
        cmp     r0, #0
        beq     no_trigger
        ldr     r0, lit_interact_hitbox
        ldr     r1, [r0]
        adds    r0, r4, #0
        adds    r0, #entity_hitbox
        cmp     r1, r0
        bne     no_trigger
        ldr     r0, [r1, #0x28]         @ the hitbox's owner
        cmp     r0, r4
        bne     no_trigger
        ldr     r1, lit_player_control
        ldrb    r2, [r1]
        movs    r0, #1
        bics    r2, r0
        strb    r2, [r1]
        ldrb    r1, [r4, #entity_flags]
        lsrs    r1, r1, #4
        movs    r0, #1
        ands    r1, r0
        adds    r0, r4, #0
        adds    r0, #entity_faced
        strb    r1, [r0]
        movs    r0, #1
        pop     {pc}
no_trigger:
        movs    r0, #0
        pop     {pc}

fill_every_tank:                        @ r0 = player; r0 = 1 when a tank held was below the cap
        push    {r5, r6, lr}
        adds    r5, r0, #0
        bl      count_tanks
        adds    r6, r0, #0
        ldr     r1, lit_tank_energy
        adds    r1, r5, r1
        movs    r3, #0
fill_next:
        cmp     r6, #0
        beq     fill_done
        ldrb    r2, [r1]
        cmp     r2, #tank_cap
        bge     fill_skip
        movs    r2, #tank_cap
        strb    r2, [r1]
        movs    r3, #1
fill_skip:
        adds    r1, r1, #1
        subs    r6, r6, #1
        b       fill_next
fill_done:
        adds    r0, r3, #0
        pop     {r5, r6, pc}

face_player:                            @ turn to the player and tell the box which side we are on
        ldr     r0, lit_player_entity
        ldr     r0, [r0]
        ldr     r0, [r0, #entity_x]
        ldr     r1, [r4, #entity_x]
        movs    r2, #0
        cmp     r1, r0
        bge     facing_known
        movs    r2, #1                  @ the player is to our right
facing_known:
        ldrb    r3, [r4, #entity_flags]
        movs    r0, #0x10
        bics    r3, r0
        lsls    r0, r2, #4
        orrs    r3, r0
        strb    r3, [r4, #entity_flags]
        adds    r1, r4, #0
        adds    r1, #0x54
        strb    r2, [r1]                @ facing byte
        adds    r1, r4, #0
        adds    r1, #0x3C
        ldrb    r3, [r1, #0x16]         @ sprite flip, bit 4 of +0x52
        movs    r0, #0x10
        bics    r3, r0
        lsls    r0, r2, #4
        orrs    r3, r0
        strb    r3, [r1, #0x16]
        movs    r3, #1
        eors    r3, r2                  @ the box sits on the player's side: 1 when they are to our left
        ldr     r0, lit_message_side
        strh    r3, [r0]
        bx      lr

        .align  2
lit_message:          .word message
lit_message_choice:   .word message_choice
lit_message_side:     .word message_side
lit_up_pressed:       .word up_pressed
lit_interact_hitbox:  .word interact_hitbox
lit_player_entity:    .word player_entity
lit_player_control:   .word player_control
lit_crystals_offset:  .word crystals_offset
lit_tank_energy:      .word tank_energy_offset
lit_msg_offer:        .word msg_offer
lit_msg_done:         .word msg_done
lit_msg_poor:         .word msg_poor
lit_msg_nothing:      .word msg_nothing
lit_msg_no:           .word msg_no

        .org    0x02193BC0
@ rom: NPC_INIT_TABLE
@ The init table of role 5, one entry longer: the seven of the game (0x020EAE00), then ours.
        .word   guardian_init + 1
        .word   0x0209B679
        .word   0x0209B63D
        .word   guardian_init + 1
        .word   guardian_init + 1
        .word   0x0209B599
        .word   guardian_init + 1
        .word   guardian_init + 1       @ modifier 7: the refill operator

        .org    0x02193BE0
@ rom: NPC_UPDATE_TABLE
@ The update table of role 5, one entry longer: the seven of the game (0x020EAE1C), then ours.
        .word   0x0209AEC5
        .word   0x0209AEAD
        .word   0x0209AE95
        .word   0x0209AE8D
        .word   0x0209AD19
        .word   0x0209AD01
        .word   0x0209ACF5
        .word   section + 1             @ modifier 7: npc_update

        .org    0x020EAD3C
@ rom: NPC_ROLE_INIT_POINTER_NEW
@ was: .word 0x020EAE00   (NPC_ROLE_INIT_POINTER_ORIG): the init table of role 5
        .word   section + 0x1C0

        .org    0x020EAD54
@ rom: NPC_ROLE_UPDATE_POINTER_NEW
@ was: .word 0x020EAE1C   (NPC_ROLE_UPDATE_POINTER_ORIG): the update table of role 5
        .word   section + 0x1E0
