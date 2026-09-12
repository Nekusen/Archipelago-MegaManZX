"""BLZ, the DS code compression, with an optimal parse.

A greedy encoder leaves no room in the ARM9 slot for the caves; this one
minimises the stream and returns the region the game's loader expects.
"""

BLZ_HEADER_LEN = 0x4000        # never compressed: secure area and crt0
BLZ_MIN_MATCH = 3
BLZ_MAX_MATCH = 18
BLZ_MAX_DIST = 0x1002          # encoded displacement 0xFFF + 3


def _longest_matches(r):
    """Longest earlier match at every position of `r`, the data reversed.

    Returns (lengths, positions): the longest r[q:q+L], 3 <= L <= 18, that also
    occurs within 0x1002 bytes before q, and its nearest occurrence; 0 = none.
    """
    n = len(r)
    lengths = [0] * n
    where = [0] * n
    rfind = r.rfind
    for q in range(n - BLZ_MIN_MATCH + 1):
        lo = q - BLZ_MAX_DIST
        if lo < 0:
            lo = 0
        p = rfind(r[q:q + BLZ_MIN_MATCH], lo, q)
        if p < 0:
            continue
        best_len, best_pos = BLZ_MIN_MATCH, p
        # A longer match implies the shorter ones: the feasible lengths are a prefix, bisect it.
        low, high = BLZ_MIN_MATCH + 1, min(BLZ_MAX_MATCH, n - q)
        while low <= high:
            mid = (low + high) >> 1
            p = rfind(r[q:q + mid], lo, q)
            if p < 0:
                high = mid - 1
            else:
                best_len, best_pos = mid, p
                low = mid + 1
        lengths[q] = best_len
        where[q] = best_pos
    return lengths, where


def _parse(r, lengths):
    """Token per position (0 = literal, L = reference of L bytes) that minimises the stream.

    A literal costs 9 bits and a reference 17: their bytes plus the flag bit.
    """
    n = len(r)
    cost = [0] * (n + 1)
    pick = [0] * n
    for i in range(n - 1, -1, -1):
        best, tok = cost[i + 1] + 9, 0
        for ln in range(BLZ_MIN_MATCH, lengths[i] + 1):
            c = cost[i + ln] + 17
            if c < best:
                best, tok = c, ln
        cost[i] = best
        pick[i] = tok
    return pick


def compress(data):
    """BLZ region (raw prefix, backwards stream, footer) for the ARM9 minus its header.

    Returns None if the region would not be smaller than the data.
    """
    r = data[::-1]                       # encode the reversed data forwards
    n = len(r)
    lengths, where = _longest_matches(r)
    pick = _parse(r, lengths)

    # `gain` is how far the in-place decoder is ahead after each token (output
    # minus input, flag bytes included); the stream is cut at its first peak.
    stream = bytearray()
    i = 0
    tokens = 0
    gain = 0
    best_gain = 0
    cut_stream = 0                       # stream bytes kept
    cut_data = 0                         # reversed-data bytes covered by them
    while i < n:
        flag_at = len(stream)
        stream.append(0)
        gain -= 1
        flags = 0
        for bit in range(7, -1, -1):
            if i >= n:
                break
            ln = pick[i]
            if ln:
                disp = i - where[i] - BLZ_MIN_MATCH
                flags |= 1 << bit
                stream.append(((ln - BLZ_MIN_MATCH) << 4) | (disp >> 8))
                stream.append(disp & 0xFF)
                i += ln
                gain += ln - 2
            else:
                stream.append(r[i])
                i += 1
            tokens += 1
            if gain > best_gain:
                best_gain = gain
                cut_stream = len(stream)
                cut_data = i
        stream[flag_at] = flags
    if best_gain <= 0:
        return None

    raw = data[:n - cut_data]            # forward order: the uncut start
    body = bytes(stream[:cut_stream])[::-1]
    padding = (-(len(raw) + len(body))) & 3
    footer_len = 8 + padding
    total = len(raw) + len(body) + footer_len
    if total >= n:
        return None
    return b"".join((
        raw, body, b"\xFF" * padding,
        (len(body) + footer_len).to_bytes(3, "little"),
        bytes([footer_len]),
        (n - total).to_bytes(4, "little"),
    ))
