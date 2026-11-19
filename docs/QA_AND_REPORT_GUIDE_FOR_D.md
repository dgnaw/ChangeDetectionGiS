# Hướng dẫn Chi tiết cho Người D — Spatial Data Analyst, System QA & Tổng biên tập Báo cáo

> **Vai trò của bạn trong nhóm:** Bạn **không cần viết code**. Bạn là người kiểm định hệ thống API & WebGIS của Người B dưới góc nhìn người dùng/QA, là người phân tích số liệu thống kê từ đầu ra của Người A để rút ra câu chuyện khoa học cho **Chương 5**, và là người điều phối ghép nối hoàn chỉnh cuốn báo cáo 6 chương + Slide bảo vệ.

---

## 1. Cách Kiểm thử Backend API không cần code (Tuần 3 & Tuần 7)

Khi Người B hoàn thiện Backend FastAPI, bạn chỉ cần mở trình duyệt truy cập **`http://localhost:8000/docs`** (giao diện Swagger UI tự động). Với mỗi endpoint, bấm **Try it out → Execute** và ghi lại kết quả vào bảng Test Case cho Chương 4 & Chương 5:

| Mã Test | Endpoint cần kiểm tra | Tham số thử nghiệm | Kết quả kỳ vọng (Pass) |
| :--- | :--- | :--- | :--- |
| `API-01` | `GET /api/v1/health` | Không có | HTTP `200 OK`, trả về `{"status": "ok", "database": "connected"}` |
| `API-02` | `GET /api/v1/aoi` | Không có | HTTP `200 OK`, trả về GeoJSON Polygon khu vực Sông Hồng – Hồ Tây – Đông Anh |
| `API-03` | `GET /api/v1/layers/water` | `year = 2020` | HTTP `200 OK`, có `type: "FeatureCollection"`, mỗi feature có `area_km2`, `change_type` |
| `API-04` | `GET /api/v1/layers/population` | `year = 2024`, `only_buffer = true` | HTTP `200 OK`, toàn bộ feature trả về đều có `in_water_buffer_500m: true` |
| `API-05` | `GET /api/v1/analytics/timeseries` | Không có | HTTP `200 OK`, đủ 5 mốc năm `2016, 2018, 2020, 2022, 2024` |
| `API-06` | `GET /api/v1/layers/water` | `year = 1999` (năm sai) | Trả về mã lỗi hợp lệ (`400` hoặc `404`), không làm sập server (`500`) |

---

## 2. Bảng Kịch bản Kiểm thử Giao diện WebGIS (Tuần 5 & Tuần 7)

Mở trình duyệt tại **`http://localhost:5173`** và kiểm tra lần lượt các chức năng sau (chụp ảnh màn hình sắc nét ở bước `UI-01`, `UI-03`, `UI-04`, `UI-05` để chèn vào **Chương 4**):

| Mã Test | Chức năng WebGIS | Thao tác kiểm thử | Kết quả kỳ vọng |
| :--- | :--- | :--- | :--- |
| `UI-01` | Bản đồ nền & AOI | Tải lại trang (`F5`) | Bản đồ tự căn giữa vào Hà Nội (Sông Hồng – Hồ Tây – Đông Anh), hiện viền đỏ AOI. |
| `UI-02` | Bật/tắt lớp & Opacity | Tắt lớp Dân cư, kéo độ mờ (Opacity) lớp Nước xuống 50% | Lớp bản đồ phản hồi ngay lập tức, không giật lag. |
| `UI-03` | Thanh trượt thời gian (Time-Slider) | Kéo từ `2016 → 2024` và bấm nút Play | Hình dạng mặt nước và màu lưới dân cư cập nhật mượt qua từng mốc năm. |
| `UI-04` | Chế độ So sánh (Compare Mode) | Bật Compare giữa `2016` và `2024` | Hiển thị rõ vùng nước ổn định (`stable`), mở rộng (`gain`), thu hẹp (`loss`). |
| `UI-05` | Biểu đồ tương quan & Popup | Click vào 1 vùng nước trên bản đồ và xem biểu đồ bên cạnh | Hiện Popup đúng diện tích `km²`; biểu đồ Recharts khớp 100% số liệu `timeseries_summary.json`. |
| `UI-06` | Tốc độ tải | Mở `F12 → Network`, đổi năm trên thanh trượt | Thời gian phản hồi API dưới `300 ms`. |

---

## 3. Hướng dẫn Phân tích Số liệu cho Chương 5 (Từ `timeseries_summary.json`)

Khi Người A chạy xong dữ liệu thật ở Tuần 6 và đưa file `timeseries_summary.json`, bạn mở file đó (có thể copy vào Excel) để tính thêm **3 chỉ số biến động cốt lõi** đưa vào bảng nhận xét Chương 5:

1. **Tốc độ biến động diện tích mặt nước giai đoạn 2016 – 2024:**
   - Công thức: `ΔWater (%) = ((Diện tích 2024 - Diện tích 2016) ÷ Diện tích 2016) × 100%`
   - So sánh riêng từng chu kỳ 2 năm (`2016→2018`, `2018→2020`, `2020→2022`, `2022→2024`) để chỉ ra giai đoạn nào biến động mạnh nhất (ví dụ năm hạn hán mùa khô hoặc giai đoạn đô thị hóa mạnh tại Đông Anh).
2. **Tốc độ tăng trưởng dân số trong vùng đệm 500m ven nước:**
   - Công thức: `ΔPop_Buffer (%) = ((Pop_500m_2024 - Pop_500m_2016) ÷ Pop_500m_2016) × 100%`
   - So sánh với tốc độ tăng dân số chung toàn AOI để rút ra kết luận: *Người dân có xu hướng tập trung ngày càng dày hơn vào hành lang 500m quanh Sông Hồng – Hồ Tây – Đông Anh hay không?*
3. **Đánh giá độ tin cậy của hệ thống:**
   - Dẫn lại chỉ số `jrc_iou_score` từ Người A (kỳ vọng `≥ 0.80`) kết hợp với bảng `Confusion Matrix` 30 điểm Ground Truth từ Người C.

---

## 4. Khung Chuẩn 6 Chương Báo cáo Chuyên đề (~45–55 trang)

*(Báo cáo Word/Google Docs và Slide Canva/PowerPoint được quản lý trên Google Drive chung của nhóm để giữ Git repo gọn sạch cho phần mã nguồn & tài liệu kỹ thuật).*

| Chương | Số trang dự kiến | Người viết chính | Nội dung bắt buộc phải có |
| :--- | :--- | :--- | :--- |
| **Chương 1 · Tổng quan đề tài** | ~4 trang | **Người D** *(C cấp hình AOI)* | Lý do chọn đề tài; đặc điểm địa lý Hành lang Sông Hồng – Hồ Tây – Đông Anh; mục tiêu & phạm vi 2016–2024; phân biệt *Diện tích mặt nước* vs *Mực nước*. |
| **Chương 2 · Cơ sở lý thuyết & Công nghệ** | ~8 trang | **Người D** *(C cấp ảnh S2)* | Dữ liệu Raster/Vector; `EPSG:4326` vs `EPSG:32648`; đặc tính phổ Sentinel-2 & công thức MNDWI; lưới dân số GHSL; tổng quan PostGIS, FastAPI, MapLibre. |
| **Chương 3 · Dữ liệu & Phương pháp xử lý** | ~11 trang | **Người C** *(A duyệt kỹ thuật)* | Truy xuất STAC Planetary Computer; lọc mây SCL & resample 10m; MNDWI + Otsu; khử nhiễu, vector hóa & `simplify`; nội suy tuyến tính GHSL & chồng lớp `Buffer 500m`. |
| **Chương 4 · Thiết kế & Xây dựng WebGIS** | ~12 trang | **Người D** *(B cấp ERD/code)* | Kiến trúc 4 tầng & Hợp đồng dữ liệu `contracts/`; thiết kế bảng PostGIS (`GEOMETRY`, `GIST`); đặc tả 5 REST API (kèm ảnh Swagger); giao diện WebGIS (Time-Slider, Compare, Recharts). |
| **Chương 5 · Kết quả thực nghiệm & Đánh giá** | ~12 trang | **Người D** *(C cấp 3 bản đồ)* | Bảng & biểu đồ biến động mặt nước 2016–2024; biến động dân cư trong hành lang 500m; đối chứng độ chính xác (JRC IoU + Confusion Matrix 30 điểm); đánh giá hiệu năng API và hạn chế (mây mùa mưa, bóng nhà cao tầng). |
| **Chương 6 · Kết luận & Hướng phát triển** | ~3 trang | **Người D** | Đối chiếu Mục tiêu (Chương 1) vs Kết quả đạt được; Hướng phát triển: tích hợp ảnh Radar **Sentinel-1 (SAR)** xuyên mây cho mùa lũ và mô hình độ cao số **DEM** ước lượng thể tích nước. |
