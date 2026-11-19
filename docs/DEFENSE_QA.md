# Bộ Câu hỏi & Câu trả lời Bảo vệ Đồ án (Chia riêng cho 4 Thành viên A, B, C, D)

> **Mục tiêu:** Đảm bảo cả 4 thành viên đều nắm chắc bản chất hệ thống và trả lời trôi chảy, đúng trọng tâm học thuật khi giảng viên hỏi xoáy từng cá nhân.

---

## 1. Câu hỏi dành cho Người A (Data & Remote Sensing Pipeline Lead)

**Q1. Tại sao dùng Planetary Computer STAC API thay vì tải ảnh trực tiếp trên Copernicus Browser?**
> **Trả lời:** Một cảnh ảnh Sentinel-2 đầy đủ nặng 800 MB – 1 GB cho vùng 100 km × 100 km, trong khi AOI của nhóm chỉ khoảng 242 km² và chỉ cần 3 kênh (`B03`, `B11`, `SCL`). Dữ liệu trên Planetary Computer lưu ở định dạng Cloud-Optimized GeoTIFF (COG) qua chuẩn STAC, cho phép đọc cắt cửa sổ (Windowed Read) trực tiếp đúng phạm vi AOI, giảm ~95% dung lượng tải và tự động hóa hoàn toàn bằng Python cho cả 5 năm.

**Q2. Tại sao dùng thuật toán phân ngưỡng động Otsu thay vì cố định ngưỡng `MNDWI > 0`?**
> **Trả lời:** Nước Sông Hồng mang hàm lượng phù sa thay đổi theo từng năm, làm giá trị phổ phản xạ dịch chuyển nhẹ. Ngưỡng cố định `0.0` dễ bỏ sót nước đục hoặc nhận nhầm đất ẩm ven bãi bồi. Thuật toán Otsu tự động tìm ngưỡng cực đại hóa phương sai giữa hai lớp (nước và không phải nước) trên từng năm riêng biệt, giúp kết quả tách nước ổn định hơn.

**Q3. Tại sao khi chồng lớp vùng đệm 500m với dân cư lại tính bằng `rasterio.mask` thay vì `geopandas.overlay()`?**
> **Trả lời:** Ở độ phân giải 100m của GHSL, vùng AOI ~242 km² có tới ~24.200 ô vuông mỗi năm. Chồng lớp hình học hai lớp vector bằng `gpd.overlay()` rất chậm và dễ sai số phân mảnh đa giác. Dùng đa giác `Buffer 500m` (hệ `EPSG:32648`) cắt trực tiếp lên mảng raster dân số 100m bằng `rasterio.mask` vừa nhanh gấp hàng chục lần vừa bảo toàn chính xác tổng dân số.

---

## 2. Câu hỏi dành cho Người B (Full-Stack WebGIS & Spatial DB Lead)

**Q1. Vai trò của chỉ mục không gian `GIST Index` trong PostGIS là gì?**
> **Trả lời:** Truy vấn dữ liệu hình học (như lọc theo khung nhìn bản đồ `ST_Intersects` hoặc cắt vùng) không thể dùng chỉ mục B-Tree thông thường. `GIST` (Generalized Search Tree) lưu hình chữ nhật bao (Bounding Box) của từng đa giác theo cấu trúc cây R-Tree, giúp PostGIS loại bỏ nhanh các vùng không liên quan và giữ thời gian phản hồi API dưới 200 ms.

**Q2. Làm sao hai người code chính (A và B) làm việc song song mà không phải chờ nhau?**
> **Trả lời:** Nhóm áp dụng kiến trúc **Contract-First**. Ngay Tuần 1, nhóm khóa cứng JSON Schema và tạo bộ dữ liệu giả lập trong `contracts/mock/` cùng `contracts/aoi.geojson`. Người B dùng bộ mock để xây dựng toàn bộ PostGIS, FastAPI và React/MapLibre từ Tuần 2 đến Tuần 6. Sang Tuần 7, khi Người A xuất dữ liệu thật vào `data/processed/`, chỉ cần chạy lại đúng 1 lệnh `seed.py` để chuyển sang dữ liệu thật.

**Q3. Tại sao chọn MapLibre GL JS thay vì Leaflet?**
> **Trả lời:** Khi hiển thị đồng thời nhiều năm dữ liệu đa giác mặt nước kết hợp hàng nghìn ô lưới mật độ dân cư (Choropleth), Leaflet vẽ bằng DOM/SVG dễ bị giật khung hình. MapLibre GL JS sử dụng tăng tốc phần cứng WebGL (GPU) nên render mượt 60 FPS khi kéo thanh trượt thời gian Time-Slider.

---

## 3. Câu hỏi dành cho Người C (GIS Cartographer & Ground-Truth QA)

**Q1. Tại sao nhóm dùng chỉ số `MNDWI = (B03 - B11) ÷ (B03 + B11)` mà không dùng `NDWI = (B03 - B08) ÷ (B03 + B08)`?**
> **Trả lời:** Khu vực nghiên cứu Hà Nội (Hồ Tây – Sông Hồng – Đông Anh) có mật độ đô thị rất cao. Trong NDWI gốc (McFeeters, 1996), mái nhà bê tông và đường nhựa có phản xạ tương tự nước ở dải `B08` (NIR) nên hay bị nhận nhầm thành nước. Chỉ số MNDWI (Xu, 2006) thay `B08` bằng dải hồng ngoại sóng ngắn `B11` (SWIR): nước hấp thụ mạnh `B11` trong khi đất và bê tông phản xạ mạnh `B11`, giúp loại bỏ triệt để nhiễu đô thị.

**Q2. Tại sao lưu trữ và truyền API dùng `EPSG:4326`, còn khi tính diện tích `km²` và `Buffer 500m` lại phải chuyển sang `EPSG:32648`?**
> **Trả lời:** `EPSG:4326` (WGS 84) là hệ tọa độ địa lý đo bằng **độ góc (kinh độ/vĩ độ)**, không thể đo trực tiếp mét hay `km²` vì độ dài 1 độ kinh tuyến thay đổi theo vĩ độ. Hà Nội nằm ở múi chiếu UTM 48 Bắc (`EPSG:32648`), là hệ tọa độ phẳng đo bằng **mét**, nên mọi phép đo diện tích và tạo vùng đệm bán kính 500m bắt buộc thực hiện trên `EPSG:32648`.

**Q3. Kênh `B03` có độ phân giải 10m nhưng kênh `B11` và lớp mây `SCL` là 20m, xử lý sự chênh lệch này thế nào?**
> **Trả lời:** Trước khi tính MNDWI, nhóm đưa `B11` từ 20m về 10m bằng nội suy **Bilinear** (vì đây là giá trị phản xạ liên tục) và đưa `SCL` từ 20m về 10m bằng **Nearest Neighbor** (vì đây là nhãn phân loại rời rạc, không được lấy trung bình giữa hai mã nhãn).

**Q4. Em đã kiểm chứng độ chính xác kết quả phân loại nước bằng cách nào?**
> **Trả lời:** Em kiểm chứng độc lập trên QGIS theo hai cách: (1) Chấm bộ 30 điểm mẫu thực địa (Ground Truth — 15 điểm nước, 15 điểm đất) trực tiếp trên ảnh vệ tinh gốc để lập Ma trận nhầm lẫn (Confusion Matrix) tính độ chính xác tổng thể; và (2) Đối chiếu diện tích trùng khớp (chỉ số `IoU`) với bộ dữ liệu chuẩn quốc tế JRC Global Surface Water.

---

## 4. Câu hỏi dành cho Người D (Spatial Data Analyst & System QA)

**Q1. Dữ liệu dân số GHSL chỉ phát hành theo mốc 5 năm (`2015, 2020, 2025`), làm sao nhóm có số liệu cho `2016, 2018, 2022, 2024`?**
> **Trả lời:** Nhóm áp dụng phương pháp **nội suy tuyến tính theo từng pixel (Pixel-wise Linear Interpolation)** giữa hai mốc 5 năm liền kề của GHSL R2023A. Ví dụ giá trị năm `2018` được tính bằng `0.4 × Pop(2015) + 0.6 × Pop(2020)`. Cách này đảm bảo đồng bộ trục thời gian với ảnh vệ tinh Sentinel-2 và đã được trình bày rõ giới hạn ước lượng trong Chương 3 và Chương 5.

**Q2. Tại sao nhóm chỉ chọn ảnh mùa khô (Tháng 1 – Tháng 4) mà không lấy ảnh cả năm?**
> **Trả lời:** Có hai lý do khoa học: (1) Sentinel-2 là cảm biến quang học không xuyên được qua mây dày mùa mưa ở miền Bắc Việt Nam; và (2) Khi phát hiện biến động nhiều năm (Change Detection), bắt buộc giữ cố định cùng một mùa (Seasonal Consistency) để tránh nhầm lẫn giữa biến động thực sự theo năm với biến động mực nước mùa lũ/mùa cạn trong cùng một năm.

**Q3. Hàm `simplify(0.0001)` và việc lọc bỏ đa giác `< 0.005 km²` có ảnh hưởng tới độ chính xác thống kê không?**
> **Trả lời:** Nhóm tính toán diện tích chính xác trên hệ mét `EPSG:32648` trước khi chạy `simplify` để truyền lên WebGIS. Việc lọc bỏ các đa giác siêu nhỏ dưới `5.000 m²` (dưới 50 pixel) giúp loại bỏ nhiễu bóng đổ/vũng nước tạm thời, còn `simplify(0.0001, preserve_topology=True)` giảm 70–80% số đỉnh răng cưa giúp bản đồ web tải nhanh trong khi sai số hình học dưới 1%.

**Q4. Hạn chế lớn nhất của hệ thống hiện tại và hướng phát triển tiếp theo là gì?**
> **Trả lời:** Hạn chế lớn nhất là ảnh quang học Sentinel-2 phụ thuộc vào thời tiết (không quan sát được mùa mưa bão) và chỉ đo được *diện tích bề mặt* chứ chưa tính được *thể tích nước*. Hướng phát triển tiếp theo là tích hợp ảnh Radar **Sentinel-1 (SAR)** có khả năng xuyên mây để theo dõi ngập lụt thời gian thực và kết hợp mô hình số độ cao **DEM** để ước lượng thể tích trữ nước.
