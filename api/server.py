"""
CozyCryptoAI — FastAPI Backend
Serves the dashboard UI and WebSocket real-time feed
"""

import asyncio
import json
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# Store connected WebSocket clients
connected_clients = []


def create_app(engine=None, brain=None):
    app = FastAPI(title="CozyCryptoAI", docs_url=None, redoc_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"]
    )

    # ── REST Endpoints ────────────────────────────────────────────────────────

    @app.get("/api/status")
    async def get_status():
        if not engine:
            return {"error": "engine not ready"}
        try:
            status = await engine.get_status()
            return JSONResponse(content={
                "active":   status["active"],
                "paused":   status["paused"],
                "leverage": status["leverage"],
                "margin":   status["margin_mode"],
                "balance": {
                    "available": round(status["balance_usdt"]["available"], 2),
                    "frozen":    round(status["balance_usdt"]["frozen"], 2),
                    "total":     round(status["balance_usdt"]["total"], 2)
                },
                "positions":     status["open_positions"],
                "pnl":           status["total_pnl"],
                "total_scans":   status["total_scans"],
                "last_scan_count": status["pairs_in_last_scan"],
                "top_movers":    status["last_opportunities"]
            })
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @app.get("/api/positions")
    async def get_positions():
        if not engine:
            return []
        return JSONResponse(content=engine.open_positions)

    @app.get("/api/scan")
    async def run_scan():
        if not engine:
            return []
        try:
            results = await engine.scanner.scan_market()
            return JSONResponse(content=results[:20])
        except Exception as e:
            return JSONResponse(content={"error": str(e)}, status_code=500)

    @app.post("/api/pause")
    async def pause():
        if engine:
            engine.pause()
        return {"status": "paused"}

    @app.post("/api/resume")
    async def resume():
        if engine:
            engine.resume()
        return {"status": "active"}

    @app.post("/api/chat")
    async def chat(body: dict):
        if not brain:
            return {"reply": "Brain not ready"}
        try:
            reply = await brain.chat(body.get("message", ""), engine=engine)
            return {"reply": reply}
        except Exception as e:
            return {"reply": f"Error: {e}"}

    # ── WebSocket — real-time push ────────────────────────────────────────────

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        connected_clients.append(websocket)
        try:
            while True:
                # Push status every 3 seconds
                if engine:
                    try:
                        status = await engine.get_status()
                        await websocket.send_json({
                            "type": "status",
                            "data": {
                                "paused":   status["paused"],
                                "balance":  round(status["balance_usdt"]["available"], 2),
                                "equity":   round(status["balance_usdt"]["total"], 2),
                                "pnl":      status["total_pnl"],
                                "positions": len(status["open_positions"]),
                                "scans":    status["total_scans"],
                                "movers":   status["last_opportunities"][:5]
                            }
                        })
                    except Exception:
                        pass
                await asyncio.sleep(3)
        except WebSocketDisconnect:
            connected_clients.remove(websocket)

    # ── Dashboard HTML ────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return get_dashboard_html()

    return app


def get_dashboard_html():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CozyCryptoAI</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

  :root {
    --bg:       #080b10;
    --surface:  #0d1117;
    --card:     #111820;
    --border:   #1e2d3d;
    --accent:   #00d4ff;
    --green:    #00ff88;
    --red:      #ff4466;
    --yellow:   #ffcc00;
    --purple:   #a855f7;
    --text:     #e2e8f0;
    --muted:    #64748b;
    --glow:     0 0 20px rgba(0,212,255,0.15);
  }

  * { margin:0; padding:0; box-sizing:border-box; }

  body {
    font-family: 'Inter', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* Animated background grid */
  body::before {
    content:'';
    position:fixed;
    inset:0;
    background-image:
      linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events:none;
    z-index:0;
  }

  .wrapper { position:relative; z-index:1; }

  /* ── HEADER ── */
  header {
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:20px 32px;
    border-bottom:1px solid var(--border);
    background:rgba(13,17,23,0.9);
    backdrop-filter:blur(12px);
    position:sticky;
    top:0;
    z-index:100;
  }

  .logo {
    display:flex;
    align-items:center;
    gap:12px;
  }

  .logo-icon {
    width:36px; height:36px;
    background:linear-gradient(135deg, var(--accent), var(--purple));
    border-radius:10px;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:18px;
    box-shadow: 0 0 20px rgba(0,212,255,0.3);
  }

  .logo-text {
    font-size:18px;
    font-weight:800;
    letter-spacing:-0.5px;
    background:linear-gradient(135deg, #fff 30%, var(--accent));
    -webkit-background-clip:text;
    -webkit-text-fill-color:transparent;
  }

  .logo-sub {
    font-size:11px;
    color:var(--muted);
    font-weight:500;
    letter-spacing:1px;
    text-transform:uppercase;
  }

  .header-right { display:flex; align-items:center; gap:16px; }

  .status-pill {
    display:flex;
    align-items:center;
    gap:8px;
    padding:6px 14px;
    border-radius:20px;
    border:1px solid var(--border);
    font-size:13px;
    font-weight:600;
    background:var(--card);
  }

  .status-dot {
    width:8px; height:8px;
    border-radius:50%;
    background:var(--green);
    animation:pulse 2s infinite;
  }

  .status-dot.paused { background:var(--yellow); animation:none; }

  @keyframes pulse {
    0%,100% { opacity:1; box-shadow:0 0 0 0 rgba(0,255,136,0.4); }
    50%      { opacity:0.8; box-shadow:0 0 0 6px rgba(0,255,136,0); }
  }

  .btn {
    padding:8px 18px;
    border-radius:8px;
    border:none;
    font-size:13px;
    font-weight:600;
    cursor:pointer;
    transition:all 0.2s;
    font-family:'Inter',sans-serif;
  }

  .btn-pause  { background:rgba(255,204,0,0.15); color:var(--yellow); border:1px solid rgba(255,204,0,0.3); }
  .btn-resume { background:rgba(0,255,136,0.15); color:var(--green);  border:1px solid rgba(0,255,136,0.3); }
  .btn:hover  { transform:translateY(-1px); filter:brightness(1.2); }

  /* ── MAIN LAYOUT ── */
  main {
    padding:28px 32px;
    display:grid;
    gap:20px;
    max-width:1600px;
    margin:0 auto;
  }

  /* ── STAT CARDS ── */
  .stats-row {
    display:grid;
    grid-template-columns:repeat(auto-fit, minmax(200px, 1fr));
    gap:16px;
  }

  .stat-card {
    background:var(--card);
    border:1px solid var(--border);
    border-radius:16px;
    padding:20px 24px;
    position:relative;
    overflow:hidden;
    transition:border-color 0.3s;
  }

  .stat-card::before {
    content:'';
    position:absolute;
    top:0; left:0; right:0;
    height:2px;
    background:linear-gradient(90deg, var(--accent), var(--purple));
    opacity:0;
    transition:opacity 0.3s;
  }

  .stat-card:hover::before { opacity:1; }
  .stat-card:hover { border-color:rgba(0,212,255,0.3); }

  .stat-label {
    font-size:11px;
    font-weight:600;
    text-transform:uppercase;
    letter-spacing:1px;
    color:var(--muted);
    margin-bottom:10px;
  }

  .stat-value {
    font-size:28px;
    font-weight:800;
    font-family:'JetBrains Mono', monospace;
    letter-spacing:-1px;
    line-height:1;
  }

  .stat-sub {
    font-size:12px;
    color:var(--muted);
    margin-top:6px;
  }

  .text-green  { color:var(--green); }
  .text-red    { color:var(--red); }
  .text-accent { color:var(--accent); }
  .text-yellow { color:var(--yellow); }
  .text-purple { color:var(--purple); }

  /* ── BOTTOM GRID ── */
  .bottom-grid {
    display:grid;
    grid-template-columns:1fr 1fr 400px;
    gap:20px;
  }

  @media(max-width:1100px) {
    .bottom-grid { grid-template-columns:1fr 1fr; }
    .chat-panel  { grid-column:1/-1; }
  }
  @media(max-width:700px) {
    .bottom-grid { grid-template-columns:1fr; }
    main { padding:16px; }
    header { padding:16px; }
  }

  /* ── PANEL ── */
  .panel {
    background:var(--card);
    border:1px solid var(--border);
    border-radius:16px;
    overflow:hidden;
  }

  .panel-header {
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:16px 20px;
    border-bottom:1px solid var(--border);
  }

  .panel-title {
    font-size:13px;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:0.8px;
    color:var(--muted);
  }

  .panel-badge {
    font-size:11px;
    padding:3px 10px;
    border-radius:20px;
    font-weight:600;
  }

  .badge-green  { background:rgba(0,255,136,0.1);  color:var(--green);  border:1px solid rgba(0,255,136,0.2); }
  .badge-accent { background:rgba(0,212,255,0.1);  color:var(--accent); border:1px solid rgba(0,212,255,0.2); }
  .badge-red    { background:rgba(255,68,102,0.1); color:var(--red);    border:1px solid rgba(255,68,102,0.2); }

  /* ── POSITIONS ── */
  .positions-list { padding:12px; display:flex; flex-direction:column; gap:10px; min-height:200px; }

  .position-card {
    background:var(--surface);
    border:1px solid var(--border);
    border-radius:12px;
    padding:14px 16px;
    display:grid;
    grid-template-columns:auto 1fr auto;
    align-items:center;
    gap:14px;
    transition:border-color 0.2s;
  }

  .position-card:hover { border-color:rgba(0,212,255,0.25); }

  .pos-direction {
    width:36px; height:36px;
    border-radius:10px;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:16px;
    font-weight:800;
    font-family:'JetBrains Mono',monospace;
  }

  .pos-long  { background:rgba(0,255,136,0.15); color:var(--green); }
  .pos-short { background:rgba(255,68,102,0.15); color:var(--red); }

  .pos-symbol  { font-size:15px; font-weight:700; margin-bottom:3px; }
  .pos-detail  { font-size:11px; color:var(--muted); font-family:'JetBrains Mono',monospace; }
  .pos-price   { text-align:right; font-family:'JetBrains Mono',monospace; }
  .pos-entry   { font-size:14px; font-weight:600; }
  .pos-sl-tp   { font-size:11px; color:var(--muted); margin-top:2px; }

  .empty-state {
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    gap:8px;
    padding:40px;
    color:var(--muted);
    font-size:13px;
  }

  .empty-icon { font-size:32px; opacity:0.4; }

  /* ── SCAN RESULTS ── */
  .scan-list { padding:12px; display:flex; flex-direction:column; gap:8px; min-height:200px; }

  .scan-item {
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:10px 14px;
    background:var(--surface);
    border:1px solid var(--border);
    border-radius:10px;
    transition:border-color 0.2s;
  }

  .scan-item:hover { border-color:rgba(0,212,255,0.25); }

  .scan-left { display:flex; align-items:center; gap:10px; }

  .scan-dir {
    width:6px; height:32px;
    border-radius:3px;
  }

  .scan-dir.long  { background:var(--green); }
  .scan-dir.short { background:var(--red); }

  .scan-symbol { font-size:14px; font-weight:700; }
  .scan-vol    { font-size:11px; color:var(--muted); }
  .scan-right  { text-align:right; }
  .scan-change { font-size:14px; font-weight:700; font-family:'JetBrains Mono',monospace; }
  .scan-score  { font-size:11px; color:var(--muted); }

  /* ── CHAT ── */
  .chat-panel { display:flex; flex-direction:column; height:520px; }

  .chat-messages {
    flex:1;
    overflow-y:auto;
    padding:16px;
    display:flex;
    flex-direction:column;
    gap:12px;
    scrollbar-width:thin;
    scrollbar-color:var(--border) transparent;
  }

  .msg {
    max-width:85%;
    padding:10px 14px;
    border-radius:12px;
    font-size:13px;
    line-height:1.6;
  }

  .msg-ai {
    align-self:flex-start;
    background:var(--surface);
    border:1px solid var(--border);
    border-bottom-left-radius:4px;
    color:var(--text);
  }

  .msg-user {
    align-self:flex-end;
    background:linear-gradient(135deg, rgba(0,212,255,0.2), rgba(168,85,247,0.2));
    border:1px solid rgba(0,212,255,0.2);
    border-bottom-right-radius:4px;
    color:var(--text);
  }

  .msg-name {
    font-size:10px;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:0.8px;
    margin-bottom:4px;
    color:var(--muted);
  }

  .msg-ai .msg-name  { color:var(--accent); }
  .msg-user .msg-name { color:var(--purple); }

  .chat-input-row {
    padding:12px 16px;
    border-top:1px solid var(--border);
    display:flex;
    gap:10px;
    align-items:center;
  }

  .chat-input {
    flex:1;
    background:var(--surface);
    border:1px solid var(--border);
    border-radius:10px;
    padding:10px 14px;
    color:var(--text);
    font-size:13px;
    font-family:'Inter',sans-serif;
    outline:none;
    transition:border-color 0.2s;
  }

  .chat-input:focus  { border-color:var(--accent); }
  .chat-input::placeholder { color:var(--muted); }

  .btn-send {
    width:40px; height:40px;
    background:linear-gradient(135deg, var(--accent), var(--purple));
    border:none;
    border-radius:10px;
    cursor:pointer;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:16px;
    transition:all 0.2s;
    flex-shrink:0;
  }

  .btn-send:hover { transform:scale(1.05); filter:brightness(1.1); }

  /* ── TYPING INDICATOR ── */
  .typing {
    display:flex;
    gap:4px;
    align-items:center;
    padding:12px 14px;
  }

  .typing span {
    width:6px; height:6px;
    background:var(--accent);
    border-radius:50%;
    animation:bounce 1.2s infinite;
  }

  .typing span:nth-child(2) { animation-delay:0.2s; }
  .typing span:nth-child(3) { animation-delay:0.4s; }

  @keyframes bounce {
    0%,60%,100% { transform:translateY(0); opacity:0.4; }
    30%          { transform:translateY(-6px); opacity:1; }
  }

  /* ── TICKER TAPE ── */
  .ticker-wrap {
    overflow:hidden;
    border-bottom:1px solid var(--border);
    background:rgba(0,212,255,0.03);
    padding:8px 0;
  }

  .ticker-inner {
    display:flex;
    gap:40px;
    animation:scroll-left 30s linear infinite;
    white-space:nowrap;
  }

  @keyframes scroll-left {
    from { transform:translateX(0); }
    to   { transform:translateX(-50%); }
  }

  .ticker-item {
    display:flex;
    align-items:center;
    gap:8px;
    font-size:12px;
    font-family:'JetBrains Mono',monospace;
  }

  .ticker-sym  { font-weight:700; color:var(--text); }
  .ticker-pct  { font-weight:600; }

  /* ── LIVE FEED DOT ── */
  .live-dot {
    display:inline-block;
    width:6px; height:6px;
    background:var(--red);
    border-radius:50%;
    margin-right:5px;
    animation:pulse-red 1.5s infinite;
  }

  @keyframes pulse-red {
    0%,100% { opacity:1; }
    50%      { opacity:0.3; }
  }

  /* ── SCAN BUTTON ── */
  .btn-scan {
    padding:5px 12px;
    font-size:11px;
    border-radius:6px;
    background:rgba(0,212,255,0.1);
    color:var(--accent);
    border:1px solid rgba(0,212,255,0.2);
    cursor:pointer;
    font-weight:600;
    transition:all 0.2s;
    font-family:'Inter',sans-serif;
  }

  .btn-scan:hover { background:rgba(0,212,255,0.2); }
</style>
</head>
<body>
<div class="wrapper">

<!-- TICKER TAPE -->
<div class="ticker-wrap">
  <div class="ticker-inner" id="ticker">
    <span class="ticker-item"><span class="ticker-sym">BTCUSDT</span><span class="ticker-pct text-green" id="t-btc">—</span></span>
    <span class="ticker-item"><span class="ticker-sym">ETHUSDT</span><span class="ticker-pct text-green" id="t-eth">—</span></span>
    <span class="ticker-item"><span class="ticker-sym">SOLUSDT</span><span class="ticker-pct text-green" id="t-sol">—</span></span>
    <span class="ticker-item"><span class="ticker-sym">BNBUSDT</span><span class="ticker-pct text-green" id="t-bnb">—</span></span>
    <span class="ticker-item"><span class="ticker-sym">XRPUSDT</span><span class="ticker-pct text-green" id="t-xrp">—</span></span>
    <!-- duplicated for seamless loop -->
    <span class="ticker-item"><span class="ticker-sym">BTCUSDT</span><span class="ticker-pct text-green">—</span></span>
    <span class="ticker-item"><span class="ticker-sym">ETHUSDT</span><span class="ticker-pct text-green">—</span></span>
    <span class="ticker-item"><span class="ticker-sym">SOLUSDT</span><span class="ticker-pct text-green">—</span></span>
    <span class="ticker-item"><span class="ticker-sym">BNBUSDT</span><span class="ticker-pct text-green">—</span></span>
    <span class="ticker-item"><span class="ticker-sym">XRPUSDT</span><span class="ticker-pct text-green">—</span></span>
  </div>
</div>

<!-- HEADER -->
<header>
  <div class="logo">
    <div class="logo-icon">⚡</div>
    <div>
      <div class="logo-text">CozyCryptoAI</div>
      <div class="logo-sub">Institutional Futures Engine</div>
    </div>
  </div>
  <div class="header-right">
    <div class="status-pill">
      <div class="status-dot" id="status-dot"></div>
      <span id="status-text">Connecting...</span>
    </div>
    <button class="btn btn-pause" id="toggle-btn" onclick="toggleTrading()">⏸ Pause</button>
  </div>
</header>

<!-- MAIN -->
<main>

  <!-- STATS ROW -->
  <div class="stats-row">
    <div class="stat-card">
      <div class="stat-label">Available Balance</div>
      <div class="stat-value text-accent" id="stat-balance">—</div>
      <div class="stat-sub">USDT futures wallet</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Total Equity</div>
      <div class="stat-value text-green" id="stat-equity">—</div>
      <div class="stat-sub">Including unrealized PnL</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Session PnL</div>
      <div class="stat-value" id="stat-pnl">—</div>
      <div class="stat-sub">This session</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Open Positions</div>
      <div class="stat-value text-purple" id="stat-positions">—</div>
      <div class="stat-sub">Max 3 concurrent</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Markets Scanned</div>
      <div class="stat-value text-accent" id="stat-scans">—</div>
      <div class="stat-sub">Total scan cycles</div>
    </div>
  </div>

  <!-- BOTTOM GRID -->
  <div class="bottom-grid">

    <!-- POSITIONS -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title"><span class="live-dot"></span>Live Positions</span>
        <span class="panel-badge badge-green" id="pos-count">0 open</span>
      </div>
      <div class="positions-list" id="positions-list">
        <div class="empty-state">
          <div class="empty-icon">📭</div>
          <span>No open positions</span>
          <span style="font-size:11px">Scanning for setups...</span>
        </div>
      </div>
    </div>

    <!-- MARKET SCANNER -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">🔍 Market Scanner</span>
        <button class="btn-scan" onclick="runScan()">Refresh</button>
      </div>
      <div class="scan-list" id="scan-list">
        <div class="empty-state">
          <div class="empty-icon">📡</div>
          <span>Scanning markets...</span>
        </div>
      </div>
    </div>

    <!-- AI CHAT -->
    <div class="panel chat-panel">
      <div class="panel-header">
        <span class="panel-title">⚡ AI Terminal</span>
        <span class="panel-badge badge-accent">Live</span>
      </div>
      <div class="chat-messages" id="chat-messages">
        <div class="msg msg-ai">
          <div class="msg-name">CozyCryptoAI</div>
          Institutional engine online. Scanning all USDT-M futures for liquidity sweeps, structure shifts, and order flow signals. Ask me anything.
        </div>
      </div>
      <div class="chat-input-row">
        <input class="chat-input" id="chat-input" placeholder="Ask about setups, positions, market structure..." onkeydown="if(event.key==='Enter') sendChat()">
        <button class="btn-send" onclick="sendChat()">➤</button>
      </div>
    </div>

  </div>
</main>
</div>

<script>
  let isPaused = false;
  let ws;

  // ── WebSocket ──────────────────────────────────────────────────────────────
  function connectWS() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${proto}//${location.host}/ws`);

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'status') updateStatus(msg.data);
    };

    ws.onclose = () => setTimeout(connectWS, 3000);
    ws.onerror = () => ws.close();
  }

  // ── Update Stats ───────────────────────────────────────────────────────────
  function updateStatus(data) {
    isPaused = data.paused;

    const dot = document.getElementById('status-dot');
    const txt = document.getElementById('status-text');
    dot.className = 'status-dot' + (isPaused ? ' paused' : '');
    txt.textContent = isPaused ? 'Paused' : 'Trading Live';

    const btn = document.getElementById('toggle-btn');
    btn.textContent  = isPaused ? '▶ Resume' : '⏸ Pause';
    btn.className    = 'btn ' + (isPaused ? 'btn-resume' : 'btn-pause');

    document.getElementById('stat-balance').textContent  = '$' + data.balance.toLocaleString('en', {minimumFractionDigits:2});
    document.getElementById('stat-equity').textContent   = '$' + data.equity.toLocaleString('en', {minimumFractionDigits:2});
    document.getElementById('stat-scans').textContent    = data.scans.toLocaleString();
    document.getElementById('stat-positions').textContent = data.positions + '/3';

    const pnl = data.pnl;
    const pnlEl = document.getElementById('stat-pnl');
    pnlEl.textContent  = (pnl >= 0 ? '+' : '') + pnl.toFixed(4) + ' USDT';
    pnlEl.className    = 'stat-value ' + (pnl >= 0 ? 'text-green' : 'text-red');

    // Ticker movers
    if (data.movers && data.movers.length) {
      // update ticker items dynamically
    }
  }

  // ── Positions ──────────────────────────────────────────────────────────────
  async function loadPositions() {
    try {
      const r = await fetch('/api/positions');
      const data = await r.json();
      const list = document.getElementById('positions-list');
      const count = document.getElementById('pos-count');
      const entries = Object.entries(data);
      count.textContent = entries.length + ' open';

      if (!entries.length) {
        list.innerHTML = `<div class="empty-state"><div class="empty-icon">📭</div><span>No open positions</span><span style="font-size:11px">Scanning for setups...</span></div>`;
        return;
      }

      list.innerHTML = entries.map(([sym, pos]) => {
        const isLong = pos.hold_side === 'long';
        return `
          <div class="position-card">
            <div class="pos-direction ${isLong ? 'pos-long' : 'pos-short'}">${isLong ? 'L' : 'S'}</div>
            <div>
              <div class="pos-symbol">${sym}</div>
              <div class="pos-detail">${pos.leverage}x · ${pos.contracts} contracts · ${pos.regime || 'expanding'}</div>
              <div class="pos-detail" style="margin-top:4px;color:#64748b">${(pos.reason||'').split('|')[0].trim()}</div>
            </div>
            <div class="pos-price">
              <div class="pos-entry">$${Number(pos.entry_price).toPrecision(6)}</div>
              <div class="pos-sl-tp">SL $${Number(pos.stop_loss).toPrecision(5)}</div>
              <div class="pos-sl-tp">TP $${Number(pos.take_profit).toPrecision(5)}</div>
            </div>
          </div>`;
      }).join('');
    } catch(e) {}
  }

  // ── Scanner ────────────────────────────────────────────────────────────────
  async function runScan() {
    const list = document.getElementById('scan-list');
    list.innerHTML = `<div class="empty-state"><div class="empty-icon">📡</div><span>Scanning ${3000}+ pairs...</span></div>`;
    try {
      const r = await fetch('/api/scan');
      const data = await r.json();
      if (!data.length) {
        list.innerHTML = `<div class="empty-state"><div class="empty-icon">😴</div><span>Markets quiet right now</span></div>`;
        return;
      }
      list.innerHTML = data.slice(0,10).map(o => {
        const isLong = o.direction === 'long';
        const chg = Number(o.change_pct);
        return `
          <div class="scan-item">
            <div class="scan-left">
              <div class="scan-dir ${isLong ? 'long' : 'short'}"></div>
              <div>
                <div class="scan-symbol">${o.symbol}</div>
                <div class="scan-vol">Vol $${(o.volume_24h/1e6).toFixed(1)}M</div>
              </div>
            </div>
            <div class="scan-right">
              <div class="scan-change ${chg>=0?'text-green':'text-red'}">${chg>=0?'+':''}${chg.toFixed(2)}%</div>
              <div class="scan-score">Score ${o.score.toFixed(0)}/100</div>
            </div>
          </div>`;
      }).join('');
    } catch(e) {
      list.innerHTML = `<div class="empty-state"><span>Scan error</span></div>`;
    }
  }

  // ── Chat ───────────────────────────────────────────────────────────────────
  async function sendChat() {
    const input = document.getElementById('chat-input');
    const msg   = input.value.trim();
    if (!msg) return;
    input.value = '';

    appendMsg('You', msg, 'msg-user');

    // Typing indicator
    const typingId = 'typing-' + Date.now();
    const typingEl = document.createElement('div');
    typingEl.className = 'msg msg-ai';
    typingEl.id = typingId;
    typingEl.innerHTML = `<div class="msg-name">CozyCryptoAI</div><div class="typing"><span></span><span></span><span></span></div>`;
    document.getElementById('chat-messages').appendChild(typingEl);
    scrollChat();

    try {
      const r = await fetch('/api/chat', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({message: msg})
      });
      const data = await r.json();
      document.getElementById(typingId)?.remove();
      appendMsg('CozyCryptoAI', data.reply, 'msg-ai');
    } catch(e) {
      document.getElementById(typingId)?.remove();
      appendMsg('CozyCryptoAI', 'Connection error. Try again.', 'msg-ai');
    }
  }

  function appendMsg(name, text, cls) {
    const el = document.createElement('div');
    el.className = `msg ${cls}`;
    el.innerHTML = `<div class="msg-name">${name}</div>${escapeHtml(text)}`;
    document.getElementById('chat-messages').appendChild(el);
    scrollChat();
  }

  function scrollChat() {
    const c = document.getElementById('chat-messages');
    c.scrollTop = c.scrollHeight;
  }

  function escapeHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>');
  }

  // ── Controls ───────────────────────────────────────────────────────────────
  async function toggleTrading() {
    const endpoint = isPaused ? '/api/resume' : '/api/pause';
    await fetch(endpoint, {method:'POST'});
  }

  // ── Init ───────────────────────────────────────────────────────────────────
  connectWS();
  loadPositions();
  runScan();

  // Refresh positions every 15s, scan every 60s
  setInterval(loadPositions, 15000);
  setInterval(runScan, 60000);

  // Pull initial status
  fetch('/api/status').then(r=>r.json()).then(d => {
    updateStatus({
      paused:    d.paused,
      balance:   d.balance?.available || 0,
      equity:    d.balance?.total || 0,
      pnl:       d.pnl || 0,
      positions: Object.keys(d.positions||{}).length,
      scans:     d.total_scans || 0,
      movers:    d.top_movers || []
    });
  }).catch(()=>{});
</script>
</body>
</html>"""
