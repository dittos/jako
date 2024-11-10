from collections import defaultdict


def detect_repeated_text(text: str, n: int) -> tuple[int, str] | None:
    if len(text) <= n:
        return None

    # 123456789..., n = 3
    # ~~~
    #  ~~~
    #   ~~~
    #      ...

    powers = [2**x for x in range(n)]

    # calculate first hash
    substr = text[:n]
    rolling_hash = 0
    for i, c in enumerate(substr):
        rolling_hash += powers[i] * ord(c)

    hashes = defaultdict(list)
    hashes[rolling_hash] = [0]

    for i in range(1, len(text) - n):
        rolling_hash = (rolling_hash - (powers[0] * ord(text[i - 1]))) // 2 + (powers[-1] * ord(text[i + n - 1]))

        candidates = hashes.get(rolling_hash)
        if candidates:
            substr = text[i:i + n]
            for offset in candidates:
                if text[offset:offset + n] == substr:
                    return (offset, substr)

        hashes[rolling_hash].append(i)
    
    return None
