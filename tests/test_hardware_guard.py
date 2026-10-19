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
    def test_caps_and_unbounded_master_clamped(self):
        policy = ResourcePolicy.for_memory(32 * GIB)
        self.assertEqual(policy.spark_limits("12g", "local[*]"), ("6144m", 2))
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
        self.assertIsNone(pressure_reason(policy, 12*GIB, 12*GIB, 20*GIB, 20))
        for values in ((7*GIB,12*GIB,20*GIB,20), (12*GIB,7*GIB,20*GIB,20),
                       (12*GIB,12*GIB,4*GIB,20), (12*GIB,12*GIB,20*GIB,90)):
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
        with patch("src.common.hardware_guard.psutil.cpu_percent", return_value=15), patch("sys.stderr"):
            guard._watch()
        guard.api.TerminateJobObject.assert_called_once_with(123, 73)


@unittest.skipUnless(os.name == "nt", "Native Windows Job Object verification")
class NativeGuardTests(unittest.TestCase):
    def child(self, code):
        result = subprocess.run([sys.executable, "-u", "-c", code], cwd=ROOT,
            text=True, capture_output=True, timeout=30)
        return result

    def test_os_limits_are_installed(self):
        code = """
import ctypes as C, json, psutil
from src.common.hardware_guard import protect_spark, ExtendedLimits, CPULimits
g=protect_spark()
memory=ExtendedLimits(); cpu=CPULimits()
assert g.api.QueryInformationJobObject(g.job,9,C.byref(memory),C.sizeof(memory),None)
assert g.api.QueryInformationJobObject(g.job,15,C.byref(cpu),C.sizeof(cpu),None)
assert memory.basic.flags & 0x2000 and memory.job_memory == g.policy.job_bytes
assert cpu.flags == 5 and cpu.rate == 1000
assert len(psutil.Process().cpu_affinity()) <= 2
print(json.dumps(g.snapshot()))
"""
        result = self.child(code)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        snapshot = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(snapshot["cpu_hard_cap_percent"], 10)

    def test_second_workload_refused_before_spark(self):
        result = self.child("""
import subprocess, sys
from src.common.hardware_guard import protect_spark
protect_spark()
probe=subprocess.run([sys.executable,'-c','from src.common.hardware_guard import protect_spark; protect_spark()'],
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
protect_spark()
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
g=protect_spark()
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
print('CHILD='+str(child.pid),flush=True)
g.api.TerminateJobObject(g.job,73)
""")
        self.assertEqual(result.returncode, 73, result.stdout + result.stderr)
        self.assert_child_reaped(result)


if __name__ == "__main__":
    unittest.main()
