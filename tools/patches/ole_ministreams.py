"""Explicit SCARA adapter for the pinned sldprt2step OLE reader.

2026-10-14: add MS-CFB MiniFAT reads for streams below the header cutoff.
Upstream: BlinkingSun/sldprt2step, fa954124f4f126e0c465c8f96454978ac80b812e.
The original module is neither edited nor redistributed here. This adapter
subclasses its reader in the converter subprocess; geometry code is unchanged.
Upstream attribution/license are preserved alongside this file.
"""
import struct


def install():
    from sldprt2step_lib.container import ole_cfb

    original = ole_cfb.OleContainerParser

    class OleWithMiniStreams(original):
        def extract_stream(self, stream_name):
            entry = next((e for e in self.entries if e.type == 2 and
                          e.name == stream_name and e.start_sector >= 0), None)
            if entry is None:
                return None
            cutoff = struct.unpack_from("<I", self.buf, 56)[0]
            if entry.size >= cutoff:
                return super().extract_stream(stream_name)
            if cutoff != 4096 or struct.unpack_from("<H", self.buf, 32)[0] != 6:
                raise ValueError("Unsupported CFB mini-stream header")
            root = next((e for e in self.entries if e.type == 5), None)
            if root is None or root.start_sector < 0:
                raise ValueError("CFB root mini-stream missing")
            first, count = struct.unpack_from("<iI", self.buf, 60)
            if first < 0 or count <= 0:
                raise ValueError("CFB MiniFAT missing")
            raw_fat = self.read_chain(first)
            if len(raw_fat) < count * self.sector_size:
                raise ValueError("Truncated CFB MiniFAT")
            raw_fat = raw_fat[:count * self.sector_size]
            mini_fat = struct.unpack("<%di" % (len(raw_fat) // 4), raw_fat)
            mini_stream = self.read_chain(root.start_sector)[:root.size]
            chunks, visited, sector = [], set(), entry.start_sector
            while sector >= 0:
                if sector in visited or sector >= len(mini_fat):
                    raise ValueError("Invalid or cyclic CFB mini-sector chain")
                visited.add(sector)
                offset = sector * 64
                if offset + 64 > len(mini_stream):
                    raise ValueError("CFB mini-sector outside root stream")
                chunks.append(mini_stream[offset:offset + 64])
                sector = mini_fat[sector]
            data = b"".join(chunks)
            if sector != -2 or len(data) < entry.size:
                raise ValueError("Truncated or unterminated CFB mini-stream")
            # Preserve OleStreamResult.offset as a physical file offset for the
            # first mini-sector, although the complete stream may be fragmented.
            root_sector = root.start_sector
            regular_steps, within = divmod(entry.start_sector * 64, self.sector_size)
            for _ in range(regular_steps):
                if root_sector < 0 or root_sector >= len(self.fat):
                    raise ValueError("Invalid CFB root stream chain")
                root_sector = self.fat[root_sector]
            if root_sector < 0:
                raise ValueError("Truncated CFB root stream chain")
            physical = (root_sector + 1) * self.sector_size + within
            return ole_cfb.OleStreamResult(entry.name, data[:entry.size], physical)

    ole_cfb.OleContainerParser = OleWithMiniStreams

