# CI/CD — Tổng Quan & Mục Tiêu

---

## 1. Tổng quan

CI/CD (Continuous Integration / Continuous Delivery hoặc Continuous Deployment) là quy trình tự động hóa trong phát triển phần mềm nhằm hỗ trợ việc kiểm tra, tích hợp và triển khai hệ thống một cách nhanh chóng, ổn định và nhất quán.

Tài liệu này mô tả quy trình CI/CD được áp dụng cho dự án nhằm chuẩn hóa API theo tiêu chuẩn **OpenAPI 3.1**. Thông qua pipeline tự động, hệ thống sẽ:

- Kiểm tra cấu trúc tài liệu API
- Validate schema
- Đảm bảo tính nhất quán giữa các endpoint
- Duy trì chất lượng tài liệu trong suốt quá trình phát triển

**Đối tượng đọc:** Backend Developer, Frontend Developer, QA, DevOps.

CI/CD nên được sử dụng khi dự án cần:

- Tự động kiểm tra và validate tài liệu API
- Đảm bảo API tuân thủ chuẩn OpenAPI 3.1
- Giảm lỗi cấu hình hoặc sai lệch schema giữa các thành viên
- Tăng tính nhất quán trong quy trình phát triển và triển khai
- Hỗ trợ làm việc nhóm hiệu quả thông qua quy trình kiểm tra tự động trước khi merge hoặc deploy

---

## 2. Mục tiêu & vai trò

Sau khi đọc xong tài liệu này, thành viên trong team có thể:

- Hiểu được quy trình hoạt động của hệ thống CI/CD trong dự án
- Biết cách cấu hình và sử dụng pipeline để kiểm tra tài liệu API
- Thực hiện validate API theo chuẩn OpenAPI 3.1 trước khi merge hoặc deploy
- Phát hiện và xử lý các lỗi liên quan đến schema, endpoint hoặc cấu trúc tài liệu API
- Tuân thủ đúng quy chuẩn tài liệu API được áp dụng trong toàn bộ dự án

Tài liệu này được xây dựng nhằm giải quyết các vấn đề:

- API thiếu tính nhất quán giữa các thành viên phát triển
- Sai cấu trúc hoặc không đúng chuẩn OpenAPI 3.1
- Phát sinh lỗi khi tích hợp giữa frontend, backend và QA
- Thiếu quy trình kiểm tra tự động trước khi merge source code
- Khó khăn trong việc quản lý và duy trì tài liệu API khi hệ thống mở rộng
- Tốn thời gian kiểm tra thủ công và dễ xảy ra sai sót

---

## 3. Điều kiện trước khi bắt đầu

### 3.1 Kiến thức cần có

- Hiểu về Git và quy trình làm việc với GitHub/GitLab
- Biết cách sử dụng command line hoặc terminal
- Có kiến thức cơ bản về API REST
- Hiểu cấu trúc tài liệu OpenAPI/Swagger
- Biết cách đọc và chỉnh sửa file YAML hoặc JSON
- Hiểu khái niệm cơ bản về CI/CD và pipeline tự động

### 3.2 Công vụ & môi trường cần thiết

Cần cài đặt và chuẩn bị:

- **Git** (phiên bản mới nhất)
- **Node.js** (khuyến nghị sử dụng phiên bản LTS)
- **npm** hoặc **yarn** (phiên bản mới nhất)
- Khuyến nghị cài đặt thêm **nvm** để quản lý phiên bản Node.js
- Trình soạn thảo mã nguồn (khuyến nghị: **VS Code**)
- Tài khoản **GitHub** để làm việc với repository

Công cụ validate OpenAPI:

- **Redocly CLI**
- **Spectral CLI**
