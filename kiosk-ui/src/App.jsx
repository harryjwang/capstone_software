import { useState, useEffect } from "react";

// ─── Design tokens ───────────────────────────────────────────────
const T = {
  bg: "#14100E",
  panel: "#221B17",
  panelHi: "#2E2520",
  amber: "#E8A33D",
  amberDim: "#8A6224",
  copper: "#C4714B",
  cream: "#F2E8D8",
  mute: "#9C8E7E",
  danger: "#D95F4C",
  ok: "#7FB069",
};

const DRINKS = [
  { id: 1, name: "Old Fashioned", base: "Bourbon", hue: "#C46A2B", abv: 32 },
  { id: 2, name: "Margarita", base: "Tequila", hue: "#B9C44A", abv: 18 },
  { id: 3, name: "Gin & Tonic", base: "Gin", hue: "#9FD8CB", abv: 12 },
  { id: 4, name: "Rum Punch", base: "Rum", hue: "#D9584C", abv: 15 },
  { id: 5, name: "Vodka Soda", base: "Vodka", hue: "#C9D4DE", abv: 10 },
];

const AMOUNTS = [
  { id: "little", label: "Little", ml: 150, fill: 0.35 },
  { id: "medium", label: "Medium", ml: 250, fill: 0.62 },
  { id: "a_lot", label: "A Lot", ml: 350, fill: 0.9 },
];

const INTENSITY = ["Light", "Standard", "Strong"];
const STRENGTH_MULT = [0.75, 1.0, 1.25]; // fraction of the drink's standard ABV

// FER+ emotion → suggested intensity (keep keys in sync with backend MOOD_MAP)
// Negative emotions map lighter by design — never stronger.
const EMOTION_MAP = {
  happiness: { intensity: 1, blurb: "Feeling good — standard pour" },
  surprise:  { intensity: 2, blurb: "Something to celebrate — make it strong" },
  neutral:   { intensity: 1, blurb: "Balanced — standard pour" },
  sadness:   { intensity: 0, blurb: "Rough day — keeping it light" },
  anger:     { intensity: 0, blurb: "Take a breath — easy does it" },
  disgust:   { intensity: 0, blurb: "Not feeling it — keeping it light" },
  fear:      { intensity: 0, blurb: "Nerves — easy does it" },
  contempt:  { intensity: 1, blurb: "Unimpressed — standard pour" },
};

// ─── CV backend integration ──────────────────────────────────────
// When running locally (Vite) with the FastAPI backend up, face scans are real.
// If the backend is unreachable (e.g., claude.ai preview), falls back to simulation.
const CV_BACKEND = "http://localhost:8000";

async function scanFace() {
  try {
    const res = await fetch(`${CV_BACKEND}/scan/face`, { method: "POST" });
    const d = await res.json();
    if (d.face_found && d.emotion) {
      const hasRealMatch = d.match !== null && d.match !== undefined;
      return {
        // real ID<->face match when the backend has an ID portrait stored;
        // simulated pass otherwise
        match: hasRealMatch ? d.match : true,
        matchScore: hasRealMatch ? d.match_score : 0.91,
        matchIsReal: hasRealMatch,
        emotion: d.emotion,
        confidence: d.confidence,
        source: "live",
      };
    }
    if (d.face_found === false) return { noFace: true, source: "live" };
    // face found but emotion model missing on backend → fall through to sim
  } catch (e) { /* backend not running — use simulation */ }
  const r = await simulateFaceScan();
  return { ...r, source: "simulated" };
}

// Parse AAMVA text from a hardware barcode scanner (HID keyboard mode).
// The scanner "types" the ID's PDF417 contents; we regex out the fields.
const LEGAL_AGE = 19; // Ontario
function parseAamva(text) {
  const get = (code) => {
    const m = text.match(new RegExp(code + "([^\\n\\r<]+)"));
    return m ? m[1].trim() : null;
  };
  const dobRaw = get("DBB");
  if (!dobRaw || !/^\d{8}/.test(dobRaw)) return null;
  const d8 = dobRaw.slice(0, 8);
  let y, mo, da;
  if (d8.slice(0, 2) === "19" || d8.slice(0, 2) === "20") {
    y = +d8.slice(0, 4); mo = +d8.slice(4, 6); da = +d8.slice(6, 8);   // Canada: CCYYMMDD
  } else {
    mo = +d8.slice(0, 2); da = +d8.slice(2, 4); y = +d8.slice(4, 8);   // US: MMDDCCYY
  }
  const now = new Date();
  let age = now.getFullYear() - y;
  if (now.getMonth() + 1 < mo || (now.getMonth() + 1 === mo && now.getDate() < da)) age--;
  const first = get("DAC") || "";
  const last = get("DCS") || "";
  const name = last ? `${first.slice(0, 1)}. ${last.slice(0, 1).toUpperCase()}${last.slice(1).toLowerCase()}` : "";
  return { ofAge: age >= LEGAL_AGE, age, name };
}

async function scanIdPortrait() {
  try {
    const res = await fetch(`${CV_BACKEND}/scan/id/portrait`, { method: "POST" });
    const d = await res.json();
    return d.found ? { ok: true } : { ok: false, error: d.error };
  } catch (e) {
    return { ok: true, simulated: true }; // no backend — skip portrait step
  }
}

function resetCvSession() {
  fetch(`${CV_BACKEND}/session/reset`, { method: "POST" }).catch(() => {});
}

// ─── Simulated CV stubs — swap for fetch() calls to the Pi backend ──
function simulateIdScan() {
  // Real: camera → PDF417 decode (zxing-cpp) → AAMVA parse → DOB check.
  // Also returns the ID portrait crop for face matching in the next step.
  return new Promise((res) =>
    setTimeout(() => res({
      name: "H. WANG",
      dob: "2003-04-12",
      age: 23,
      ofAge: true,
      confidence: 0.97,
    }), 2400)
  );
}
function simulateFaceScan() {
  // Real: camera → face detect → (1) embedding vs ID portrait embedding
  // (cosine similarity) for identity match, (2) emotion classifier head.
  const emotions = Object.keys(EMOTION_MAP);
  const emotion = emotions[Math.floor(Math.random() * emotions.length)];
  return new Promise((res) =>
    setTimeout(() => res({
      match: true,
      matchScore: 0.91,
      emotion,
      confidence: 0.84,
    }), 2400)
  );
}

// ─── Shared bits ─────────────────────────────────────────────────
function Btn({ children, onClick, big, ghost, disabled, style }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        fontFamily: "inherit",
        fontSize: big ? "clamp(20px, 3vh, 26px)" : 18,
        fontWeight: 700,
        letterSpacing: "0.04em",
        padding: big ? "clamp(14px, 2.5vh, 22px) clamp(32px, 5vw, 48px)" : "14px 28px",
        minHeight: 64,
        borderRadius: 14,
        border: ghost ? `2px solid ${T.mute}` : "none",
        background: ghost ? "transparent" : disabled ? T.amberDim : T.amber,
        color: ghost ? T.mute : "#1A130C",
        cursor: disabled ? "default" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "transform 0.1s ease",
        ...style,
      }}
      onPointerDown={(e) => !disabled && (e.currentTarget.style.transform = "scale(0.96)")}
      onPointerUp={(e) => (e.currentTarget.style.transform = "scale(1)")}
      onPointerLeave={(e) => (e.currentTarget.style.transform = "scale(1)")}
    >
      {children}
    </button>
  );
}

function Eyebrow({ children }) {
  return (
    <div style={{ color: T.copper, fontSize: 14, fontWeight: 700, letterSpacing: "0.28em", textTransform: "uppercase", marginBottom: 10 }}>
      {children}
    </div>
  );
}

function CameraFeed({ label }) {
  const [err, setErr] = useState(false);
  if (err) return <ScanRing label={label} />;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
      <img
        src={`${CV_BACKEND}/camera/stream`}
        onError={() => setErr(true)}
        alt="camera preview"
        style={{
          width: "min(400px, 70vw)", borderRadius: 18,
          border: `3px solid ${T.amber}`, boxShadow: `0 0 30px ${T.amber}33`,
        }}
      />
      <div style={{ color: T.mute, fontSize: 16 }}>{label}</div>
    </div>
  );
}

function ScanRing({ label, done }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 24 }}>
      <div style={{ position: "relative", width: 180, height: 180 }}>
        <svg viewBox="0 0 100 100" width="180" height="180">
          <circle cx="50" cy="50" r="44" fill="none" stroke={T.panelHi} strokeWidth="5" />
          <circle
            cx="50" cy="50" r="44" fill="none"
            stroke={done ? T.ok : T.amber} strokeWidth="5"
            strokeDasharray="276" strokeDashoffset={done ? 0 : 200}
            strokeLinecap="round"
            style={{
              transformOrigin: "50% 50%",
              animation: done ? "none" : "spin 1.2s linear infinite",
              transition: "stroke-dashoffset 0.4s ease",
            }}
          />
        </svg>
      </div>
      <div style={{ color: T.mute, fontSize: 18 }}>{label}</div>
    </div>
  );
}

function Glass({ fill, hue, height = 170 }) {
  const w = height * 0.62;
  const liquidH = Math.max(4, (height - 24) * fill);
  return (
    <div style={{ position: "relative", width: w, height, margin: "0 auto" }}>
      <div style={{
        position: "absolute", inset: 0,
        border: `3px solid ${T.cream}33`, borderTop: "none",
        borderRadius: "0 0 22px 22px",
      }} />
      <div style={{
        position: "absolute", bottom: 6, left: 6, right: 6,
        height: liquidH,
        background: `linear-gradient(180deg, ${hue}CC, ${hue})`,
        borderRadius: "6px 6px 18px 18px",
        transition: "height 0.5s cubic-bezier(.3,1.4,.5,1)",
        boxShadow: `0 0 26px ${hue}55`,
      }} />
    </div>
  );
}

function ResultCard({ icon, title, lines, onRescan }) {
  return (
    <div style={{ background: T.panel, borderRadius: 18, padding: "28px 40px", display: "inline-block" }}>
      <div style={{ fontSize: 44, marginBottom: 10 }}>{icon}</div>
      <div style={{ fontSize: 22, fontWeight: 800 }}>{title}</div>
      {lines.map((l, i) => (
        <div key={i} style={{ color: T.mute, marginTop: 8, fontSize: 15 }}>{l}</div>
      ))}
      {onRescan && (
        <div style={{ marginTop: 18 }}>
          <Btn ghost onClick={onRescan} style={{ fontSize: 15, minHeight: 48, padding: "10px 22px" }}>
            Rescan
          </Btn>
        </div>
      )}
    </div>
  );
}

// ─── Main ────────────────────────────────────────────────────────
export default function DrinkKiosk() {
  const [screen, setScreen] = useState("attract");
  // Session state — persists across back/forward navigation until reset()
  const [idResult, setIdResult] = useState(null);
  const [portraitDone, setPortraitDone] = useState(false);
  const [faceResult, setFaceResult] = useState(null);
  const [drink, setDrink] = useState(null);
  const [amount, setAmount] = useState(null);
  const [intensity, setIntensity] = useState(1);
  const [useMood, setUseMood] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [log, setLog] = useState([]);

  const addLog = (msg) => setLog((l) => [...l.slice(-6), `${new Date().toLocaleTimeString()}  ${msg}`]);

  // Hardware barcode scanner input (HID keyboard mode): while the ID screen is
  // waiting, buffer keystrokes; a scan arrives as a fast burst ending in Enter.
  // Dev shortcut: pasting AAMVA text (Cmd+V) works too.
  useEffect(() => {
    if (screen !== "idscan" || idResult || scanning) return;
    let buf = "";
    let timer = null;
    const finish = () => {
      const text = buf; buf = "";
      if (text.length < 20) return; // ignore stray typing
      const parsed = parseAamva(text);
      if (parsed) {
        setIdResult({ ...parsed, source: "scanner" });
        addLog(`[scanner] ID: age ${parsed.age}, of_age=${parsed.ofAge}`);
      } else {
        setIdResult({ failed: true, error: "Couldn't parse the ID data — try scanning again." });
        addLog("Scanner data didn't parse as AAMVA");
      }
    };
    const onKey = (e) => {
      if (e.key === "Enter") buf += "\n";
      else if (e.key.length === 1) buf += e.key;
      clearTimeout(timer);
      timer = setTimeout(finish, 300);
    };
    const onPaste = (e) => {
      buf += e.clipboardData.getData("text");
      clearTimeout(timer);
      timer = setTimeout(finish, 100);
    };
    window.addEventListener("keydown", onKey);
    window.addEventListener("paste", onPaste);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("paste", onPaste);
      clearTimeout(timer);
    };
  }, [screen, idResult, scanning]);

  const runIdPortrait = async () => {
    setScanning(true);
    const r = await scanIdPortrait();
    setScanning(false);
    if (r.ok) {
      setPortraitDone(true);
      addLog(r.simulated ? "Portrait step skipped (sim)" : "ID portrait captured");
    } else {
      addLog(`Portrait failed: ${r.error}`);
      setIdResult({ ...idResult, portraitError: r.error });
    }
  };

  const runFaceScan = async () => {
    setScanning(true);
    const r = await scanFace();
    setScanning(false);
    if (r.noFace) {
      setFaceResult({ noFace: true, source: r.source });
      addLog("No face detected in frame");
      return;
    }
    setFaceResult(r);
    if (r.match) {
      addLog(`[${r.source}] Face↔ID match ${r.matchScore} · mood: ${r.emotion}`);
      setIntensity(EMOTION_MAP[r.emotion].intensity);
    } else {
      addLog(`Face↔ID MISMATCH (${r.matchScore}) — blocked`);
    }
  };

  useEffect(() => {
    if (screen !== "dispensing") return;
    setProgress(0);
    addLog("PUB drinks/orders → payload sent");
    addLog("SUB drinks/status ← ack (order accepted)");
    const iv = setInterval(() => {
      setProgress((p) => (p >= 100 ? (clearInterval(iv), 100) : p + 2));
    }, 90);
    return () => clearInterval(iv);
  }, [screen]);

  useEffect(() => {
    if (screen === "dispensing" && progress >= 100) {
      addLog("SUB drinks/status ← done");
      const t = setTimeout(() => setScreen("done"), 600);
      return () => clearTimeout(t);
    }
  }, [progress, screen]);

  const reset = () => {
    resetCvSession();
    setScreen("attract"); setIdResult(null); setFaceResult(null); setPortraitDone(false);
    setDrink(null); setAmount(null); setIntensity(1); setUseMood(false); setLog([]);
  };

  const effectiveIntensity = useMood && faceResult
    ? EMOTION_MAP[faceResult.emotion].intensity
    : intensity;

  const payload = drink && amount ? {
    order_id: `ord_${Date.now().toString(36)}`,
    drink_id: drink.id,
    drink: drink.name,
    volume_ml: amount.ml,
    abv_level: effectiveIntensity,
    abv_multiplier: STRENGTH_MULT[effectiveIntensity],
    abv_percent: +(drink.abv * STRENGTH_MULT[effectiveIntensity]).toFixed(1),
    abv_source: useMood ? "emotion" : "manual",
    ts: new Date().toISOString(),
  } : null;

  // ── Screens ──
  const renderAttract = () => (
    <Center>
      <div style={{ fontSize: 15, letterSpacing: "0.4em", color: T.copper, textTransform: "uppercase" }}>Autonomous Bartender</div>
      <h1 style={{ fontSize: "clamp(44px, 8vw, 76px)", margin: "14px 0 6px", color: T.cream, fontWeight: 800, letterSpacing: "-0.02em" }}>
        POUR<span style={{ color: T.amber }}>DECISIONS</span>
      </h1>
      <div style={{ color: T.mute, fontSize: 20, marginBottom: 48 }}>Five drinks. Zero judgment.</div>
      <Btn big onClick={() => setScreen("idscan")}>Tap to Start</Btn>
      <div style={{ marginTop: 28, color: T.mute, fontSize: 14 }}>19+ · Valid government ID required</div>
    </Center>
  );

  const renderIdScan = () => (
    <Step eyebrow="Step 1 of 4" title="Scan your ID">
      {scanning ? (
        <CameraFeed label="Hold the FRONT of your ID (photo side) up to the camera" />
      ) : idResult?.failed ? (
        <ResultCard
          icon="🪪"
          title="Couldn't read the barcode"
          lines={[idResult.error || "Hold the ID steady and fill the frame."]}
          onRescan={() => setIdResult(null)}
        />
      ) : idResult && !portraitDone ? (
        <div>
          <ResultCard
            icon={idResult.ofAge ? "✅" : "⛔"}
            title={idResult.ofAge ? "Verified — 19+" : "Under age"}
            lines={[
              `Age ${idResult.age}${idResult.name ? ` · ${idResult.name}` : ""}`,
              idResult.portraitError || "Step 2: flip your ID to the photo side.",
            ]}
            onRescan={() => { setIdResult(null); setFaceResult(null); setPortraitDone(false); }}
          />
          {idResult.ofAge && (
            <div style={{ marginTop: 22 }}>
              <Btn big onClick={runIdPortrait}>Scan ID Photo (front)</Btn>
            </div>
          )}
        </div>
      ) : idResult && portraitDone ? (
        <ResultCard
          icon="✅"
          title="ID verified — 19+"
          lines={[
            `Age ${idResult.age}${idResult.name ? ` · ${idResult.name}` : ""}`,
            idResult.source === "live" ? "Barcode + photo captured · ● Live" : "○ Simulated result",
          ]}
          onRescan={() => { setIdResult(null); setFaceResult(null); setPortraitDone(false); }}
        />
      ) : (
        <div>
          <div style={{ color: T.mute, fontSize: 17, maxWidth: 460, margin: "0 auto 26px" }}>
            Scan the barcode on the back of your ID using the scanner below the screen. We check your date of birth, then capture the photo on the front to verify it's really you. Nothing is stored after your order.
          </div>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 14,
            background: T.panel, borderRadius: 16, padding: "18px 30px",
          }}>
            <span style={{
              width: 12, height: 12, borderRadius: "50%", background: T.amber,
              animation: "pulse 1.2s ease-in-out infinite",
            }} />
            <span style={{ fontSize: 18, fontWeight: 700 }}>Waiting for scan…</span>
          </div>
        </div>
      )}
      <Footer>
        <Btn ghost onClick={reset}>Cancel Order</Btn>
        <Btn big disabled={!idResult?.ofAge || !portraitDone || scanning} onClick={() => setScreen("facescan")}>Continue</Btn>
      </Footer>
      {/* DEV ONLY — remove for the real kiosk build */}
      <button
        onClick={() => {
          setIdResult({ ofAge: true, age: 23, name: "Dev Skip", source: "skipped" });
          setPortraitDone(true);
          setScreen("facescan");
        }}
        style={{
          marginTop: 26, background: "none", border: "none", cursor: "pointer",
          color: T.mute, fontSize: 13, textDecoration: "underline", fontFamily: "inherit",
        }}>
        Skip ID verification (dev)
      </button>
    </Step>
  );

  const renderFaceScan = () => {
    const em = faceResult?.emotion ? EMOTION_MAP[faceResult.emotion] : null;
    return (
      <Step eyebrow="Step 2 of 4" title="Verify it's you">
        {scanning ? (
          <CameraFeed label="Look at the camera…" />
        ) : faceResult ? (
          faceResult.noFace ? (
            <ResultCard
              icon="🫥"
              title="No face detected"
              lines={["Step closer to the camera and make sure your face is well lit."]}
              onRescan={() => setFaceResult(null)}
            />
          ) : faceResult.match ? (
            <ResultCard
              icon="🪪"
              title={`Identity match · ${Math.round(faceResult.matchScore * 100)}%`}
              lines={[
                `Face matches ID photo`,
                `Mood detected: ${cap(faceResult.emotion)} — "${em.blurb}"`,
                faceResult.source === "live"
                  ? (faceResult.matchIsReal ? "● Live · real ID match" : "● Live emotion · match simulated")
                  : "○ Simulated result",
              ]}
              onRescan={() => setFaceResult(null)}
            />
          ) : (
            <ResultCard
              icon="⛔"
              title="Face doesn't match ID"
              lines={[`Match score ${Math.round(faceResult.matchScore * 100)}% — below threshold`]}
              onRescan={() => setFaceResult(null)}
            />
          )
        ) : (
          <div>
            <div style={{ color: T.mute, fontSize: 17, maxWidth: 440, margin: "0 auto 30px" }}>
              Look at the camera. We verify your face matches the photo on your ID, and read your mood to suggest a drink strength. You always get final say.
            </div>
            <Btn big onClick={runFaceScan} disabled={!idResult}>Start Face Scan</Btn>
          </div>
        )}
        <Footer>
          <Btn ghost onClick={() => setScreen("idscan")}>Back</Btn>
          <Btn big disabled={!faceResult?.match || scanning} onClick={() => setScreen("drinks")}>Continue</Btn>
        </Footer>
      </Step>
    );
  };

  const renderDrinks = () => (
    <Step eyebrow="Step 3 of 4" title="Pick your drink">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(128px, 1fr))", gap: 12, width: "100%", maxWidth: 900 }}>
        {DRINKS.map((d) => {
          const sel = drink?.id === d.id;
          return (
            <button key={d.id} onClick={() => setDrink(d)}
              style={{
                fontFamily: "inherit", cursor: "pointer", padding: "16px 10px 14px",
                borderRadius: 18, minHeight: 160,
                background: sel ? T.panelHi : T.panel,
                border: sel ? `3px solid ${T.amber}` : `3px solid transparent`,
                color: T.cream, transition: "border 0.15s ease",
              }}>
              <div style={{
                width: 54, height: 54, borderRadius: "50%", margin: "0 auto 14px",
                background: `radial-gradient(circle at 35% 30%, ${d.hue}, ${d.hue}77)`,
                boxShadow: sel ? `0 0 22px ${d.hue}88` : "none",
              }} />
              <div style={{ fontSize: 19, fontWeight: 800 }}>{d.name}</div>
              <div style={{ fontSize: 13, color: T.mute, marginTop: 5 }}>{d.base} · {d.abv}% base</div>
            </button>
          );
        })}
      </div>
      <Footer>
        <Btn ghost onClick={() => setScreen("facescan")}>Back</Btn>
        <Btn big disabled={!drink} onClick={() => setScreen("amount")}>Continue</Btn>
      </Footer>
    </Step>
  );

  const renderAmount = () => {
    const em = faceResult?.emotion ? EMOTION_MAP[faceResult.emotion] : null;
    return (
      <Step eyebrow="Step 4 of 4" title="How much?">
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap", justifyContent: "center" }}>
          {AMOUNTS.map((a) => {
            const sel = amount?.id === a.id;
            return (
              <button key={a.id} onClick={() => setAmount(a)}
                style={{
                  fontFamily: "inherit", cursor: "pointer",
                  width: "clamp(140px, 22vw, 200px)", padding: "18px 10px 14px", borderRadius: 18,
                  background: sel ? T.panelHi : T.panel,
                  border: sel ? `3px solid ${T.amber}` : "3px solid transparent",
                  color: T.cream,
                }}>
                <Glass fill={a.fill} hue={drink?.hue || T.amber} height={110} />
                <div style={{ fontSize: 21, fontWeight: 800, marginTop: 14 }}>{a.label}</div>
                <div style={{ fontSize: 13, color: T.mute, marginTop: 4 }}>{a.ml} mL</div>
              </button>
            );
          })}
        </div>

        <div style={{ marginTop: 30, textAlign: "center" }}>
          <div style={{ color: T.mute, fontSize: 14, marginBottom: 10 }}>Strength</div>
          <div style={{ display: "inline-flex", gap: 10, background: T.panel, borderRadius: 14, padding: 6, flexWrap: "wrap", justifyContent: "center" }}>
            {INTENSITY.map((label, i) => {
              const sel = !useMood && intensity === i;
              return (
                <button key={i} onClick={() => { setIntensity(i); setUseMood(false); }}
                  style={{
                    fontFamily: "inherit", cursor: "pointer", fontSize: 16, fontWeight: 700,
                    padding: "10px 26px", borderRadius: 10, border: "none",
                    background: sel ? T.amber : "transparent",
                    color: sel ? "#1A130C" : T.mute,
                  }}>
                  <div>{label}</div>
                  <div style={{ fontSize: 12.5, fontWeight: 600, opacity: 0.8, marginTop: 3 }}>
                    {Math.round(STRENGTH_MULT[i] * 100)}%{drink ? ` · ${(drink.abv * STRENGTH_MULT[i]).toFixed(1)}% ABV` : ""}
                  </div>
                </button>
              );
            })}
            {em && (
              <button onClick={() => setUseMood(true)}
                style={{
                  fontFamily: "inherit", cursor: "pointer", fontSize: 16, fontWeight: 700,
                  padding: "10px 26px", borderRadius: 10,
                  border: `2px dashed ${useMood ? "transparent" : T.copper}`,
                  background: useMood ? T.copper : "transparent",
                  color: useMood ? "#1A130C" : T.copper,
                }}>
                <div>🎭 Match my mood</div>
                <div style={{ fontSize: 12.5, fontWeight: 600, opacity: 0.8, marginTop: 3 }}>
                  {Math.round(STRENGTH_MULT[em.intensity] * 100)}%{drink ? ` · ${(drink.abv * STRENGTH_MULT[em.intensity]).toFixed(1)}% ABV` : ""}
                </div>
              </button>
            )}
          </div>
          {useMood && em && (
            <div style={{ color: T.copper, fontSize: 15, marginTop: 12 }}>
              {cap(faceResult.emotion)} → {INTENSITY[em.intensity]} ({Math.round(STRENGTH_MULT[em.intensity] * 100)}% of standard) · "{em.blurb}"
            </div>
          )}
        </div>

        <Footer>
          <Btn ghost onClick={() => setScreen("drinks")}>Back</Btn>
          <Btn big disabled={!amount} onClick={() => setScreen("confirm")}>Review Order</Btn>
        </Footer>
      </Step>
    );
  };

  const renderConfirm = () => (
    <Step eyebrow="Confirm" title="Your order">
      <div style={{ display: "flex", gap: 48, alignItems: "flex-start", flexWrap: "wrap", justifyContent: "center" }}>
        <div style={{ paddingTop: 10 }}>
          <Glass fill={amount.fill} hue={drink.hue} height={200} />
        </div>

        {/* Customer-facing summary */}
        <div style={{
          background: T.panel, borderRadius: 18, padding: "26px 34px",
          textAlign: "left", minWidth: 300,
        }}>
          <div style={{ fontSize: 26, fontWeight: 800, marginBottom: 4 }}>{drink.name}</div>
          <div style={{ color: T.mute, fontSize: 15, marginBottom: 18 }}>{drink.base}</div>
          <SummaryRow label="Size" value={`${amount.label} · ${amount.ml} mL`} />
          <SummaryRow
            label="Strength"
            value={`${INTENSITY[effectiveIntensity]} · ${(drink.abv * STRENGTH_MULT[effectiveIntensity]).toFixed(1)}% ABV`}
          />
          <SummaryRow
            label="Chosen by"
            value={useMood ? `Your mood (${cap(faceResult.emotion)})` : "You"}
          />
          <SummaryRow label="ID check" value="Verified 19+" last />
        </div>
      </div>

      {/* Dev view — what actually gets sent to the dispenser */}
      <details style={{ marginTop: 26, maxWidth: 440 }}>
        <summary style={{ color: T.mute, fontSize: 13, cursor: "pointer", letterSpacing: "0.08em", textTransform: "uppercase" }}>
          Dev: MQTT payload
        </summary>
        <pre style={{
          background: "#0C0908", color: T.ok, padding: "16px 20px", borderRadius: 12,
          fontSize: 13, lineHeight: 1.7, textAlign: "left", overflow: "auto", marginTop: 10,
        }}>
{`// MQTT → drinks/orders
${JSON.stringify(payload, null, 2)}`}
        </pre>
      </details>

      <Footer>
        <Btn ghost onClick={() => setScreen("amount")}>Back</Btn>
        <Btn big onClick={() => setScreen("dispensing")}>Pour It</Btn>
      </Footer>
    </Step>
  );

  const renderDispensing = () => (
    <Step eyebrow="Dispensing" title="Pouring…">
      <Glass fill={(progress / 100) * amount.fill} hue={drink.hue} height={220} />
      <div style={{ width: 320, height: 8, background: T.panel, borderRadius: 4, margin: "30px auto 8px" }}>
        <div style={{ width: `${progress}%`, height: "100%", background: T.amber, borderRadius: 4, transition: "width 0.1s linear" }} />
      </div>
      <div style={{ color: T.mute }}>{progress}%</div>
      <MqttLog log={log} />
    </Step>
  );

  const renderDone = () => (
    <Center>
      <div style={{ fontSize: 64 }}>🥃</div>
      <h1 style={{ fontSize: 48, color: T.cream, margin: "16px 0 8px" }}>Enjoy.</h1>
      <div style={{ color: T.mute, fontSize: 18, marginBottom: 40 }}>
        {drink.name} · {amount.ml} mL · {INTENSITY[effectiveIntensity]}
      </div>
      <Btn big onClick={reset}>New Order</Btn>
    </Center>
  );

  const screens = {
    attract: renderAttract, idscan: renderIdScan, facescan: renderFaceScan,
    drinks: renderDrinks, amount: renderAmount, confirm: renderConfirm,
    dispensing: renderDispensing, done: renderDone,
  };

  return (
    <div style={{
      minHeight: "100vh", background: T.bg, color: T.cream,
      fontFamily: "'Avenir Next', 'Segoe UI', system-ui, sans-serif",
      display: "flex", flexDirection: "column",
    }}>
      <style>{`@keyframes spin { from { transform: rotate(0) } to { transform: rotate(360deg) } }
@keyframes pulse { 0%,100% { opacity: 1; transform: scale(1) } 50% { opacity: 0.35; transform: scale(0.8) } }`}</style>
      {screens[screen]()}
    </div>
  );
}

// ─── Layout helpers ──────────────────────────────────────────────
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

function Center({ children }) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 32, textAlign: "center" }}>
      {children}
    </div>
  );
}
function Step({ eyebrow, title, children }) {
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "24px 20px", textAlign: "center" }}>
      <Eyebrow>{eyebrow}</Eyebrow>
      <h2 style={{ fontSize: "clamp(26px, 4.5vh, 40px)", margin: "0 0 clamp(16px, 3vh, 36px)", fontWeight: 800 }}>{title}</h2>
      {children}
    </div>
  );
}
function Footer({ children }) {
  return <div style={{ display: "flex", gap: 16, marginTop: "clamp(20px, 4vh, 44px)" }}>{children}</div>;
}
function SummaryRow({ label, value, last }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", gap: 30,
      padding: "11px 0",
      borderBottom: last ? "none" : `1px solid ${T.panelHi}`,
    }}>
      <span style={{ color: T.mute, fontSize: 15 }}>{label}</span>
      <span style={{ fontSize: 15, fontWeight: 700 }}>{value}</span>
    </div>
  );
}
function MqttLog({ log }) {
  return (
    <pre style={{
      marginTop: 28, background: "#0C0908", color: "#6FA86A", padding: "14px 18px",
      borderRadius: 12, fontSize: 12.5, lineHeight: 1.8, textAlign: "left", width: 380, maxWidth: "90vw", overflow: "auto",
    }}>
      {log.join("\n") || "…"}
    </pre>
  );
}
