"""Explain existing aggregate exports in business language; no pipeline execution."""
import csv
import hashlib
import html
import json
from pathlib import Path
import sys
from datetime import datetime

HERE = Path(__file__).resolve().parent
INPUT = HERE / "generated"
SELECTED = {"ibm_aml": "full_fusion", "paysim": "without_centrality"}
LABELS = {"ibm_aml": "IBM AML", "paysim": "PaySim"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    with (INPUT / name).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def n(value):
    return f"{int(value):,}".replace(",", ".")


def main():
    if sys.platform != "win32" or sys.version_info[:2] != (3, 12):
        raise RuntimeError("Use native Windows repository Python 3.12")
    out = HERE / "business_report"
    if out.exists():
        out = HERE / ("business_report_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir()
    files = ["model_comparison.csv", "review_budget_comparison.csv", "feature_usage.csv", "completion.json"]
    before = {name: sha(INPUT / name) for name in files}
    completion = json.loads((INPUT / "completion.json").read_text(encoding="utf-8"))
    if completion["status"] != "COMPLETE":
        raise ValueError("Underlying aggregate analysis incomplete")
    models, budgets, usage = read(files[0]), read(files[1]), read(files[2])
    tests = []
    def check(ok, label):
        tests.append({"check": label, "pass": bool(ok)})
        if not ok:
            raise ValueError(label)
    check(len(models) == 18 and len(budgets) == 54, "18 models / 54 budget rows")
    def model(d, selected):
        family = SELECTED[d] if selected else "transaction_only"
        return next(r for r in models if r["dataset"] == d and r["family"] == family)
    def budget(d, selected, fraction):
        family = SELECTED[d] if selected else "transaction_only"
        return next(r for r in budgets if r["dataset"] == d and r["model"] == family and float(r["review_fraction"]) == fraction)
    for d in SELECTED:
        a, b = model(d, True), model(d, False)
        check(a["selected_on_validation"] == "True", d + " validation winner preserved")
        for f in [.001, .005, .01]:
            x, y = budget(d, True, f), budget(d, False, f)
            check(x["K"] == y["K"] and x["transactions"] == y["transactions"], d + " equal review workload " + str(f))
            check(int(x["TP_at_K"]) - int(y["TP_at_K"]) == int(x["delta_TP_at_K_vs_baseline"]), d + " exported delta " + str(f))
    selected_paysim = [r for r in usage if r["dataset"] == "paysim" and r["family"] == SELECTED["paysim"] and r["used_in_split"] == "True"]
    check(any(r["feature"] == "receiver_in_168h" for r in selected_paysim), "PaySim uses receiver history")
    check(not any(r["group"] == "L" for r in selected_paysim), "PaySim selected does not split on community")

    esc = html.escape
    sections, md = [], []
    def paragraph(text):
        return "<p>" + esc(text) + "</p>"
    def section(title, text, body="", markdown_extra=""):
        sections.append("<section><h2>" + esc(title) + "</h2>" + paragraph(text) + body + "</section>")
        md.extend(["## " + title, "", text, "", markdown_extra, ""])
    def table(headers, rows):
        return '<div class="table"><table><thead><tr>' + "".join("<th>"+esc(h)+"</th>" for h in headers) + "</tr></thead><tbody>" + "".join("<tr>"+"".join("<td>"+esc(str(v))+"</td>" for v in row)+"</tr>" for row in rows) + "</tbody></table></div>"
    def mtable(headers, rows):
        return "\n".join(["| " + " | ".join(headers)+" |", "| " + " | ".join("---" for _ in headers)+" |"] + ["| "+" | ".join(map(str,r))+" |" for r in rows])

    title = "GraphGuard có giúp chọn đúng giao dịch cần kiểm tra?"
    subtitle = "Cùng số lượt kiểm tra, kết quả tốt hơn rõ trên PaySim ở các mức đã thử; IBM cải thiện nhẹ ở hai mức thấp và giảm ở mức cao hơn."
    md += ["# " + title, "", subtitle, "", "Báo cáo dễ đọc • Kết quả thử nghiệm trên dữ liệu mô phỏng", ""]
    section("1. Vấn đề cần giải quyết", "Đội kiểm tra không thể xem hết hàng triệu giao dịch. Câu hỏi thực tế là: nếu chỉ được kiểm tra một số lượng giao dịch nhất định, nên xem những giao dịch nào trước?", paragraph("GraphGuard xếp thứ tự ưu tiên để hỗ trợ người kiểm tra. Một cảnh báo chỉ là yêu cầu xem xét thêm; kết quả đúng/sai trong báo cáo được đối chiếu với nhãn có sẵn của bộ dữ liệu."))
    methods = [
        ("Cách cơ bản", "Xem thông tin của từng giao dịch, như loại giao dịch và số tiền."),
        ("GraphGuard được chọn", "Xem thêm quan hệ tài khoản và lịch sử dòng tiền. Cấu hình được chọn từ giai đoạn đánh giá trước tập kiểm tra cuối; không đổi người thắng sau khi xem kết quả.")]
    section("2. Chúng ta đang so sánh điều gì?", "So sánh cách cơ bản với cấu hình GraphGuard đã được chọn riêng cho từng bộ dữ liệu. GraphGuard không có một cấu hình duy nhất luôn tốt nhất cho mọi môi trường.", table(["Phương pháp", "Thông tin được xem xét"], methods), mtable(["Phương pháp", "Thông tin được xem xét"], methods))

    bars = []
    rows = []
    for d in SELECTED:
        a, b = budget(d, True, .005), budget(d, False, .005)
        delta = int(a["TP_at_K"]) - int(b["TP_at_K"])
        noun = "laundering" if d == "ibm_aml" else "fraud"
        rows.append([LABELS[d], n(a["K"]), n(b["TP_at_K"]), n(a["TP_at_K"]), "+"+n(delta)])
        maximum = max(int(a["TP_at_K"]), int(b["TP_at_K"]))
        bar = '<article class="card"><h3>'+LABELS[d]+'</h3>' + paragraph("Cả hai phương pháp cùng kiểm tra " + n(a["K"]) + " giao dịch.")
        for label, r, color in [("Cách cơ bản", b, "baseline"), ("GraphGuard", a, "graph")]:
            bar += '<div class="barlabel"><span>'+label+'</span><strong>'+n(r["TP_at_K"])+ '</strong></div><div class="track"><div class="bar '+color+'" style="width:'+str(100*int(r["TP_at_K"])/maximum)+'%"></div></div>'
        bar += '<p class="result">Thêm '+n(delta)+' giao dịch có nhãn '+noun+'.</p><p class="small">Thanh biểu diễn số giao dịch tìm đúng, không phải số tiền hoặc số vụ án. Mỗi bộ dữ liệu có thang riêng.</p></article>'
        bars.append(bar)
    headers = ["Bộ dữ liệu", "Cùng số lượt kiểm tra", "Cơ bản tìm đúng", "GraphGuard tìm đúng", "Tìm thêm"]
    section("3. Cùng nguồn lực kiểm tra, tìm thêm được gì?", "Ở ví dụ này, mỗi phương pháp được kiểm tra khoảng 0,5% giao dịch trong tập kiểm tra cuối. Hai phương pháp có thể chọn các giao dịch khác nhau, nhưng số lượt xem xét bằng nhau.", '<div class="cards">'+"".join(bars)+'</div>'+paragraph("Đây là kết quả ở một mức nguồn lực cụ thể. Không thể dùng riêng bảng này để kết luận GraphGuard luôn tốt hơn ở mọi mức.")+table(headers, rows), mtable(headers,rows))

    all_budget = []
    for d in SELECTED:
        for fraction, label in [(.001,"0,1%"),(.005,"0,5%"),(.01,"1%")]:
            a,b = budget(d,True,fraction),budget(d,False,fraction)
            delta = int(a["TP_at_K"])-int(b["TP_at_K"])
            all_budget.append([LABELS[d],label,n(a["K"]),n(b["TP_at_K"]),n(a["TP_at_K"]),("+" if delta>=0 else "−")+n(abs(delta))])
    headers2 = ["Bộ dữ liệu", "Phần được xem", "Số lượt kiểm tra", "Cơ bản tìm đúng", "GraphGuard tìm đúng", "Chênh lệch"]
    section("4. Khi thay đổi nguồn lực, lợi ích có còn không?", "PaySim tốt hơn cách cơ bản ở cả ba mức đã thử. IBM chỉ tốt hơn ở hai mức thấp; khi xem 1% tập kiểm tra, GraphGuard tìm ít hơn cách cơ bản 88 giao dịch có nhãn laundering.", table(headers2,all_budget)+paragraph("Vì vậy, bài học là phải đánh giá hệ thống ở mức nguồn lực dự kiến sử dụng. Số lượt kiểm tra bằng nhau chưa đồng nghĩa chi phí hay thời gian xử lý bằng nhau, vì các ca có thể khó dễ khác nhau."), mtable(headers2,all_budget))

    operations = []
    for d in SELECTED:
        b,a=model(d,False),model(d,True)
        for key,label in [("alerts","Giao dịch được cảnh báo"),("TP","Trong đó: đúng theo nhãn"),("FP","Trong đó: cảnh báo nhầm"),("FN","Positive bị bỏ sót")]:
            operations.append([LABELS[d],label,n(b[key]),n(a[key])])
    headers3 = ["Bộ dữ liệu", "Kết quả", "Cách cơ bản", "GraphGuard"]
    section("5. Dùng quy tắc cảnh báo hiện tại thì phải đánh đổi gì?", "Phần này dùng ngưỡng cảnh báo đã chọn trước, nên số cảnh báo của hai phương pháp khác nhau. Nó trả lời câu hỏi khác với phần cùng số lượt kiểm tra phía trên.", table(headers3,operations)+ '<div class="callout"><strong>IBM:</strong> Danh sách ngắn hơn, cảnh báo nhầm giảm, nhưng tìm được ít giao dịch laundering hơn.<br><strong>PaySim:</strong> Tìm được nhiều fraud hơn, nhưng cảnh báo nhầm tăng và cần xử lý thêm nhiều cảnh báo.</div>'+paragraph("Không thể chỉ nói “cảnh báo giảm là thành công” hoặc “tìm thêm fraud là thành công”. Phải xem cả phần tìm đúng và phần bị bỏ sót/cảnh báo nhầm."),mtable(headers3,operations))

    roles = [
        ["Vai trò tài khoản", "Tài khoản kết nối với nhiều ai, giữ vai trò trung tâm ra sao?", "Degree / PageRank"],
        ["Hành vi dòng tiền", "Trước đó tài khoản nhận/chuyển tiền thế nào; có gom tiền, phân tán hay giao dịch qua lại?", "Motif / history"],
        ["Bối cảnh nhóm", "Tài khoản thuộc nhóm nào; giao dịch chủ yếu trong hay ngoài nhóm?", "LPA / community"]]
    rolehead=["Góc nhìn", "Câu hỏi dễ hiểu", "Tên trong project"]
    section("6. Ba phần của project kết nối với nhau thế nào?", "Ba phần cung cấp thêm bối cảnh cho việc xếp thứ tự ưu tiên. Chúng không tự kết luận tài khoản có tội và không nhất thiết đều cần thiết trong mọi bộ dữ liệu.", table(rolehead,roles)+paragraph("IBM: mô hình được chọn thực sự dùng thông tin từ cả ba góc nhìn. Điều đó cho thấy cây có dùng chúng, chưa chứng minh từng phần đều làm hiệu quả tăng.")+paragraph("PaySim: mô hình được chọn dùng thông tin về lịch sử nhận tiền. Thông tin nhóm được cung cấp nhưng cây cuối không dùng để quyết định; không nên ép kết luận rằng community đã giúp phát hiện fraud."),mtable(rolehead,roles))

    proved=[
        "Trong các tập kiểm tra đã có, thông tin quan hệ/lịch sử có thể giúp ưu tiên giao dịch tốt hơn ở một số mức nguồn lực.",
        "Lợi ích phụ thuộc bộ dữ liệu và số giao dịch được phép kiểm tra. IBM cho kết quả pha trộn; PaySim cải thiện ở cả ba mức đã thử.",
        "Thêm thuật toán không tự động làm mô hình tốt hơn. Cần giữ đối chứng và xem cả cảnh báo nhầm, bỏ sót."]
    unproved=[
        "Chưa chứng minh tiết kiệm được bao nhiêu tiền hoặc giờ làm việc: chưa có dữ liệu chi phí và thời gian điều tra.",
        "Chưa chứng minh ngăn chặn thiệt hại hay phát hiện cả đường dây rửa tiền: nhãn đánh giá nằm ở từng giao dịch.",
        "Chưa chứng minh hiệu quả trên ngân hàng thực tế: hai bộ dữ liệu là mô phỏng và đây là đánh giá nội bộ."]
    ul=lambda items:'<ul>'+''.join('<li>'+esc(x)+'</li>' for x in items)+'</ul>'
    section("7. Kết quả này chứng minh được gì?", "Kết quả cung cấp bằng chứng thử nghiệm về khả năng hỗ trợ lựa chọn giao dịch cần xem trước. Nó không đủ để cam kết hiệu quả tài chính hoặc hiệu quả triển khai thực tế.", '<h3>Bằng chứng hiện có</h3>'+ul(proved)+'<h3>Những điều chưa thể kết luận</h3>'+ul(unproved),"\n".join('- '+x for x in proved+unproved))
    conclusion="GraphGuard cho thấy tiềm năng hỗ trợ đội kiểm tra ưu tiên giao dịch. Trên PaySim, phương pháp được chọn tìm đúng nhiều hơn với cùng số lượt kiểm tra ở cả ba mức đã thử. Trên IBM, lợi ích phụ thuộc mức nguồn lực và có trường hợp kém hơn cách cơ bản. Vì vậy cần chọn cách dùng theo mục tiêu và nguồn lực, thay vì khẳng định kết hợp ba thuật toán luôn tốt hơn."
    section("8. Kết luận để trình bày",conclusion, '<div class="callout">Bước tiếp theo cho ứng dụng thực tế: chốt số lượt kiểm tra/ngày, đo thời gian và chi phí mỗi ca, sau đó thử nghiệm trên dữ liệu thực tế theo thời gian. Đây là đề xuất tương lai, chưa phải kết quả đã đạt.</div>')

    glossary=[
        ["Tìm đúng", "Giao dịch có nhãn positive được đưa vào danh sách xem xét."],
        ["Cảnh báo nhầm", "Giao dịch có nhãn bình thường nhưng bị cảnh báo."],
        ["Bỏ sót", "Giao dịch có nhãn positive nhưng không bị cảnh báo."],
        ["Tập kiểm tra cuối", "Phần giao dịch diễn ra sau giai đoạn dùng để chọn mô hình."],
        ["Nhãn positive", "IBM: laundering; PaySim: fraud. Hai nhãn không gộp thành một kết quả chung."]]
    scope=[]
    for d in SELECTED:
        r=model(d,True)
        scope.append([LABELS[d],n(r["test_transactions"]),n(r["test_positives"]),SELECTED[d],r["threshold"]])
    appendix='<details><summary>Từ ngữ, phạm vi và nguồn số liệu</summary>'+table(["Từ ngữ","Cách hiểu"],glossary)+table(["Dataset","Giao dịch test","Positive test","Cấu hình giữ nguyên","Ngưỡng"],scope)+paragraph("Toàn bộ số trong các bảng chính thuộc toàn tập kiểm tra cuối tương ứng, không tính từ vài examples. “GraphGuard” ở đây là validation-selected model; không đổi model dựa trên kết quả test. Các mức 0,1%, 0,5%, 1% là số lượng xem xét đã được export; 0,5% chỉ là ví dụ trình bày, không phải ngưỡng vận hành tối ưu đã được chứng minh.")+paragraph("Bản phân tích kỹ thuật gốc: CP0–CP4 và CP6–CP7 PASS; CP5 LIMITED vì examples thiếu feature để xác minh rule path. Bản dễ đọc này chỉ dùng các bảng tổng hợp, không suy intersection C∩M∩L hoặc kết luận pháp lý.")+'<ul><li><a href="sources/model_comparison.csv">Bảng so sánh model</a></li><li><a href="sources/review_budget_comparison.csv">Bảng cùng số lượt kiểm tra</a></li><li><a href="sources/feature_usage.csv">Feature mô hình thực sự dùng</a></li><li><a href="validation.json">Kiểm tra và hash nguồn</a></li></ul></details>'
    md += ["## Phạm vi và nguồn", "",mtable(["Dataset","Giao dịch test","Positive test","Cấu hình giữ nguyên","Ngưỡng"],scope),"",mtable(["Từ ngữ","Cách hiểu"],glossary),"", "Số liệu toàn bộ test holdout, không suy từ examples. Hai dataset mô phỏng, nhãn khác nhau. 0,5% chỉ là ví dụ minh họa; không phải ngân sách tối ưu đã được chứng minh.","", "[Model comparison](sources/model_comparison.csv), [review budgets](sources/review_budget_comparison.csv), [feature usage](sources/feature_usage.csv), [kiểm tra/hash](validation.json)."]
    css='''*{box-sizing:border-box}body{margin:0;background:#f5f7fa;color:#243247;font:18px/1.75 "Segoe UI",Arial,sans-serif}main{max-width:1100px;margin:auto;padding:36px 28px 70px}header{padding:38px 0 28px;border-bottom:3px solid #1e6579}h1{font-size:40px;line-height:1.2;max-width:850px;margin:12px 0 22px;color:#153c4d}h2{font-size:27px;line-height:1.35;color:#153c4d;margin:0 0 18px}h3{font-size:21px;line-height:1.4}.eyebrow{font-size:14px;letter-spacing:.08em;text-transform:uppercase;color:#577086}.lead{font-size:22px;max-width:900px}section{padding:36px 0;border-bottom:1px solid #d7e0e8}.cards{display:grid;grid-template-columns:1fr 1fr;gap:24px}.card{padding:24px;background:white;border:1px solid #d8e1e9;border-radius:12px}.card h3{margin-top:0}.small{font-size:14px;color:#56677b}.barlabel{display:flex;justify-content:space-between;margin-top:16px}.track{height:20px;background:#eef2f6;border-radius:4px;margin:7px 0 18px}.bar{height:100%;border-radius:4px}.baseline{background:#8296aa}.graph{background:#16766d}.result{font-size:20px;font-weight:600;color:#155b54}.table{overflow:auto;margin:24px 0}table{width:100%;border-collapse:collapse;font-size:16px;background:white}th,td{padding:14px 16px;border-bottom:1px solid #dde5ec;text-align:left;vertical-align:top}th{background:#e6eef4;color:#24495e}td:first-child{font-weight:600}.callout{background:#e8f2f2;border-left:4px solid #1e6579;padding:22px 24px;margin:24px 0}details{margin-top:35px;padding:22px;background:white;border:1px solid #d7e0e8;border-radius:8px}summary{cursor:pointer;font-weight:600}a{color:#1b627b}li{margin:12px 0}@media(max-width:720px){main{padding:20px 16px}h1{font-size:31px}.cards{grid-template-columns:1fr}body{font-size:17px}th,td{padding:10px}}@media print{body{background:white;font-size:12pt}main{max-width:none;padding:0}h1{font-size:26pt}h2{font-size:19pt}section{break-inside:avoid}details{display:block}.table{overflow:visible}table{font-size:10pt}}'''
    page='<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+esc(title)+'</title><style>'+css+'</style></head><body><main><header><div class="eyebrow">GraphGuard · Kết quả thử nghiệm trên dữ liệu mô phỏng</div><h1>'+esc(title)+'</h1><p class="lead">'+esc(subtitle)+'</p></header>'+''.join(sections)+appendix+'</main></body></html>'
    source_dir=out/"sources"
    source_dir.mkdir()
    for name in files:
        (source_dir/name).write_bytes((INPUT/name).read_bytes())
    (out/"GRAPHGUARD_BUSINESS_REPORT.html").write_text(page,encoding="utf-8")
    (out/"GRAPHGUARD_BUSINESS_REPORT.md").write_text('\n'.join(md),encoding="utf-8")
    for name,h in before.items():
        check(sha(INPUT/name)==h,"Original unchanged: "+name)
        check(sha(source_dir/name)==h,"Snapshot exact: "+name)
    import re
    for link in re.findall('href="([^"]+)"',page):
        check(not link.startswith(("http:","https:")),"Offline link: "+link)
        if link!='validation.json':
            check((out/link).is_file(),"Link resolves: "+link)
    (out/"validation.json").write_text(json.dumps({"status":"PASS","checks":tests,"input_sha256":before,"builder_sha256":sha(Path(__file__)),"no_spark":True,"no_pipeline_rerun":True,"scope":"readable presentation of existing aggregate results"},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"output":str(out),"checks":len(tests),"status":"PASS"},ensure_ascii=False))


if __name__ == "__main__":
    main()
