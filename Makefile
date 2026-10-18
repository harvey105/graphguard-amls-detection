# Run with Windows GNU Make from PowerShell. The PowerShell script also runs directly.
.PHONY: check check-task3 check-task4 check-task4-full
check:
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check_task3.ps1

check-task3: check

check-task4:
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check_task4.ps1

check-task4-full:
	powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check_task4.ps1 -Full -Runs 1
