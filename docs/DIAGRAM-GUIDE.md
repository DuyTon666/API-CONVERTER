# Giải thích các loại sơ đồ UML

## UC tổng quát (Use Case Diagram)

Mô tả **hệ thống làm được gì** và **ai sử dụng nó**. Không đi vào chi tiết cách thực hiện — chỉ liệt kê chức năng và tác nhân. Elip = chức năng, hình người = tác nhân, mũi tên = quan hệ `<<include>>` / `<<extend>>`.

**Đọc để biết:** Phạm vi hệ thống, ai làm gì.

---

## UC chi tiết (Use Case Specification)

Mô tả **từng chức năng cụ thể** theo cấu trúc chuẩn: tác nhân, điều kiện tiên quyết, điều kiện hậu, luồng chính, luồng thay thế, luồng ngoại lệ.

**Đọc để biết:** Chức năng đó hoạt động như thế nào, lỗi nào có thể xảy ra.

---

## Activity Diagram

Mô tả **luồng xử lý bên trong một chức năng** — bước nào trước, bước nào sau, điều kiện rẽ nhánh ở đâu, vòng lặp xảy ra chỗ nào. Swimlane phân chia ai làm bước nào.

**Đọc để biết:** Logic xử lý, thứ tự các bước.

---

## Sequence Diagram

Mô tả **các thành phần giao tiếp với nhau như thế nào** theo thứ tự thời gian — Frontend gọi API nào, Backend gọi Pipeline ra sao, kết quả trả về theo chiều nào.

**Đọc để biết:** Luồng kỹ thuật giữa các layer, ai gọi ai lúc nào.

---

## Tóm tắt

| Loại | Câu hỏi trả lời | Đối tượng |
|---|---|---|
| UC tổng quát | Hệ thống làm gì? Ai dùng? | Khách hàng, BA |
| UC chi tiết | Chức năng hoạt động thế nào? | BA, tester |
| Activity | Luồng xử lý ra sao? | Developer, tester |
| Sequence | Các thành phần giao tiếp thế nào? | Developer, architect |
