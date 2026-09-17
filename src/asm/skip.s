@ Tutorial skip.
@ New Game enters the scene through the LOAD handler when the game mode has its
@ low half clear and the title carousel is at step 6; otherwise the displaced
@ prologue of the New Game handler runs and the handler resumes as in vanilla.
@ On the skip path the copy cave first fills the load buffer with the golden
@ image the patch carries (an autoload section the boot code places at
@ GOLDEN_IMAGE), so New Game needs nothing from the client.
@ Entry hook at 0x02022544 (rom/ui.py SKIP_ENTRY_NEW), caves at 0x020CB460
@ (SKIP_CAVE) and 0x020CB560 (SKIP_COPY_CAVE).

        .thumb

.equ GAME_STATE,            0x0215E6D8  @ u32 game mode / state word
.equ TITLE_STEP,            0x0214CD70  @ u8 title carousel step; 6 = a game was launched
.equ LOAD_BUFFER,           0x021602A8  @ the save image the LOAD handler enters the scene from
.equ GOLDEN_IMAGE,          0x02191600  @ the slot's golden image, autoload section (rom/ui.py GOLDEN_IMAGE_RAM)
.equ GOLDEN_IMAGE_LEN,      0x4F4
.equ newgame_prologue_call, 0x0202298C  @ FUN_0202298c, called by the displaced prologue
.equ newgame_resume,        0x0202254C  @ New Game handler, right after the displaced prologue
.equ load_handler_body,     0x0202252C  @ LOAD handler: enters the scene from the load buffer
.equ skip_cave,             0x020CB460
.equ skip_copy_cave,        0x020CB560

        .org    0x02022544
@ rom: SKIP_ENTRY_NEW
@ Entry hook: the first 8 bytes of the New Game state handler.
@ was: push {r4, lr}; adds r4, r0, #0; bl newgame_prologue_call   (SKIP_ENTRY_ORIG)
        ldr     r3, lit_skip_cave       @ jump into the cave
        bx      r3
lit_skip_cave:
        .word   skip_cave + 1           @ Thumb bit set

        .org    0x020CB460
@ rom: SKIP_CAVE
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
skip:   ldr     r3, lit_copy            @ fill the load buffer, then the LOAD handler
        bx      r3
lit_game_state: .word GAME_STATE
lit_title_step: .word TITLE_STEP
lit_resume:     .word newgame_resume + 1
lit_copy:       .word skip_copy_cave + 1

        .org    0x020CB560
@ rom: SKIP_COPY_CAVE
@ r0 (the state object) is kept for the LOAD handler; r1-r3 are scratch, as in SKIP_CAVE.
        push    {r4}
        ldr     r1, lit_image
        ldr     r2, lit_load_buffer
        ldr     r3, lit_image_end
copy:   ldmia   r1!, {r4}
        stmia   r2!, {r4}
        cmp     r1, r3
        bne     copy
        pop     {r4}
        ldr     r3, lit_load
        bx      r3
        mov     r8, r8                  @ padding before the pool
lit_image:       .word GOLDEN_IMAGE
lit_load_buffer: .word LOAD_BUFFER
lit_image_end:   .word GOLDEN_IMAGE + GOLDEN_IMAGE_LEN
lit_load:        .word load_handler_body + 1
