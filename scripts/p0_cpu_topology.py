"""只读核验 P0 本机 CPU 拓扑，并给出实例到物理核的固定映射。"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import struct
import sys


PROJECT = Path(__file__).resolve().parents[1]
EXPECTED_P_CORES = [(i, i + 1) for i in range(0, 16, 2)]
EXPECTED_E_CORES = [(i,) for i in range(16, 28)]
ERROR_INSUFFICIENT_BUFFER = 122


def _query_buffer(function, arguments, get_error):
    size = wintypes.DWORD()
    if function(None, 0, ctypes.byref(size), *arguments) or get_error() != ERROR_INSUFFICIENT_BUFFER:
        raise OSError("查询 Windows CPU 拓扑大小失败。")
    if not 0 < size.value <= 1024 * 1024:
        raise ValueError("Windows 返回的 CPU 拓扑大小无效。")
    buffer = ctypes.create_string_buffer(size.value)
    if not function(buffer, size.value, ctypes.byref(size), *arguments):
        raise OSError(f"读取 Windows CPU 拓扑失败：{get_error()}")
    return buffer.raw[:size.value]


def read_windows_topology():
    """分别读取物理核关系、CPU 集合以及当前进程可用掩码。"""
    if os.name != "nt":
        raise OSError("P0 核映射检查仅支持当前 Windows 主机。")
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise OSError("P0 核映射检查需要 64 位 Python。")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetLogicalProcessorInformationEx.argtypes = [
        ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)
    ]
    kernel.GetLogicalProcessorInformationEx.restype = wintypes.BOOL
    kernel.GetSystemCpuSetInformation.argtypes = [
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        wintypes.HANDLE, wintypes.DWORD,
    ]
    kernel.GetSystemCpuSetInformation.restype = wintypes.BOOL
    kernel.GetProcessAffinityMask.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)
    ]
    kernel.GetProcessAffinityMask.restype = wintypes.BOOL

    needed = wintypes.DWORD()
    if kernel.GetLogicalProcessorInformationEx(0, None, ctypes.byref(needed)) or ctypes.get_last_error() != 122:
        raise OSError("查询 Windows 物理核信息大小失败。")
    if not 0 < needed.value <= 1024 * 1024:
        raise ValueError("Windows 返回的物理核信息大小无效。")
    buffer = ctypes.create_string_buffer(needed.value)
    if not kernel.GetLogicalProcessorInformationEx(0, buffer, ctypes.byref(needed)):
        raise OSError(f"读取 Windows 物理核信息失败：{ctypes.get_last_error()}")
    raw = buffer.raw[:needed.value]
    cores = []
    offset = 0
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError("物理核记录头不完整。")
        relationship, size = struct.unpack_from("<II", raw, offset)
        if size < 48 or offset + size > len(raw) or relationship != 0:
            raise ValueError("物理核记录格式无效。")
        group_count = struct.unpack_from("<H", raw, offset + 30)[0]
        if group_count != 1:
            raise ValueError("当前合同只支持每个物理核位于一个处理器组。")
        mask, group = struct.unpack_from("<QH", raw, offset + 32)
        logical = tuple(i for i in range(64) if mask & (1 << i))
        if not logical:
            raise ValueError("物理核没有逻辑处理器。")
        cores.append({"group": group, "logical": logical, "efficiency": raw[offset + 9]})
        offset += size

    process = kernel.GetCurrentProcess()
    raw = _query_buffer(kernel.GetSystemCpuSetInformation, (process, 0), ctypes.get_last_error)
    cpu_sets = {}
    offset = 0
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError("CPU 集合记录头不完整。")
        size, kind = struct.unpack_from("<II", raw, offset)
        if size < 8 or offset + size > len(raw):
            raise ValueError("CPU 集合记录格式无效。")
        if kind == 0:
            if size < 32:
                raise ValueError("CPU 集合记录不完整。")
            identifier = struct.unpack_from("<I", raw, offset + 8)[0]
            group = struct.unpack_from("<H", raw, offset + 12)[0]
            logical = raw[offset + 14]
            key = (group, logical)
            if key in cpu_sets:
                raise ValueError("CPU 集合包含重复逻辑处理器。")
            cpu_sets[key] = {
                "id": identifier,
                "core_index": raw[offset + 15],
                "efficiency": raw[offset + 18],
                "flags": raw[offset + 19],
            }
        offset += size

    process_mask = ctypes.c_size_t()
    system_mask = ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(process, ctypes.byref(process_mask), ctypes.byref(system_mask)):
        raise OSError(f"读取进程 CPU 掩码失败：{ctypes.get_last_error()}")
    return cores, cpu_sets, process_mask.value, system_mask.value


def select_mapping(cores, cpu_sets, process_mask, system_mask):
    """拓扑发生变化或 CPU 不可用时拒绝沿用冻结映射。"""
    if any(core["group"] != 0 for core in cores):
        raise ValueError("出现额外处理器组，须重新确定核映射。")
    e_cores = sorted(core["logical"] for core in cores if core["efficiency"] == 0)
    p_cores = sorted(core["logical"] for core in cores if core["efficiency"] == 1)
    if e_cores != EXPECTED_E_CORES or p_cores != EXPECTED_P_CORES or len(cores) != 20:
        raise ValueError("物理核拓扑与 P0 合同不一致，须重新确定核映射。")
    if set(cpu_sets) != {(0, i) for i in range(28)}:
        raise ValueError("CPU 集合与 P0 合同不一致，须重新确定核映射。")
    if len({row["id"] for row in cpu_sets.values()}) != 28:
        raise ValueError("CPU 集合编号重复，须重新确定核映射。")

    core_indices = set()
    for core in cores:
        rows = [cpu_sets[(0, logical)] for logical in core["logical"]]
        if any(row["efficiency"] != core["efficiency"] for row in rows):
            raise ValueError("两套 Windows 接口的核心类型不一致。")
        indices = {row["core_index"] for row in rows}
        if len(indices) != 1 or indices & core_indices:
            raise ValueError("两套 Windows 接口的物理核关系不一致。")
        core_indices.update(indices)

    slots = list(range(16, 28)) + [8, 10, 12, 14]
    for logical in slots:
        if not (process_mask & (1 << logical)) or not (system_mask & (1 << logical)):
            raise ValueError(f"逻辑处理器 {logical} 不在当前进程的可用掩码中。")
        if cpu_sets[(0, logical)]["flags"] & 0x02:
            raise ValueError(f"逻辑处理器 {logical} 已被 CPU 集合分配，须重新核验。")

    workers = [
        {"slot": i, "logical_processor": logical, "core_type": "E" if i < 12 else "P",
         "cpu_set_id": cpu_sets[(0, logical)]["id"],
         "parked": bool(cpu_sets[(0, logical)]["flags"] & 0x01)}
        for i, logical in enumerate(slots)
    ]
    instances = []
    for size, count in ((50, 5), (200, 10)):
        for index in range(count):
            worker = workers[len(instances)]
            instances.append({"instance_id": f"tsp{size}-{index:03}", "planned_seed": 0,
                              "slot": worker["slot"], "logical_processor": worker["logical_processor"]})
    return {
        "processor_group": 0,
        "physical_cores": len(cores),
        "logical_processors": len(cpu_sets),
        "workers": workers,
        "reserved_p_cores": [list(core) for core in p_cores[:4]],
        "unassigned_p_siblings": [9, 11, 13, 15],
        "instances": instances,
        "scope": "映射只约束本项目作业，不表示操作系统已为其独占处理器。",
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        mapping = select_mapping(*read_windows_topology())
        manifest = json.loads((PROJECT / "data" / "p0_tsp" / "manifest.json").read_text(encoding="utf-8"))
        datasets = [(item["shape"], item["instance_id_prefix"]) for item in manifest["datasets"]]
        if datasets != [([5, 50, 2], "tsp50-"), ([10, 200, 2], "tsp200-")]:
            raise ValueError("实例清单已改变，须重新确定实例与核的映射。")
    except (OSError, ValueError, KeyError, TypeError, struct.error) as exc:
        print(f"P0 核映射检查失败：{exc}", file=sys.stderr)
        return 1
    print(json.dumps(mapping, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
