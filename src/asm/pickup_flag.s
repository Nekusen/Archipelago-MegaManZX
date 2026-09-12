@ Life Up and Sub Tank: collected versus capacity.
@ The capacity bytes 0x0214FC77 (Life Ups) and 0x0214FC78 (Sub Tanks) doubled as
@ the "slot collected" record. The pickup now sets bit 4 + slot (high nibble),
@ the spawn gates test that bit and the vanilla capacity effects are removed.
@ Six in-place patches (rom.py PICKUP_FLAG_PATCH); no cave.

        .thumb

        .org    0x02045014
@ rom.py: PICKUP_FLAG_PATCH[0][2]
@ was: movs r1, #1
        movs    r1, #0x10               @ grant_life_up (FUN_02045008): bit 4 + slot

        .org    0x0204501E
@ rom.py: PICKUP_FLAG_PATCH[1][2]
@ was: bl FUN_0204502c   (+4 max HP)
        mov     r8, r8                  @ grant_life_up: no maximum HP increase
        mov     r8, r8

        .org    0x02044CAA
@ rom.py: PICKUP_FLAG_PATCH[2][2]
@ was: movs r4, #1
        movs    r4, #0x10               @ grant_sub_tank (FUN_02044ca4): bit 4 + slot

        .org    0x02044CD4
@ rom.py: PICKUP_FLAG_PATCH[3][2]
@ was: strb r2, [r1, r0]   (tank contents = 0)
        mov     r8, r8                  @ grant_sub_tank: tank contents untouched

        .org    0x020A3E30
@ rom.py: PICKUP_FLAG_PATCH[4][2]
@ was: movs r1, #1
        movs    r1, #0x10               @ Life Up spawn gate (FUN_020a3dd4): despawn on bit 4 + slot

        .org    0x020A3E86
@ rom.py: PICKUP_FLAG_PATCH[5][2]
@ was: movs r1, #1
        movs    r1, #0x10               @ Sub Tank spawn gate: despawn on bit 4 + slot
