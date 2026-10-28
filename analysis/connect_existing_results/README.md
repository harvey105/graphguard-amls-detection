# Connected graph insights reports

Hai báo cáo đọc cùng nhau:

- [Bản nghiệp vụ](business_report/GRAPHGUARD_BUSINESS_REPORT.html): nối kết quả cấu trúc, tín hiệu hành vi và giá trị ưu tiên kiểm tra.
- [Bản kỹ thuật](generated/CONNECTED_RESULTS_REPORT.html): cohort/lift, feature sử dụng, đối chứng novelty, top-K, hiệu suất biên, hòa điểm và biến thiên thời gian.

Giữ hai thư mục `business_report` và `generated` cạnh nhau để đọc offline. Các nguồn được báo cáo sử dụng có snapshot trong `sources/`; các nguồn này phục vụ lần chạy lịch sử đã ghi trong provenance. Bundle chung của repository là `Report_Bundle` ở thư mục gốc. Nếu một tệp trong bundle được cập nhật sau đó, không tự thay snapshot lịch sử hoặc gắn hash mới vào kết quả cũ.

## Kiểm tra và dựng lại phần báo cáo

Chạy từ thư mục gốc bằng native Windows PowerShell và Python 3.12 trong `.venv`:

```powershell
& '.\.venv\Scripts\python.exe' -B 'analysis/connect_existing_results/revise_insight_reports.py' --check-only
```

Lệnh kiểm tra đối chiếu nguồn, số liệu, hash artifact, liên kết HTML/Markdown và anchors. Font cache, checkpoint bookkeeping và backup local không thuộc tập bằng chứng bắt buộc khi clone. Kiểm tra này không chạy Spark, notebook, training hoặc scoring và không thay thế nghiệm thu full pipeline gốc.

Để dựng lại hai báo cáo từ các aggregate exports đã có:

```powershell
& '.\.venv\Scripts\python.exe' -B 'analysis/connect_existing_results/revise_insight_reports.py' --update-reports
```

Script tạo revision mới, giữ bản trước trong `report_revisions/` local, kiểm tra staging rồi mới cập nhật báo cáo. Nguồn bổ sung đã có được đối chiếu với SHA-256 lịch sử. Chỉ khi thiếu nguồn, script mới tìm tệp khớp hash trong `Report_Bundle`; khác hash thì dừng thay vì sửa provenance.

Hai script `build_analysis.py` và `build_business_report.py` được giữ làm nguồn thực thi của các bản tổng hợp ban đầu. Dùng `revise_insight_reports.py` để duy trì phiên bản insight hiện tại.

## Phạm vi bằng chứng

Các công thức mới chỉ tổng hợp lại exports: lift trong cohort, hiệu suất biên, phân bố positive theo kỳ và độ nhạy phân bổ trong nhóm hòa điểm. Không suy positive mới duy nhất, giao nhau giữa danh sách hoặc hiệu quả điều tra từ vài examples. Các mô hình/ngưỡng vẫn giữ lựa chọn bằng validation; các giới hạn về synthetic data, test nội bộ và case rule paths được nêu trong báo cáo.

Các manifest `analysis_config.json`, `completion.json`, `input_hashes.json` và `source_inventory.csv` gốc vẫn là provenance lịch sử. `revision_validation.json` ghi riêng script, output và kiểm tra của bản báo cáo hiện tại. `.gitattributes` giữ nguyên byte các tệp trong thư mục này để hash không đổi theo cấu hình xuống dòng của Git.
