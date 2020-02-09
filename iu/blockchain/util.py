import uuid


def uuid_to_bip44_path(id_: uuid.UUID):
    parts = [int.from_bytes(id_.bytes[i:i+4], 'big') for i in range(0, 16, 4)]
    sign = 0
    paths = []
    for i, part in enumerate(parts):
        if part >= 0x80000000:
            sign += i << i
            paths.append(part - 0x80000000)
        else:
            paths.append(part)
    print([sign] + paths)
    return '/'.join(map(str, [sign] + paths))
