# GIS Change Detection — Biến động Mặt nước & Dân cư (Hành lang Sông Hồng – Hồ Tây – Đông Anh, Hà Nội)

Hệ thống WebGIS và chuỗi xử lý dữ liệu không gian (Data Pipeline) đo lường, phân tích và trực quan hóa sự thay đổi **diện tích bề mặt nước (Surface Water Extent)** và **mật độ dân cư** tại khu vực **Hành lang Sông Hồng – Hồ Tây – Đông Anh (Hà Nội)** giai đoạn **2016 – 2024**.

---

## 1. Thông tin Dự án & Khu vực Nghiên cứu (PA3)

| Hạng mục | Giá trị khóa cứng |
| :--- | :--- |
| **Khu vực nghiên cứu (AOI)** | Hành lang Sông Hồng – Hồ Tây – Đông Anh, Hà Nội (`contracts/aoi.geojson`) |
| **Phạm vi tọa độ (EPSG:4326)** | Kinh độ `105.78° E → 105.93° E`, Vĩ độ `21.01° N → 21.15° N` (~241.8 km²) |
| **Hệ quy chiếu lưu trữ & API** | `EPSG:4326` (WGS 84 — độ kinh/vĩ độ) |
| **Hệ quy chiếu tính toán mét** | `EPSG:32648` (UTM Zone 48N — mét, dùng cho diện tích `km²` và `Buffer 500m`) |
| **Chuỗi mốc thời gian** | 5 mốc mùa khô (Tháng 1 – Tháng 4): `2016, 2018, 2020, 2022, 2024` |
| **Dữ liệu mặt nước** | Sentinel-2 L2A (Microsoft Planetary Computer STAC API) → MNDWI + Otsu |
| **Dữ liệu dân cư** | GHSL GHS-POP R2023A (100m, mốc 2015–2020–2025 nội suy tuyến tính) |
| **Đối chứng độ chính xác** | JRC Global Surface Water + Điểm mẫu Ground Truth trên QGIS |

---

## 2. Bộ Tài liệu Đọc cho Cả Nhóm (4 Thành viên)

Mọi thành viên nên đọc các tài liệu sau trước khi bắt đầu công việc của mình:

1. **[docs/TEAM_GUIDE.md](docs/TEAM_GUIDE.md)** — Giải thích tổng quan dự án, kiến trúc 4 tầng, bảng thuật ngữ GIS/Viễn thám dễ hiểu và mô hình vận hành 2 + 2.
2. **[ROADMAP.md](ROADMAP.md)** — Bảng phân công chi tiết 4 người (A, B, C, D) và checklist 8 tuần.
3. **[CLAUDE.md](CLAUDE.md)** — Quy chuẩn kỹ thuật, Schema dữ liệu & luật bắt buộc khi dùng AI hỗ trợ lập trình (dành cho A & B).
4. **[docs/QGIS_GUIDE_FOR_C.md](docs/QGIS_GUIDE_FOR_C.md)** — Hướng dẫn từng bước thao tác QGIS Desktop & Copernicus Browser (dành cho Người C).
5. **[docs/QA_AND_REPORT_GUIDE_FOR_D.md](docs/QA_AND_REPORT_GUIDE_FOR_D.md)** — Hướng dẫn test Swagger API, WebGIS và khung chi tiết 6 chương báo cáo (dành cho Người D).
6. **[docs/DEFENSE_QA.md](docs/DEFENSE_QA.md)** — Bộ câu hỏi và câu trả lời mẫu cho buổi bảo vệ đồ án (chia riêng từng người).

---

## 3. Cấu trúc Thư mục (Monorepo — Tách luồng tuyệt đối)

```text
GISChangeDetection/
├── README.md                           # Tổng quan & hướng dẫn chạy nhanh
├── ROADMAP.md                          # Phân công 4 thành viên & lộ trình 8 tuần
├── CLAUDE.md                           # Luật kỹ thuật & CRS cho AI
├── .env.example                        # Mẫu biến môi trường (DB URL, Vite API URL)
├── docker-compose.yml                  # PostgreSQL 16 + PostGIS 3.4 + FastAPI
├── .gitignore                          # Chặn tuyệt đối file raster .tif, .jp2 nặng
│
├── contracts/                          # [ĐÃ KHÓA] Hợp đồng dữ liệu giữa A và B
│   ├── aoi.geojson                     # Ranh giới PA3 (Sông Hồng – Hồ Tây – Đông Anh)
│   ├── schemas/                        # JSON Schema chuẩn cho nước, dân cư, chuỗi năm
│   └── mock/                           # Dữ liệu giả lập 5 mốc năm (2016..2024)
│
├── services/
│   ├── gis-pipeline/                   # [NGƯỜI A] Python ETL hợp nhất (Sentinel-2 MNDWI + GHSL + Buffer 500m)
│   └── api/                            # [NGƯỜI B] FastAPI + GeoAlchemy2 + PostGIS (ST_AsGeoJSON)
│
├── apps/
│   └── web/                            # [NGƯỜI B] React + TypeScript + MapLibre GL JS
│
├── data/                               # [GITIGNORED] Ảnh vệ tinh gốc & GeoJSON thật
│   ├── raw/
│   └── processed/
│
└── docs/                               # Tài liệu hướng dẫn kỹ thuật & vận hành nhóm (.md)
    ├── TEAM_GUIDE.md
    ├── QGIS_GUIDE_FOR_C.md
    ├── QA_AND_REPORT_GUIDE_FOR_D.md
    └── DEFENSE_QA.md
```

---

## 4. Hướng dẫn Khởi chạy Nhanh (Quick Start)

### Bước 1: Dựng CSDL PostGIS và Backend API (Người B & Người D)
```bash
# Khởi động PostgreSQL + PostGIS 3.4
docker compose up -d db

# Cài đặt thư viện Python cho API
cd services/api
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Nạp dữ liệu giả lập (Tuần 2-6) hoặc dữ liệu thật (Tuần 7)
python scripts/seed.py --source ../../contracts/mock

# Chạy FastAPI (mở Swagger UI tại http://localhost:8000/docs)
uvicorn app.main:app --reload --port 8000
```

### Bước 2: Chạy Giao diện WebGIS (Người B & Người D)
```bash
cd apps/web
npm install
npm run dev
# Mở trình duyệt tại http://localhost:5173
```

### Bước 3: Chạy Chuỗi Xử lý Dữ liệu GIS Hợp nhất (Người A)
```bash
cd services/gis-pipeline
pip install -r requirements.txt

# Chạy toàn bộ chuỗi (water + pop + timeseries) hoặc chọn --step water | pop
python run_pipeline.py --step all --aoi ../../contracts/aoi.geojson --years 2016 2018 2020 2022 2024 --out ../../data/processed
```
