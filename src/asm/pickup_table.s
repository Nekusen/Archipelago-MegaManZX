@ Pickup table: the per-seed table of pickup locations baked into the ROM.
@ Every pickup that stands for a location has an entry (coords index, slot,
@ icon code, flags) under its subarea; two bitmaps by slot sit next to the
@ table: `checked`, written by the client when the server has the location,
@ and `collected`, written by the game when a pickup is taken. The three
@ routines at the start of the section serve the icon caves (LOOKUP), the
@ PICKUP_AP gate and the mailbox cave, which only trampoline here.
@ Section at 0x02191B00 (rom/table.py PICKUP_TABLE_CODE; offsets in PICKUP_TABLE_ENTRIES).

        .thumb

.equ SUBAREA,               0x02108228  @ u8 current subarea id
.equ SPAWN_LIST_HEAD,       0x021081F4  @ ptr: active spawn records [+0 next, +4 entity, +8 u16 coords index]
.equ TABLE,                 0x02191B00  @ data.py PICKUP_TABLE_ADDR
.equ FLAGS,                 0x02191C00  @ TABLE + rom/table.py FLAGS_OFF: u8, 1 = icons off
.equ CHECKED,               0x02191C04  @ TABLE + CHECKED_OFF: u8[32] by slot, location already sent
.equ COLLECTED,             0x02191C24  @ TABLE + COLLECTED_OFF: u8[32] by slot, pickup taken since boot
.equ INDEX,                 0x02191C60  @ TABLE + INDEX_OFF: u16 start[129], first entry of each subarea
.equ ENTRIES,               0x02191D64  @ TABLE + ENTRIES_OFF: [u8 coords index, u8 slot, u8 code, u8 flags]
.equ INDEX_SUBAREAS,        128
.equ ENTRY_RESPAWNS,        1           @ flags bit 0: the pickup respawns (a refill)

        .org    0x02191B00
@ rom: PICKUP_TABLE_CODE
lookup:                                 @ +0x00 lookup(ent) -> r0 = animation of the AP set, or -1
        push    {r4, lr}
        bl      find
        cmp     r0, #0
        beq     l_none
        movs    r4, r0
        ldr     r0, lit_flags
        ldrb    r0, [r0]
        cmp     r0, #0
        bne     l_none                  @ icons switched off by the client
        ldrb    r0, [r4, #1]            @ slot
        bl      checked
        cmp     r0, #0
        bne     l_none                  @ already sent: vanilla look
        ldrb    r0, [r4, #2]            @ code
        subs    r0, #1                  @ code - 1 = animation; 0 (no icon) becomes -1
        pop     {r4, pc}
l_none: movs    r0, #0
        mvns    r0, r0                  @ -1
        pop     {r4, pc}
        mov     r8, r8                  @ pad to a word
lit_flags:      .word FLAGS

gate:                                   @ +0x30 gate(ent) -> r0 = 1 if the pickup stands for a pending location
        push    {r4, lr}
        bl      find
        cmp     r0, #0
        beq     g_no
        movs    r4, r0
        ldrb    r0, [r4, #3]            @ flags
        lsrs    r0, r0, #1
        bcc     g_yes                   @ never respawns: pending even after a collect
        ldrb    r0, [r4, #1]            @ slot
        bl      checked
        movs    r1, #1
        eors    r0, r1                  @ pending = not sent
        pop     {r4, pc}
g_yes:  movs    r0, #1
        pop     {r4, pc}
g_no:   movs    r0, #0
        pop     {r4, pc}
        mov     r8, r8                  @ pad to a word

collect:                                @ +0x58 collect(ent): set the pickup's bit in `collected`
        push    {r4, lr}
        bl      find
        cmp     r0, #0
        beq     c_done
        ldrb    r1, [r0, #1]            @ slot
        ldr     r2, lit_collected
        lsrs    r3, r1, #3
        adds    r2, r2, r3              @ byte of the slot
        movs    r3, #7
        ands    r3, r1
        movs    r1, #1
        lsls    r1, r3                  @ bit of the slot
        ldrb    r3, [r2]
        orrs    r3, r1
        strb    r3, [r2]
c_done: pop     {r4, pc}
        mov     r8, r8                  @ pad to a word
lit_collected:  .word COLLECTED

find:                                   @ +0x80 find(ent) -> r0 = the entry of the entity's location, or 0
        push    {r4, r5, lr}
        ldr     r1, lit_spawn_list
        ldr     r1, [r1]
f_loop: cmp     r1, #0
        beq     f_none                  @ entity has no spawn record
        ldr     r2, [r1, #4]
        cmp     r2, r0
        beq     f_found
        ldr     r1, [r1]
        b       f_loop
f_found:
        ldrh    r2, [r1, #8]            @ coords index
        ldr     r3, lit_subarea
        ldrb    r3, [r3]
        cmp     r3, #INDEX_SUBAREAS
        bhs     f_none
        ldr     r4, lit_index
        lsls    r3, r3, #1
        ldrh    r0, [r4, r3]            @ start[subarea]
        adds    r3, #2
        ldrh    r5, [r4, r3]            @ start[subarea + 1]
        ldr     r4, lit_entries
        lsls    r0, r0, #2
        adds    r0, r0, r4              @ first entry of the room
        lsls    r5, r5, #2
        adds    r5, r5, r4              @ one past its last entry
f_scan: cmp     r0, r5
        bhs     f_none
        ldrb    r3, [r0]
        cmp     r3, r2
        beq     f_ret
        adds    r0, #4
        b       f_scan
f_none: movs    r0, #0
f_ret:  pop     {r4, r5, pc}
lit_spawn_list: .word SPAWN_LIST_HEAD
lit_subarea:    .word SUBAREA
lit_index:      .word INDEX
lit_entries:    .word ENTRIES

checked:                                @ +0xD4 checked(slot) -> r0 = 1 if the location is marked as sent
        ldr     r2, lit_checked
        lsrs    r3, r0, #3
        ldrb    r2, [r2, r3]            @ byte of the slot
        movs    r3, #7
        ands    r3, r0
        lsrs    r2, r3
        movs    r0, #1
        ands    r0, r2                  @ bit of the slot
        bx      lr
        mov     r8, r8                  @ pad to a word
lit_checked:    .word CHECKED
