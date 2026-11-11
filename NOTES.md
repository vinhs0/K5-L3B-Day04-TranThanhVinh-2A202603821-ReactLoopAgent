# Ghi chú phân tích · Day 04

Họ và tên: Trần Thanh Vinh
MSSV: 2A202603821

Cấu hình giống nhau ở cả hai lần chạy: provider `openai`, model `gpt-4o-mini` (cả agent và judge), `max_steps` 8, dataset core 22 case, snapshot cố định.

## 1. Case được chọn

- ID case: **H1** (và **H6**, cùng kiểu lỗi).
- Câu hỏi H1: điều tra incident GitHub `h02n9572mx9y`, *theo liên kết do incident cung cấp* để tìm nguyên nhân, rồi đối chiếu với incident Cloudflare `yaa0witbl2me`.
- Câu trả lời của agent (lần 1): trình bày đúng incident `h02n9572mx9y` và Cloudflare, có chèn link `xr3myzj7ms51` nhưng không hề đọc incident đó, nên không nêu được nguyên nhân.
- Điểm ở lần chạy 1: H1 = **60**, H6 = **60** (cùng bị `score_cap` 60).

## 2. Bằng chứng trong trace

Trích từ `eval_before.json`, case H1 (`grade.mechanical`):

```text
violations: ['Cần tool calls ở ít nhất 2 model steps khác nhau.']
score_cap: 60, tool_calls: 2, tool_steps: 1

trace:
  model 1 tool_calls
  TOOL step 1 get_incident_details {github, h02n9572mx9y}
  TOOL step 1 get_incident_details {cloudflare, yaa0witbl2me}
  model 2 stop            <- trả lời luôn, không đọc xr3myzj7ms51
```

Update của `h02n9572mx9y` có câu "xem thêm chi tiết trong incident liên quan" kèm link tới `xr3myzj7ms51`. Model chỉ gọi tool một đợt rồi kết thúc.

Nguyên nhân có thể: agent loop chấp nhận câu trả lời cuối ngay khi `finish == 'stop'`, không có cơ chế nào nhắc model đọc incident được dẫn tới; `gpt-4o-mini` thường dừng sau một lượt tool call. Case H6 có đúng cùng mẫu (2 tool call trong 1 step).

## 3. Thay đổi đã thực hiện

- Sửa gì, ở đâu: trong `run_agent` (`agent.py`), khi một `get_incident_details` thành công, agent quét `body` của các update tìm link dạng `.../incidents/<id>` và ghi lại các incident được nhắc nhưng chưa đọc. Nếu model đưa câu trả lời cuối mà vẫn còn incident như vậy và còn bước, agent ghi event `validation_unfollowed_reference` vào trace và thêm một tin nhắn yêu cầu gọi `get_incident_details` cho các incident đó. Mỗi incident chỉ nhắc một lần và không chặn hoàn thành khi hết bước. Thêm `tests/test_followup.py` (3 test).
- Vì sao chọn: lỗi nằm ở vòng lặp (thiếu bước đọc tiếp) chứ không ở tool; cách sửa tổng quát, không hard-code ID, cùng kiểu với kiểm tra nguồn đã có (`validation_missing_source`). Không sửa fixtures, cases, scenarios, grading hay rubric.

## 4. So sánh hai lần chạy

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 75.0 | 76.14 |
| Điểm case đã chọn | H1 60, H6 60 | H1 65, H6 75 |
| Số model calls (22 case) | 52 | 56 |
| Token (tổng `total_tokens`) | 43 706 | 58 074 |

Chi phí tiền không có trong output của provider nên không ghi.

- Lỗi đã giải quyết: ở H1 và H6, agent giờ đọc `xr3myzj7ms51` ở model step 3, `tool_steps` tăng từ 1 lên 2 và `score_cap` 60 biến mất (`violations` rỗng). Đây là thay đổi được xác nhận bằng trace. Event `validation_unfollowed_reference` chỉ xuất hiện ở H1 và H6.
- Lỗi còn lại hoặc mới xuất hiện: điểm judge của H1 chỉ lên 65 vì câu trả lời vẫn chưa nêu rõ nguyên nhân và chưa dẫn nguồn đủ cho Cloudflare. Một số case khác giảm nhưng không có event của thay đổi mới trong trace: H2 95 → 50 (không gọi `get_status`), H8 60 → 40, E4 100 → 70, A5 75 → 10 (khẳng định "không có sự cố năm 2025", sai kỳ vọng). Các thay đổi này không do thay đổi của tôi gây ra theo trace, nhưng tôi chưa chứng minh được nguyên nhân cụ thể.
- Lần chạy `eval_after` đầu tiên có H4 `unscored` vì judge lỗi mạng (`WinError 10054`), nên điểm tổng là `null`. Tôi giữ file đó là `eval_after_attempt1_h4_unscored.json` và chạy lại toàn bộ bộ eval để có `eval_after.json` (22/22 case được chấm).

## 5. Giới hạn

- Mỗi phiên bản chỉ chạy một lần. Giữa hai lần chạy của cùng một agent, nhiều case khác nhau lệch rất lớn (ví dụ E1 50 → 100 ở lần chạy after đầu và 50 → 65 ở lần sau, A4 55 → 100 ở cả hai) dù không có event mới, nên mức tăng điểm tổng 75.0 → 76.14 nằm trong nhiễu và **không chứng minh** cải tiến tổng thể.
- Judge là cùng model `gpt-4o-mini` với agent: có thể thiên lệch và không ổn định, ví dụ H1 vẫn bị trừ điểm vì lý do mà trace không phản ánh rõ.
- Snapshot cố định và chỉ có 50 incident gần nhất mỗi provider; một số kỳ vọng (A5, H8) phụ thuộc vào việc model nói rõ giới hạn đó.
- Kiểm tra mới chỉ nhận diện link dạng `/incidents/<id>` cùng provider; link rút gọn (`stspg.io/...`) hoặc tham chiếu bằng chữ không được phát hiện. Chi phí tăng: +4 model call và +14 000 token trên bộ eval.
