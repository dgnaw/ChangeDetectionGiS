# Tài liệu Tổng hợp cho Cả Nhóm: Giải thích Dự án, Kiến trúc & Thuật ngữ GIS

> **Dành cho ai?** Cả 4 thành viên (A, B, C, D) đọc trong Tuần 1 để hiểu chung một ngôn ngữ, nắm rõ bản chất kỹ thuật của đồ án và biết chính xác phần việc của mình nằm ở đâu trong bức tranh tổng thể.

---

## 1. Dự án này làm gì? (Giải thích bằng ngôn ngữ dễ hiểu)

Đề tài của nhóm là **Phát hiện biến động Mặt nước và Dân cư theo thời gian (GIS Change Detection)** tại khu vực **Hành lang Sông Hồng – Hồ Tây – Đông Anh (Hà Nội)** giai đoạn **2016 – 2024**.

Hiểu một cách đơn giản, hệ thống tự động thực hiện 3 việc:
1. **Lấy ảnh chụp từ vệ tinh Sentinel-2** vào cùng mùa khô (Tháng 1 – Tháng 4) của 5 mốc năm: `2016, 2018, 2020, 2022, 2024`.
2. **Dùng công thức toán học (MNDWI + Otsu)** để tự động tách riêng toàn bộ vùng có mặt nước (Sông Hồng, Hồ Tây, Đầm Vân Trì, ao hồ nội đô/ven đô) và đo chính xác diện tích (`km²`) xem vùng nào bị thu hẹp (`loss`), vùng nào ổn định (`stable`), vùng nào mở rộng (`gain`).
3. **Chồng lớp với bản đồ mật độ dân số (GHSL)** trong hành lang bán kính `500m` quanh mặt nước, sau đó đưa toàn bộ lên **Website bản đồ tương tác (WebGIS)** có thanh trượt thời gian và biểu đồ thống kê để trả lời câu hỏi:
   > *"Trong giai đoạn 2016 – 2024, diện tích mặt nước quanh Sông Hồng – Hồ Tây – Đông Anh đã thay đổi ra sao và mật độ dân cư sống sát vùng nước (trong bán kính 500m) đã dịch chuyển như thế nào?"*

**Lưu ý học thuật cực quan trọng (nhớ để không bị bắt bẻ khi bảo vệ):**
- Hệ thống đo **Diện tích bề mặt nước (Surface Water Extent, đơn vị km²)** nhìn từ trên cao xuống, **KHÔNG** đo độ sâu hay mực nước (Water Level, đơn vị mét) vì ảnh vệ tinh quang học 2D không đo được độ sâu lòng sông/hồ.

---

## 2. Kiến trúc Hệ thống 4 Tầng & Cách chia 2 Luồng Độc lập

Hệ thống gồm 4 tầng rõ rệt, được cắt đôi tại ranh giới **`contracts/`** để **Người A** và **Người B** chạy song song 0% chờ đợi, không bao giờ xung đột code:

```text
[Tầng 1: Python ETL Pipeline Hợp nhất - NGƯỜI A (`services/gis-pipeline/`)]
  Ảnh Sentinel-2 (gốc EPSG:32648, bù trừ PB 04.00) + Dân số GHSL (100m)
        │  MNDWI + Otsu + Nội suy tuyến tính + Buffer 500m
        ▼
  File GeoJSON & JSON chuẩn EPSG:4326 (khớp 100% thư mục contracts/)
        │
        ├──────────────────► [Người C mở trên QGIS kiểm định & xuất bản đồ]
        ▼
[Tầng 2: Spatial Database - NGƯỜI B]
  PostgreSQL 16 + PostGIS 3.4 (lưu GEOMETRY ở EPSG:4326 + chỉ mục GIST)
        │
        ▼
[Tầng 3: Backend REST API - NGƯỜI B]
  FastAPI + GeoAlchemy2 (truy vấn `ST_AsGeoJSON` trực tiếp, trả về GeoJSON/JSON)
        │
        ├──────────────────► [Người D test trên Swagger /docs & phân tích số liệu]
        ▼
[Tầng 4: WebGIS Frontend - NGƯỜI B]
  React + TypeScript + MapLibre GL JS + Recharts (Time-Slider, Compare Mode)
```

---

## 3. Bảng Thuật ngữ & Công cụ Cốt lõi (Cả 4 người phải nắm vững)

| Thuật ngữ / Công cụ | Giải thích ngắn gọn, dễ hiểu | Vai trò trong đồ án |
| :--- | :--- | :--- |
| **Raster vs. Vector (GeoJSON)** | **Raster** là ảnh lưới ô vuông điểm ảnh pixel (như file ảnh vệ tinh `.tif`); **Vector (GeoJSON)** là các đối tượng hình học (điểm, đường, vùng đa giác) rất nhẹ và sắc nét khi phóng to. | Đầu vào (Sentinel-2, GHSL) là **Raster**; đầu ra truyền lên Web là **Vector GeoJSON**. |
| **EPSG:4326 vs. EPSG:32648** | `EPSG:4326` (WGS 84) đo bằng **độ (kinh độ, vĩ độ)** để hiển thị bản đồ toàn cầu. `EPSG:32648` (UTM Zone 48N cho miền Bắc VN) chiếu phẳng đo bằng **mét**. | Lưu PostGIS & hiển thị Web bằng `4326`; tính diện tích `km²` và `Buffer 500m` bắt buộc chuyển sang `32648`. |
| **Sentinel-2 L2A & STAC API** | Vệ tinh miễn phí của Châu Âu chụp lại mỗi ~5 ngày với 13 dải ánh sáng (độ phân giải 10m–20m). **STAC API** (Planetary Computer) cho phép cắt đúng vùng AOI Hà Nội về máy mà không cần tải cả cảnh ảnh nặng 1 GB. | Nguồn ảnh vệ tinh chính cho 5 mốc năm `2016, 2018, 2020, 2022, 2024`. |
| **Chỉ số MNDWI (Xu, 2006)** | Công thức: `MNDWI = (B03 - B11) ÷ (B03 + B11)` (trong đó `B03` là ánh sáng Xanh lục 10m, `B11` là Hồng ngoại sóng ngắn 20m). Nước hấp thụ mạnh tia `B11`, còn bê tông/nhà cửa phản xạ mạnh `B11`, nên MNDWI tách nước khỏi đô thị cực chuẩn. | Công thức toán học cốt lõi để khoanh vùng mặt nước. |
| **Lớp SCL & Ngưỡng Otsu** | **SCL** (Scene Classification Layer) là lớp nhãn đi kèm ảnh Sentinel-2 giúp lọc bỏ mây và bóng mây. **Otsu** là thuật toán tự động tìm ngưỡng cắt tối ưu giữa nước và đất tùy theo độ đục phù sa của nước Sông Hồng từng năm. | Làm sạch ảnh và tự động hóa bước tách nước (không chọn ngưỡng bằng tay cảm tính). |
| **Simplify (Douglas-Peucker)** | Thuật toán lược bỏ các đỉnh răng cưa dư thừa dọc theo cạnh đa giác (`simplify(0.0001, preserve_topology=True)`). | Giảm 70–80% dung lượng GeoJSON giúp bản đồ WebGIS chạy mượt mà không làm méo hình dạng. |
| **GHSL (GHS-POP R2023A)** | Bản đồ lưới mật độ dân số toàn cầu (độ phân giải 100m) do Ủy ban Châu Âu phát hành theo các mốc `2015, 2020, 2025`. Nhóm dùng nội suy tuyến tính theo từng pixel để đồng bộ đúng các năm `2016, 2018, 2020, 2022, 2024`. | Nguồn dữ liệu dân cư để chồng lớp với vùng đệm `500m` quanh mặt nước. |
| **JRC Global Surface Water** | Bộ dữ liệu mặt nước lịch sử toàn cầu của Trung tâm Nghiên cứu Chung Châu Âu (JRC). | Nguồn chuẩn độc lập để đối chứng độ chính xác (chỉ số `IoU`) kết quả MNDWI của nhóm. |
| **PostGIS & GIST Index** | Phần mở rộng không gian cho cơ sở dữ liệu PostgreSQL. **GIST Index** là chỉ mục cây không gian giúp tìm kiếm đa giác trong vùng bản đồ nhanh gấp hàng chục lần. | Cơ sở dữ liệu không gian của hệ thống WebGIS. |
| **MapLibre GL JS** | Thư viện mã nguồn mở vẽ bản đồ tương tác bằng tăng tốc phần cứng WebGL trên trình duyệt. | Hiển thị bản đồ động, thanh trượt năm và chế độ so sánh trên Frontend. |

---

## 4. Quy trình Làm việc Nhóm (2 Code Chính + 2 Chuyên môn GIS & Báo cáo)

- **Người A** (Xây móng + Data/GIS Pipeline): Làm chủ `services/gis-pipeline/`.
- **Người B** (Full-Stack WebGIS): Làm chủ `services/api/` và `apps/web/`.
- **Người C** (GIS Cartographer & Ground-Truth QA): Dùng **QGIS Desktop** để kiểm định trực quan file GeoJSON của Người A, chấm điểm mẫu Ground Truth và xuất toàn bộ bản đồ chuẩn học thuật cho báo cáo. Xem chi tiết tại [QGIS_GUIDE_FOR_C.md](QGIS_GUIDE_FOR_C.md).
- **Người D** (Spatial Data Analyst & System QA): Dùng **Swagger UI** và trình duyệt để kiểm thử hệ thống của Người B, phân tích bảng số liệu `timeseries_summary.json` và biên tập báo cáo 6 chương + Slide. Xem chi tiết tại [QA_AND_REPORT_GUIDE_FOR_D.md](QA_AND_REPORT_GUIDE_FOR_D.md).
