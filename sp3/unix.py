from __future__ import annotations
import io
import typing


def uncompress(input: typing.IO[bytes], output: typing.IO[bytes]):
    header = True
    buffer = b""
    block_compressed = False
    maximum = 0
    end = 0
    mask = 0x1FF
    code = 0
    previous_code = 0
    final = 0
    bits = 9
    left = 7
    offset = 2
    skip = 0
    mid_code = False
    prefix: list[int] = [0] * 65536
    suffix: list[int] = [0] * 65536
    while True:
        buffer += input.read(4096)
        if len(buffer) == 0:
            break
        buffer = buffer[skip:]
        skip = 0
        if header:
            if len(buffer) < 3:
                raise Exception("uncompress requires at least 3 bytes")
            if buffer[0] != 0x1F or buffer[1] != 0x9D:
                raise Exception("bad magic number")
            block_compressed = (buffer[2] & 0x80) > 1
            if buffer[2] & 0x60 > 0:
                raise Exception("invalid header flags byte")
            maximum = buffer[2] & 0x1F
            if maximum < 9 or maximum > 16:
                raise Exception("invalid header flags byte")
            if len(buffer) == 3:
                return b""
            if len(buffer) == 4:
                raise Exception("unexpected end of stream")
            if maximum == 9:
                maximum = 10
            if (buffer[4] & 1) != 0:
                raise Exception("the first code must be a literal")
            code = buffer[4] >> 1
            previous_code = buffer[3] | ((buffer[4] & 0x1) << 8)
            final = previous_code
            output.write(bytes([final]))
            end = 0x100 if (buffer[2] & 0x80) > 0 else 0xFF
            header = False
            buffer = buffer[5:]
        while len(buffer) > 0:
            if mid_code:
                mid_code = False
            elif end >= mask and bits < maximum:
                remainder = offset % bits
                code = 0
                left = 0
                offset = 0
                mask = (mask << 1) + 1
                if remainder > 0:
                    skip = bits - remainder
                    if len(buffer) > skip:
                        buffer = buffer[skip:]
                    else:
                        buffer = b""
                        skip -= len(buffer)
                        bits += 1
                        break
                bits += 1
            code += buffer[0] << left
            buffer = buffer[1:]
            offset += 1
            left += 8
            if left < bits:
                mid_code = True
                continue
            masked_code = code & mask
            code >>= bits
            left -= bits
            if masked_code == 0xFF and block_compressed:
                remainder = offset % bits
                code = 0
                left = 0
                offset = 0
                mask = 0x1FF
                end = 0xFF
                if remainder > 0:
                    skip = bits - remainder
                    if len(buffer) > skip:
                        buffer = buffer[skip:]
                    else:
                        buffer = b""
                        skip -= len(buffer)
                        bits = 9
                        break
                bits = 9
                continue
            stack = []
            current_masked_code = masked_code
            if masked_code > end:
                if masked_code != end + 1 or previous_code > end:
                    raise Exception("invalid code")
                stack.append(final)
                masked_code = previous_code
            while masked_code > 0xFF:
                stack.append(suffix[masked_code])
                masked_code = prefix[masked_code]
            stack.append(masked_code)
            final = masked_code
            if end < mask:
                end += 1
                prefix[end] = previous_code
                suffix[end] = final
            previous_code = current_masked_code
            output.write(bytes(stack[::-1]))


if __name__ == "__main__":
    output = io.BytesIO()
    uncompress(
        io.BytesIO(
            b"\x1f\x9d\x90f\xde\xbc\x11\x13FN\xc0\x81\x05\x0f\x124(p\xa1\xc2\x82"
        ),
        output,
    )
    print(output.getvalue())
