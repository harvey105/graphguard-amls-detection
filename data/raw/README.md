# Raw datasets

The project uses PaySim and the IBM AML **HI-Small** variant. IBM's other 15 files belong to HI-Medium, HI-Large, LI-Small, LI-Medium, and LI-Large; they are alternative variants and are not inputs to the current pipeline. Raw CSVs are downloaded locally and excluded from Git; the small HI-Small Patterns text is tracked.

| Dataset | Required file | Local path | Verification |
|---|---|---|---|
| PaySim | `PS_20174392719_1491204439457_log.csv` | `data/raw/paysim/` | 6,362,620 rows; graph ETL |
| IBM AML (HI-Small) | `HI-Small_Trans.csv` | `data/raw/ibm_aml/` | 5,078,345 rows; edge ETL |
| IBM AML (HI-Small) | `HI-Small_accounts.csv` | `data/raw/ibm_aml/` | 518,581 rows; vertex ETL |
| IBM AML (HI-Small) | `HI-Small_Patterns.txt` | `data/raw/ibm_aml/` | 54 CYCLE blocks / 370 attempts; motif audit |

From the repository root in Windows PowerShell, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\download_datasets.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\download_datasets.ps1 -VerifyOnly
```

The downloader validates all four required files. `-Dataset IbmAml` covers all three HI-Small files; `-VerifyOnly` checks without accessing the network. A missing file is downloaded by default; `-FileName HI-Small_Patterns.txt -Force` refreshes only that file. Do not commit the downloaded CSV files.
