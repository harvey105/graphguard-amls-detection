# Raw datasets

Raw datasets are downloaded locally and excluded from Git because of their size and licensing terms.

| Dataset | Source file | Local path | Expected rows |
|---|---|---|---:|
| PaySim | `PS_20174392719_1491204439457_log.csv` | `data/raw/paysim/` | 6,362,620 |
| IBM AML (HI-Small) | `HI-Small_Trans.csv` | `data/raw/ibm_aml/` | 5,078,345 |
| IBM AML (HI-Small) | `HI-Small_accounts.csv` | `data/raw/ibm_aml/` | 518,581 |

From the repository root in Windows PowerShell, run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\download_datasets.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\download_datasets.ps1 -VerifyOnly
```

The downloader fetches the three required CSV files (PaySim transactions, IBM AML transactions and accounts) and validates each header, size, and row count. `-Dataset IbmAml` and `-VerifyOnly` cover both IBM files. Do not commit the downloaded CSV files.
