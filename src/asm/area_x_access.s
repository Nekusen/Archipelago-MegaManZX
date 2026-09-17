@ Area X access.
@ The Report routine (0x02031028) sets the X-1 destination bit, 0x02104629
@ bit 0, in the branches of Locate Giro (state 0x95) and Pass The Test (state
@ 0x99) once both missions are completed (0x021045DE bit 7 and 0x021045E0
@ bit 0). The destination belongs to the "Transerver Access - Area X" item and
@ to the hub script, which sets it when the player stands on the X floor, as
@ for every other area. The store of each branch becomes a no-op; the
@ completion bits, the test and the branch to the common tail are untouched
@ (rom/pickups.py AREA_X_ACCESS_PATCH); no cave.

        .thumb

        .org    0x02031254
@ rom: AREA_X_ACCESS_PATCH[0][2]
@ was: strb r2, [r1, #0x1d]   (AREA_X_ACCESS_PATCH[0][1]): r1 = 0x0210460C, r2 = byte | 1
        mov     r8, r8                  @ no X-1 bit on the Locate Giro report

        .org    0x0203128C
@ rom: AREA_X_ACCESS_PATCH[1][2]
@ was: strb r2, [r0, #0x1d]   (AREA_X_ACCESS_PATCH[1][1]): r0 = 0x0210460C, r2 = byte | 1
        mov     r8, r8                  @ no X-1 bit on the Pass The Test report
