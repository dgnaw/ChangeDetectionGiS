# ROADMAP.md — Bản Phân công Công việc & Lộ trình 8 Tuần (Mô hình 2 + 2)

> **Cập nhật phân công sau khi hoàn thiện móng dự án:**
> - **Người A (Trưởng nhóm kỹ thuật / Người xây móng → Data & Remote Sensing Lead):** Đã hoàn thiện khung Monorepo, hợp đồng `contracts/`, dữ liệu Mock và tài liệu nhóm. Từ Tuần 2 trở đi, Người A tập trung 100% vào chuỗi ETL hợp nhất trong `services/gis-pipeline/`.
> - **Người B (Full-Stack WebGIS & Spatial DB Lead):** Tiếp nhận khung `services/api/`, `apps/web/`, `docker-compose.yml` và `contracts/mock/` để dựng PostGIS, FastAPI và React/MapLibre chạy độc lập ngay từ Tuần 2 (không cần chờ Người A).
> - **Người C (GIS Cartographer & Ground-Truth QA — Không cần code):** Chuyên trách QGIS Desktop, Copernicus Browser, kiểm định độ chính xác phân loại nước và biên tập bản đồ chuẩn học thuật cho Chương 1, 2, 3, 5.
> - **Người D (Spatial Data Analyst & System QA — Không cần code):** Chuyên trách test API (Swagger UI) & WebGIS, phân tích thống kê chuỗi thời gian Nước – Dân cư và điều phối báo cáo 6 chương + Slide bảo vệ.

---

## 1. Bảng Tóm tắt Trách nhiệm & Đầu ra Cá nhân (Bảo vệ Đồ án)

| Thành viên | Vai trò chính thức | Phạm vi sở hữu | Sản phẩm bàn giao cá nhân (Deliverables) |
| :--- | :--- | :--- | :--- |
| **Người A** | Foundation & Data/GIS Pipeline Lead | `contracts/`, `services/gis-pipeline/` | Khung Monorepo, Script STAC Sentinel-2 (`EPSG:32648`), chuẩn hóa PB 04.00 (`-1000`), MNDWI-Otsu, Nội suy dân số GHSL, Buffer 500m, Đối chứng JRC, Bộ dữ liệu thật `data/processed/`. |
| **Người B** | Full-Stack WebGIS & Spatial DB Lead | `docker-compose.yml`, `services/api/`, `apps/web/` | CSDL PostGIS + GIST Index, Script `seed.py`, 5 REST API FastAPI (tối ưu `ST_AsGeoJSON`), WebGIS React + MapLibre (Time-Slider, Compare Mode, Popup, Biểu đồ Recharts). |
| **Người C** | GIS Cartographer & Ground-Truth QA | `QGIS Desktop`, Google Drive (Hình ảnh), Chương 1, 2 (phần GIS/Viễn thám), 3 | Bản đồ AOI PA3, Ảnh tổ hợp màu Sentinel-2, Bộ 30 điểm Ground Truth & Ma trận nhầm lẫn, 3 Bản đồ kết quả chuẩn GIS cho Chương 5. |
| **Người D** | Spatial Data Analyst & System QA | `Swagger UI`, `WebGIS UI`, Google Drive/Word & Canva (Báo cáo/Slide), Chương 4, 5, 6 | Bảng Test Case API & WebGIS, Phân tích định lượng `timeseries_summary.json`, Báo cáo hoàn chỉnh 6 chương (~50 trang), Slide bảo vệ. |

---

## 2. Lộ trình Chi tiết 8 Tuần (Checklist theo từng người)

### Tuần 1: Xây móng, Khóa Hợp đồng & Làm quen Công cụ
- [x] **Người A:** Chốt PA3 (Hành lang Sông Hồng – Hồ Tây – Đông Anh), khởi tạo Monorepo, khóa `contracts/aoi.geojson`, `contracts/schemas/`, bộ `contracts/mock/` (5 mốc năm) và bộ tài liệu `docs/`.
- [ ] **Người B:** Pull repo về máy, chạy thử `docker compose up -d db`, cài môi trường Python cho `services/api/` và Node.js cho `apps/web/`, đọc kỹ `CLAUDE.md` và `contracts/schemas/`.
- [ ] **Người C:** Cài đặt **QGIS Desktop (LTR 3.34+)** theo hướng dẫn trong `docs/QGIS_GUIDE_FOR_C.md`. Mở thử `contracts/aoi.geojson` và `contracts/mock/water_2020.geojson` lên nền OpenStreetMap. Xuất hình đầu tiên (`fig1_aoi_hanoi.png`) lên Google Drive nhóm.
- [ ] **Người D:** Đọc `docs/TEAM_GUIDE.md` và `docs/QA_AND_REPORT_GUIDE_FOR_D.md`. Tạo file Word/Google Docs mẫu báo cáo 6 chương trên Drive nhóm và viết nháp **Chương 1 (Tổng quan đề tài)**.

---

### Tuần 2: Tải ảnh STAC (A) vs. PostGIS & Seed Mock (B) vs. Lý thuyết & Ảnh mẫu (C, D)
- [ ] **Người A:** Hoàn thiện `services/gis-pipeline/src/water/fetch_stac.py`: kết nối Planetary Computer STAC API (`eo:cloud_cover < 10%`), cắt band `B03, B11, SCL` mùa khô (Tháng 1–4) các năm `2016, 2018, 2020, 2022, 2024` trực tiếp trên lưới gốc `EPSG:32648` lưu vào `data/raw/`.
- [ ] **Người B:** Hoàn thiện `services/api/app/models.py` (3 bảng PostGIS + chỉ mục `GIST`) và `services/api/scripts/seed.py`. Nạp thành công toàn bộ `contracts/mock/` vào PostGIS.
- [ ] **Người C:** Vào Copernicus Browser tìm cảnh ảnh Sentinel-2 mùa khô tại Hồ Tây – Đông Anh, chụp ảnh so sánh True Color (`B04-B03-B02`) và False Color (`B08-B11-B04`) lưu lên Drive nhóm để minh họa **Chương 2**.
- [ ] **Người D:** Viết **Chương 2 (Cơ sở lý thuyết)** mục 2.1 & 2.2: Raster/Vector, `EPSG:4326` vs `EPSG:32648`, đặc tính phổ Sentinel-2 và công thức `MNDWI = (B03 - B11) ÷ (B03 + B11)`.

---

### Tuần 3: MNDWI-Otsu (A) vs. REST API FastAPI (B) vs. Lưu đồ & Test Swagger (C, D)
- [ ] **Người A:** Hoàn thiện `src/water/preprocess.py` (áp dụng bù trừ PB 04.00 `-1000` cho ảnh từ 2022 trở đi, Resample `B11`/`SCL` về 10m, mask mây SCL, Median composite) và `src/water/mndwi_otsu.py` (tính MNDWI và ngưỡng Otsu tự động từng năm).
- [ ] **Người B:** Hoàn thiện 5 REST API endpoints trong `services/api/app/routers/` (`health`, `aoi`, `layers/water`, `layers/population`, `analytics/timeseries`) dùng `ST_AsGeoJSON` trực tiếp từ PostGIS. Bật CORS và kiểm tra Swagger UI tại `http://localhost:8000/docs`.
- [ ] **Người C:** Vẽ lưu đồ (Flowchart) quy trình xử lý ảnh vệ tinh và soạn nháp **Chương 3 (mục 3.1 & 3.2)**.
- [ ] **Người D:** Test toàn bộ 5 endpoint của Người B trên Swagger UI (`/docs`), chụp màn hình kết quả JSON và viết **Chương 4 (mục 4.1 & 4.2: Kiến trúc 4 tầng & Thiết kế CSDL/API)**.

---

### Tuần 4: Vector hóa & JRC (A) vs. Bản đồ MapLibre & Time-Slider (B) vs. Kiểm định QGIS (C, D)
- [ ] **Người A:** Hoàn thiện `src/water/vectorize.py` (khử nhiễu 3×3 & lọc diện tích `< 0.005 km²` ngay trên `EPSG:32648` gốc, gắn nhãn `change_type`, rồi `.to_crs("EPSG:4326")` + `simplify(0.0001)` + `make_valid()`) và `src/water/validate_jrc.py` (tính IoU với JRC Global Surface Water). Gửi file `water_2020.geojson` thật đầu tiên cho Người C.
- [ ] **Người B:** Hoàn thiện `MapCanvas.tsx` (hiển thị đa giác mặt nước tô màu theo `change_type` + lưới dân cư Choropleth), `LayerControl.tsx` và `TimeSlider.tsx` (trượt mượt `2016 → 2024` + nút Play/Pause).
- [ ] **Người C:** Mở file `water_2020.geojson` thật của Người A đè lên ảnh vệ tinh gốc trên QGIS. Chấm **30 điểm kiểm chứng (Ground Truth)** để lập Ma trận nhầm lẫn (Confusion Matrix) và báo lại nếu có vùng bị nhận nhầm bóng đổ/mây.
- [ ] **Người D:** Hoàn thiện phần công nghệ **Chương 2** (PostGIS, FastAPI, MapLibre) và phần Vector hóa/Làm mượt hình học trong **Chương 3**.

---

### Tuần 5: Pipeline Dân số GHSL & Buffer 500m (A) vs. Compare Mode & Recharts (B) vs. Test UI (C, D)
- [ ] **Người A:** Hoàn thiện `services/gis-pipeline/src/population/` (`clip_population.py` nội suy tuyến tính GHSL `2015–2020–2025`, `spatial_overlay.py` tạo `Buffer 500m` trên `EPSG:32648` và đếm dân số bằng `rasterio.mask`, `grid_to_geojson.py` gộp lưới 250m, `build_timeseries.py`).
- [ ] **Người B:** Hoàn thiện `CompareToggle.tsx` (so sánh 2 mốc năm, ví dụ 2016 vs 2024) và `StatsChart.tsx` (biểu đồ Recharts trục kép: Diện tích mặt nước `km²` vs Dân số vùng đệm 500m).
- [ ] **Người C:** Mở lớp `Buffer 500m` và lưới dân số trên QGIS, xuất bản đồ minh họa phương pháp chồng lớp không gian cho **Chương 3 (mục 3.3)**.
- [ ] **Người D:** Thực hiện kiểm thử giao diện WebGIS của Người B theo bảng Test Case trong `docs/QA_AND_REPORT_GUIDE_FOR_D.md`, ghi nhận lỗi UI (nếu có) và viết **Chương 4 (mục 4.3: Thiết kế Giao diện WebGIS)**.

---

### Tuần 6: Chạy Batch Dữ liệu Thật (A) vs. Tối ưu WebGIS (B) vs. Bản đồ & Số liệu Chương 5 (C, D)
- [ ] **Người A:** Chạy hoàn chỉnh `python run_pipeline.py --step all` cho cả 5 mốc năm `2016, 2018, 2020, 2022, 2024`. Chạy `pytest` xác nhận 100% dữ liệu trong `data/processed/` hợp lệ theo Schema. Chia sẻ thư mục `data/processed/` cho B, C, D.
- [ ] **Người B:** Thêm Popup hiển thị thuộc tính khi click vào đa giác nước/ô dân cư trên bản đồ, thêm nút lọc "Chỉ hiện dân cư trong vùng đệm 500m", hoàn thiện `Dockerfile` cho API.
- [ ] **Người C:** Mở bộ dữ liệu thật trên QGIS, xuất **3 bản đồ kết quả chất lượng cao** cho **Chương 5**:
  1. Biến động diện tích mặt nước 2016–2024 (Sông Hồng, Hồ Tây, Đầm Vân Trì).
  2. Phân bố mật độ dân cư & vùng đệm 500m năm 2024.
  3. So sánh trực quan MNDWI của nhóm với JRC Global Surface Water.
- [ ] **Người D:** Dùng `timeseries_summary.json` thật để lập bảng số liệu, biểu đồ và viết phân tích định lượng **Chương 5 (Kết quả thực nghiệm & Đánh giá)**.

---

### Tuần 7: Tích hợp Thật vào PostGIS & Hoàn thiện Báo cáo
- [ ] **Người A & Người B:** Nạp dữ liệu thật vào PostGIS bằng 1 lệnh (`python scripts/seed.py --source ../../data/processed`). Đo thời gian phản hồi API (`< 200 ms`) và đóng băng code (Code Freeze).
- [ ] **Người D:** Chụp ảnh màn hình WebGIS với dữ liệu thật thay vào Chương 4 & 5. Viết **Chương 6 (Kết luận & Hướng phát triển: Sentinel-1 SAR & DEM)**.
- [ ] **Cả 4 người:** Họp 60 phút rà soát toàn bộ báo cáo (~45–55 trang), kiểm tra mục lục, số thứ tự hình/bảng và tài liệu tham khảo.

---

### Tuần 8: Slide, Quay Video Backup & Bảo vệ Thử
- [ ] **Người C & Người D:** Thiết kế 18–22 slides thuyết trình trên Canva/PowerPoint (lưu ở Google Drive nhóm).
- [ ] **Người A & Người B:** Chuẩn bị môi trường Live Demo (`QGIS`, `Swagger /docs`, `WebGIS localhost:5173`) và quay sẵn 1 video demo dự phòng 2 phút.
- [ ] **Cả 4 người:** Tập duyệt thuyết trình theo đúng 4 phần và tập trả lời câu hỏi trong `docs/DEFENSE_QA.md`.

---

## 3. Quy ước Họp Đồng bộ Ngắn (20 phút — Tối Chủ Nhật hàng tuần)
1. **Người A** gửi 1 file `.geojson` mới nhất để **Người C** tự kéo thả vào QGIS kiểm tra.
2. **Người B** cập nhật link/lệnh chạy mới nhất để **Người D** tự bấm thử trên trình duyệt.
3. **Người C & D** báo cáo tiến độ số trang báo cáo và các câu hỏi chuyên môn cần A, B giải thích lại để hiểu sâu bản chất.
