## MỤC 5: PHÂN TÍCH RỦI RO & HƯỚNG PHÁT TRIỂN

### 5.1 Rủi ro kỹ thuật

| Rủi ro | Mức độ | Ảnh hưởng |
|---|---|---|
| Lỗi xử lý xung đột báo thành công giả, gây mất dữ liệu âm thầm (Mục 4.2) | **Cao** | Người dùng tưởng đã lưu đúng nhưng dữ liệu chỉnh sửa tay bị mất, không cách nào phục hồi từ giao diện |
| Backend và Pipeline chạy chung 1 process, không tách rời được | Trung bình | Không thể nâng cấp/deploy 2 phần độc lập; lỗi ở Pipeline có thể ảnh hưởng trực tiếp đến Backend đang phục vụ người dùng |
| Trạng thái import job chỉ lưu trong RAM, mất khi khởi động lại Backend | Trung bình | Nếu server restart giữa lúc đang import, người dùng mất toàn bộ tiến trình đang theo dõi, phải chạy lại từ đầu |
| Chưa có test tự động cho toàn bộ Backend/Pipeline | Trung bình | Mỗi lần sửa code phải test tay lại theo checklist thủ công — chậm, dễ bỏ sót khi checklist không được cập nhật kịp |
| Tình huống tài liệu nguồn đổi version thật chưa từng được kiểm thử qua pipeline thật | Trung bình | Đây là tình huống sẽ xảy ra thường xuyên nhất khi dùng thật — rủi ro chưa được đo lường đầy đủ |

### 5.2 Rủi ro vận hành & tổ chức

- **Phụ thuộc vào số ít người phát triển:** dự án hiện do 2 người xây dựng, trong đó phần Pipeline (`2.pipeline/`) do 1 người phụ trách riêng — nếu người này không còn tham gia, phần lõi enrich/convert dữ liệu sẽ thiếu người nắm rõ.
- **Phụ thuộc dịch vụ AI bên ngoài:** việc sinh mô tả tự động cần gọi Claude qua gateway nội bộ công ty — nếu gateway gián đoạn, hệ thống vẫn hoạt động nhờ cơ chế dự phòng (rule-based), nhưng chất lượng mô tả sẽ giảm và cần người rà soát lại nhiều hơn.
- **Chi phí vận hành tăng theo quy mô sử dụng:** số lượt gọi AI (enrich khi import, gợi ý mô tả, tự động sửa lỗi lint) tỉ lệ thuận với số module/endpoint — càng mở rộng phạm vi sử dụng, chi phí này càng tăng, cần có ngưỡng theo dõi.
- **Không có kiểm soát tự động chất lượng code Backend/Pipeline:** CI hiện chỉ kiểm tra tài liệu OpenAPI đầu ra (Spectral/Redocly), không kiểm tra logic Python — lỗi logic có thể lọt qua CI mà không bị phát hiện.

### 5.3 Nợ kỹ thuật tồn đọng

| Hạng mục | Hiện trạng |
|---|---|
| Lệnh `make scan`/`approve`/`run-module`/`run-single`/`run-batch` | Bị hỏng — gọi vào file đã bị dời chỗ, không còn tồn tại ở đường dẫn cũ |
| Trang Developer Portal riêng | Đã code xong nhưng không có đường dẫn nào trong ứng dụng trỏ tới, trùng chức năng với trang Swagger UI đang dùng |
| 1 route dispatch quy trình tạo PR tài liệu | Không được giao diện nào gọi tới, đồng thời có lỗi chính tả nhỏ trong request gửi đi |
| 2 pipeline xử lý PDF/Excel riêng | Đã viết nhưng chưa được kết nối vào luồng chính của hệ thống |

Các hạng mục này không ảnh hưởng đến vận hành hiện tại (không nằm trên đường đi của luồng chính) nhưng làm tăng độ rối khi có người mới tham gia đọc code.

### 5.4 Hướng phát triển đề xuất

**Ưu tiên trước khi mở rộng quy mô sử dụng:**
1. Khắc phục lỗi mất dữ liệu âm thầm khi xử lý xung đột (Mục 4.2) — ưu tiên cao nhất vì ảnh hưởng trực tiếp đến độ tin cậy của dữ liệu.
2. Chạy kiểm thử tình huống tài liệu nguồn đổi version thật qua pipeline thật, thay vì chỉ giả lập.
3. Bổ sung test tự động cho phần lõi xử lý (đặc biệt cơ chế đồng bộ nội dung và xử lý xung đột) để giảm phụ thuộc vào test tay.

**Có thể làm sau, không gấp:**
4. Quyết định giữ hoặc gỡ bỏ Developer Portal và route dư thừa để giảm nợ kỹ thuật.
5. Sửa lại các lệnh `make` đang hỏng, hoặc thay thế hoàn toàn bằng quy trình đang dùng hiện tại (CLI chính thức) để tránh gây nhầm lẫn cho người mới.
6. Cân nhắc tách Pipeline khỏi Backend thành 2 thành phần triển khai độc lập nếu quy mô sử dụng tăng đáng kể.
7. Bổ sung theo dõi tiến trình chi tiết hơn (theo từng file thay vì theo từng module) để cải thiện trải nghiệm khi import số lượng lớn.
8. Kết nối 2 pipeline xử lý PDF/Excel vào luồng chính nếu có nhu cầu thực tế từ phía sử dụng.
