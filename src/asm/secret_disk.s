@ Secret Disks as multiworld items.
@ The game keeps two twin bit series per disk: "collected" and "read in the
@ database", with twin set/test routines. The world's disks move to the "read"
@ series (their pickup and their "already taken" test), so the "collected"
@ series is written by nobody but the client, one bit per Secret Disk received,
@ and the database viewer lists exactly the disks received. The viewer's own
@ "mark read" call is dropped and its three "is read" tests answer yes, so every
@ disk received shows its entry at once. Sites in rom/pickups.py SECRET_DISK_PATCH.

        .thumb

.equ disk_set_collected,    0x02009370  @ FUN_02009370(series, n): set the collected bit
.equ disk_test_collected,   0x0200932C  @ FUN_0200932c(series, n): collected?
.equ disk_set_read,         0x020092F4  @ FUN_020092f4(series, n): set the read bit
.equ disk_test_read,        0x020092B0  @ FUN_020092b0(series, n): read?

        .org    0x020A3AA0
@ rom: SECRET_DISK_PATCH[0][2]
@ Placed disk touched (disk_pickup FUN_020a3a6c). was: bl disk_set_collected
        bl      disk_set_read

        .org    0x020A401A
@ rom: SECRET_DISK_PATCH[1][2]
@ Carried disk touched (the H-1 balloon, FUN_020a3ff4). was: bl disk_set_collected
        bl      disk_set_read

        .org    0x020A3B76
@ rom: SECRET_DISK_PATCH[2][2]
@ Placed disk init (FUN_020a3b6c): do not spawn a taken disk. was: bl disk_test_collected
        bl      disk_test_read

        .org    0x020A414E
@ rom: SECRET_DISK_PATCH[3][2]
@ Carrier init: the disk it holds is taken. was: bl disk_test_collected
        bl      disk_test_read

        .org    0x0202AEE2
@ rom: SECRET_DISK_PATCH[4][2]
@ Database viewer, entry opened. was: bl disk_set_read
        mov     r8, r8
        mov     r8, r8

        .org    0x0202B5D2
@ rom: SECRET_DISK_PATCH[5][2]
@ Database viewer, text under the cursor. was: bl disk_test_read
        movs    r0, #1
        mov     r8, r8

        .org    0x0202BE66
@ rom: SECRET_DISK_PATCH[6][2]
@ Database viewer, entry icons. was: bl disk_test_read
        movs    r0, #1
        mov     r8, r8

        .org    0x0202BF6E
@ rom: SECRET_DISK_PATCH[7][2]
@ Database viewer, entry icons (second drawer). was: bl disk_test_read
        movs    r0, #1
        mov     r8, r8
