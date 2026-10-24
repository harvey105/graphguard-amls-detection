"""Conservative native Windows admission, isolation and pressure monitoring.

This bounds our process tree; it cannot diagnose cooling, power or hardware
faults. There is deliberately no switch to disable protection for a big run.
The mutex lasts until Python/kernel exit: Spark.stop() can leave its JVM alive.
"""

from __future__ import annotations

import atexit
import ctypes as C
from ctypes import wintypes as W
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import threading
import time

import psutil

GIB = 1024 ** 3
MUTEX_NAME = r"Local\GraphGuard-Spark-single-workload-v1"


@dataclass(frozen=True)
class ResourcePolicy:
    job_bytes: int
    reserve_bytes: int
    max_heap_gib: int
    workers: int = 2
    cpu_percent: int = 100

    @classmethod
    def for_memory(cls, total: int):
        budget = int(min(10 * GIB, total * 0.32))
        reserve = int(max(4 * GIB, total * 0.25))
        heap = min(6, budget // GIB - 3)
        if heap < 2:
            raise RuntimeError("Insufficient RAM for the protected Spark profile (about 16 GiB required)")
        # The user authorizes the available CPUs. Concurrent Spark tasks must
        # still fit the unchanged heap; sort/hash operators spill to disk.
        logical = len(psutil.Process().cpu_affinity()) if os.name == "nt" else (os.cpu_count() or 1)
        workers = max(1, min(logical, heap * 4))
        return cls(budget, reserve, heap, workers)

    def spark_limits(self, requested_heap: str, requested_master: str):
        match = re.fullmatch(r"(\d+)([gGmM])", requested_heap)
        if not match:
            raise ValueError("Spark heap must use integer g or m units")
        mib = int(match[1]) * (1024 if match[2].lower() == "g" else 1)
        if mib < 512:
            raise ValueError("Spark heap must be at least 512 MiB")
        heap = f"{min(mib, self.max_heap_gib * 1024)}m"
        master = re.fullmatch(r"local\[(\*|\d+)\]", requested_master)
        if not master:
            raise ValueError("Protected workstation supports only local[n] Spark; no unbounded/cluster launch")
        workers = self.workers if master[1] == "*" else min(self.workers, int(master[1]))
        if workers < 1:
            raise ValueError("At least one worker required")
        return heap, workers

    @classmethod
    def for_workload(cls, total: int, requested_heap: str):
        """A smaller heap gets a smaller hard job cap, with the same OS reserve.

        The default/full profile is unchanged. A process admitted with a smaller
        profile cannot later upgrade its heap or job limit in the same kernel.
        """
        base = cls.for_memory(total)
        heap, _ = base.spark_limits(requested_heap, f"local[{base.workers}]")
        mib = int(heap[:-1])
        if mib >= base.max_heap_gib * 1024:
            return base
        rounded_gib = (mib + 1023) // 1024
        budget = min(base.job_bytes, (rounded_gib + 3) * GIB)
        return cls(budget, base.reserve_bytes, min(base.max_heap_gib, rounded_gib),
                   min(base.workers, rounded_gib * 4), base.cpu_percent)


def pressure_reason(policy: ResourcePolicy, available: int, commit_free: int,
                    disk_free: int, cpu_percent: float) -> str | None:
    if available < policy.reserve_bytes:
        return "Physical RAM reserve exhausted"
    if commit_free < policy.reserve_bytes:
        return "Windows commit reserve exhausted"
    if disk_free < 5 * GIB:
        return "Temporary/workspace disk reserve below 5 GiB"
    # High CPU is authorized work, not memory pressure. RAM/commit/disk remain
    # mandatory stop conditions, independently of CPU utilization.
    return None


class MemoryStatus(C.Structure):
    _fields_ = [("length", W.DWORD), ("load", W.DWORD)] + [
        (name, C.c_ulonglong) for name in (
            "total_phys", "avail_phys", "total_page", "avail_page",
            "total_virtual", "avail_virtual", "avail_extended")]


class BasicLimits(C.Structure):
    _fields_ = [("process_time", C.c_longlong), ("job_time", C.c_longlong),
        ("flags", W.DWORD), ("minimum_working_set", C.c_size_t),
        ("maximum_working_set", C.c_size_t), ("active_process_limit", W.DWORD),
        ("affinity", C.c_size_t), ("priority", W.DWORD), ("scheduling", W.DWORD)]


class IOLimits(C.Structure):
    _fields_ = [(name, C.c_ulonglong) for name in (
        "read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]


class ExtendedLimits(C.Structure):
    _fields_ = [("basic", BasicLimits), ("io", IOLimits),
        ("process_memory", C.c_size_t), ("job_memory", C.c_size_t),
        ("peak_process_memory", C.c_size_t), ("peak_job_memory", C.c_size_t)]


class CPULimits(C.Structure):
    _fields_ = [("flags", W.DWORD), ("rate", W.DWORD)]


class AccountingInfo(C.Structure):
    _fields_ = [(name, C.c_longlong) for name in
                ("user_time", "kernel_time", "period_user_time", "period_kernel_time")] + [
                    (name, W.DWORD) for name in
                    ("page_faults", "total_processes", "active_processes", "terminated_processes")]


class WindowsGuard:
    def __init__(self, requested_heap="6g"):
        if os.name != "nt":
            raise RuntimeError("Hardware protection requires native Windows")
        self.api = C.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateMutexW": ([W.LPVOID, W.BOOL, W.LPCWSTR], W.HANDLE),
            "WaitForSingleObject": ([W.HANDLE, W.DWORD], W.DWORD),
            "ReleaseMutex": ([W.HANDLE], W.BOOL),
            "CreateJobObjectW": ([W.LPVOID, W.LPCWSTR], W.HANDLE),
            "SetInformationJobObject": ([W.HANDLE, C.c_int, W.LPVOID, W.DWORD], W.BOOL),
            "QueryInformationJobObject": ([W.HANDLE, C.c_int, W.LPVOID, W.DWORD, W.LPVOID], W.BOOL),
            "GetCurrentProcess": ([], W.HANDLE),
            "AssignProcessToJobObject": ([W.HANDLE, W.HANDLE], W.BOOL),
            "IsProcessInJob": ([W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)], W.BOOL),
            "TerminateJobObject": ([W.HANDLE, W.UINT], W.BOOL),
            "GlobalMemoryStatusEx": ([C.POINTER(MemoryStatus)], W.BOOL),
            "CloseHandle": ([W.HANDLE], W.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        self.mutex = self.api.CreateMutexW(None, False, MUTEX_NAME)
        if not self.mutex:
            raise C.WinError(C.get_last_error())
        wait = self.api.WaitForSingleObject(self.mutex, 0)
        if wait not in (0, 0x80):  # acquired or abandoned by an exited process
            self.api.CloseHandle(self.mutex)
            raise RuntimeError("Another GraphGuard workload holds the lock. Finish/close its kernel first.")
        self.job = None
        self.assigned = False
        self.finished = threading.Event()
        try:
            # Catch Spark started outside our mutex/another repository clone.
            for process in psutil.process_iter(["pid", "name", "cmdline"]):
                if (process.info["name"] or "").lower() == "java.exe" and any(
                    "org.apache.spark.deploy.SparkSubmit" in part for part in process.info["cmdline"] or []):
                    raise RuntimeError(f"Existing Spark JVM PID {process.pid}; close it before starting another workload")
            initial = self.memory()
            self.policy = ResourcePolicy.for_workload(initial.total_phys, requested_heap)
            self.disks = list(dict.fromkeys([Path(tempfile.gettempdir()).anchor, Path(__file__).resolve().anchor]))
            if initial.avail_phys < self.policy.reserve_bytes + self.policy.job_bytes:
                raise RuntimeError("Not enough free RAM for the job budget AND OS reserve; close applications, do not raise limits")
            if initial.avail_page < self.policy.reserve_bytes + self.policy.job_bytes:
                raise RuntimeError("Not enough Windows commit headroom for a protected Spark run")
            if self.disk_free() < 12 * GIB:
                raise RuntimeError("At least 12 GiB free on temp/workspace drives required for spilling")
            self.job = self.api.CreateJobObjectW(None, None)
            if not self.job:
                raise C.WinError(C.get_last_error())
            self.limits = ExtendedLimits()
            # Commit budget + inherited CPU affinity + below-normal priority.
            # Do not set BREAKAWAY_OK. Children (JVM/workers) inherit the job.
            self.limits.basic.flags = 0x200 | 0x10 | 0x20 | 0x2000
            # Preserve every CPU allowed by Windows. Task concurrency is set
            # separately; Java GC/JIT can use other available cores as needed.
            allowed = psutil.Process().cpu_affinity()
            self.allowed_cpus = allowed
            self.limits.basic.affinity = sum(1 << core for core in allowed)
            self.limits.basic.priority = 0x4000  # BELOW_NORMAL_PRIORITY_CLASS
            self.limits.job_memory = self.policy.job_bytes
            self.set_information(9, self.limits)
            self.set_information(15, CPULimits(0x1 | 0x4, self.policy.cpu_percent * 100))
            if not self.api.AssignProcessToJobObject(self.job, self.api.GetCurrentProcess()):
                raise C.WinError(C.get_last_error())  # no unprotected fallback
            self.assigned = True
            self.started = time.monotonic()
            self.minimum_available = initial.avail_phys
            self.maximum_host_cpu = 0.0
            self.maximum_job_cpu = 0.0
            self.thread = threading.Thread(target=self._watch, name="GraphGuard-resource-watchdog", daemon=True)
            self.thread.start()
            atexit.register(self.close)
            print(f"[RESOURCE] One workload; CPU capacity {self.policy.cpu_percent}%; "
                  f"{len(allowed)} CPUs available / {self.policy.workers} Spark tasks; job commit cap {self.policy.job_bytes/GIB:.1f} GiB; "
                  f"RAM reserve {self.policy.reserve_bytes/GIB:.1f} GiB", flush=True)
        except BaseException:
            self.close()
            raise

    def set_information(self, kind, value):
        if not self.api.SetInformationJobObject(self.job, kind, C.byref(value), C.sizeof(value)):
            raise C.WinError(C.get_last_error())

    def memory(self):
        status = MemoryStatus()
        status.length = C.sizeof(status)
        if not self.api.GlobalMemoryStatusEx(C.byref(status)):
            raise C.WinError(C.get_last_error())
        return status

    def disk_free(self):
        return min(shutil.disk_usage(drive).free for drive in self.disks)

    def snapshot(self):
        measured = ExtendedLimits()
        if not self.api.QueryInformationJobObject(self.job, 9, C.byref(measured), C.sizeof(measured), None):
            raise C.WinError(C.get_last_error())
        accounting = AccountingInfo()
        if not self.api.QueryInformationJobObject(self.job, 1, C.byref(accounting), C.sizeof(accounting), None):
            raise C.WinError(C.get_last_error())
        elapsed = max(time.monotonic() - self.started, 0.001)
        cpu_seconds = (accounting.user_time + accounting.kernel_time) / 10_000_000
        return {"cpu_hard_cap_percent": self.policy.cpu_percent, "max_logical_cpus": len(self.allowed_cpus),
            "spark_task_slots": self.policy.workers,
            "job_cpu_seconds": round(cpu_seconds, 3), "job_wall_seconds": round(elapsed, 3),
            "average_job_cpu_percent": round(100 * cpu_seconds / elapsed / (os.cpu_count() or 1), 2),
            "maximum_job_cpu_percent": round(self.maximum_job_cpu, 2),
            "job_commit_cap_gib": round(self.policy.job_bytes/GIB, 2),
            "peak_job_commit_gib": round(measured.peak_job_memory/GIB, 2),
            "minimum_available_ram_gib": round(self.minimum_available/GIB, 2),
            "maximum_host_cpu_percent": self.maximum_host_cpu,
            "thermal_sensor": "CPU temperature unavailable; not a thermal/power hardware guarantee"}

    def _watch(self):
        strikes = 0
        psutil.cpu_percent()  # prime the host counter
        while not self.finished.wait(2):
            try:
                status = self.memory()
                cpu = psutil.cpu_percent()
                self.minimum_available = min(self.minimum_available, status.avail_phys)
                self.maximum_host_cpu = max(self.maximum_host_cpu, cpu)
                reason = pressure_reason(self.policy, status.avail_phys, status.avail_page, self.disk_free(), cpu)
                strikes = strikes + 1 if reason else 0
                measured = self.snapshot()
                current = (time.monotonic(), measured["job_cpu_seconds"])
                previous = getattr(self, "_previous_cpu", current)
                if current[0] > previous[0]:
                    self.maximum_job_cpu = max(self.maximum_job_cpu,
                        100 * max(0, current[1]-previous[1]) / (current[0]-previous[0]) / (os.cpu_count() or 1))
                self._previous_cpu = current
                if (reason and strikes >= 2) or status.avail_phys < 2 * GIB:
                    print("[RESOURCE STOP] " + (reason or "Critical RAM pressure"), file=sys.stderr, flush=True)
                    self.api.TerminateJobObject(self.job, 73)
                    return
            except Exception as error:
                # Losing visibility is not permission to continue unmonitored.
                print(f"[RESOURCE STOP] Monitoring failed: {error}", file=sys.stderr, flush=True)
                self.api.TerminateJobObject(self.job, 73)
                return

    def close(self):
        self.finished.set()
        # Once assigned, let Windows close the handle at process termination.
        # KILL_ON_JOB_CLOSE then reaps JVM descendants even if Python crashes.
        # Closing it earlier would also terminate this Python process mid-save.
        if self.job and not self.assigned:
            self.api.CloseHandle(self.job)
            self.job = None
        if self.mutex:
            self.api.ReleaseMutex(self.mutex)
            self.api.CloseHandle(self.mutex)
            self.mutex = None


_GUARD = None


def protect_spark(requested_heap="6g") -> WindowsGuard:
    global _GUARD
    if _GUARD is None:
        _GUARD = WindowsGuard(requested_heap)
    return _GUARD


def protection_snapshot() -> dict:
    return _GUARD.snapshot() if _GUARD else {"hardware_guard": "not started"}
