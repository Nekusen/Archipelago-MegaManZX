@ Missions taken again from the Transerver.
@ The Mission Requests list of the consoles is built from a table of 39 flags, one
@ per id 2 to 40 (the missions, then the quests), and the consoles count the same
@ flags to decide whether to offer the list at all. The patched ROM points the
@ builder at its own table, in which each mission's entry is its "completed" bit,
@ and routes the consoles' count through `count`, so the list holds the missions
@ already reported, ready to be played again, plus the quests as in vanilla.
@ Taking a mission from the list goes through `take`, which accepts it the vanilla
@ way and then clears the bits that would end it at once: the objective, the boss
@ already beaten, the phases already played. The consoles' "story mission pending"
@ test, which hides "Abort the mission?" during Troop Reinforcement and Protect HQ,
@ becomes `pending`: Abort is offered only for what the player took from the list
@ (a quest, or a mission whose completed bit is set), and with any other mission
@ under way the consoles show their normal menu, list included, instead of the
@ reduced one. The routines and their tables travel in an autoload section
@ (rom/missions.py MISSION_SECTION_RAM); the tables are built from data.py.

        .thumb

.equ progress_block,        0x021045CC
.equ take_mission,          0x02094FAC  @ mission start snapshot, story handler and accept, by id
.equ section,               0x02193000  @ MISSION_SECTION_RAM
.equ list_table,            section + 0xC0   @ u32[39]: the flag that lists ids 2 to 40
.equ state_table,           section + 0x160  @ u8[14]: the state value of ids 2 to 15
.equ repeat_index,          section + 0x170  @ u8[14]: where each id's row starts in repeat_table
.equ repeat_table,          section + 0x180  @ u16 flags `take` clears, 0xFFFF ends each row
.equ count_routine,         section + 0x00   @ MISSION_SECTION_ENTRIES
.equ take_routine,          section + 0x30
.equ pending_routine,       section + 0x70

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
        ldr     r5, lit_index
        ldrb    r4, [r5, r4]
        ldr     r5, lit_repeat
        adds    r5, r5, r4
        ldr     r6, lit_block2
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
        b       take_loop
take_done:
        pop     {r4, r5, r6, pc}
        .align  2
lit_index:  .word repeat_index
lit_repeat: .word repeat_table
lit_block2: .word progress_block

pending:                                @ r0 = 0 when what is under way was taken from the list
        push    {r4, r5}
        ldr     r3, lit_block3
        movs    r1, #0x5f               @ the mission byte
        ldrb    r0, [r3, r1]
        lsls    r0, r0, #29
        bmi     pending_chosen          @ bit 2: a quest
        movs    r1, #0xe0               @ the state word
        ldr     r4, [r3, r1]
        ldr     r2, lit_states
        movs    r5, #0
pending_next:
        ldrb    r0, [r2, r5]
        cmp     r0, r4
        beq     pending_found
        adds    r5, #1
        cmp     r5, #14
        blo     pending_next
        movs    r0, #1                  @ no mission of the list: offer the menu
        b       pending_done
pending_found:
        ldr     r2, lit_list3
        lsls    r5, r5, #2
        ldr     r1, [r2, r5]            @ the mission's completed flag
        lsrs    r2, r1, #3
        ldrb    r2, [r3, r2]
        movs    r0, #7
        ands    r1, r0
        lsrs    r2, r1
        movs    r0, #1
        bics    r0, r2                  @ completed: it was taken from the list
        b       pending_done
pending_chosen:
        movs    r0, #0
pending_done:
        pop     {r4, r5}
        bx      lr
        .align  2
lit_block3: .word progress_block
lit_states: .word state_table
lit_list3:  .word list_table

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
@ rom: thumb_bl(0x020934EE, MISSION_SECTION_RAM + MISSION_SECTION_ENTRIES["pending"])
@ was: bl 0x02008A34   (MISSION_PENDING_HOOKS[0][1]): "story mission pending" in the Computer console
        bl      pending_routine

        .org    0x02093C8A
@ rom: thumb_bl(0x02093C8A, MISSION_SECTION_RAM + MISSION_SECTION_ENTRIES["pending"])
@ was: bl 0x02008A34   (MISSION_PENDING_HOOKS[1][1]): the same test in the Teleporter console
        bl      pending_routine

        .org    0x0202C522
@ rom: thumb_bl(0x0202C522, MISSION_SECTION_RAM + MISSION_SECTION_ENTRIES["pending"])
@ was: bl 0x02008A34   (MISSION_PENDING_HOOKS[2][1]): the same test when the retry menu lists its entries
        bl      pending_routine

        .org    0x020934F6
@ rom: MISSION_MENU_PATCH[0][2]
@ was: ldr r0, [pc, #0x18c]   (MISSION_MENU_PATCH[0][1]): first instruction of the Computer console's reduced menu
        b       0x02093496              @ the normal menu instead, list included

        .org    0x02093C92
@ rom: MISSION_MENU_PATCH[1][2]
@ was: lsls r1, r5, #1   (MISSION_MENU_PATCH[1][1]): first instruction of the Teleporter console's reduced menu
        b       0x02093C28
