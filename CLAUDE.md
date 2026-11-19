# CLAUDE.md — Luật Kỹ thuật & Ngữ cảnh Bắt buộc cho AI

> **Hướng dẫn:** Người A và Người B luôn đính kèm hoặc cho AI đọc file này trước khi sinh code để đảm bảo 100% thống nhất về Hệ quy chiếu (CRS), tên trường dữ liệu (Schema), Endpoint API và cấu trúc thư mục.

---

## 1. Thông số Cố định của Dự án
- **Đề tài:** GIS Change Detection — Biến động Mặt nước & Dân cư theo Thời gian.
- **Khu vực nghiên cứu (AOI):** Hành lang Sông Hồng – Hồ Tây – Đông Anh, Hà Nội (`contracts/aoi.geojson`).
- **Mốc năm phân tích:** `[2016, 2018, 2020, 2022, 2024]` (ảnh Sentinel-2 L2A mùa khô tháng 1–4, mây `< 10%`).
- **Ranh giới sở hữu thư mục (KHÔNG sửa chéo):**
  - **Người A** chỉ sửa trong `services/gis-pipeline/` (bao gồm `src/water/`, `src/population/`, `notebooks/`, `tests/`).
  - **Người B** chỉ sửa trong `services/api/` và `apps/web/`.
  - Thư mục `contracts/` đã được khóa cứng. Mọi thay đổi schema phải thông báo cả 2 người.

---

## 2. Luật Hệ quy chiếu (CRS) — TUYỆT ĐỐI KHÔNG VI PHẠM
1. **Lưu trữ & Truyền tải (`GeoJSON`, `PostGIS`, `FastAPI`, `MapLibre`):** LUÔN dùng **`EPSG:4326`** (WGS 84).
2. **Xử lý Ảnh & Tính toán Hình học trên lưới gốc `EPSG:32648` (Tránh chiếu 2 lần):**
   - Ảnh Sentinel-2 L2A khu vực Hà Nội trên Planetary Computer vốn đã lưu ở hệ mét **`EPSG:32648`** (UTM Zone 48N).
   - Quy trình bắt buộc: Chiếu `aoi.geojson` từ `4326 → 32648` ngay từ đầu → Cắt ảnh `B03, B11, SCL`, tính MNDWI, Otsu, Vector hóa, lọc diện tích `km²`, tính chu vi `km`, tạo `Buffer 500m` và tính `dist_to_water_m` **ngay trên `EPSG:32648` gốc** → Chỉ gọi `.to_crs("EPSG:4326")` đúng 1 lần trước khi ghi GeoJSON đầu ra.
3. **Không bao giờ** gọi `.area` hoặc `.buffer(500)` trên GeoDataFrame đang ở `EPSG:4326`.

---

## 3. Luật Xử lý Ảnh & Hình học (Dành cho Người A — `services/gis-pipeline/`)
1. **Truy xuất STAC Planetary Computer (`src/water/fetch_stac.py`):**
   - Collection `sentinel-2-l2a`, lọc độ mây theo chuẩn `query={"eo:cloud_cover": {"lt": 10}}`, ký URL bằng `planetary_computer.sign_inplace`, đọc các assets `"B03"`, `"B11"`, `"SCL"`.
2. **Chuẩn hóa Phổ ESA Processing Baseline 04.00 (`src/water/preprocess.py`):**
   - Từ ngày **25/01/2022** trở đi (ảnh năm `2022` và `2024`), ESA cộng thêm hằng số `+1000` (`BOA_ADD_OFFSET`) vào giá trị pixel các kênh quang phổ. Bắt buộc trừ đi `1000` (và clip tối thiểu về `0.0`) bằng `apply_pb0400_offset()` cho ảnh từ `2022-01-25` trở đi để đồng nhất phổ với giai đoạn `2016–2020`.
3. **Resampling Sentinel-2:**
   - `B03` (Green): 10m (lưới chuẩn).
   - `B11` (SWIR1): 20m → Resample về 10m bằng phương pháp `Resampling.bilinear`.
   - `SCL` (Scene Classification Layer): 20m → Resample về 10m bằng `Resampling.nearest`.
4. **Lọc mây SCL:** Loại bỏ các pixel có giá trị `SCL` thuộc `[0, 1, 3, 8, 9, 10]` (No Data, Saturated, Cloud Shadows, Cloud Medium/High Prob, Thin Cirrus).
5. **Công thức MNDWI:** `MNDWI = (B03 - B11) / (B03 + B11)` (dùng `float32`, tránh chia cho 0 bằng `np.where((B03 + B11) == 0, np.nan, ...)`).
6. **Hậu xử lý Vector mặt nước (`src/water/vectorize.py`):**
   - Khử nhiễu hình thái học (`binary_opening` & `binary_closing`, kernel 3×3) và lọc bỏ đa giác `< 0.005 km²` (5.000 m²) trực tiếp trên `EPSG:32648`.
   - Chuyển sang `EPSG:4326` đúng 1 lần, bắt buộc chạy `simplify(0.0001, preserve_topology=True)` và `.make_valid()` để tránh lỗi hình học tự cắt khi nạp vào PostGIS.
7. **Dân số GHSL (`src/population/`):**
   - Nội suy tuyến tính theo từng pixel giữa các mốc GHSL R2023A (`2015, 2020, 2025`) để tạo raster dân số cho các năm `2016, 2018, 2020, 2022, 2024`.
   - Tính tổng dân số trong `Buffer 500m` trực tiếp trên raster 100m bằng `rasterio.mask` (KHÔNG dùng `gpd.overlay()` lên lưới 100m).
   - Khi xuất GeoJSON hiển thị WebGIS (`pop_YYYY.geojson`), gộp lưới lên kích thước **250m × 250m** và lọc bỏ các ô có `pop_count < 5`.

---

## 4. Hợp đồng Dữ liệu & REST API (Khớp `contracts/schemas/`)

### Các file trong `contracts/mock/` và `data/processed/`
- `water_{year}.geojson`: Properties gồm `water_id` (str), `year` (int), `area_km2` (float), `perimeter_km` (float), `mean_mndwi` (float), `otsu_threshold` (float), `change_type` (`"stable" | "gain" | "loss"`).
- `pop_{year}.geojson`: Properties gồm `grid_id` (str), `year` (int), `pop_count` (float), `density_per_km2` (float), `in_water_buffer_500m` (bool), `dist_to_water_m` (float).
- `timeseries_summary.json`: Gồm `aoi_name`, `aoi_area_km2`, `crs_storage`, `crs_metric`, `years`, và mảng `series[]` với các trường `year`, `water_area_km2`, `water_ratio_pct`, `water_gain_km2`, `water_loss_km2`, `otsu_threshold`, `cloud_cover_pct`, `total_pop`, `pop_in_buffer_500m`, `pop_buffer_ratio_pct`, `jrc_iou_score`.

### REST API Endpoints & Tối ưu PostGIS (`services/api/` — Dành cho Người B)
- **Tối ưu truy vấn:** Khi nối API thật vào PostGIS, dùng hàm `func.ST_AsGeoJSON(Model.geom)` (hoặc `jsonb_build_object`) trực tiếp trong câu lệnh SQL để trả thẳng `FeatureCollection` với độ trễ `< 50 ms`, tránh kéo binary WKB về Python lặp thủ công.
- `GET /api/v1/health` → Kiểm tra trạng thái API & DB.
- `GET /api/v1/aoi` → Trả về GeoJSON ranh giới AOI (`contracts/aoi.geojson`).
- `GET /api/v1/layers/water?year=2020` → Trả về GeoJSON `FeatureCollection` lớp mặt nước năm được chọn.
- `GET /api/v1/layers/population?year=2020&only_buffer=false` → Trả về GeoJSON `FeatureCollection` lớp dân cư 250m (có tùy chọn lọc `only_buffer=true`).
- `GET /api/v1/analytics/timeseries` → Trả về JSON chuỗi thời gian 2016–2024 để vẽ biểu đồ Recharts.

---

## 5. Quy tắc Git & Điểm dừng cho AI (A và B bắt buộc tuân thủ)

### 5.1. Chia nhánh làm việc (Tuần 1 – Tuần 6)
- `main`: Nhánh gốc ổn định, chỉ chứa khung móng và code đã kiểm thử.
- **Người A** làm việc trên nhánh `feat/data-pipeline` — **CHỈ sửa** trong `services/gis-pipeline/`.
- **Người B** làm việc trên nhánh `feat/webgis-app` — **CHỈ sửa** trong `services/api/`, `apps/web/` và `docker-compose.yml`.
- **Người C & D** (nếu cập nhật tài liệu hướng dẫn) dùng nhánh `docs/guides` — **CHỈ sửa** trong `docs/`.

### 5.2. Điểm dừng cứng cho AI (Hard Boundaries)
Khi Người A hoặc Người B dùng AI hỗ trợ code, **AI TUYỆT ĐỐI KHÔNG ĐƯỢC**:
1. Sửa chéo sang thư mục của người còn lại (ví dụ: AI của Người B không sửa `services/gis-pipeline/`, AI của Người A không sửa `services/api/` hay `apps/web/`).
2. Tự ý thêm/đổi tên trường dữ liệu hoặc sửa `contracts/schemas/` và `contracts/mock/` nếu chưa có sự đồng thuận của cả A và B.
3. Tự ý sửa các file gốc dùng chung (`README.md`, `ROADMAP.md`, `.gitignore`, `.env.example`) khi đang làm tính năng trên nhánh riêng.
4. Commit bất kỳ file nào trong `data/raw/` hoặc `data/processed/` (đã bị chặn bởi `.gitignore`).
5. Ép cứng kiểu hình học `Polygon` cho bảng mặt nước ở Backend: `seed.py` và `models.py` của Người B **phải** nhận được cả `Polygon` lẫn `MultiPolygon` (`Geometry(geometry_type="GEOMETRY", srid=4326)`) vì dữ liệu thật Sentinel-2 tại Hồ Tây / Sông Hồng có đảo nổi và bãi giữa.

### 5.3. Quy trình Ghép nối & Đóng băng (Tuần 7 – Tuần 8)
- **Tuần 7 (Tích hợp):**
  1. Người B merge `feat/webgis-app` → `main`; Người A merge `feat/data-pipeline` → `main`.
  2. Người A nén thư mục `data/processed/` (`.zip`) gửi ngoài Git cho Người B giải nén vào `data/processed/`.
  3. Người B chạy `python services/api/scripts/seed.py --source ../../data/processed` để chuyển toàn bộ DB từ Mock sang dữ liệu thật.
  4. Cả nhóm kiểm thử End-to-End và **Đóng băng code (Code Freeze)**.
- **Tuần 8 (Tuần cuối):** Tuyệt đối không sửa logic code lõi; chỉ chạy demo trên máy bảo vệ, quay video backup 2 phút và tập dượt thuyết trình theo `docs/DEFENSE_QA.md`.
