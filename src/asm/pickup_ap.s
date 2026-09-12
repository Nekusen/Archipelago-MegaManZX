@ PICKUP_AP: pickups replaced by AP items.
@ The gate routine says whether an entity stands for a pending multiworld
@ location (the `present` bitmap of the client's icon table); four hooks make
@ such a pickup only chime, skipping its vanilla effect, popup or disk label.
@ Cave at 0x020CB800 (rom.py PICKUP_AP_CAVE; entry offsets in PICKUP_AP_ENTRIES),
@ hooks in PICKUP_AP_HOOKS.

        .thumb

.equ ICON_TABLE,            0x02191460  @ client table (data.py ICON_TABLE_ADDR): +0 u8 subarea, +1 u8 flags (bit 0 valid), +0xA4 u8 present[32]
.equ PRESENT_OFF,           0xA4        @ data.py ICON_TABLE_PRESENT_OFF
.equ SUBAREA,               0x02108228  @ u8 current subarea id
.equ SPAWN_LIST_HEAD,       0x021081F4  @ ptr: active spawn records [+0 next, +4 entity, +8 u16 coords index]
.equ KIND_HANDLER_TABLES,   0x020EB8B0  @ u32[kind] -> u32[state] handler table
.equ play_sfx,              0x020058DC  @ FUN_020058dc(id)
.equ show_pickup_msg,       0x020122D4  @ FUN_020122d4(id, duration)
.equ disk_label_spawn,      0x020A3A38  @ FUN_020a3a38(ent): "E-04" label + chime; also the disk's state 2 handler
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

        .org    0x020CB800
@ rom.py: PICKUP_AP_CAVE
@ Six routines, each with its own literal pool; the offsets are PICKUP_AP_ENTRIES.

gate:                                   @ +0x00 apgate(ent) -> r0 = 1 if a pending AP location
        push    {r4, lr}
        ldr     r4, lit_gate_table
        ldrb    r1, [r4]                @ table subarea
        ldr     r2, lit_gate_subarea
        ldrb    r2, [r2]
        cmp     r1, r2
        bne     gate_no                 @ table is for another room
        ldrb    r1, [r4, #1]
        lsls    r1, r1, #31
        beq     gate_no                 @ table not valid
        ldr     r1, lit_gate_spawn_list
        ldr     r1, [r1]
gate_loop:
        cmp     r1, #0
        beq     gate_no                 @ entity has no spawn record
        ldr     r2, [r1, #4]
        cmp     r2, r0
        beq     gate_found
        ldr     r1, [r1]
        b       gate_loop
gate_found:
        ldrh    r2, [r1, #8]            @ coords index
        cmp     r2, #0x80
        bhs     gate_no                 @ outside the 128-entry bitmap
        lsrs    r3, r2, #3
        adds    r3, #PRESENT_OFF
        ldrb    r3, [r4, r3]            @ present[index >> 3]
        movs    r1, #7
        ands    r1, r2
        lsrs    r3, r1
        movs    r0, #1
        ands    r0, r3                  @ bit (index & 7)
        pop     {r4, pc}
gate_no:
        movs    r0, #0
        pop     {r4, pc}
        nop                             @ pad to a word
lit_gate_table:      .word ICON_TABLE
lit_gate_subarea:    .word SUBAREA
lit_gate_spawn_list: .word SPAWN_LIST_HEAD

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

        .org    0x020A30F4
@ rom.py: pickup_ap_hook(0)
@ Refill think FUN_020a309c, r5 = entity.
@ was: ldrb r0, [r5, #0x14]; cmp r0, #0
        bl      pickup_ap_refill

        .org    0x020A3ADE
@ rom.py: pickup_ap_hook(1)
@ Disk pickup FUN_020a3a6c.
@ was: bl disk_label_spawn
        bl      pickup_ap_disk

        .org    0x020A3CD4
@ rom.py: pickup_ap_hook(2)
@ Life Up branch of FUN_020a3c98 (14 bytes), r4 = entity.
@ was: movs r0, #0x24; bl play_sfx; ldr r0, =1065; movs r1, #0x5a; bl show_pickup_msg
        adds    r0, r4, #0
        bl      pickup_ap_lifeup
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8

        .org    0x020A3CEE
@ rom.py: pickup_ap_hook(3)
@ Sub Tank branch of FUN_020a3c98 (14 bytes), r4 = entity.
@ was: movs r0, #0x18; bl play_sfx; ldr r0, =1066; movs r1, #0x5a; bl show_pickup_msg
        adds    r0, r4, #0
        bl      pickup_ap_subtank
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
        mov     r8, r8
