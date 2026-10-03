@ Mission objectives as items (mission_objectives: items).
@ The story objects (the Computer Chips, the Stuffed Animal, the three Data Disks)
@ and what four story events unlock (the door past the terminal of F-3, the door
@ the sprinkler key of G-2 opens, the slow lava of Area K, the door of K-1 that the
@ switch of K-4 unlocks) are items of the pool.
@ The game's own flags keep meaning "picked up here" or "done here", which is what
@ the locations detect; what the player holds lives in two bytes of the pickup
@ table section that only the items received fill (rom/table.py STORY_OFF and
@ STORY_GATES_OFF), and everything that used to ask the game's flags asks those:
@ the Report of the five missions, through `report_gate`; the two doors, through
@ their entries in the table of door flags; the lava wall of K-4, the door tiles
@ of F-3 and the door of K-1, through the literal their code loads; and the ITEM C
@ list of the pause menu. Nothing here is applied in the other two modes of the option.

        .thumb

.equ progress_block,        0x021045CC
.equ objective_met,         0x020318EC  @ r0 = 1 when the objective of the mission under way is met
.equ mission_state,         0x021046AC
.equ story_byte,            0x02191C46  @ PICKUP_TABLE_ADDR + STORY_OFF
.equ gates_byte,            0x02191C47  @ PICKUP_TABLE_ADDR + STORY_GATES_OFF
.equ story_flag_base,       (story_byte - progress_block) * 8
.equ gates_flag_base,       (gates_byte - progress_block) * 8
.equ section,               0x02193200  @ STORY_SECTION_RAM
.equ report_table,          section + 0x40   @ rows of u16 mission state, u8 mask of story_byte, u8 0
.equ report_gate_routine,   section + 0x00

        .org    0x02193200
@ rom: STORY_SECTION_CODE
report_gate:                            @ r0 = objective met and the mission's object held
        push    {r4, lr}
        bl      objective_met
        cmp     r0, #0
        beq     gate_done
        ldr     r1, lit_state
        ldr     r1, [r1]
        ldr     r2, lit_table
gate_loop:
        ldrh    r3, [r2]
        cmp     r3, #0
        beq     gate_done               @ no row for this mission: it asks for nothing
        cmp     r3, r1
        beq     gate_found
        adds    r2, #4
        b       gate_loop
gate_found:
        ldrb    r3, [r2, #2]
        ldr     r1, lit_story
        ldrb    r1, [r1]
        tst     r1, r3
        bne     gate_done
        movs    r0, #0                  @ the object is missing: no Report yet
gate_done:
        pop     {r4, pc}
        .align  2
lit_state:  .word mission_state
lit_table:  .word report_table
lit_story:  .word story_byte

        .org    0x020934CE
@ rom: thumb_bl(0x020934CE, STORY_SECTION_RAM + STORY_SECTION_ENTRIES["report_gate"])
@ was: bl 0x020318EC   (STORY_REPORT_HOOKS[0][1]): the Computer console asks whether to offer the Report
        bl      report_gate_routine

        .org    0x02093C66
@ rom: thumb_bl(0x02093C66, STORY_SECTION_RAM + STORY_SECTION_ENTRIES["report_gate"])
@ was: bl 0x020318EC   (STORY_REPORT_HOOKS[1][1]): the same question in the Teleporter console
        bl      report_gate_routine

        .org    0x02026A8E
@ rom: thumb_bl(0x02026A8E, STORY_SECTION_RAM + STORY_SECTION_ENTRIES["report_gate"])
@ was: bl 0x020318EC   (STORY_REPORT_HOOKS[2][1]): the MISSION page picks "File a mission report"
        bl      report_gate_routine

        .org    0x0204B904
@ rom: thumb_bl(0x0204B904, STORY_SECTION_RAM + STORY_SECTION_ENTRIES["report_gate"])
@ was: bl 0x020318EC   (STORY_REPORT_HOOKS[3][1]): the "objective met" notice of the HUD
        bl      report_gate_routine

        .org    0x020E9EC0
@ rom: STORY_DOOR_FLAGS_NEW
@ was: the flags 381 and 382 (STORY_DOOR_FLAGS_ORIG): the event gates F-3 to F-4 and G-2 to G-4
        .word   gates_flag_base + 5
        .word   gates_flag_base + 6

        .org    0x020D97B0
@ rom: STORY_MENU_FLAGS_NEW
@ was: the flags 663 to 667 and 693 to 695 (STORY_MENU_FLAGS_ORIG): the four Computer Chips,
@ the Stuffed Animal and the three Data Disks in the ITEM C list
        .word   story_flag_base + 0
        .word   story_flag_base + 1
        .word   story_flag_base + 2
        .word   story_flag_base + 3
        .word   story_flag_base + 4
        .word   story_flag_base + 5
        .word   story_flag_base + 6
        .word   story_flag_base + 7

@ Room overlays (rom/story.py STORY_OVERLAY_PATCH). Overlay 73 is F-3, overlay 95 is K-1,
@ overlay 98 is K-4.

        .org    0x021948EC
@ rom: STORY_OVERLAY_PATCH[73][0][2]
@ was: .word 0x021045EC   (STORY_OVERLAY_PATCH[73][0][1]): the room draws the door open with bit 5 of this address + 0x0F
        .word   gates_byte - 0x0F

        .org    0x02195584
@ rom: STORY_OVERLAY_PATCH[98][0][2]
@ was: .word 0x021045CC   (STORY_OVERLAY_PATCH[98][0][1]): the lava wall takes the slow speed with bit 0 of this address + 1
        .word   gates_byte - 1

        .org    0x021956BC
@ rom: STORY_OVERLAY_PATCH[98][1][2]
@ was: .word 0x021045CC   (STORY_OVERLAY_PATCH[98][1][1]): the same test in the second lava wall
        .word   gates_byte - 1

        .org    0x02195DA8
@ rom: STORY_OVERLAY_PATCH[95][0][2]
@ was: .word 0x021045EC   (STORY_OVERLAY_PATCH[95][0][1]): the door opens at a touch with bit 7 of this address + 0x0F
        .word   gates_byte - 0x0F
