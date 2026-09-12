@ Pickup mailbox (rom_patches.md "Pickup mailbox").
@ The animation-advance call of the refill think handler goes through the cave,
@ which calls the original and, when the entity was just collected, finds its
@ spawn record and appends (subarea, coords index, role) to a ring the client polls.
@ Hook at 0x020A30A2 (rom.py PICKUP_MAILBOX_HOOK_NEW), cave at 0x020CB4A0
@ (PICKUP_MAILBOX_CAVE), mailbox at 0x020CB500 (data.py PICKUP_MAILBOX_ADDR).

        .thumb

.equ SUBAREA,               0x02108228  @ u8 current subarea id
.equ SPAWN_LIST_HEAD,       0x021081F4  @ ptr: active spawn records [+0 next, +4 entity, +8 u16 coords index]
.equ entity_anim_tick,      0x0200FC0C  @ FUN_0200fc0c(ent): per-frame animation advance
.equ PICKUP_MAILBOX,        0x020CB500  @ u32 counter, then 8 x u32 [u8 subarea, u8 index, u8 role, 0]
.equ pickup_mailbox_cave,   0x020CB4A0

        .org    0x020A30A2
@ rom.py: PICKUP_MAILBOX_HOOK_NEW
@ Prologue of the refill think handler (FUN_020a309c); r5 = entity.
@ was: bl entity_anim_tick   (PICKUP_MAILBOX_HOOK_ORIG)
        bl      pickup_mailbox_cave

        .org    0x020CB4A0
@ rom.py: PICKUP_MAILBOX_CAVE
        push    {r4, lr}
        bl      entity_anim_tick        @ the displaced call (icon_retry.s re-hooks this bl)
        movs    r0, #0x94
        ldr     r0, [r5, r0]            @ entity +0x94: collision flags
        lsrs    r0, r0, #3
        bcc     done                    @ bit 2 clear: not collected this frame
        movs    r0, #0xc0
        ldr     r0, [r5, r0]            @ entity +0xC0: collider pointer (the player)
        cmp     r0, #0
        beq     done
        ldr     r1, lit_spawn_list
        ldr     r1, [r1]
loop:   cmp     r1, #0                  @ walk the active spawn records
        beq     done                    @ no record: enemy or NPC drop, not reported
        ldr     r2, [r1, #4]
        cmp     r2, r5
        beq     found
        ldr     r1, [r1]
        b       loop
found:  ldrh    r2, [r1, #8]            @ coords index -> byte 1
        lsls    r2, r2, #8
        ldr     r0, lit_subarea
        ldrb    r0, [r0]
        orrs    r2, r0                  @ subarea -> byte 0
        ldrb    r0, [r5, #0x14]         @ entity +0x14: role
        lsls    r0, r0, #16
        orrs    r2, r0                  @ role -> byte 2
        ldr     r3, lit_mailbox
        ldr     r0, [r3]                @ counter
        movs    r4, #7
        ands    r4, r0
        lsls    r4, r4, #2
        adds    r4, r4, r3
        str     r2, [r4, #4]            @ ring[counter & 7] = entry
        adds    r0, #1
        str     r0, [r3]                @ counter += 1
done:   pop     {r4, pc}
lit_spawn_list: .word SPAWN_LIST_HEAD
lit_subarea:    .word SUBAREA
lit_mailbox:    .word PICKUP_MAILBOX
