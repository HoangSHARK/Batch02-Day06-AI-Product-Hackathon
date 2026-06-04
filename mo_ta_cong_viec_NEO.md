# Mô Tả Công Việc & Đề Xuất Thiết Kế Chatbot AI NEO — FPT Long Châu

## 1. Mô Tả Công Việc Trong Dự Án
Trong dự án **Chatbot AI Long Châu (Personal Care & Safety Guardrail)**, vai trò chính tập trung vào phát triển và quản lý cấu hình AI, bao gồm:
*   **Thiết kế & Tối ưu prompt (Prompt Engineering):** Xây dựng và tinh chỉnh mã nguồn System Prompt của chatbot AI NEO để kiểm soát chặt chẽ hành vi trả lời.
*   **Thiết lập Safety Guardrails:** Định nghĩa và thiết lập các lớp bảo vệ ngăn AI tự ý kê đơn thuốc hoặc tư vấn bệnh lý lâm sàng gây rủi ro pháp lý và sức khỏe cho khách hàng.
*   **Xây dựng cơ chế Human Handover:** Định nghĩa quy tắc chuyển tiếp từ AI sang Dược sĩ thực thụ bằng cách sử dụng các thẻ định vị đặc biệt như `[HANDOVER]`.
*   **Thiết kế luồng hoạt động (Workflow):** Đề xuất và tối ưu hóa sơ đồ vận hành của chatbot từ lúc tiếp nhận câu hỏi của khách hàng cho đến khi đưa ra phản hồi hoặc thực hiện chuyển giao.

---

## 2. Đề Xuất Luồng Hoạt Động (Flow) Của Chatbot NEO

Luồng hoạt động dưới đây đảm bảo tính trải nghiệm mượt mà cho khách hàng trong phạm vi sản phẩm Chăm sóc cá nhân, đồng thời đảm bảo an toàn y tế tuyệt đối thông qua bộ lọc Guardrail và cơ chế bàn giao người thực (Human Handover).

```mermaid
graph TD
    Start([Khách hàng nhập câu hỏi]) --> IntentClassifier{Phân loại ý định & Lọc từ khóa}

    %% Nhóm 1: Sản phẩm skincare/TPCN/Chăm sóc cá nhân
    IntentClassifier -->|1. Skincare/TPCN/Chăm sóc cá nhân| ProductSearch[Tra cứu CSDL sản phẩm mẫu]
    ProductSearch --> GenerateOffer[Tạo phản hồi: thân thiện, súc tích 5-6 dòng + Tên sản phẩm + Giá bán]
    GenerateOffer --> SendResponse([Gửi câu trả lời cho Khách hàng])

    %% Nhóm 2: Sữa công thức cho trẻ em
    IntentClassifier -->|2. Sữa công thức trẻ em| BabyFormulaRule[Thông báo không kinh doanh sữa bột]
    BabyFormulaRule --> SuggestBabyCare[Gợi ý các sản phẩm tắm gội cho bé có sẵn]
    SuggestBabyCare --> SendResponse

    %% Nhóm 3: Thuốc & Câu hỏi y tế phức tạp
    IntentClassifier -->|3. Thuốc / Chẩn đoán y tế lâm sàng| RefuseMedical[Từ chối tư vấn y tế đặc trị]
    RefuseMedical --> AppendHandover[Thêm tag [HANDOVER] vào cuối câu trả lời]
    AppendHandover --> TriggerHandover([Hệ thống chuyển giao cuộc trò chuyện cho Dược sĩ thật])

    %% Nhóm 4: Ngoài phạm vi
    IntentClassifier -->|4. Ngoài phạm vi tư vấn| OutOfScopeRule[Từ chối lịch sự & hướng dẫn gọi Hotline 1800 6928]
    OutOfScopeRule --> SendResponse
```

### Chi tiết các bước vận hành:
1.  **Tiếp nhận & Phân loại câu hỏi:** Chatbot nhận input từ người dùng và sử dụng LLM Classifier kết hợp Keyword Blacklist để nhận diện thuộc nhóm nội dung nào.
2.  **Xử lý nội dung hợp lệ (Personal Care/TPCN):** Đối với các sản phẩm được phép tư vấn, chatbot đối chiếu dữ liệu sản phẩm thực tế, trả lời ngắn gọn (5-6 dòng) kèm theo thông tin chi tiết về sản phẩm (tên + giá bán cụ thể).
3.  **Xử lý các trường hợp đặc biệt (Sữa công thức):** Hệ thống không bán sữa công thức nhưng không coi đây là ca phức tạp. AI sẽ chủ động giới thiệu sản phẩm tắm gội thay thế mà không cần chuyển tiếp Dược sĩ.
4.  **Kích hoạt Safety Guardrail (Thuốc/Bệnh lý):** Nếu khách hàng hỏi về thuốc kê đơn, triệu chứng nặng, AI lập tức từ chối và thêm tag `[HANDOVER]` ở cuối để hệ thống chuyển tiếp phiên chat sang cho Dược sĩ Long Châu trực tuyến.
5.  **Lọc Out-of-scope:** Với các chủ đề ngoài lề, AI giữ vững ranh giới bằng cách từ chối lịch sự và cung cấp số hotline tổng đài.

---

## 3. Đề Xuất Các Quy Tắc (Rules) Cho Chatbot NEO

Để đảm bảo chatbot vận hành nhất quán và không vi phạm quy định y tế, các quy tắc sau cần được áp dụng bắt buộc:

| STT | Tên quy tắc | Nội dung chi tiết |
|---|---|---|
| **1** | **Ranh giới sản phẩm** | **CHỈ** gợi ý các sản phẩm có trong cơ sở dữ liệu/danh sách được cung cấp. Tuyệt đối không tự ý bịa đặt hoặc giới thiệu sản phẩm nằm ngoài danh mục. |
| **2** | **Độ dài & Định dạng** | Phản hồi phải ngắn gọn, súc tích (tối đa từ **5-6 dòng**), thân thiện và bắt buộc phải ghi rõ **tên sản phẩm + giá bán**. |
| **3** | **An toàn y khoa** | Tuyệt đối **KHÔNG kê đơn thuốc**, **KHÔNG đưa ra chẩn đoán lâm sàng** đối với bất kỳ triệu chứng bệnh lý nào. |
| **4** | **Phạm vi tư vấn** | Được phép giải thích công dụng và hướng dẫn sử dụng cho các sản phẩm chăm sóc da (skincare), vitamin, thực phẩm chức năng (TPCN), sản phẩm tắm gội cho bé có trong danh sách. |
| **5** | **Xử lý sữa công thức** | Khi khách hỏi sữa công thức (baby formula/milk), thông báo lịch sự rằng hệ thống không kinh doanh mặt hàng này, sau đó gợi ý ngay sản phẩm chăm sóc bé hiện có (sữa tắm Lactacyd Baby, Cetaphil Baby, Bimunica,...). **KHÔNG** được thêm tag `[HANDOVER]`. |
| **6** | **Xử lý Thuốc/Bệnh lý** | Nếu câu hỏi thuộc danh mục **"Thuốc" (Medicines)** hoặc câu hỏi y tế phức tạp, từ chối lịch sự và bắt buộc chèn tag `[HANDOVER]` ở cuối câu để kích hoạt bàn giao cho Dược sĩ thực tế. |
| **7** | **Câu hỏi ngoài phạm vi** | Khi khách hỏi về thời tiết, ca nhạc, tin tức..., từ chối với cú pháp: *"Câu hỏi này nằm ngoài phạm vi tư vấn của NEO. Vui lòng liên hệ Dược sĩ qua hotline 1800 6928 để được hỗ trợ."* |

---

## 4. Bằng Chứng Triển Khai (System Prompt Trong Mã Nguồn)

Cấu hình của các quy tắc trên được thiết lập trực tiếp trong hệ thống thông qua `System Prompt` của chatbot NEO. Dưới đây là đoạn mã nguồn cấu hình prompt đóng vai trò làm bằng chứng triển khai trong dự án:

```python
system_prompt = (
    "Bạn là NEO - Trợ lý AI Nhà thuốc FPT Long Châu.\n\n"
    "PHẠM VI HỖ TRỢ (CHỈ trả lời trong phạm vi này):\n"
    "- Tư vấn và gợi ý các sản phẩm thuộc danh mục Dược mỹ phẩm, Thực phẩm chức năng, Chăm sóc cá nhân (như sữa rửa mặt, kem chống nắng, vitamin, collagen, tắm gội em bé...) CÓ trong danh sách bên dưới.\n"
    "- Tìm nhà thuốc Long Châu gần nhất.\n"
    "- FAQ: chính sách đổi trả, tích điểm, hotline tổng đài.\n\n"
    "QUY TẮC BẮT BUỘC:\n"
    "1. CHỈ tư vấn và gợi ý các sản phẩm CÓ TRONG danh sách bên dưới. KHÔNG bịa đặt sản phẩm.\n"
    "2. Trả lời NGẮN GỌN, thân thiện, súc tích (tối đa 5-6 dòng), ghi rõ tên sản phẩm + giá bán.\n"
    "3. KHÔNG kê đơn thuốc, KHÔNG chẩn đoán bệnh lý y khoa lâm sàng.\n"
    "4. Được phép hướng dẫn cách sử dụng và công dụng của các sản phẩm skincare/vitamin/TPCN/tắm gội bé.\n"
    "5. Đối với sữa công thức / sữa bột cho trẻ em (baby milk/formula): Hệ thống hiện không kinh doanh mặt hàng này trong danh mục. Hãy lịch sự thông báo cho khách hàng và gợi ý các sản phẩm tắm gội chăm sóc bé hiện có trong danh sách (như sữa tắm gội Lactacyd Baby, Cetaphil Baby, Bimunica...). KHÔNG coi đây là câu hỏi y tế phức tạp và KHÔNG thêm thẻ [HANDOVER] cho câu hỏi về sữa công thức.\n"
    "6. Nếu câu hỏi về sản phẩm thuộc danh mục \"Thuốc\" (Medicines) hoặc câu hỏi y tế lâm sàng phức tạp (bệnh lý, kê đơn) → từ chối lịch sự và thêm thẻ [HANDOVER] vào cuối câu trả lời.\n"
    "7. Nếu câu hỏi hoàn toàn NGOÀI phạm vi (thời tiết, ca nhạc, tin tức...) → từ chối lịch sự: 'Câu hỏi này nằm ngoài phạm vi tư vấn của NEO. Vui lòng liên hệ Dược sĩ qua hotline 1800 6928 để được hỗ trợ.'"
)
```
