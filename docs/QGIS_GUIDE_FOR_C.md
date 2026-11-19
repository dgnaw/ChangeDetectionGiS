# Hướng dẫn Chi tiết cho Người C — GIS Cartographer & Ground-Truth QA

> **Vai trò của bạn trong nhóm:** Bạn **không cần viết code Python hay React**. Bạn là người trực tiếp sử dụng phần mềm chuyên ngành **QGIS Desktop** và **Copernicus Browser** để: (1) kiểm định độc lập độ chính xác kết quả tách nước của Người A, và (2) biên tập toàn bộ bản đồ chuẩn học thuật (Cartography) cho Báo cáo và Slide.

---

## 1. Cài đặt Công cụ (Làm trong Tuần 1 — mất ~15 phút)

1. Tải và cài đặt **QGIS Desktop bản LTR (Long Term Release, 3.34+)** miễn phí tại: https://qgis.org/download/
2. Mở QGIS → vào menu **Plugins → Manage and Install Plugins...** → tìm và cài plugin **QuickMapServices**.
3. Vào menu **Web → QuickMapServices → Settings → More services → Get contributed pack** → bấm Save.
   - Từ giờ bạn có thể bật bản đồ nền **OpenStreetMap** hoặc **Google Satellite** chỉ bằng 1 cú click tại **Web → QuickMapServices → OSM → OSM Standard**.

---

## 2. Hướng dẫn 4 Thao tác Cốt lõi bạn sẽ làm suốt 8 tuần

### Thao tác 1: Mở và kiểm tra dữ liệu GeoJSON (Tuần 1, Tuần 4, Tuần 6)
1. Bật lớp nền vệ tinh hoặc bản đồ đường phố (**Web → QuickMapServices → OSM → OSM Standard**).
2. Mở thư mục `contracts/` hoặc `data/processed/` trên Windows Explorer.
3. Kéo thả file `contracts/aoi.geojson` và `contracts/mock/water_2020.geojson` trực tiếp vào màn hình QGIS.
4. Click chuột phải vào tên lớp ở bảng **Layers** (bên trái) → chọn **Zoom to Layer** để phóng đúng vào khu vực Hành lang Sông Hồng – Hồ Tây – Đông Anh.
5. Đổi màu cho đẹp: Click đúp vào lớp → chọn tab **Symbology**:
   - Với `aoi.geojson`: Chọn **Simple Fill** → **Fill style = No Brush** (rỗng ruột), **Stroke color = Đỏ**, **Stroke width = 0.8 mm**.
   - Với `water_YYYY.geojson`: Chọn **Categorized** theo cột `change_type`:
     - `stable` → Màu xanh dương (`#0284c7`)
     - `gain` → Màu xanh lá (`#16a34a`)
     - `loss` → Màu đỏ cam (`#ea580c`)

### Thao tác 2: Xuất Bản đồ Chuẩn Học thuật cho Báo cáo (Print Layout)
Mọi bản đồ đưa vào báo cáo GIS đều **bắt buộc** có 5 yếu tố: *Tiêu đề, Bản đồ chính, Mũi tên chỉ Bắc (North Arrow), Thước tỉ lệ (Scale Bar), Bảng chú giải (Legend) và Lưới tọa độ (Grid)*.
1. Trong QGIS, bấm `Ctrl + P` (**Project → New Print Layout...**) → đặt tên (ví dụ `Fig1_AOI`).
2. Dùng thanh công cụ bên trái:
   - **Add Map**: Kéo 1 khung chữ nhật lớn để hiện bản đồ.
   - Trong bảng **Item Properties** của khung bản đồ → mục **Grids** → bấm dấu `+` → **Modify Grid** → chọn Interval `0.03` độ (EPSG:4326) và tick **Draw Coordinates**.
   - **Add North Arrow**: Đặt ở góc trên bên phải.
   - **Add Scale Bar**: Đặt ở góc dưới bên trái (đơn vị `km`).
   - **Add Legend**: Đặt ở góc dưới bên phải (chỉnh lại tên tiếng Việt dễ đọc).
   - **Add Label**: Đặt tiêu đề ở phía trên cùng.
3. Xuất ảnh sắc nét: **Layout → Export as Image...** (để độ phân giải `300 dpi`), tải lên thư mục **Hình ảnh Báo cáo** trên Google Drive của nhóm.

### Thao tác 3: Chụp ảnh Tổ hợp màu Sentinel-2 trên Copernicus Browser (Tuần 2)
1. Truy cập https://browser.dataspace.copernicus.eu/ (tạo tài khoản miễn phí).
2. Gõ tìm **Hanoi** hoặc kéo bản đồ tới khu vực Hồ Tây – Sông Hồng – Đông Anh.
3. Chọn nguồn **Sentinel-2 L2A**, lọc thời gian mùa khô (ví dụ `01/01/2024 – 30/04/2024`), kéo thanh **Max Cloud Coverage** xuống `< 10%` → bấm **Search**.
4. Chọn 1 cảnh ảnh trong xanh rõ nét:
   - Chụp ảnh chế độ **True Color (B04-B03-B02)** → lưu file `fig2_s2_true_color.png` lên Drive nhóm.
   - Chuyển sang chế độ **SWIR / False Color** hoặc **NDWI/MNDWI** → chụp lại lưu file `fig2_s2_mndwi_preview.png` lên Drive nhóm.
   - Hai ảnh này đưa vào **Chương 2** để chứng minh tại sao mắt thường nhìn nước đục Sông Hồng khó phân biệt với bãi cát, nhưng kênh hồng ngoại sóng ngắn (`B11`) tách nước cực kỳ rõ nét.

### Thao tác 4: Chấm 30 Điểm Kiểm chứng Ground Truth (Tuần 4 — Vũ khí ăn điểm khi Bảo vệ!)
Khi Người A gửi file `water_2020.geojson` thật đầu tiên ở Tuần 4:
1. Mở lớp nền **Google Satellite** (hoặc ảnh Sentinel-2 gốc) cùng với lớp `water_2020.geojson` trong QGIS.
2. Tạo một lớp điểm mới: **Layer → Create Layer → New GeoPackage Layer** (`ground_truth_30pts.gpkg`, Geometry type: `Point`, CRS: `EPSG:4326`), thêm 2 cột: `actual_water` (Integer: `1` là Nước thật, `0` là Đất thật) và `pred_water` (Integer: `1` nếu nằm trong polygon của Người A, `0` nếu nằm ngoài).
3. Bật chế độ chỉnh sửa (biểu tượng cây bút chì vàng) → chấm ngẫu nhiên **15 điểm trên mặt nước thật** (Hồ Tây, Sông Hồng, Đầm Vân Trì) và **15 điểm trên đất liền/đô thị** (bãi giữa, mái nhà, công viên).
4. Đếm số điểm đúng/sai và điền vào **Ma trận nhầm lẫn (Confusion Matrix)** cho Chương 5:
   - `TP` (Nước thật & Máy đoán Nước)
   - `TN` (Đất thật & Máy đoán Đất)
   - `FP` (Đất thật nhưng Máy đoán nhầm là Nước — ví dụ bóng nhà cao tầng)
   - `FN` (Nước thật nhưng Máy bỏ sót — ví dụ kênh nhỏ `< 10m`)
   - Tính **Độ chính xác tổng thể**: `Overall Accuracy = (TP + TN) ÷ 30 × 100%`.

---

## 3. Danh sách Hình ảnh & Nội dung Chương Báo cáo bạn phụ trách

*(Lưu toàn bộ file ảnh dưới đây lên thư mục Google Drive chung của nhóm để Người D chèn vào Word/Slide; không cần đẩy ảnh nặng vào repo Git).*

| Tuần | Tên file cần xuất & nộp lên Drive nhóm | Chương báo cáo liên quan |
| :--- | :--- | :--- |
| Tuần 1 | `fig1_aoi_hanoi.png` (Bản đồ vị trí PA3: Sông Hồng – Hồ Tây – Đông Anh) | Chương 1 |
| Tuần 2 | `fig2_s2_true_color.png` & `fig2_s2_swir_mndwi.png` | Chương 2 |
| Tuần 3 | `fig3_etl_flowchart.png` (Sơ đồ luồng xử lý ảnh Sentinel-2) | Chương 3 (mục 3.1, 3.2) |
| Tuần 4 | Bảng `Confusion Matrix` 30 điểm Ground Truth + ảnh zoom kiểm chứng | Chương 5 |
| Tuần 5 | `fig3_buffer_500m_overlay.png` (Minh họa vùng đệm 500m chồng lưới dân cư) | Chương 3 (mục 3.3) |
| Tuần 6 | `fig5_water_change_2016_2024.png`, `fig5_pop_buffer_2024.png`, `fig5_jrc_compare.png` | Chương 5 |
