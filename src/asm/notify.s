@ NOTIFY: on-screen notices (rom_patches.md "NOTIFY: on-screen notices").
@ The gameplay handler's per-frame call to the message tick goes through the
@ cave: with a request pending and the message system idle it opens the small
@ pickup popup on the client's text (or a vanilla message id) and clears the
@ request once the popup reaches its closing phase.
@ Hook at 0x02021DD4 (rom.py NOTIFY_HOOK_NEW), cave at 0x020CB600 (NOTIFY_CAVE),
@ notice block at 0x020CB700 (data.py NOTIFY_ADDR).

        .thumb

.equ NOTIFY_BLOCK,      0x020CB700      @ +0 u8 request (1 text / 2 id), +1 u8 state (cave), +2 u16 duration, +4 text buffer
.equ MSG_SYS,           0x027E02C4      @ message system (DTCM): +0xA u16 state (0 idle), +0xE u16 close-other flag
.equ MSG_OBJ,           0x027E02CC      @ message object = MSG_SYS + 8: +4 style, +0xC duration, +0x10 type, +0x11 phase, +0x1C text pointer
.equ CUTSCENE_FLAGS,    0x0214F502      @ u8: bit 0 = cutscene or scripted dialogue running
.equ INTERACT_FLAGS,    0x0214F506      @ u8: bit 1 = console or NPC interaction open
.equ show_pickup_msg,   0x020122D4      @ FUN_020122d4(id, duration): the "Found a Life Up!" popup
.equ msg_close_other,   0x02007524      @ FUN_02007524: closes another window first (called when MSG_SYS+0xE != 0)
.equ msg_obj_init,      0x020121DC      @ FUN_020121dc(obj)
.equ msg_obj_parse,     0x02012050      @ FUN_02012050(obj): copies the page to the decode buffer, parses controls
.equ msg_tick,          0x0201242C      @ FUN_0201242c: per-frame message tick
.equ notify_cave,       0x020CB600

        .org    0x02021DD4
@ rom.py: NOTIFY_HOOK_NEW
@ Gameplay handler FUN_02021bb0.
@ was: bl msg_tick   (NOTIFY_HOOK_ORIG)
        bl      notify_cave

        .org    0x020CB600
@ rom.py: NOTIFY_CAVE
        push    {r4, lr}
        ldr     r4, lit_notify
        ldrb    r0, [r4]                @ request
        cmp     r0, #0
        beq     done                    @ nothing pending
        ldr     r1, lit_msg_sys
        ldrb    r0, [r4, #1]            @ state: 1 = already launched
        cmp     r0, #0
        beq     check_idle
        ldrb    r0, [r1, #0x19]         @ MSG_OBJ+0x11 phase
        cmp     r0, #6                  @ 6 = closing: the notice is over
        bne     check_idle              @ (a reset to phase 0 relaunches it below)
        movs    r0, #0
        strb    r0, [r4]                @ clear request and state
        strb    r0, [r4, #1]
        b       done
check_idle:
        ldrh    r0, [r1, #0xa]          @ MSG_SYS+0xA state: 0 = free
        cmp     r0, #0
        bne     done
        ldr     r0, [r1, #0x18]         @ MSG_OBJ+0x10 type word: 0 = no message
        cmp     r0, #0
        bne     done
        ldr     r0, lit_cutscene
        ldrb    r0, [r0]
        lsrs    r0, r0, #1
        bcs     done                    @ cutscene running
        ldr     r0, lit_interact
        ldrb    r0, [r0]
        lsrs    r0, r0, #2
        bcs     done                    @ console or NPC dialogue open
        movs    r0, #1
        strb    r0, [r4, #1]            @ state = launched
        ldrb    r0, [r4]
        cmp     r0, #2
        bne     text
        ldrh    r0, [r4, #4]            @ request 2: vanilla message id at buffer+0
        ldrh    r1, [r4, #2]            @ duration
        bl      show_pickup_msg
        b       done
text:   adds    r0, r4, #4              @ request 1: replicate show_pickup_msg with a direct pointer
        str     r0, [r1, #0x24]         @ MSG_OBJ+0x1C = our text buffer
        ldrh    r0, [r4, #2]
        str     r0, [r1, #0x14]         @ MSG_OBJ+0xC = duration
        ldrh    r0, [r1, #0xe]          @ MSG_SYS+0xE: another window to close first
        cmp     r0, #0
        beq     skip_close
        bl      msg_close_other
skip_close:
        ldr     r0, lit_msg_obj
        bl      msg_obj_init
        ldr     r0, lit_msg_obj
        bl      msg_obj_parse
        ldr     r1, lit_msg_sys
        ldrb    r0, [r1, #0xc]          @ MSG_OBJ+4 style: 0 = small popup
        cmp     r0, #0
        beq     type_popup
        movs    r0, #1                  @ type 1 = dialogue window
        b       set_type
type_popup:
        movs    r0, #2                  @ type 2 = popup
set_type:
        str     r0, [r1, #0x18]         @ MSG_OBJ+0x10 = type
done:   bl      msg_tick                @ the displaced call, always
        pop     {r4, pc}
lit_notify:     .word NOTIFY_BLOCK
lit_msg_sys:    .word MSG_SYS
lit_cutscene:   .word CUTSCENE_FLAGS
lit_interact:   .word INTERACT_FLAGS
lit_msg_obj:    .word MSG_OBJ
