@ Goal progress lines in the pause menu.
@ The STATUS tab help texts (messages 0-9 of m_sub_en.bin) are rebuilt by
@ rom/ui.py as two lines of GOAL_LINE_GLYPHS glyphs: the vanilla text padded
@ with spaces, a line break and a blank line. The client keeps GOAL_LINE_BUF in
@ the same layout (line, break, line) with the requirement progress. The message
@ pointer routine of the text banks jumps into the cave, which resolves the
@ pointer as the game does and, when the bank holds the pause menu file (its
@ message 10 starts "Swit") and the message is one of those, copies the
@ buffer's second line over the reserved one; when byte 30 of the buffer is
@ the line break, the first line is copied too (three requirements do not fit
@ in one line, so the vanilla help gives way). Other files share the bank (the
@ database viewer of Fleuve loads its own), so the file and the exact layout
@ are both checked before writing. The file is recognised by a message the
@ cave never writes: the bank stays loaded between pauses, so a signature on
@ message 0 would vanish with the first copy of a first line.
@ Cave at 0x020CB588 (rom/ui.py GOAL_LINE_CAVE), buffer at 0x020CB6A0
@ (data.GOAL_LINE_ADDR).

        .thumb

.equ MSG_TEXT_BASES,    0x02104594  @ u32 text base of each loaded text bank (1 = pause menu)
.equ MSG_TABLE_BASES,   0x0210458C  @ u32 offset table of each bank
.equ PAUSE_TABLE_BASE,  0x02104590  @ MSG_TABLE_BASES + 4: the pause menu bank
.equ PAUSE_SIGNATURE_INDEX, 10      @ "Switch main weapon and", the first message left as vanilla
.equ PAUSE_SIGNATURE_GLYPHS, 0x54495733 @ "Swit"
.equ GOAL_LINE_BUF,     0x020CB6A0
.equ GOAL_LINE_GLYPHS,  30
.equ GOAL_LINE_BUF_LEN, 61          @ two lines and the break between them
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
        movs    r4, #PAUSE_SIGNATURE_INDEX * 2
        ldrh    r4, [r2, r4]            @ offset of the signature message
        ldr     r4, [r3, r4]            @ its first glyphs (word aligned: rom/ui.py checks the layout)
        ldr     r5, lit_signature
        cmp     r4, r5
        bne     out                     @ another file in the bank
        movs    r3, #GOAL_LINE_GLYPHS
        ldrb    r4, [r0, r3]
        cmp     r4, #0xFC
        bne     out                     @ no break after the first line
        movs    r3, #GOAL_LINE_BUF_LEN
        ldrb    r4, [r0, r3]
        cmp     r4, #0xFE
        bne     out                     @ not the reserved second line
        ldr     r2, lit_buf
        adds    r4, r0, #0
        movs    r5, #GOAL_LINE_GLYPHS
        ldrb    r5, [r2, r5]
        cmp     r5, #0xFC
        beq     copy                    @ both lines: r3 = GOAL_LINE_BUF_LEN
        adds    r2, #GOAL_LINE_GLYPHS + 1
        adds    r4, #GOAL_LINE_GLYPHS + 1
        movs    r3, #GOAL_LINE_GLYPHS   @ the second line only
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
lit_signature:      .word PAUSE_SIGNATURE_GLYPHS
lit_buf:            .word GOAL_LINE_BUF
