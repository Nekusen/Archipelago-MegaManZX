@ The bridge of D-1 (mission_objectives: checks or items).
@ In the original game the bridge is down for good after the first visit, and the
@ client lowers it from the start while the option is off. With the option on it
@ stays up until the player lowers it: with a shot at its switch (checks) or with
@ the Area D Bridge item (items), where the shot only marks the switch as pressed,
@ which is its location.
@ The raised bridge is no wall: every frame the room tells the player how far it
@ reaches, and whoever stands outside is put back inside. The original room had
@ one reach for the raised bridge, its left side, so walking in from D-2 landed
@ the player beside the switch. Here the reach is the side the player is on.
@ The switch answers in any mission, not only during Troop Reinforcement.
@ Room overlay 58 (rom/story.py BRIDGE_*); the literals that tie the bridge to its
@ item are in story.s.

        .thumb

.equ set_reach,             0x020451D4  @ (player, left, top, right, [sp] bottom), in 1/256 px
.equ player_holder,         0x0214F3D0  @ u32[+8] = player
.equ switch_flags_literal,  0x02194974  @ the switch's own literal: progress block + 0x20

        .org    0x02194614
@ rom: BRIDGE_REACH_NEW
@ Room routine, r0 = 1 with the bridge up, 0 with it down.
@ was: the whole room (right = 16384 px) or, with the bridge up, its left side alone (right = 2304 px)
reach:
        push    {lr}
        sub     sp, #4
        ldr     r1, lit_holder
        ldr     r1, [r1, #8]            @ player
        movs    r3, #1
        lsls    r3, r3, #22             @ right = 16384 px
        movs    r2, #0                  @ left = 0
        cmp     r0, #0
        beq     reach_set               @ bridge down: the whole room
        ldr     r0, [r1, #0x5c]         @ player x
        movs    r2, #0xa1
        lsls    r2, r2, #12             @ 2576 px, the right edge of the gap
        cmp     r0, r2
        bge     reach_set               @ right of the gap: from its edge to the end of the room
        movs    r2, #0
        movs    r3, #9
        lsls    r3, r3, #16             @ left of the gap: up to 2304 px, as in the original
reach_set:
        movs    r0, #3
        lsls    r0, r0, #20             @ bottom = 12288 px
        str     r0, [sp]
        adds    r0, r1, #0
        adds    r1, r2, #0
        movs    r2, #0                  @ top = 0
        bl      set_reach
        add     sp, #4
        pop     {pc}
        mov     r8, r8
lit_holder: .word player_holder

        .org    0x021948D6
@ rom: BRIDGE_SWITCH_LOWERS
@ Switch think, state 1, once a shot has hit it (r1 = 1, r4 = switch).
@ was: movs r0, #0xa2 ; bl mission_active ; cmp r0, #0 ; beq skip ; the same test on bit 0
@      of progress block + 0x15 ; then the three instructions kept below
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        adds    r0, r4, #0
        adds    r0, #0xc0
        strb    r1, [r0]                @ tell the lift to come down

        .org    0x021948D6
@ rom: BRIDGE_SWITCH_MARKS
@ The same spot with the bridge tied to its item: the shot sets the flag the lift
@ would have set once down, and the lift is told nothing.
        ldr     r0, [pc, #0x9c]         @ switch_flags_literal
        ldrb    r1, [r0, #0xf]
        movs    r2, #8
        orrs    r1, r2
        strb    r1, [r0, #0xf]          @ flag 379: the switch is pressed
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
