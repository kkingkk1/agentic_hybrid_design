from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from .problem import Customer

def _is_int(s: str) -> bool:
    try:
        int(s)
        return True
    except ValueError:
        return False

def _is_float(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False

def load_solomon_instance(path: str | Path) -> Tuple[List[Customer], float]:
    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    cap_idx = None
    for i, line in enumerate(lines):
        if "CAPACITY" in line.upper():
            cap_idx = i
            break
    if cap_idx is None:
        raise ValueError("Nie znaleziono sekcji VEHICLE/CAPACITY w pliku instancji")

    capacity = None
    for j in range(cap_idx + 1, len(lines)):
        parts = lines[j].strip().split()
        if len(parts) >= 2 and _is_int(parts[0]) and _is_float(parts[1]):
            capacity = float(parts[1])
            break
    if capacity is None:
        raise ValueError("Nie udało się sparsować CAPACITY")

    cust_idx = None
    for i, line in enumerate(lines):
        if line.strip().upper().startswith("CUSTOMER"):
            cust_idx = i
            break
    if cust_idx is None:
        raise ValueError("Nie znaleziono sekcji CUSTOMER w pliku instancji")

    rows: List[Tuple[int, float, float, float, float, float, float]] = []
    for j in range(cust_idx + 1, len(lines)):
        parts = lines[j].strip().split()
        if len(parts) < 7:
            continue
        if not _is_int(parts[0]):
            continue
        if not all(_is_float(x) for x in parts[1:7]):
            continue

        cust_no = int(parts[0])
        x = float(parts[1])
        y = float(parts[2])
        demand = float(parts[3])
        ready = float(parts[4])
        due = float(parts[5])
        service = float(parts[6])
        rows.append((cust_no, x, y, demand, ready, due, service))

    if not rows:
        raise ValueError("Nie znaleziono wierszy klientów (7 kolumn numerycznych)")

    by_id = {r[0]: r for r in rows}
    if 0 not in by_id:
        raise ValueError("Brak depotu o numerze klienta 0")

    max_id = max(by_id.keys())
    missing = [i for i in range(0, max_id + 1) if i not in by_id]
    if missing:
        raise ValueError(f"Brak ciągłości numerów klientów: missing={missing[:10]}")

    customers: List[Customer] = []
    for i in range(0, max_id + 1):
        cust_no, x, y, demand, ready, due, service = by_id[i]
        customers.append(
            Customer(
                idx=cust_no,
                x=x,
                y=y,
                demand=demand,
                ready_time=ready,
                due_time=due,
                service_time=service,
            )
        )

    return customers, capacity