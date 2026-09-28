@ Missions taken again from the Transerver.
@ The Mission Requests list of the consoles is built from a table of 39 flags, one
@ per id 2 to 40 (the missions, then the quests), and the consoles count the same
@ flags to decide whether to offer the list at all. The patched ROM points the
@ builder at its own table, in which each mission's entry is its "completed" bit,
@ and routes the consoles' count through `count`, so the list holds the missions
@ already reported, ready to be played again, plus the quests as in vanilla.
@ Taking a mission from the list goes through `take`, which accepts it the vanilla
@ way and then clears the bits that would end it at once: the objective, the boss
@ already beaten, the phases already played. Both routines and their tables travel
@ in an autoload section (rom/missions.py MISSION_SECTION_RAM); the tables are
@ built from data.py. The consoles' "story mission pending" test, which hides
@ "Abort the mission?" during Troop Reinforcement and Protect HQ, is replaced by
@ zero at its three menu sites.

        .thumb

.equ progress_block,        0x021045CC
.equ take_mission,          0x02094FAC  @ mission start snapshot, story handler and accept, by id
.equ section,               0x02193000  @ MISSION_SECTION_RAM
.equ list_table,            section + 0x80   @ u32[39]: the flag that lists ids 2 to 40
.equ repeat_table,          section + 0x120  @ 14 rows of 8 u16: the flags `take` clears for ids 2 to 15
.equ count_routine,         section + 0x00   @ MISSION_SECTION_ENTRIES
.equ take_routine,          section + 0x30

        .org    0x02193000
@ rom: MISSION_SECTION_CODE
count:                                  @ r0 = entries of the list whose flag is set
        push    {r4, r5, r6}
        ldr     r4, lit_list
        ldr     r1, lit_block
        movs    r0, #0
        movs    r5, #39
count_loop:
        ldr     r3, [r4]
        asrs    r2, r3, #3
        ldrb    r2, [r1, r2]
        movs    r6, #7
        ands    r3, r6
        movs    r6, #1
        lsls    r6, r3
        tst     r2, r6
        beq     count_skip
        adds    r0, #1
count_skip:
        adds    r4, #4
        subs    r5, #1
        bne     count_loop
        pop     {r4, r5, r6}
        bx      lr
        .align  2
lit_list:   .word list_table
lit_block:  .word progress_block

take:                                   @ r0 = r1 = id chosen in the list
        push    {r4, r5, r6, lr}
        movs    r4, r0
        bl      take_mission
        subs    r4, #2
        cmp     r4, #13
        bhi     take_done               @ a quest: nothing to clear
        lsls    r4, r4, #4
        ldr     r5, lit_repeat
        adds    r5, r5, r4
        ldr     r6, lit_block2
        movs    r4, #8
take_loop:
        ldrh    r3, [r5]
        lsls    r2, r3, #16
        bmi     take_done               @ 0xFFFF ends the row
        lsrs    r2, r3, #3
        ldrb    r0, [r6, r2]
        movs    r1, #7
        ands    r3, r1
        movs    r1, #1
        lsls    r1, r3
        bics    r0, r1
        strb    r0, [r6, r2]            @ live copy only, like the accept itself
        adds    r5, #2
        subs    r4, #1
        bne     take_loop
take_done:
        pop     {r4, r5, r6, pc}
        .align  2
lit_repeat: .word repeat_table
lit_block2: .word progress_block

        .org    0x02027FEC
@ rom: MISSION_LIST_LITERAL_PATCH[0][2]
@ was: .word 0x020DAE7C   (MISSION_LIST_LITERAL_PATCH[0][1]): the vanilla table of "offered" flags
        .word   list_table

        .org    0x02093496
@ rom: thumb_bl(0x02093496, MISSION_SECTION_RAM + MISSION_SECTION_ENTRIES["count"])
@ was: bl 0x02008774   (MISSION_COUNT_HOOKS[0][1]): the Computer console counts the offered flags
        bl      count_routine

        .org    0x02093C28
@ rom: thumb_bl(0x02093C28, MISSION_SECTION_RAM + MISSION_SECTION_ENTRIES["count"])
@ was: bl 0x02008774   (MISSION_COUNT_HOOKS[1][1]): the Teleporter console counts the offered flags
        bl      count_routine

        .org    0x02093604
@ rom: thumb_bl(0x02093604, MISSION_SECTION_RAM + MISSION_SECTION_ENTRIES["take"])
@ was: bl 0x02094FAC   (MISSION_TAKE_HOOKS[0][1]): the Computer console accepts the chosen id
        bl      take_routine

        .org    0x02093E0A
@ rom: thumb_bl(0x02093E0A, MISSION_SECTION_RAM + MISSION_SECTION_ENTRIES["take"])
@ was: bl 0x02094FAC   (MISSION_TAKE_HOOKS[1][1]): the Teleporter console accepts the chosen id
        bl      take_routine

        .org    0x020934EE
@ rom: MISSION_ABORT_PATCH[0][2]
@ was: bl 0x02008A34   (MISSION_ABORT_PATCH[0][1]): "story mission pending" hides Abort in the Computer console
        movs    r0, #0
        mov     r8, r8

        .org    0x02093C8A
@ rom: MISSION_ABORT_PATCH[1][2]
@ was: bl 0x02008A34   (MISSION_ABORT_PATCH[1][1]): the same test in the Teleporter console
        movs    r0, #0
        mov     r8, r8

        .org    0x0202C522
@ rom: MISSION_ABORT_PATCH[2][2]
@ was: bl 0x02008A34   (MISSION_ABORT_PATCH[2][1]): the same test when the mission menu lists its entries
        movs    r0, #0
        mov     r8, r8
