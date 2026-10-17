#!/usr/bin/env python3
"""Regression check against hashes from an independent read-only CFB extractor.

Run with stock Python (no OCP needed):
python -B tools/patches/comprobar_ministreams.py --converter-root /path/to/pinned/source
"""
import argparse
import hashlib
from pathlib import Path
import sys
import zlib

EXPECTED = {
    "A-EjeInterior": (1831, "453d03cd7c2e19b62c2671049be799815c1f065ecdb38bde92c47c31379e8edc",
                     "ab7f0bfe4ce1c9f3c0a62ed58be998ca9e1646a8ce287f26afb0f9d913535403"),
    "B-Eje": (1842, "264a207f7a96b38cec97be5a73a47abc46229ea867cacbcc72cddcd7804f1d17",
              "7a68e4fb4a65513b79242e468293300a5b2edbacef007a5f388dcb490ec896cc"),
    "Z-VarillaACME": (1935, "940b4ee5d3b4156efeacffd2ec0ecc09eec595f7630a4ea420b17325c4f747a9",
                      "948f3ec2a1e82ec55faf5c0d4e3a3002a952df4c834a5c04e0a83d5eba782dd9"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--converter-root", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2] / "Modelos3D")
    args = parser.parse_args()
    sys.path.insert(0, str(args.converter_root.resolve()))
    from sldprt2step_lib.container import ole_cfb
    from ole_ministreams import install
    original = ole_cfb.OleContainerParser
    install()
    patched = ole_cfb.OleContainerParser
    for name, (size, stream_hash, parasolid_hash) in EXPECTED.items():
        raw = (args.source / (name + ".SLDPRT")).read_bytes()
        before = original(raw).extract_stream("Config-0-Partition").data
        result = patched(raw).extract_stream("Config-0-Partition")
        assert before != result.data, name + ": regression fixture no longer exposes the bug"
        assert len(result.data) == size
        assert hashlib.sha256(result.data).hexdigest() == stream_hash
        assert hashlib.sha256(zlib.decompress(result.data[28:])).hexdigest() == parasolid_hash
        assert raw[result.offset:result.offset + 16] == result.data[:16]
        print(name + ": MiniFAT extraction matches independent stream and Parasolid hashes")
    raw = (args.source / "A-Brazo.SLDPRT").read_bytes()
    assert (original(raw).extract_stream("Config-0-Partition").data ==
            patched(raw).extract_stream("Config-0-Partition").data)
    print("A-Brazo: regular FAT partition unchanged")


if __name__ == "__main__":
    main()
