@ Cutscenes always skippable.
@ The script opcode that opens a skippable block flags it only when the event
@ was already seen; that branch becomes a no-op. The START reader calls the
@ cave, which marks the event seen (with its backup) and re-executes the two
@ displaced instructions.
@ Patches at 0x0201C00C and 0x0201B1E4 (rom.py CUTSCENE_SKIP_PATCH), cave at
@ 0x020CB540 (CUTSCENE_SKIP_CAVE).

        .thumb

.equ SCRIPT_RUNNER,     0x0214F500      @ script runner block: +3 u8 unique event id of the open block
.equ CUTSCENE_HANDLER,  0x0214F6B0      @ object read by the START reader (displaced load)
.equ event_mark_seen,   0x02008624      @ FUN_02008624(event): set the event bit and write the backup
.equ cutscene_skip_cave, 0x020CB540

        .org    0x0201C00C
@ rom.py: CUTSCENE_SKIP_PATCH[0][2]
@ Opcode 0x23 sub 0 (FUN_0201bfd0).
@ was: beq 0x0201C03E   (skip the "skippable" flag when the event was not seen)
        mov     r8, r8                  @ the block is always skippable

        .org    0x0201B1E4
@ rom.py: CUTSCENE_SKIP_PATCH[1][2]
@ START reader FUN_0201b1c8.
@ was: ldr r0, =CUTSCENE_HANDLER; ldrb r1, [r0, #0x1d]
        bl      cutscene_skip_cave

        .org    0x020CB540
@ rom.py: CUTSCENE_SKIP_CAVE
        push    {r4, lr}
        ldr     r4, lit_runner
        ldrb    r0, [r4, #3]            @ event id of the block being skipped
        bl      event_mark_seen         @ what the closing opcode would have done
        ldr     r0, lit_handler         @ the displaced instructions
        ldrb    r1, [r0, #0x1d]
        pop     {r4, pc}
lit_runner:     .word SCRIPT_RUNNER
lit_handler:    .word CUTSCENE_HANDLER
