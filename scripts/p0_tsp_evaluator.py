"""P0 TSP 实例解析、求解输入构造和独立评价；不执行候选程序。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys


PROJECT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT / "data" / "p0_tsp"
DATASET_COUNTS = {50: 5, 200: 10}
MAX_STDOUT_BYTES = 16 * 1024


class EvaluationError(ValueError):
    """输入、执行状态或解不符合 P0 合同时的可报告错误。"""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON 对象包含重复字段")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"JSON 不允许非有限数值：{value}")


def _parse_json(data: bytes | str) -> object:
    try:
        text = data.decode("utf-8") if isinstance(data, bytes) else data
        return json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise EvaluationError("invalid_json", "JSON 无法解析或包含重复字段、非有限数值。") from exc


def _finite_number(value: object) -> bool:
    return type(value) is int or (type(value) is float and math.isfinite(value))


def _coordinates(value: object) -> list:
    if type(value) is not list or not value:
        raise EvaluationError("invalid_coordinates", "坐标须为非空二维点数组。")
    for point in value:
        if (type(point) is not list or len(point) != 2
                or not all(_finite_number(number) for number in point)):
            raise EvaluationError("invalid_coordinates", "每个城市须有两个有限数值坐标。")
    return value


def _positive_time_limit(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise EvaluationError("invalid_metadata", "time_limit_ms 须为正整数。")
    return value


def load_instance(instance_id: str) -> list:
    """按冻结清单核验并加载一个 P0 实例，不加载候选代码。"""
    if type(instance_id) is not str:
        raise EvaluationError("invalid_instance", "实例 ID 须为字符串。")
    match = re.fullmatch(r"tsp(50|200)-(\d{3})", instance_id, flags=re.ASCII)
    if match is None:
        raise EvaluationError("invalid_instance", "实例 ID 须为 tsp50-NNN 或 tsp200-NNN。")
    size, index = map(int, match.groups())
    count = DATASET_COUNTS[size]
    if index >= count:
        raise EvaluationError("invalid_instance", "实例索引超出冻结数据范围。")

    try:
        manifest = _parse_json((DATA_DIR / "manifest.json").read_bytes())
        if type(manifest) is not dict or type(manifest.get("datasets")) is not list:
            raise EvaluationError("invalid_instance", "实例清单格式错误。")
        entries = [entry for entry in manifest["datasets"]
                   if type(entry) is dict and entry.get("instance_id_prefix") == f"tsp{size}-"]
        if len(entries) != 1:
            raise EvaluationError("invalid_instance", "实例清单缺少唯一的数据集条目。")
        entry = entries[0]
        digest = entry.get("sha256")
        if (entry.get("file") != f"train{size}.json"
                or entry.get("shape") != [count, size, 2]
                or type(digest) is not str or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
            raise EvaluationError("invalid_instance", "实例清单与 P0 规格不一致。")
        raw = (DATA_DIR / entry["file"]).read_bytes()
    except OSError as exc:
        raise EvaluationError("invalid_instance", "无法读取实例清单或数据文件。") from exc

    if hashlib.sha256(raw).hexdigest() != digest:
        raise EvaluationError("invalid_instance", "实例文件的 SHA-256 与清单不一致。")
    dataset = _parse_json(raw)
    if type(dataset) is not list or len(dataset) != count:
        raise EvaluationError("invalid_instance", "数据集的实例数量不符合合同。")
    for instance in dataset:
        points = _coordinates(instance)
        if len(points) != size or any(number < 0 or number >= 1 for point in points for number in point):
            raise EvaluationError("invalid_instance", "数据集的形状或坐标范围不符合合同。")
    return dataset[index]


def make_solver_input(coordinates: object, *, seed: int, time_limit_ms: int) -> dict:
    """构造合同规定的求解输入；不启动求解器。"""
    points = _coordinates(coordinates)
    if type(seed) is not int or seed < 0:
        raise EvaluationError("invalid_metadata", "seed 须为非负整数。")
    _positive_time_limit(time_limit_ms)
    return {"coordinates": points, "seed": seed, "time_limit_ms": time_limit_ms}


def evaluate_response(coordinates: object, stdout: bytes, *, exit_code: int,
                      elapsed_ms: int | float, time_limit_ms: int) -> dict:
    """验解并独立计算闭合路径长度；执行状态必须来自可信宿主。"""
    points = _coordinates(coordinates)
    _positive_time_limit(time_limit_ms)
    if type(exit_code) is not int or not _finite_number(elapsed_ms) or elapsed_ms < 0:
        raise EvaluationError("invalid_metadata", "退出码或运行时间无效。")
    if exit_code != 0:
        raise EvaluationError("execution_failed", "求解进程退出码非零。")
    if elapsed_ms > time_limit_ms:
        raise EvaluationError("timeout", "完整输出超过本作业时限。")
    if type(stdout) is not bytes:
        raise EvaluationError("invalid_output", "求解输出须为 UTF-8 JSON 字节。")
    if len(stdout) > MAX_STDOUT_BYTES:
        raise EvaluationError("stdout_limit", "求解标准输出超过 16 KiB。")

    response = _parse_json(stdout)
    if (type(response) is not dict or "tour" not in response
            or set(response) - {"tour", "objective"}):
        raise EvaluationError("invalid_output", "输出须包含 tour，且只能附带 objective。")
    if "objective" in response and not _finite_number(response["objective"]):
        raise EvaluationError("invalid_output", "声明的 objective 须为有限数值。")
    tour = response["tour"]
    if type(tour) is not list or len(tour) != len(points):
        raise EvaluationError("invalid_tour", "路径须恰好包含每个城市一次。")
    if any(type(city) is not int or city < 0 or city >= len(points) for city in tour):
        raise EvaluationError("invalid_tour", "路径城市编号必须是范围内的整数。")
    if len(set(tour)) != len(points):
        raise EvaluationError("invalid_tour", "路径包含重复城市或漏访城市。")

    try:
        objective = math.fsum(
            math.hypot(points[tour[i]][0] - points[tour[(i + 1) % len(tour)]][0],
                       points[tour[i]][1] - points[tour[(i + 1) % len(tour)]][1])
            for i in range(len(tour))
        )
    except (OverflowError, ValueError) as exc:
        raise EvaluationError("invalid_coordinates", "坐标无法计算有限的路径长度。") from exc
    if not math.isfinite(objective):
        raise EvaluationError("invalid_coordinates", "路径长度不是有限数值。")
    result = {"valid": True, "objective": objective}
    if "objective" in response:
        result["declared_objective"] = response["objective"]
    return result


def _add_instance_arguments(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--instance", help="冻结实例 ID，例如 tsp50-000")
    source.add_argument("--coordinates", help="用于核验的小实例坐标 JSON")
    parser.add_argument("--time-limit-ms", type=int, required=True, help="可信合同中的总时限")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="构造 P0 TSP 求解输入或独立评价输出，不运行求解器。")
    actions = parser.add_subparsers(dest="action", required=True)
    prepare = actions.add_parser("input", help="生成求解器输入 JSON")
    _add_instance_arguments(prepare)
    prepare.add_argument("--seed", type=int, required=True)
    evaluate = actions.add_parser("evaluate", help="从标准输入读取求解器输出并验解")
    _add_instance_arguments(evaluate)
    evaluate.add_argument("--exit-code", type=int, required=True, help="可信宿主记录的退出码")
    evaluate.add_argument("--elapsed-ms", type=float, required=True, help="可信宿主记录的总墙钟毫秒")
    args = parser.parse_args()

    try:
        coordinates = load_instance(args.instance) if args.instance else _parse_json(args.coordinates)
        if args.action == "input":
            result = make_solver_input(coordinates, seed=args.seed, time_limit_ms=args.time_limit_ms)
        else:
            stdout = sys.stdin.buffer.read(MAX_STDOUT_BYTES + 1)
            result = evaluate_response(coordinates, stdout, exit_code=args.exit_code,
                                       elapsed_ms=args.elapsed_ms, time_limit_ms=args.time_limit_ms)
    except EvaluationError as exc:
        print(json.dumps({"valid": False, "error": exc.code, "message": str(exc)}, ensure_ascii=True))
        return 1
    print(json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
