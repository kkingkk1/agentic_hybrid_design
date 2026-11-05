"""按 ReEvo 的 TSP 训练实例规则生成或核验 P0 数据。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys


PROJECT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT / "data" / "p0_tsp"

# 数量和种子分别对应 ReEvo 的 tsp_aco 与 tsp_gls 训练实例。
SPECS = {
    50: (5, 1234, "56e109bc69c145779555da56649794643e3fbc2b085f82b063f601a4e85d3de3"),
    200: (10, 5, "a64babca6b3a12c436e95267f87c31096cf8c1d97e38ae81f68e3e2c4d6dbbf9"),
}


def legacy_random_state(seed: int) -> random.Random:
    """用 CPython 的 MT19937 重现 NumPy 旧版 RandomState 的整数种子流。"""
    if sys.implementation.name != "cpython":
        raise RuntimeError("实例生成器需要 CPython；其他解释器尚未核验。")
    state = [seed & 0xFFFFFFFF]
    for index in range(1, 624):
        previous = state[-1]
        state.append((1812433253 * (previous ^ (previous >> 30)) + index) & 0xFFFFFFFF)
    rng = random.Random(0)
    rng.setstate((3, tuple(state + [624]), None))
    return rng


def generate(size: int) -> bytes:
    """返回指定规模的 UTF-8 JSON 数据，错误时拒绝输出。"""
    count, seed, expected_sha256 = SPECS[size]
    rng = legacy_random_state(seed)
    instances = [
        [[rng.random(), rng.random()] for _ in range(size)]
        for _ in range(count)
    ]
    data = (json.dumps(instances, ensure_ascii=True, separators=(",", ":"), allow_nan=False)
            + "\n").encode("utf-8")
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise RuntimeError("生成结果与已核验的参考数据不一致；请检查 Python 随机数实现。")
    return data


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="生成或核验 RoCo/ReEvo 规格的 P0 TSP 实例。")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--size", type=int, choices=sorted(SPECS), help="生成此节点规模的完整数据集")
    action.add_argument("--verify", action="store_true", help="重新生成并核对现有的两个数据文件")
    parser.add_argument("--output", type=Path, help="新建项目内的输出文件；默认写入标准输出")
    options = parser.parse_args()
    if options.verify and options.output is not None:
        parser.error("--verify 不能与 --output 一起使用。")

    try:
        if options.verify:
            for size in SPECS:
                path = DATA_DIR / f"train{size}.json"
                if path.read_bytes() != generate(size):
                    raise ValueError(f"数据与生成结果不一致：{path}")
                print(f"通过：{path.relative_to(PROJECT)}")
            return 0

        data = generate(options.size)
        if options.output is None:
            sys.stdout.buffer.write(data)
        else:
            output = options.output.resolve()
            if not output.is_relative_to(PROJECT):
                raise ValueError("输出文件必须位于本项目内。")
            with output.open("xb") as stream:
                stream.write(data)
            print(f"已生成：{output.relative_to(PROJECT)}", file=sys.stderr)
        return 0
    except FileExistsError:
        print("实例生成失败：输出文件已存在，未覆盖。", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"实例生成失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
