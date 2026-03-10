#!/usr/bin/env python3
"""Report experiment environment details for paper-ready methods text."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _run(cmd: list[str]) -> Tuple[int, str, str]:
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _parse_os_release() -> Optional[str]:
    os_release = Path("/etc/os-release")
    if not os_release.exists():
        return None

    lines = os_release.read_text(encoding="utf-8", errors="ignore").splitlines()
    parsed: Dict[str, str] = {}
    for line in lines:
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"')
    return parsed.get("PRETTY_NAME")


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _human_gb_from_bytes(num_bytes: Optional[float]) -> Optional[float]:
    if num_bytes is None:
        return None
    return num_bytes / 1_000_000_000.0


def _read_mem_total_bytes_linux() -> Optional[float]:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None

    for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2:
                kb = _safe_float(parts[1])
                if kb is not None:
                    return kb * 1024.0
    return None


def _collect_cpu_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "model": None,
        "cores": None,
        "frequency_ghz": None,
    }

    if shutil.which("lscpu"):
        code, out, _ = _run(["lscpu"])
        if code == 0 and out:
            kv: Dict[str, str] = {}
            for raw_line in out.splitlines():
                if ":" not in raw_line:
                    continue
                key, value = raw_line.split(":", 1)
                kv[key.strip()] = value.strip()

            info["model"] = kv.get("Model name")

            cores_per_socket = _safe_float(kv.get("Core(s) per socket"))
            sockets = _safe_float(kv.get("Socket(s)"))
            cpus = _safe_float(kv.get("CPU(s)"))
            if cores_per_socket and sockets:
                info["cores"] = int(cores_per_socket * sockets)
            elif cpus:
                info["cores"] = int(cpus)

            mhz = _safe_float(kv.get("CPU max MHz")) or _safe_float(kv.get("CPU MHz"))
            if mhz is not None and mhz > 0:
                info["frequency_ghz"] = mhz / 1000.0

    if info["model"] is None and shutil.which("sysctl"):
        code, out, _ = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        if code == 0 and out:
            info["model"] = out.strip()
        code, out, _ = _run(["sysctl", "-n", "hw.physicalcpu"])
        if code == 0 and out.isdigit():
            info["cores"] = int(out)
        code, out, _ = _run(["sysctl", "-n", "hw.cpufrequency"])
        if code == 0 and out.isdigit():
            hz = _safe_float(out)
            if hz:
                info["frequency_ghz"] = hz / 1_000_000_000.0

    if info["model"] and info["frequency_ghz"] is None:
        match = re.search(r"@\s*([0-9.]+)\s*GHz", str(info["model"]))
        if match:
            info["frequency_ghz"] = _safe_float(match.group(1))

    if info["cores"] is None:
        count = os.cpu_count()
        if count:
            info["cores"] = int(count)

    return info


def _storage_type(name: str, rota: Optional[str], transport: Optional[str], model: Optional[str]) -> str:
    name_lower = name.lower()
    transport_lower = (transport or "").lower()
    model_lower = (model or "").lower()

    if name_lower.startswith("nvme") or transport_lower == "nvme" or "nvme" in model_lower:
        return "NVMe SSD"
    if rota == "0":
        return "SSD"
    if rota == "1":
        return "HDD"
    return "disk"


def _collect_storage_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "device": None,
        "model": None,
        "size_bytes": None,
        "size_gb": None,
        "type": None,
    }

    root_source: Optional[str] = None
    if shutil.which("df"):
        code, out, _ = _run(["df", "--output=source", "/"])
        if code == 0 and out:
            lines = [line.strip() for line in out.splitlines() if line.strip()]
            if len(lines) >= 2:
                root_source = lines[-1]

    disk_name: Optional[str] = None
    if root_source and root_source.startswith("/dev/") and shutil.which("lsblk"):
        code, out, _ = _run(["lsblk", "-no", "PKNAME", root_source])
        if code == 0 and out:
            disk_name = out.splitlines()[0].strip()
        if not disk_name:
            disk_name = Path(root_source).name

    if shutil.which("lsblk"):
        if disk_name:
            code, out, _ = _run(
                ["lsblk", "-b", "-dn", "-o", "NAME,SIZE,ROTA,TRAN,MODEL,TYPE", f"/dev/{disk_name}"]
            )
            if code == 0 and out:
                row = out.splitlines()[0].split(None, 5)
                if len(row) >= 5:
                    name = row[0]
                    size = _safe_float(row[1])
                    rota = row[2] if len(row) > 2 else None
                    transport = row[3] if len(row) > 3 else None
                    model = row[4] if len(row) > 4 else None
                    info["device"] = f"/dev/{name}"
                    info["model"] = model
                    info["size_bytes"] = size
                    info["size_gb"] = _human_gb_from_bytes(size)
                    info["type"] = _storage_type(name, rota, transport, model)
                    return info

        code, out, _ = _run(["lsblk", "-b", "-dn", "-o", "NAME,SIZE,ROTA,TRAN,MODEL,TYPE"])
        if code == 0 and out:
            candidates = []
            for line in out.splitlines():
                parts = line.split(None, 5)
                if len(parts) < 6:
                    continue
                name, size_raw, rota, transport, model, dtype = parts
                if dtype != "disk":
                    continue
                size = _safe_float(size_raw)
                if size is None:
                    continue
                candidates.append((size, name, rota, transport, model))

            if candidates:
                size, name, rota, transport, model = max(candidates, key=lambda x: x[0])
                info["device"] = f"/dev/{name}"
                info["model"] = model
                info["size_bytes"] = size
                info["size_gb"] = _human_gb_from_bytes(size)
                info["type"] = _storage_type(name, rota, transport, model)
                return info

    if shutil.which("df"):
        code, out, _ = _run(["df", "-B1", "--output=size", "/"])
        if code == 0 and out:
            lines = [line.strip() for line in out.splitlines() if line.strip()]
            if len(lines) >= 2:
                size = _safe_float(lines[-1])
                info["size_bytes"] = size
                info["size_gb"] = _human_gb_from_bytes(size)
    info["type"] = "storage"
    return info


def _docker_version() -> Optional[str]:
    if not shutil.which("docker"):
        return None
    code, out, err = _run(["docker", "--version"])
    text = out or err
    if code != 0 or not text:
        return None
    match = re.search(r"Docker version\s+([^,]+)", text)
    return match.group(1) if match else text.strip()


def _python_version() -> str:
    return platform.python_version()

def _collect_environment() -> Dict[str, Any]:
    os_name = _parse_os_release() or platform.platform()
    kernel = platform.release()

    cpu = _collect_cpu_info()
    ram_bytes = _read_mem_total_bytes_linux()
    if ram_bytes is None and shutil.which("sysctl"):
        code, out, _ = _run(["sysctl", "-n", "hw.memsize"])
        if code == 0:
            ram_bytes = _safe_float(out)

    storage = _collect_storage_info()

    return {
        "os_name": os_name,
        "kernel_version": kernel,
        "cpu": cpu,
        "memory_bytes": ram_bytes,
        "memory_gb": _human_gb_from_bytes(ram_bytes),
        "storage": storage,
        "software": {
            "docker": _docker_version(),
            "python": _python_version(),
        },
    }


def _format_float_or_unknown(value: Optional[float], decimals: int = 1) -> str:
    if value is None:
        return "unknown"
    return f"{value:.{decimals}f}"


def _article_for(word: str) -> str:
    if not word:
        return "a"
    return "an" if word[0].lower() in {"a", "e", "i", "o", "u"} else "a"


def _sentence(env: Dict[str, Any]) -> str:
    cpu_model = env["cpu"].get("model") or "unknown CPU"
    cpu_cores = env["cpu"].get("cores")
    cpu_freq = env["cpu"].get("frequency_ghz")

    cpu_parts = [cpu_model]
    inner_parts = []
    if cpu_cores is not None:
        inner_parts.append(f"{cpu_cores} cores")
    if cpu_freq is not None:
        inner_parts.append(f"{cpu_freq:.1f} GHz")
    if inner_parts:
        cpu_parts.append(f"({', '.join(inner_parts)})")
    cpu_text = " ".join(cpu_parts)

    ram_gb = env.get("memory_gb")
    ram_text = f"{ram_gb:.1f} GB RAM" if ram_gb is not None else "unknown RAM capacity"

    storage = env.get("storage") or {}
    storage_size = storage.get("size_gb")
    storage_type = storage.get("type") or "storage"
    if storage_size is None:
        storage_text = f"unknown-capacity {storage_type}"
    else:
        storage_text = f"{storage_size:.0f} GB {storage_type}"

    docker = env["software"].get("docker") or "unknown"
    python = env["software"].get("python") or "unknown"
    article = _article_for(cpu_model)
    return (
        f"All experiments were conducted on a workstation running {env['os_name']} with "
        f"{article} {cpu_text}, {ram_text} and a {storage_text}, "
        f"Kernel version {env['kernel_version']}. "
        f"Software versions: Docker {docker}, Python {python}."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect OS/hardware/software conditions for paper reporting."
    )
    parser.add_argument(
        "--format",
        choices=["sentence", "json", "both"],
        default="both",
        help="Output format.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Optional file path to write output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = _collect_environment()
    sentence = _sentence(env)
    json_output = json.dumps(env, indent=2)

    if args.format == "sentence":
        text = sentence
    elif args.format == "json":
        text = json_output
    else:
        text = f"{sentence}\n\n{json_output}"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
