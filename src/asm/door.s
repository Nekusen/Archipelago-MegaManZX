@ Closed door sprite.
@ A door that opens with UP draws its sprite only while it opens; closed, it is
@ part of the room's background. A door locked by a door constraint keeps the
@ background of the plain door it was, so its think attaches the sprite of its
@ key colour as soon as it starts waiting, stopped on the first frame of the
@ opening, and the opening restarts that sprite instead of attaching it again.
@ Doors of the original game with a key take the same path and look the same.
@ Section at 0x02193800 (rom/doors.py DOOR_CAVES); hooks at 0x02092508 and 0x020927A0.

        .thumb

.equ release_palette,       0x0200EE4C  @ FUN_0200ee4c(ent)
.equ attach_set,            0x02010624  @ FUN_02010624(ent, set)
.equ set_animation,         0x0200FE64  @ FUN_0200fe64(ent, animation)
.equ advance_animation,     0x0200FC0C  @ FUN_0200fc0c(ent)
.equ load_palette,          0x0200EEA4  @ FUN_0200eea4(ent, palette)
.equ DOOR_SETS,             0x020E9E6C  @ u16[modifier]: sprite set of the opening door
.equ opening_done,          0x020927E0  @ door think FUN_020924d0: the sprite of the opening is ready
.equ door_closed_cave,      0x02193800
.equ door_opening_cave,     0x0219385C

        .org    0x02092508
@ rom: thumb_bl(DOOR_CLOSED_HOOK_RAM, DOOR_CLOSED_CAVE_RAM)
@ Door think FUN_020924d0, state 0 (start waiting); r0 = r4 = door.
@ was: bl release_palette
        bl      door_closed_cave

        .org    0x020927A0
@ rom: thumb_bl(DOOR_OPENING_HOOK_RAM, DOOR_OPENING_CAVE_RAM)
@ Door think FUN_020924d0, state 1, first two instructions of the block that attaches the sprite.
@ was: movs r0, #0x10 ; strh r0, [r4, #0x28]
        bl      door_opening_cave

        .org    0x02193800
@ rom: DOOR_CAVES
closed:                                 @ replaces `bl release_palette` (r0 = door)
        push    {r4, lr}
        adds    r4, r0, #0
        ldr     r1, lit_release
        blx     r1                      @ the displaced call
        ldrb    r0, [r4, #0x14]         @ role
        movs    r1, #0x82               @ a door of an event, or one with nothing to draw
        tst     r0, r1
        bne     c_done
        movs    r1, #0x70               @ key type
        tst     r0, r1
        beq     c_done
        ldrb    r0, [r4, #0x15]         @ modifier: 1 to 5 are the key colours
        subs    r0, r0, #1
        cmp     r0, #4
        bhi     c_done
        movs    r0, #0x10               @ as the opening sets the sprite up
        strh    r0, [r4, #0x28]
        movs    r1, #1
        adds    r0, r4, #0
        adds    r0, #0x2a
        strb    r1, [r0]
        ldrb    r1, [r4, #0x15]
        lsls    r2, r1, #1
        ldr     r1, lit_sets
        ldrh    r1, [r1, r2]
        adds    r0, r4, #0
        ldr     r2, lit_attach
        blx     r2
        adds    r0, r4, #0
        movs    r1, #0
        ldr     r2, lit_animation
        blx     r2
        adds    r0, r4, #0
        ldr     r2, lit_advance
        blx     r2                      @ builds the first frame; nothing advances it while the door waits
        ldrb    r1, [r4, #0xa]
        movs    r0, #1
        orrs    r1, r0
        strb    r1, [r4, #0xa]          @ drawn
        adds    r0, r4, #0
        ldrb    r1, [r4, #0x15]
        subs    r1, r1, #1
        ldr     r2, lit_palette
        blx     r2                      @ the palette of the key colour
c_done:
        pop     {r4, pc}
        mov     r8, r8
opening:                                @ replaces `movs r0, #0x10 ; strh r0, [r4, #0x28]` (r4 = door)
        ldrb    r0, [r4, #0xa]
        movs    r1, #1
        tst     r0, r1
        bne     o_shown
        movs    r0, #0x10               @ the displaced instructions
        strh    r0, [r4, #0x28]
        bx      lr
o_shown:                                @ the closed sprite is already there: play it from the start
        adds    r0, r4, #0
        movs    r1, #0
        ldr     r2, lit_animation
        blx     r2
        ldr     r0, lit_done
        bx      r0
        mov     r8, r8
lit_release:    .word release_palette + 1
lit_sets:       .word DOOR_SETS
lit_attach:     .word attach_set + 1
lit_animation:  .word set_animation + 1
lit_advance:    .word advance_animation + 1
lit_palette:    .word load_palette + 1
lit_done:       .word opening_done + 1
