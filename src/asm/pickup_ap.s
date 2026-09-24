@ PICKUP_AP: pickups replaced by AP items.
@ The gate routine says whether an entity stands for a pending multiworld
@ location; the answer comes from the pickup table section (pickup_table.s),
@ so the gate only jumps there. Five hooks make such a pickup only chime,
@ skipping its vanilla effect, popup or disk label. The disk the H-1 balloon
@ holds has no spawn record, so it asks the gate about its carrier.
@ Cave at 0x020CB800 (rom/pickups.py PICKUP_AP_CAVE; entry offsets in PICKUP_AP_ENTRIES),
@ hooks in PICKUP_AP_HOOKS.

        .thumb

.equ pickup_gate,           0x02191B30  @ pickup_table.s gate(ent) -> 1 if pending (PICKUP_TABLE_ADDR + PICKUP_TABLE_ENTRIES["gate"])
.equ KIND_HANDLER_TABLES,   0x020EB8B0  @ u32[kind] -> u32[state] handler table
.equ play_sfx,              0x020058DC  @ FUN_020058dc(id)
.equ show_pickup_msg,       0x020122D4  @ FUN_020122d4(id, duration)
.equ disk_label_spawn,      0x020A3A38  @ FUN_020a3a38(ent): "E-04" label + chime; also the disk's state 2 handler
.equ carried_label_spawn,   0x020A3FC0  @ FUN_020a3fc0(ent): the same for a carried disk (kind 3)
.equ refill_think_epilogue, 0x020A31AC  @ FUN_020a309c after the effect switch
.equ SFX_DISK_CHIME,        0x1A
.equ SFX_LIFE_UP,           0x24
.equ SFX_SUB_TANK,          0x18
.equ MSG_LIFE_UP,           1065        @ "Found a Life Up!"
.equ MSG_SUB_TANK,          1066
.equ pickup_ap_refill,      0x020CB858  @ cave + PICKUP_AP_ENTRIES["refill"]
.equ pickup_ap_disk,        0x020CB87C  @ cave + PICKUP_AP_ENTRIES["disk"]
.equ pickup_ap_lifeup,      0x020CB8AC  @ cave + PICKUP_AP_ENTRIES["lifeup"]
.equ pickup_ap_subtank,     0x020CB8CC  @ cave + PICKUP_AP_ENTRIES["subtank"]
.equ pickup_ap_carried,     0x020CB8EC  @ cave + PICKUP_AP_ENTRIES["carried"]

        .org    0x020CB800
@ rom: PICKUP_AP_CAVE
@ Seven routines, each with its own literal pool when it needs one; the offsets are PICKUP_AP_ENTRIES.

gate:                                   @ +0x00 apgate(ent) -> r0 = 1 if a pending AP location
        ldr     r3, lit_gate
        bx      r3                      @ the pickup table's gate returns to our caller
lit_gate:       .word pickup_gate + 1
        .word   0                       @ the per-room bitmap test that lived here (18 words)
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0
        .word   0

tail:                                   @ +0x50 shared ending: chime and return
        movs    r0, #SFX_DISK_CHIME
        bl      play_sfx
        pop     {r4, pc}

refill:                                 @ +0x58 hook 0x020A30F4 (refill think, r5 = entity)
        push    {lr}
        movs    r0, r5
        bl      gate
        cmp     r0, #0
        beq     refill_vanilla
        movs    r0, #SFX_DISK_CHIME
        bl      play_sfx
        pop     {r0}                    @ drop the return address
        ldr     r0, lit_refill_epilogue
        bx      r0                      @ skip the effect switch
refill_vanilla:
        pop     {r1}
        ldrb    r0, [r5, #0x14]         @ the displaced instructions: role, then the caller's cmp
        cmp     r0, #0
        bx      r1                      @ return with the flags intact
lit_refill_epilogue: .word refill_think_epilogue + 1

disk:                                   @ +0x7C hook 0x020A3ADE (disk pickup, r0 = entity)
        push    {r4, lr}
        movs    r4, r0
        bl      gate
        cmp     r0, #0
        bne     disk_ap
        movs    r0, r4
        bl      disk_label_spawn        @ vanilla: label + chime
        pop     {r4, pc}
disk_ap:
        movs    r0, #4
        str     r0, [r4, #0x10]         @ entity state = 4 (release), as the label routine does
        ldrb    r0, [r4, #9]            @ entity kind
        lsls    r1, r0, #2
        ldr     r0, lit_disk_handlers
        ldr     r1, [r0, r1]            @ handler table of the kind
        ldr     r0, [r4, #0x10]
        lsls    r0, r0, #2
        ldr     r0, [r1, r0]
        str     r0, [r4, #0x18]         @ entity handler = table[state]
        b       tail
        nop                             @ pad to a word
lit_disk_handlers:   .word KIND_HANDLER_TABLES

lifeup:                                 @ +0xAC hook 0x020A3CD4 (Life Up pickup, r0 = entity)
        push    {r4, lr}
        movs    r4, r0
        bl      gate
        cmp     r0, #0
        bne     tail                    @ AP: chime only
        movs    r0, #SFX_LIFE_UP        @ vanilla: jingle and popup (the displaced code)
        bl      play_sfx
        ldr     r0, lit_msg_life_up
        movs    r1, #0x5a
        bl      show_pickup_msg
        pop     {r4, pc}
lit_msg_life_up:     .word MSG_LIFE_UP

subtank:                                @ +0xCC hook 0x020A3CEE (Sub Tank pickup, r0 = entity)
        push    {r4, lr}
        movs    r4, r0
        bl      gate
        cmp     r0, #0
        bne     tail                    @ AP: chime only
        movs    r0, #SFX_SUB_TANK       @ vanilla: jingle and popup (the displaced code)
        bl      play_sfx
        ldr     r0, lit_msg_sub_tank
        movs    r1, #0x5a
        bl      show_pickup_msg
        pop     {r4, pc}
lit_msg_sub_tank:    .word MSG_SUB_TANK

carried:                                @ +0xEC hook 0x020A4058 (carried disk pickup, r0 = entity)
        push    {r4, lr}
        movs    r4, r0
        ldr     r0, [r4, #0x30]         @ the carrier owns the spawn record
        bl      gate
        cmp     r0, #0
        bne     disk_ap                 @ AP: release and chime like a placed disk
        movs    r0, r4
        bl      carried_label_spawn     @ vanilla: label + chime
        pop     {r4, pc}

        .org    0x020A30F4
@ rom: pickup_ap_hook(0)
@ Refill think FUN_020a309c, r5 = entity.
@ was: ldrb r0, [r5, #0x14]; cmp r0, #0
        bl      pickup_ap_refill

        .org    0x020A3ADE
@ rom: pickup_ap_hook(1)
@ Disk pickup FUN_020a3a6c.
@ was: bl disk_label_spawn
        bl      pickup_ap_disk

        .org    0x020A3CD4
@ rom: pickup_ap_hook(2)
@ Life Up branch of FUN_020a3c98 (14 bytes), r4 = entity.
@ was: movs r0, #0x24; bl play_sfx; ldr r0, =1065; movs r1, #0x5a; bl show_pickup_msg
        adds    r0, r4, #0
        bl      pickup_ap_lifeup
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8

        .org    0x020A3CEE
@ rom: pickup_ap_hook(3)
@ Sub Tank branch of FUN_020a3c98 (14 bytes), r4 = entity.
@ was: movs r0, #0x18; bl play_sfx; ldr r0, =1066; movs r1, #0x5a; bl show_pickup_msg
        adds    r0, r4, #0
        bl      pickup_ap_subtank
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8

        .org    0x020A4058
@ rom: pickup_ap_hook(4)
@ Carried disk think FUN_020a3ff4, r0 = entity.
@ was: bl carried_label_spawn
        bl      pickup_ap_carried
