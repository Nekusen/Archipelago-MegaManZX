@ Tutorial skip (rom_patches.md "Tutorial skip").
@ New Game enters the scene through the LOAD handler when the game mode has its
@ low half clear and the title carousel is at step 6; otherwise the displaced
@ prologue of the New Game handler runs and the handler resumes as in vanilla.
@ Entry hook at 0x02022544 (rom.py SKIP_ENTRY_NEW), cave at 0x020CB460 (SKIP_CAVE).

        .thumb

.equ GAME_STATE,            0x0215E6D8  @ u32 game mode / state word
.equ TITLE_STEP,            0x0214CD70  @ u8 title carousel step; 6 = a game was launched
.equ newgame_prologue_call, 0x0202298C  @ FUN_0202298c, called by the displaced prologue
.equ newgame_resume,        0x0202254C  @ New Game handler, right after the displaced prologue
.equ load_handler_body,     0x0202252C  @ LOAD handler: enters the scene from the load buffer
.equ skip_cave,             0x020CB460

        .org    0x02022544
@ rom.py: SKIP_ENTRY_NEW
@ Entry hook: the first 8 bytes of the New Game state handler.
@ was: push {r4, lr}; adds r4, r0, #0; bl newgame_prologue_call   (SKIP_ENTRY_ORIG)
        ldr     r3, lit_skip_cave       @ jump into the cave
        bx      r3
lit_skip_cave:
        .word   skip_cave + 1           @ Thumb bit set

        .org    0x020CB460
@ rom.py: SKIP_CAVE
        ldr     r1, lit_game_state
        ldr     r1, [r1]
        lsls    r1, r1, #16             @ low 16 bits of the mode: 0 = New Game, any character/difficulty
        bne     orig                    @ attract demo (0xB00/0xC00) and the rest: vanilla path
        ldr     r2, lit_title_step
        ldrb    r2, [r2]
        cmp     r2, #6                  @ carousel at "game launched"
        beq     skip
orig:   push    {r4, lr}                @ the displaced prologue, then back into the handler
        mov     r4, r0
        bl      newgame_prologue_call
        ldr     r3, lit_resume
        bx      r3
skip:   ldr     r3, lit_load            @ into the LOAD handler instead
        bx      r3
lit_game_state: .word GAME_STATE
lit_title_step: .word TITLE_STEP
lit_resume:     .word newgame_resume + 1
lit_load:       .word load_handler_body + 1
