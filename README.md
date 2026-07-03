# 📚 Finally The Light (Novel Translator Web App)

Hệ thống dịch thuật tiểu thuyết đa ngôn ngữ, đa thể loại sử dụng Google GenAI API (Gemini/Gemma). Phiên bản web được phát triển đáp ứng đầy đủ các đặc tả thiết kế và luồng xử lý trong `DESIGN.md` và `TODO.md`.

---

## 🛠️ Tính năng nổi bật

- **Giao diện Split-Pane Translator**: Thiết kế 2 cột chuẩn DeepL tối giản, canvas ngà ấm, dùng đường kẻ tóc hairline phân tách, điểm xuyết duy nhất **Dấu son màu đỏ** (`#C1272D`) khi hoàn tất.
- **Tải lên & Tải xuống tệp tin**: Dễ dàng kéo thả tệp tin `.txt`/`.md` để dịch và tải xuống tệp kết quả dịch cùng tệp báo cáo thuật ngữ.
- **Hàng Pill Chọn Thể Loại**: Tích hợp các thể loại từ `genres.yaml` (tiên hiệp, khoa học viễn tưởng, huyền ảo, lãng mạn...) để điều chỉnh văn phong tự động của mô hình.
- **Thư viện thuật ngữ (Glossary Drawer)**: Drawer trượt từ phải để quản lý động các danh từ riêng và danh sách nhân vật (tên dịch, vai trò, xưng hô).
- **Tooltip Thuật Ngữ Thông Minh**: Các từ có trong bảng thuật ngữ được tự động gạch chân nét đứt màu son trong bản dịch, rê chuột vào sẽ hiển thị tooltip bản dịch chi tiết.
- **Tiến Trình Dịch Trực Quan**: Hiển thị phần trăm tiến trình, đếm số chunk, và xem nhật ký hoạt động của pipeline (Real-time logs) dạng terminal console ngay bên dưới màn hình.
- **Resume Checkpoint**: Tự động phục hồi trạng thái từ checkpoint khi gặp sự cố, cho phép tiếp tục dịch mà không bị mất chi phí token.

---

## ⚙️ Cài đặt & Khởi chạy

### 1. Cài đặt các thư viện cần thiết
Đảm bảo bạn đã kích hoạt môi trường ảo `.venv` hoặc sử dụng pip toàn hệ thống:
```bash
pip install -r requirements.txt
```

### 2. Thiết lập API Key
Tạo hoặc kiểm tra tệp tin `.env` bên trong thư mục `backend/` có chứa khóa API của Google GenAI:
```env
GEMINI_API_KEY="AIzaSyAg..."
```

### 3. Khởi chạy FastAPI Server
Mở terminal và chuyển hướng vào thư mục `backend/`, sau đó khởi chạy Uvicorn:
```bash
cd backend
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

### 4. Truy cập giao diện Web
Sau khi server chạy, truy cập đường dẫn sau trên trình duyệt của bạn:
```
http://127.0.0.1:8000/
```

---

## 📁 Cấu trúc dự án

```
Finally The Light - LLM_Trans_Web/
├── backend/
│   ├── app.py               ← Web API chính (FastAPI) phục vụ frontend & backend pipeline
│   ├── main.py              ← CLI entry point
│   ├── src/                 ← Bộ mã nguồn lõi dịch thuật (pipeline, chunker, glossary_manager...)
│   ├── config/              ← Thiết lập settings.yaml & genres.yaml
│   ├── data/                ← Bộ nhớ đệm glossary và temp_inputs
│   └── logs/                ← File logs chạy của từng project
├── frontend/
│   ├── index.html           ← Layout trang web tối giản, tinh tế (Vue 3 CDN)
│   ├── index.css            ← Hệ thống CSS Design Tokens (màu mực đen, giấy trắng, dấu son, hairline)
│   └── index.js             ← Logic ứng dụng và giao tiếp API
└── requirements.txt         ← Quản lý các thư viện Python
```
