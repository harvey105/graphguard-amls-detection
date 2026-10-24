"""Verify limits and process cleanup with tiny children, never a stress test."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import Mock, patch

import psutil

from src.common.hardware_guard import GIB, ResourcePolicy, WindowsGuard, pressure_reason

ROOT = Path(__file__).resolve().parents[1]


class PolicyTests(unittest.TestCase):
    def test_smaller_heap_reduces_real_job_cap_without_reducing_reserve(self):
        full = ResourcePolicy.for_workload(32 * GIB, "6g")
        small = ResourcePolicy.for_workload(32 * GIB, "4g")
        self.assertEqual((full.job_bytes, small.job_bytes), (10 * GIB, 7 * GIB))
        self.assertEqual(full.reserve_bytes, small.reserve_bytes)
        self.assertEqual(small.spark_limits("6g", "local[*]"), ("4096m", small.workers))
        self.assertEqual(small.cpu_percent, 100)
        medium = ResourcePolicy.for_workload(32 * GIB, "5g")
        self.assertEqual(medium.job_bytes, 8 * GIB)
        self.assertEqual(medium.reserve_bytes, full.reserve_bytes)
        self.assertEqual(medium.spark_limits("6g", "local[*]"), ("5120m", medium.workers))
    def test_optional_heap_ceiling_only_reduces_allocation(self):
        from src.common.spark_session import _bounded_heap
        self.assertEqual(_bounded_heap("6g", "5g"), "5120m")
        self.assertEqual(_bounded_heap("4g", "5g"), "4096m")
        self.assertEqual(_bounded_heap("6g", "12g"), "6144m")
        self.assertEqual(_bounded_heap("6g", None), "6g")
        for ceiling in ("", "oops", "0g", "511m"):
            with self.assertRaises(ValueError):
                _bounded_heap("6g", ceiling)

    def test_caps_and_unbounded_master_clamped(self):
        policy = ResourcePolicy.for_memory(32 * GIB)
        self.assertEqual(policy.spark_limits("12g", "local[*]"), ("6144m", policy.workers))
        self.assertEqual(policy.spark_limits("2g", "local[1]"), ("2048m", 1))
        self.assertEqual(policy.job_bytes, 10 * GIB)
        self.assertEqual(policy.reserve_bytes, 8 * GIB)
        for heap, master in (("oops", "local[2]"), ("0g", "local[2]"), ("2g", "local[0]"), ("2g", "spark://host")):
            with self.assertRaises(ValueError):
                policy.spark_limits(heap, master)

    def test_low_memory_scales_or_refuses(self):
        self.assertLess(ResourcePolicy.for_memory(16 * GIB).max_heap_gib, 6)
        with self.assertRaises(RuntimeError):
            ResourcePolicy.for_memory(8 * GIB)

    def test_pressure_decisions_without_exhausting_resources(self):
        policy = ResourcePolicy.for_memory(32 * GIB)
        self.assertIsNone(pressure_reason(policy, 12*GIB, 12*GIB, 20*GIB, 100))
        for values in ((7*GIB,12*GIB,20*GIB,20), (12*GIB,7*GIB,20*GIB,20),
                       (12*GIB,12*GIB,4*GIB,20)):
            self.assertIsNotNone(pressure_reason(policy, *values))

    def test_watchdog_automatically_stops_on_simulated_pressure(self):
        guard = WindowsGuard.__new__(WindowsGuard)
        guard.policy = ResourcePolicy.for_memory(32 * GIB)
        guard.finished = Mock()
        guard.finished.wait.side_effect = [False, False, True]
        guard.memory = Mock(return_value=Mock(avail_phys=7*GIB, avail_page=12*GIB))
        guard.disk_free = Mock(return_value=20*GIB)
        guard.minimum_available, guard.maximum_host_cpu = 12*GIB, 0.0
        guard.api, guard.job = Mock(), 123
        guard.snapshot = Mock(return_value={"job_cpu_seconds": 0})
        with patch("src.common.hardware_guard.psutil.cpu_percent", return_value=15), patch("sys.stderr"):
            guard._watch()
        guard.api.TerminateJobObject.assert_called_once_with(123, 73)


@unittest.skipUnless(os.name == "nt", "Native Windows Job Object verification")
class NativeGuardTests(unittest.TestCase):
    def test_small_profile_installs_lower_os_cap(self):
        result = self.child("""
import ctypes as C
from src.common.hardware_guard import protect_spark, ExtendedLimits, GIB
g=protect_spark('4g')
limits=ExtendedLimits()
assert g.api.QueryInformationJobObject(g.job,9,C.byref(limits),C.sizeof(limits),None)
assert limits.job_memory == min(g.policy.job_bytes,7*GIB)
assert g.policy.reserve_bytes >= 4*GIB
assert g.policy.max_heap_gib <= 4
print('Lower OS cap installed; reserve retained')
""")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_full_low_memory_profile_installs_eight_gib_os_cap(self):
        result = self.child("""
import ctypes as C
from src.common.hardware_guard import protect_spark, ExtendedLimits, ResourcePolicy, GIB
g=protect_spark('5g')
limits=ExtendedLimits()
assert g.api.QueryInformationJobObject(g.job,9,C.byref(limits),C.sizeof(limits),None)
assert limits.job_memory == min(g.policy.job_bytes,8*GIB)
assert g.policy.reserve_bytes == ResourcePolicy.for_memory(g.memory().total_phys).reserve_bytes
assert g.policy.max_heap_gib <= 5 and g.policy.cpu_percent == 100
print('5 GiB heap / 8 GiB OS cap; original memory reserve retained; CPU fully authorized')
""")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def child(self, code):
        result = subprocess.run([sys.executable, "-u", "-c", code], cwd=ROOT,
            text=True, capture_output=True, timeout=30)
        return result

    def test_os_limits_are_installed(self):
        code = """
import ctypes as C, json, psutil
from src.common.hardware_guard import protect_spark, ExtendedLimits, CPULimits
g=protect_spark('4g')
memory=ExtendedLimits(); cpu=CPULimits()
assert g.api.QueryInformationJobObject(g.job,9,C.byref(memory),C.sizeof(memory),None)
assert g.api.QueryInformationJobObject(g.job,15,C.byref(cpu),C.sizeof(cpu),None)
assert memory.basic.flags & 0x2000 and memory.job_memory == g.policy.job_bytes
assert cpu.flags == 5 and cpu.rate == 10000
assert psutil.Process().cpu_affinity() == g.allowed_cpus
assert g.policy.workers == min(len(g.allowed_cpus),g.policy.max_heap_gib*4)
print(json.dumps(g.snapshot()))
"""
        result = self.child(code)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        snapshot = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(snapshot["cpu_hard_cap_percent"], 100)

    def test_second_workload_refused_before_spark(self):
        result = self.child("""
import subprocess, sys
from src.common.hardware_guard import protect_spark
protect_spark('4g')
probe=subprocess.run([sys.executable,'-c',"from src.common.hardware_guard import protect_spark; protect_spark('4g')"],
    capture_output=True,text=True,timeout=10)
assert probe.returncode != 0 and 'Another GraphGuard workload' in probe.stderr, probe.stderr
print('Second workload rejected')
""")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_child_reaped(self, result):
        pid = int(next(line.split("=")[1] for line in result.stdout.splitlines() if line.startswith("CHILD=")))
        for _ in range(20):
            if not psutil.pid_exists(pid):
                return
            time.sleep(0.1)
        self.fail(f"Managed descendant PID {pid} survived job shutdown")

    def test_abrupt_parent_exit_reaps_descendant(self):
        result = self.child("""
import os, subprocess, sys
from src.common.hardware_guard import protect_spark
protect_spark('4g')
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
print('CHILD='+str(child.pid),flush=True)
os._exit(0)
""")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_child_reaped(result)

    def test_emergency_stop_only_managed_tree(self):
        result = self.child("""
import subprocess, sys
from src.common.hardware_guard import protect_spark
g=protect_spark('4g')
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
print('CHILD='+str(child.pid),flush=True)
g.api.TerminateJobObject(g.job,73)
""")
        self.assertEqual(result.returncode, 73, result.stdout + result.stderr)
        self.assert_child_reaped(result)


if __name__ == "__main__":
    unittest.main()
