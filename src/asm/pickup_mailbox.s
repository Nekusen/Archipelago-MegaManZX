@ Pickup mailbox.
@ The animation-advance call of the refill think handler goes through the cave,
@ which calls the original and, when the entity was just collected, records the
@ pickup in the `collected` bitmap of the pickup table section (pickup_table.s),
@ which the client polls.
@ Hook at 0x020A30A2 (rom/pickups.py PICKUP_MAILBOX_HOOK_NEW), cave at 0x020CB4A0
@ (PICKUP_MAILBOX_CAVE).

        .thumb

.equ entity_anim_tick,      0x0200FC0C  @ FUN_0200fc0c(ent): per-frame animation advance
.equ pickup_collect,        0x02191B58  @ pickup_table.s collect(ent) (PICKUP_TABLE_ADDR + PICKUP_TABLE_ENTRIES["collect"])
.equ pickup_mailbox_cave,   0x020CB4A0

        .org    0x020A30A2
@ rom: PICKUP_MAILBOX_HOOK_NEW
@ Prologue of the refill think handler (FUN_020a309c); r5 = entity.
@ was: bl entity_anim_tick   (PICKUP_MAILBOX_HOOK_ORIG)
        bl      pickup_mailbox_cave

        .org    0x020CB4A0
@ rom: PICKUP_MAILBOX_CAVE
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
        movs    r0, r5
        ldr     r1, lit_collect
        blx     r1                      @ a drop without a spawn record has no entry: nothing recorded
done:   pop     {r4, pc}
        mov     r8, r8                  @ pad to a word
lit_collect:    .word pickup_collect + 1
