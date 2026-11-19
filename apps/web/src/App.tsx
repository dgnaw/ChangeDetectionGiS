import React, { useState } from "react";
import { MapCanvas } from "./components/MapCanvas";
import { TimeSlider } from "./components/TimeSlider";
import { CompareToggle } from "./components/CompareToggle";
import { LayerControl } from "./components/LayerControl";
import { StatsChart } from "./components/StatsChart";

const YEARS = [2016, 2018, 2020, 2022, 2024];

export default function App() {
  const [year, setYear] = useState<number>(2020);
  const [showWater, setShowWater] = useState<boolean>(true);
  const [showPopulation, setShowPopulation] = useState<boolean>(true);
  const [onlyBuffer, setOnlyBuffer] = useState<boolean>(false);
  const [compareMode, setCompareMode] = useState<boolean>(false);

  return (
    <div style={{ display: "flex", height: "100vh", flexDirection: "column" }}>
      <header
        style={{
          padding: "12px 20px",
          background: "#0f172a",
          color: "#f8fafc",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center"
        }}
      >
        <div>
          <strong>GIS Change Detection</strong> — Hành lang Sông Hồng · Hồ Tây · Đông Anh (2016–2024)
        </div>
        <TimeSlider years={YEARS} selectedYear={year} onChange={setYear} />
      </header>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        <aside
          style={{
            width: 320,
            padding: 16,
            borderRight: "1px solid #cbd5e1",
            display: "flex",
            flexDirection: "column",
            gap: 16,
            overflowY: "auto"
          }}
        >
          <LayerControl
            showWater={showWater}
            showPopulation={showPopulation}
            onlyBuffer={onlyBuffer}
            onToggleWater={setShowWater}
            onTogglePopulation={setShowPopulation}
            onToggleOnlyBuffer={setOnlyBuffer}
          />
          <CompareToggle enabled={compareMode} onToggle={setCompareMode} />
          <StatsChart series={[]} />
        </aside>

        <MapCanvas
          year={year}
          showWater={showWater}
          showPopulation={showPopulation}
          onlyBuffer={onlyBuffer}
          compareMode={compareMode}
        />
      </div>
    </div>
  );
}
