# Codebase - FPT Long Châu Interactive Clone & AI Chatbot NEO

Thư mục này chứa toàn bộ mã nguồn của prototype ứng dụng web **Nhà thuốc FPT Long Châu Clone** tích hợp **Trợ lý ảo AI NEO**.

---

## 1. Hướng dẫn cài đặt & Chạy ứng dụng

### Bước 1: Cài đặt các thư viện cần thiết
Đảm bảo bạn đã cài đặt Python 3. Chạy lệnh sau để cài đặt các package phụ thuộc:
```bash
pip install flask httpx python-dotenv google-genai pyngrok
```

### Bước 2: Cấu hình biến môi trường
1. Nhân bản file `.env.example` thành `.env` nằm cùng cấp với file `app.py`.
2. Mở file `.env` vừa tạo và điền key API Gemini của bạn vào:
```env
GEMINI_API_KEY=AIzaSy...
```

### Bước 3: Chạy ứng dụng
Khởi chạy Flask development server bằng lệnh:
```bash
python app.py
```
Mặc định, ứng dụng sẽ chạy tại địa chỉ: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**.

*(Tùy chọn) Để tạo đường link public ngrok chia sẻ ra ngoài:*
```bash
ngrok http 5000
```

---

## 2. Công cụ & API sử dụng

*   **Backend:** Python 3, Flask framework.
*   **Frontend:** HTML5, CSS3 (thiết kế Responsive theo UI Long Châu thật), JavaScript thuần (ES6+).
*   **AI API:** SDK `google-genai` chính thức, sử dụng mô hình **Gemini 2.5 Flash** cho tốc độ phản hồi cực nhanh (< 2s) và khả năng xử lý ngữ cảnh tốt.
*   **Proxy & Crawler:** Thư viện `httpx` dùng để proxy các file tĩnh (CSS/JS/Fonts) từ website Long Châu thật, và crawler theo dạng `__NEXT_DATA__` để lấy chi tiết sản phẩm trực tuyến thời gian thực (real-time).
*   **State Management:** Sử dụng `localStorage` trên trình duyệt để lưu trữ giỏ hàng (không cần đăng nhập) và đồng bộ badge số lượng sản phẩm trên header.

---

## 3. Phân công công việc (Nhóm 5)

| Thành viên | Nhiệm vụ đảm nhận | Kết quả đóng góp |
|---|---|---|
| **A** | Nghiên cứu & Thiết lập dữ liệu | Thu thập dữ liệu 500+ sản phẩm mẫu, xây dựng danh mục skincare, danh sách địa chỉ 12 chi nhánh giả lập tại HN/HCM. |
| **B** | Thiết kế SPEC & Viết Prompt | Hoàn thiện bản tài liệu SPEC y khoa, xây dựng bộ lọc chặn nhanh từ khóa y tế, thiết lập System Prompt an toàn cho AI NEO. |
| **C** | Phát triển Prototype (Lập trình chính) | Lập trình Flask backend, xử lý proxy CSS/JS, crawler live dữ liệu sản phẩm, phát triển giao diện Chatbot UI, Giỏ hàng localStorage, Toast thông báo. |
| **D** | Kiểm thử & Tối ưu hóa | Xây dựng 15+ test cases chống jailbreak (lách luật), thử nghiệm luồng chatbot, phát hiện và đề xuất sửa lỗi rò rỉ ngữ cảnh y tế trong history chat. |
| **E** | Demo & Presentation | Thiết kế slides thuyết trình, soạn kịch bản pitching 3 phút, chuẩn bị dữ liệu thử nghiệm live cho buổi báo cáo. |
