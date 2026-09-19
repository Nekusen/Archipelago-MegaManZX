@ Goal progress line in the pause menu.
@ The STATUS tab help texts (messages 0-9 of m_sub_en.bin, rebuilt by rom/ui.py
@ with a second line of GOAL_LINE_GLYPHS spaces) show the requirement progress
@ the client keeps in GOAL_LINE_BUF. The message pointer routine of the text
@ banks jumps into the cave, which resolves the pointer as the game does and,
@ when the bank holds the pause menu file (its first message starts "Choo")
@ and the message is one of those, copies the buffer over the reserved line
@ before returning. Other files share the bank (the database viewer of Fleuve
@ loads its own), so the file and the exact line length are both checked.
@ Cave at 0x020CB588 (rom/ui.py GOAL_LINE_CAVE), buffer at 0x020CB6A0
@ (data.GOAL_LINE_ADDR).

        .thumb

.equ MSG_TEXT_BASES,    0x02104594  @ u32 text base of each loaded text bank (1 = pause menu)
.equ MSG_TABLE_BASES,   0x0210458C  @ u32 offset table of each bank
.equ PAUSE_TABLE_BASE,  0x02104590  @ MSG_TABLE_BASES + 4: the pause menu bank
.equ PAUSE_FIRST_GLYPHS, 0x4F4F4823 @ "Choo" of "Choose the model", message 0 of m_sub_en.bin
.equ GOAL_LINE_BUF,     0x020CB6A0
.equ GOAL_LINE_GLYPHS,  30
.equ GOAL_LINE_MESSAGES, 10
.equ goal_line_cave,    0x020CB588

        .org    0x02007F40
@ rom: GOAL_LINE_ENTRY_NEW
@ Message pointer routine FUN_02007f40(bank, index) -> text pointer.
@ was: lsls r2, r0, #2; ldr r0, [pc, #0x10]; ldr r3, [r0, r2]; ldr r0, [pc, #0x10]
        ldr     r3, entry_lit
        bx      r3
entry_lit:      .word goal_line_cave + 1

        .org    0x020CB588
@ rom: GOAL_LINE_CAVE
        lsls    r2, r0, #2
        ldr     r0, lit_text_bases
        ldr     r3, [r0, r2]            @ text base of the bank
        ldr     r0, lit_table_bases
        ldr     r2, [r0, r2]            @ offset table of the bank
        lsls    r0, r1, #1
        ldrh    r0, [r2, r0]
        adds    r0, r3, r0              @ the message pointer, as the game computes it
        cmp     r1, #GOAL_LINE_MESSAGES
        bhs     done
        push    {r4, r5}
        ldr     r4, lit_pause_table
        ldr     r4, [r4]
        cmp     r2, r4
        bne     out                     @ another bank
        ldr     r4, [r3]                @ first glyphs of message 0
        ldr     r5, lit_first_glyphs
        cmp     r4, r5
        bne     out                     @ another file in the bank
        adds    r4, r0, #0
find:   ldrb    r5, [r4]
        cmp     r5, #0xFE
        beq     out                     @ no second line in this message
        adds    r4, #1
        cmp     r5, #0xFC
        bne     find
        movs    r5, #GOAL_LINE_GLYPHS
        ldrb    r5, [r4, r5]
        cmp     r5, #0xFE
        bne     out                     @ not the reserved line
        ldr     r2, lit_buf
        movs    r3, #GOAL_LINE_GLYPHS
copy:   ldrb    r5, [r2]
        strb    r5, [r4]
        adds    r2, #1
        adds    r4, #1
        subs    r3, #1
        bne     copy
out:    pop     {r4, r5}
done:   bx      lr
        .align  2
lit_text_bases:     .word MSG_TEXT_BASES
lit_table_bases:    .word MSG_TABLE_BASES
lit_pause_table:    .word PAUSE_TABLE_BASE
lit_first_glyphs:   .word PAUSE_FIRST_GLYPHS
lit_buf:            .word GOAL_LINE_BUF
