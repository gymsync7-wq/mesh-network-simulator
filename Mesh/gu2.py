import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import networkx as nx
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import random
import math
from datetime import datetime
from collections import deque


# ══════════════════════════════════════════════════════════
#  NETWORK LOGIC
# ══════════════════════════════════════════════════════════

def create_network(n=12, range_val=55):
    while True:
        G = nx.Graph()
        for i in range(n):
            G.add_node(i, pos=(random.randint(5,95), random.randint(5,95)), failed=False)
        nodes = list(G.nodes(data=True))
        for i in range(len(nodes)):
            for j in range(i+1, len(nodes)):
                x1,y1 = nodes[i][1]['pos']
                x2,y2 = nodes[j][1]['pos']
                dist = math.sqrt((x1-x2)**2+(y1-y2)**2)
                if dist <= range_val:
                    G.add_edge(nodes[i][0], nodes[j][0], weight=round(dist,2))
        pair = find_long_path_pair(G, min_length=4)
        if pair:
            return G, pair[0], pair[1]

def find_long_path_pair(G, min_length=4):
    nodes = list(G.nodes())
    random.shuffle(nodes)
    for i in range(len(nodes)):
        for j in range(i+1, len(nodes)):
            try:
                path = nx.dijkstra_path(G, nodes[i], nodes[j])
                if len(path) >= min_length:
                    return nodes[i], nodes[j]
            except:
                continue
    return None

def get_path_dijkstra(G, src, dst, failed_links=None, congestion=None, qos_mode="normal"):
    G2 = G.copy()
    for n in list(G2.nodes()):
        if G2.nodes[n]['failed']:
            G2.remove_node(n)
    if failed_links:
        for u, v in failed_links:
            if G2.has_edge(u, v):
                G2.remove_edge(u, v)
    # QoS: emergency/high packets avoid highly congested links
    if congestion and qos_mode in ("high", "emergency"):
        threshold = 0.5 if qos_mode == "emergency" else 0.8
        for (u, v), load in congestion.items():
            if load >= threshold and G2.has_edge(u, v):
                G2.remove_edge(u, v)
    # Adjust weights for congestion (makes Dijkstra prefer less-congested paths)
    if congestion:
        for (u, v), load in congestion.items():
            if G2.has_edge(u, v):
                base = G2[u][v]['weight']
                G2[u][v]['weight'] = base * (1 + load * 3)
    try:
        path = nx.dijkstra_path(G2, src, dst, weight='weight')
        # Report original cost, not inflated
        cost = sum(G[path[i]][path[i+1]]['weight'] for i in range(len(path)-1))
        return path, round(cost, 2)
    except:
        return None, None

def get_path_bfs(G, src, dst, failed_links=None):
    G2 = G.copy()
    for n in list(G2.nodes()):
        if G2.nodes[n]['failed']:
            G2.remove_node(n)
    if failed_links:
        for u, v in failed_links:
            if G2.has_edge(u, v):
                G2.remove_edge(u, v)
    try:
        path = nx.shortest_path(G2, src, dst)   # BFS = unweighted shortest
        cost = sum(G[path[i]][path[i+1]]['weight'] for i in range(len(path)-1))
        return path, round(cost, 2)
    except:
        return None, None

def fail_node_on_path(G, path):
    if not path or len(path) < 3:
        return None
    candidates = [n for n in path[1:-1] if not G.nodes[n]['failed']]
    if not candidates:
        return None
    node = random.choice(candidates)
    G.nodes[node]['failed'] = True
    return node

def fail_multiple_nodes(G, path, count=2):
    candidates = [n for n in path[1:-1] if not G.nodes[n]['failed']]
    failed = []
    for n in random.sample(candidates, min(count, len(candidates))):
        G.nodes[n]['failed'] = True
        failed.append(n)
    return failed

def fix_all_nodes(G):
    for n in G.nodes():
        G.nodes[n]['failed'] = False

def path_distance(G, path):
    if not path or len(path) < 2:
        return 0
    return round(sum(G[path[i]][path[i+1]]['weight'] for i in range(len(path)-1)), 2)

def network_health(G, failed_links=None):
    total_nodes = G.number_of_nodes()
    total_edges = G.number_of_edges()
    failed_nodes = sum(1 for n in G.nodes() if G.nodes[n]['failed'])
    failed_edges = len(failed_links) if failed_links else 0
    total = total_nodes + total_edges
    if total == 0:
        return 0
    healthy = (total_nodes - failed_nodes) + (total_edges - failed_edges)
    return round((healthy / total) * 100, 1)

def packet_loss_percent(G, path):
    if not path:
        return 100.0
    failed_on = sum(1 for n in path if G.nodes[n]['failed'])
    return round((failed_on / len(path)) * 100, 1)

def path_efficiency(G, path):
    """Ratio: direct distance SRC-DST vs actual path distance"""
    if not path or len(path) < 2:
        return 0
    sx, sy = G.nodes[path[0]]['pos']
    dx, dy = G.nodes[path[-1]]['pos']
    direct = math.sqrt((sx-dx)**2 + (sy-dy)**2)
    actual = path_distance(G, path)
    if actual == 0:
        return 100
    return round(min((direct / actual) * 100, 100), 1)


# ══════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ══════════════════════════════════════════════════════════

class MeshNetworkApp(tk.Tk):

    # ── Palette ──
    BG      = "#1a1a2e"
    PANEL   = "#16213e"
    CARD    = "#0f3460"
    ACCENT  = "#e94560"
    GREEN   = "#00b894"
    YELLOW  = "#fdcb6e"
    BLUE    = "#0984e3"
    PURPLE  = "#6c5ce7"
    TEXT    = "#dfe6e9"
    MUTED   = "#8899aa"

    def __init__(self):
        super().__init__()
        self.title("Mesh Network Simulator  |  CCE Major Project")
        self.configure(bg=self.BG)
        self.geometry("1400x820")
        self.resizable(True, True)

        # State
        self.G              = None
        self.src            = None
        self.dst            = None
        self.current_path   = None
        self.original_path  = None
        self.selected_nodes = []
        self.reroute_history= []          # list of (old_path, new_path, reason)
        self.packet_anim_id = None        # after() id for animation
        self.anim_step      = 0           # current animation step
        self.multi_failed   = []          # nodes failed in multi-fail
        self.failed_links   = set()       # set of (u,v) tuples — broken edges
        self.congestion     = {}          # (u,v) -> load 0.0-1.0
        self.qos_mode       = "normal"    # "normal" | "high" | "emergency"

        # Trend analysis data
        self.trend_failures      = []    # number of failures at each event
        self.trend_path_lengths  = []    # path length (hops) at each event
        self.trend_path_distance = []    # path distance at each event
        self.trend_health        = []    # network health % at each event
        self.trend_latency       = []    # estimated latency (distance * 0.5ms) at each event
        self.trend_labels        = []    # event label at each event
        self.trend_fail_count    = 0     # running failure counter

        self._build_ui()
        self._new_network()

    # ────────────────────────────────────────────
    #  UI CONSTRUCTION
    # ────────────────────────────────────────────

    def _build_ui(self):
        # Title bar
        tb = tk.Frame(self, bg=self.PANEL, height=52)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="⬡  Mesh Network Simulator",
                 bg=self.PANEL, fg=self.TEXT,
                 font=("Helvetica",16,"bold")).pack(side="left", padx=20, pady=10)
        tk.Label(tb, text="Computer & Communication Engineering  |  Major Project",
                 bg=self.PANEL, fg=self.MUTED,
                 font=("Helvetica",9)).pack(side="right", padx=20)

        # Notebook (tabs)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.TNotebook",
                        background=self.BG, borderwidth=0)
        style.configure("Dark.TNotebook.Tab",
                        background=self.CARD, foreground=self.TEXT,
                        padding=[14,6], font=("Helvetica",10,"bold"))
        style.map("Dark.TNotebook.Tab",
                  background=[("selected", self.ACCENT)],
                  foreground=[("selected","white")])

        self.nb = ttk.Notebook(self, style="Dark.TNotebook")
        self.nb.pack(fill="both", expand=True, padx=8, pady=6)

        # Tab 1 — Simulator
        sim_tab = tk.Frame(self.nb, bg=self.BG)
        self.nb.add(sim_tab, text="  📡  Simulator  ")
        self._build_sim_tab(sim_tab)

        # Tab 2 — Algorithm Comparison
        cmp_tab = tk.Frame(self.nb, bg=self.BG)
        self.nb.add(cmp_tab, text="  🔬  Dijkstra vs BFS  ")
        self._build_compare_tab(cmp_tab)

        # Tab 3 — Reroute History
        hist_tab = tk.Frame(self.nb, bg=self.BG)
        self.nb.add(hist_tab, text="  📋  Reroute History  ")
        self._build_history_tab(hist_tab)

        # Tab 4 — Network Stats Dashboard
        dash_tab = tk.Frame(self.nb, bg=self.BG)
        self.nb.add(dash_tab, text="  📊  Dashboard  ")
        self._build_dashboard_tab(dash_tab)

        # Tab 5 — Trend Analysis
        trend_tab = tk.Frame(self.nb, bg=self.BG)
        self.nb.add(trend_tab, text="  📈  Trend Analysis  ")
        self._build_trend_tab(trend_tab)

    # ── TAB 1: SIMULATOR ──────────────────────────

    def _build_sim_tab(self, parent):
        body = tk.Frame(parent, bg=self.BG)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        # Left control panel — fixed, no scroll needed
        left = tk.Frame(body, bg=self.PANEL, width=310)
        left.pack(side="left", fill="y", padx=(0,8))
        left.pack_propagate(False)
        self._build_controls(left)

        # Right canvas
        right = tk.Frame(body, bg=self.BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_canvas(right)

    def _build_controls(self, parent):
        def sep():
            tk.Frame(parent, bg=self.MUTED, height=1).pack(fill="x", padx=10, pady=4)

        def section(text):
            sep()
            tk.Label(parent, text=text, bg=self.PANEL, fg=self.ACCENT,
                     font=("Helvetica",8,"bold")).pack(anchor="w", padx=12, pady=(0,2))

        def btn2(parent_frame, text, color, cmd):
            """Helper to create a compact button."""
            return tk.Button(parent_frame, text=text, bg=color, fg="white",
                             font=("Helvetica",8,"bold"), relief="flat",
                             cursor="hand2", activebackground=color,
                             activeforeground="white", command=cmd,
                             wraplength=120)

        tk.Label(parent, text="CONTROLS", bg=self.PANEL, fg=self.ACCENT,
                 font=("Helvetica",9,"bold")).pack(anchor="w", padx=12, pady=(10,4))

        # ── NODE section (2 columns) ──
        section("NODE FAILURE")
        g1 = tk.Frame(parent, bg=self.PANEL)
        g1.pack(fill="x", padx=10, pady=2)
        btn2(g1,"💥 Fail Node",    self.ACCENT,  self._fail_node   ).grid(row=0,column=0,padx=2,pady=2,sticky="ew",ipady=5)
        btn2(g1,"💣 Fail Multiple","#c0392b",    self._fail_multiple).grid(row=0,column=1,padx=2,pady=2,sticky="ew",ipady=5)
        btn2(g1,"🔀 Reroute Node", self.PURPLE,  self._reroute      ).grid(row=1,column=0,padx=2,pady=2,sticky="ew",ipady=5)
        btn2(g1,"🔧 Fix Nodes",    "#e67e22",    self._fix_nodes    ).grid(row=1,column=1,padx=2,pady=2,sticky="ew",ipady=5)
        g1.columnconfigure(0, weight=1)
        g1.columnconfigure(1, weight=1)

        # ── LINK section (2 columns) ──
        section("LINK FAILURE")
        g2 = tk.Frame(parent, bg=self.PANEL)
        g2.pack(fill="x", padx=10, pady=2)
        btn2(g2,"🔗 Fail Link",     "#d35400",   self._fail_link         ).grid(row=0,column=0,padx=2,pady=2,sticky="ew",ipady=5)
        btn2(g2,"💣 Fail Multi Link","#922b21",   self._fail_multiple_links).grid(row=0,column=1,padx=2,pady=2,sticky="ew",ipady=5)
        btn2(g2,"🔀 Reroute Link",  "#8e44ad",   self._reroute_link       ).grid(row=1,column=0,padx=2,pady=2,sticky="ew",ipady=5)
        btn2(g2,"🔧 Fix Links",     "#27ae60",   self._fix_links          ).grid(row=1,column=1,padx=2,pady=2,sticky="ew",ipady=5)
        g2.columnconfigure(0, weight=1)
        g2.columnconfigure(1, weight=1)

        # ── CONGESTION section (2 columns) ──
        section("CONGESTION")
        g3 = tk.Frame(parent, bg=self.PANEL)
        g3.pack(fill="x", padx=10, pady=2)
        btn2(g3,"📶 Simulate",  "#2980b9",  self._simulate_congestion).grid(row=0,column=0,padx=2,pady=2,sticky="ew",ipady=5)
        btn2(g3,"🧹 Clear",     "#16a085",  self._clear_congestion   ).grid(row=0,column=1,padx=2,pady=2,sticky="ew",ipady=5)
        g3.columnconfigure(0, weight=1)
        g3.columnconfigure(1, weight=1)

        # ── QoS row ──
        section("QoS PRIORITY")
        qos_row = tk.Frame(parent, bg=self.PANEL)
        qos_row.pack(fill="x", padx=10, pady=(0,2))
        self.qos_var = tk.StringVar(value="normal")
        for val, label, col in [("normal","Normal","#74b9ff"),
                                  ("high","High","#fdcb6e"),
                                  ("emergency","SOS","#e17055")]:
            tk.Radiobutton(qos_row, text=label, variable=self.qos_var,
                           value=val, bg=self.PANEL, fg=col,
                           selectcolor=self.CARD, activebackground=self.PANEL,
                           font=("Helvetica",9,"bold"),
                           command=self._on_qos_change).pack(side="left", padx=3)

        # ── GENERAL buttons (full width) ──
        section("GENERAL")
        for label, color, cmd in [
            ("🔄  New Network",      self.BLUE,   self._new_network),
            ("📡  Show Current Path", self.GREEN,  self._show_path),
        ]:
            tk.Button(parent, text=label, bg=color, fg="white",
                      font=("Helvetica",9,"bold"), relief="flat",
                      cursor="hand2", activebackground=color,
                      activeforeground="white", command=cmd
                      ).pack(fill="x", padx=10, pady=2, ipady=4)

        # Save / Load row
        section("SAVE / LOAD")
        g_sl = tk.Frame(parent, bg=self.PANEL)
        g_sl.pack(fill="x", padx=10, pady=2)
        btn2(g_sl, "💾 Save Network", "#2c3e50", self._save_network).grid(
            row=0, column=0, padx=2, pady=2, sticky="ew", ipady=5)
        btn2(g_sl, "📂 Load Network", "#34495e", self._load_network).grid(
            row=0, column=1, padx=2, pady=2, sticky="ew", ipady=5)
        g_sl.columnconfigure(0, weight=1)
        g_sl.columnconfigure(1, weight=1)

        # ── Animate packet — full width, highlighted ──
        sep()
        tk.Button(parent, text="▶  Animate Packet", bg="#00cec9", fg="white",
                  font=("Helvetica",10,"bold"), relief="flat", cursor="hand2",
                  activebackground="#00cec9", activeforeground="white",
                  command=self._animate_packet
                  ).pack(fill="x", padx=10, pady=(0,4), ipady=6)

        section("NETWORK STATS")
        self.svars = {}
        rows = [
            ("Total Nodes",   "nodes"),
            ("Total Edges",   "edges"),
            ("Active Nodes",  "active"),
            ("Failed Nodes",  "failed"),
            ("Failed Links",  "failedlinks"),
            ("Source",        "src"),
            ("Destination",   "dst"),
            ("Path Hops",     "hops"),
            ("Path Distance", "dist"),
            ("Network Health","health"),
            ("Packet Loss",   "pktloss"),
            ("Path Efficiency","effic"),
            ("Congested Links","conglinks"),
            ("QoS Priority",  "qos"),
            ("Status",        "status"),
        ]
        for label, key in rows:
            row = tk.Frame(parent, bg=self.PANEL)
            row.pack(fill="x", padx=14, pady=1)
            tk.Label(row, text=label+":", bg=self.PANEL, fg=self.MUTED,
                     font=("Helvetica",8), width=15, anchor="w").pack(side="left")
            v = tk.StringVar(value="—")
            self.svars[key] = v
            tk.Label(row, textvariable=v, bg=self.PANEL, fg=self.TEXT,
                     font=("Helvetica",8,"bold"), anchor="w").pack(side="left")

        section("EVENT LOG")
        lf = tk.Frame(parent, bg=self.CARD)
        lf.pack(fill="both", expand=True, padx=14, pady=(0,14))
        self.log = tk.Text(lf, bg=self.CARD, fg=self.TEXT,
                           font=("Courier",7), relief="flat",
                           state="disabled", wrap="word", bd=0)
        self.log.pack(fill="both", expand=True, padx=4, pady=4)
        self.log.tag_config("info",    foreground="#74b9ff")
        self.log.tag_config("success", foreground="#00b894")
        self.log.tag_config("error",   foreground="#e17055")
        self.log.tag_config("warn",    foreground="#fdcb6e")
        self.log.tag_config("time",    foreground="#636e72")

    def _build_canvas(self, parent):
        # Legend
        leg = tk.Frame(parent, bg=self.PANEL, height=34)
        leg.pack(fill="x")
        leg.pack_propagate(False)
        items = [("● SRC","#00b894"),("● DST","#fdcb6e"),
                 ("● On-Path","#00cec9"),("● Off-Path","#576574"),
                 ("● Failed Node","#e17055"),("✖ Failed Link","#e74c3c"),
                 ("🟡 Congested","#f39c12"),("━ Active Path","#00b894")]
        for t,c in items:
            tk.Label(leg, text=t, bg=self.PANEL, fg=c,
                     font=("Helvetica",8,"bold")).pack(side="left", padx=8, pady=7)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(parent, textvariable=self.status_var,
                 bg=self.CARD, fg=self.TEXT,
                 font=("Helvetica",9), anchor="w", padx=10
                 ).pack(fill="x", side="bottom", pady=(4,0))

        # Matplotlib canvas
        self.fig, self.ax = plt.subplots(figsize=(8,5.8), facecolor=self.BG)
        self.ax.set_facecolor(self.BG)
        self.fig.tight_layout(pad=1)
        self.mpl_canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.mpl_canvas.get_tk_widget().configure(bg=self.BG)
        self.mpl_canvas.get_tk_widget().pack(fill="both", expand=True)
        self.mpl_canvas.mpl_connect("button_press_event", self._on_click)

    # ── TAB 5: TREND ANALYSIS ────────────────────

    def _build_trend_tab(self, parent):
        tk.Label(parent,
                 text="Trend Analysis — how path length, latency, and network health change as failures increase.",
                 bg=self.BG, fg=self.MUTED, font=("Helvetica",10)).pack(pady=(12,4))

        # Top controls
        ctrl = tk.Frame(parent, bg=self.BG)
        ctrl.pack(fill="x", padx=20, pady=4)
        tk.Button(ctrl, text="▶  Run Full Trend Simulation",
                  bg=self.PURPLE, fg="white", font=("Helvetica",11,"bold"),
                  relief="flat", cursor="hand2",
                  command=self._run_trend_simulation
                  ).pack(side="left", ipadx=12, ipady=6)
        tk.Button(ctrl, text="🗑  Clear Trend Data",
                  bg=self.ACCENT, fg="white", font=("Helvetica",10,"bold"),
                  relief="flat", cursor="hand2",
                  command=self._clear_trend_data
                  ).pack(side="left", padx=12, ipadx=8, ipady=6)
        self.trend_status = tk.StringVar(value="Click 'Run Full Trend Simulation' to generate analysis")
        tk.Label(ctrl, textvariable=self.trend_status,
                 bg=self.BG, fg=self.MUTED, font=("Helvetica",9)).pack(side="left", padx=10)

        # 4 charts in a 2x2 grid
        chart_frame = tk.Frame(parent, bg=self.BG)
        chart_frame.pack(fill="both", expand=True, padx=12, pady=6)

        self.trend_fig, axes = plt.subplots(2, 2, figsize=(12, 6),
                                             facecolor=self.BG)
        self.trend_fig.tight_layout(pad=2.5)
        self.ax_pl, self.ax_lat, self.ax_hlth, self.ax_pdr = axes.flat

        for ax in [self.ax_pl, self.ax_lat, self.ax_hlth, self.ax_pdr]:
            ax.set_facecolor(self.CARD)
            ax.tick_params(colors=self.MUTED, labelsize=7)
            ax.spines['bottom'].set_color(self.MUTED)
            ax.spines['left'].set_color(self.MUTED)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

        self.trend_fig.patch.set_facecolor(self.BG)
        self.trend_canvas = FigureCanvasTkAgg(self.trend_fig, master=chart_frame)
        self.trend_canvas.get_tk_widget().configure(bg=self.BG)
        self.trend_canvas.get_tk_widget().pack(fill="both", expand=True)

        self._draw_empty_trend_charts()

    def _draw_empty_trend_charts(self):
        """Draw placeholder charts with labels."""
        titles = [
            (self.ax_pl,   "Path Length vs Number of Failures", "#00cec9"),
            (self.ax_lat,  "Estimated Latency vs Number of Failures", "#fdcb6e"),
            (self.ax_hlth, "Network Health % vs Number of Failures", "#00b894"),
            (self.ax_pdr,  "Packet Delivery Success Rate vs Failures", "#6c5ce7"),
        ]
        for ax, title, color in titles:
            ax.clear()
            ax.set_facecolor(self.CARD)
            ax.set_title(title, color=color, fontsize=8, fontweight='bold', pad=6)
            ax.text(0.5, 0.5, "Run Simulation to generate data",
                    ha='center', va='center', color=self.MUTED,
                    fontsize=9, transform=ax.transAxes)
            ax.tick_params(colors=self.MUTED, labelsize=7)
            for spine in ['top','right']:
                ax.spines[spine].set_visible(False)
            ax.spines['bottom'].set_color(self.MUTED)
            ax.spines['left'].set_color(self.MUTED)
        self.trend_fig.patch.set_facecolor(self.BG)
        self.trend_canvas.draw()

    def _run_trend_simulation(self):
        """
        Run automated simulation:
        Start with clean network, progressively fail nodes and record metrics.
        """
        if not self.G or self.src is None:
            self.trend_status.set("Generate a network first in the Simulator tab.")
            return

        self.trend_status.set("Running simulation...")
        self.update()

        # Reset trend data
        self._clear_trend_data()

        # Save current state to restore later
        import copy
        saved_failed = {n: self.G.nodes[n]['failed'] for n in self.G.nodes()}
        saved_path   = self.current_path[:]
        saved_links  = set(self.failed_links)

        # Fix all nodes/links for clean start
        for n in self.G.nodes():
            self.G.nodes[n]['failed'] = False
        self.failed_links = set()

        # Recompute initial clean path
        clean_path, _ = get_path_dijkstra(self.G, self.src, self.dst)
        self.current_path = clean_path or saved_path

        # Record baseline (0 failures)
        self._record_trend_point(0, "Baseline")

        # Progressive failure simulation
        intermediate = [n for n in self.current_path[1:-1]]
        failure_count = 0

        for i, node_to_fail in enumerate(intermediate):
            if self.G.nodes[node_to_fail]['failed']:
                continue

            self.G.nodes[node_to_fail]['failed'] = True
            failure_count += 1

            # Try to reroute
            new_path, _ = get_path_dijkstra(self.G, self.src, self.dst,
                                             self.failed_links, {}, "normal")
            if new_path:
                self.current_path = new_path
            # else path is broken — still record the broken state

            self._record_trend_point(failure_count, f"Fail node {node_to_fail}")

        # Also simulate link failures on a fresh network
        for n in self.G.nodes():
            self.G.nodes[n]['failed'] = False
        self.failed_links = set()
        clean_path, _ = get_path_dijkstra(self.G, self.src, self.dst)
        self.current_path = clean_path or saved_path

        path_edges = list(zip(self.current_path, self.current_path[1:]))
        for i, (u, v) in enumerate(path_edges):
            self.failed_links.add((u, v))
            failure_count += 1
            new_path, _ = get_path_dijkstra(self.G, self.src, self.dst, self.failed_links)
            if new_path:
                self.current_path = new_path
            self._record_trend_point(failure_count, f"Fail link {u}↔{v}")

        # Restore original state
        for n in self.G.nodes():
            self.G.nodes[n]['failed'] = saved_failed[n]
        self.failed_links = saved_links
        self.current_path = saved_path

        # Draw all 4 charts
        self._update_trend_charts()
        self.trend_status.set(
            f"Simulation complete — {len(self.trend_failures)} data points recorded. "
            f"Max failures tested: {max(self.trend_failures) if self.trend_failures else 0}"
        )

    def _record_trend_point(self, fail_count, label):
        """Record one data point for all 4 trend metrics."""
        path = self.current_path
        self.trend_failures.append(fail_count)
        self.trend_labels.append(label)

        # Path length (hops)
        hops = len(path) - 1 if path and len(path) >= 2 else 0
        self.trend_path_lengths.append(hops)

        # Path distance
        if path and len(path) >= 2:
            try:
                dist = sum(self.G[path[i]][path[i+1]]['weight']
                           for i in range(len(path)-1))
                dist = round(dist, 2)
            except Exception:
                dist = 0
        else:
            dist = 0
        self.trend_path_distance.append(dist)

        # Estimated latency: each unit distance = 0.5ms propagation + 2ms per hop processing
        latency = round(dist * 0.5 + hops * 2.0, 2) if dist > 0 else 0
        self.trend_latency.append(latency)

        # Network health
        total_n = self.G.number_of_nodes()
        total_e = self.G.number_of_edges()
        failed_n = sum(1 for n in self.G.nodes() if self.G.nodes[n]['failed'])
        failed_e = len(self.failed_links)
        total = total_n + total_e
        health = round(((total_n - failed_n + total_e - failed_e) / total) * 100, 1) if total > 0 else 0
        self.trend_health.append(health)

        # Packet delivery success rate
        # 100% = path exists and no failed nodes on it
        # 0%   = no path or network partitioned
        failed_on_path = sum(1 for n in path if self.G.nodes[n]['failed']) if path else 0
        link_fail_on_path = sum(
            1 for i in range(len(path)-1)
            if (path[i],path[i+1]) in self.failed_links or (path[i+1],path[i]) in self.failed_links
        ) if path else 0
        if not path or len(path) < 2:
            pdr = 0.0
        elif failed_on_path > 0 or link_fail_on_path > 0:
            pdr = 0.0   # path is broken — packet cannot be delivered
        else:
            pdr = 100.0  # path exists and is clear
        self.trend_pdr.append(pdr)

    def _update_trend_charts(self):
        """Redraw all 4 trend charts with current data."""
        failures = self.trend_failures
        if not failures:
            self._draw_empty_trend_charts()
            return

        # ── Chart 1: Path Length vs Failures ──
        ax = self.ax_pl
        ax.clear()
        ax.set_facecolor(self.CARD)
        ax.plot(failures, self.trend_path_lengths,
                color="#00cec9", linewidth=2, marker='o',
                markersize=5, markerfacecolor="#00b894", markeredgecolor="white",
                markeredgewidth=1, label="Path Hops")
        ax.fill_between(failures, self.trend_path_lengths, alpha=0.15, color="#00cec9")
        ax.set_title("Path Length (Hops) vs Failures", color="#00cec9",
                     fontsize=8, fontweight='bold', pad=6)
        ax.set_xlabel("Number of Failures", color=self.MUTED, fontsize=7)
        ax.set_ylabel("Hops", color=self.MUTED, fontsize=7)
        ax.tick_params(colors=self.MUTED, labelsize=7)
        ax.yaxis.label.set_color(self.MUTED)
        ax.xaxis.label.set_color(self.MUTED)
        for spine in ['top','right']:
            ax.spines[spine].set_visible(False)
        ax.spines['bottom'].set_color(self.MUTED)
        ax.spines['left'].set_color(self.MUTED)
        # Annotate max
        if self.trend_path_lengths:
            mx = max(self.trend_path_lengths)
            mi = self.trend_path_lengths.index(mx)
            ax.annotate(f"Max: {mx}",
                        xy=(failures[mi], mx),
                        xytext=(failures[mi], mx + 0.3),
                        color="#fdcb6e", fontsize=7,
                        ha='center')

        # ── Chart 2: Latency vs Failures ──
        ax = self.ax_lat
        ax.clear()
        ax.set_facecolor(self.CARD)
        ax.plot(failures, self.trend_latency,
                color="#fdcb6e", linewidth=2, marker='s',
                markersize=5, markerfacecolor="#e67e22", markeredgecolor="white",
                markeredgewidth=1, label="Latency (ms)")
        ax.fill_between(failures, self.trend_latency, alpha=0.15, color="#fdcb6e")
        ax.set_title("Estimated Latency (ms) vs Failures", color="#fdcb6e",
                     fontsize=8, fontweight='bold', pad=6)
        ax.set_xlabel("Number of Failures", color=self.MUTED, fontsize=7)
        ax.set_ylabel("Latency (ms)", color=self.MUTED, fontsize=7)
        ax.tick_params(colors=self.MUTED, labelsize=7)
        ax.yaxis.label.set_color(self.MUTED)
        ax.xaxis.label.set_color(self.MUTED)
        for spine in ['top','right']:
            ax.spines[spine].set_visible(False)
        ax.spines['bottom'].set_color(self.MUTED)
        ax.spines['left'].set_color(self.MUTED)
        if self.trend_latency:
            mx = max(self.trend_latency)
            mi = self.trend_latency.index(mx)
            ax.annotate(f"Max: {mx}ms",
                        xy=(failures[mi], mx),
                        xytext=(failures[mi], mx * 1.05),
                        color="#e74c3c", fontsize=7, ha='center')

        # ── Chart 3: Network Health vs Failures ──
        ax = self.ax_hlth
        ax.clear()
        ax.set_facecolor(self.CARD)
        bar_colors = ["#e74c3c" if h < 70 else "#fdcb6e" if h < 90 else "#00b894"
                      for h in self.trend_health]
        x_pos = list(range(len(failures)))
        ax.bar(x_pos, self.trend_health, color=bar_colors, width=0.6, alpha=0.85)
        ax.plot(x_pos, self.trend_health,
                color="#dfe6e9", linewidth=1.5, linestyle='--',
                marker='o', markersize=4, alpha=0.8)
        ax.set_xticks(x_pos)
        ax.set_xticklabels([str(f) for f in failures], fontsize=6)
        ax.axhline(100, color="#2d4a6b", linewidth=0.8, linestyle="--")
        ax.axhline(70,  color="#e74c3c", linewidth=0.8, linestyle=":",
                   alpha=0.8)
        ax.text(len(failures)-1, 72, "Critical 70%", color="#e74c3c", fontsize=6, ha='right')
        ax.set_ylim(0, 115)
        ax.set_title("Network Health (%) vs Failures", color="#00b894",
                     fontsize=8, fontweight='bold', pad=6)
        ax.set_xlabel("Number of Failures", color=self.MUTED, fontsize=7)
        ax.set_ylabel("Health %", color=self.MUTED, fontsize=7)
        ax.tick_params(colors=self.MUTED, labelsize=7)
        ax.yaxis.label.set_color(self.MUTED)
        ax.xaxis.label.set_color(self.MUTED)
        for spine in ['top','right']:
            ax.spines[spine].set_visible(False)
        ax.spines['bottom'].set_color(self.MUTED)
        ax.spines['left'].set_color(self.MUTED)

        # ── Chart 4: Packet Delivery Rate vs Failures ──
        ax = self.ax_pdr
        ax.clear()
        ax.set_facecolor(self.CARD)

        pdr = self.trend_pdr if self.trend_pdr else [100.0] * len(failures)
        x_pos_pdr = list(range(len(failures)))
        pdr_colors = ["#e74c3c" if p < 100 else "#00b894" for p in pdr]
        ax.bar(x_pos_pdr, pdr, color=pdr_colors, width=0.6, alpha=0.85)
        ax.step(x_pos_pdr, pdr, color="#6c5ce7", linewidth=2, where='mid')
        ax.fill_between(x_pos_pdr, pdr, alpha=0.12, color="#6c5ce7", step='mid')
        ax.set_xticks(x_pos_pdr)
        ax.set_xticklabels([str(f) for f in failures], fontsize=6)
        ax.set_ylim(-5, 115)
        ax.axhline(100, color="#00b894", linewidth=1.0, linestyle='--', alpha=0.8)
        ax.text(0, 102, "100% = Full Delivery", color="#00b894", fontsize=6)
        ax.text(0, 2, "0% = Path Broken / Partitioned", color="#e74c3c", fontsize=6)
        ax.set_title("Packet Delivery Success Rate (%) vs Failures", color="#6c5ce7",
                     fontsize=8, fontweight='bold', pad=6)
        ax.set_xlabel("Number of Failures", color=self.MUTED, fontsize=7)
        ax.set_ylabel("Delivery Rate %", color=self.MUTED, fontsize=7)
        ax.tick_params(colors=self.MUTED, labelsize=7)
        ax.yaxis.label.set_color(self.MUTED)
        ax.xaxis.label.set_color(self.MUTED)
        for spine in ['top','right']:
            ax.spines[spine].set_visible(False)
        ax.spines['bottom'].set_color(self.MUTED)
        ax.spines['left'].set_color(self.MUTED)

        self.trend_fig.patch.set_facecolor(self.BG)
        self.trend_fig.tight_layout(pad=2.5)
        self.trend_canvas.draw()

    def _clear_trend_data(self):
        """Reset all trend data."""
        self.trend_failures      = []
        self.trend_path_lengths  = []
        self.trend_path_distance = []
        self.trend_health        = []
        self.trend_latency       = []
        self.trend_labels        = []
        self.trend_fail_count    = 0
        self.trend_pdr           = []
        self._draw_empty_trend_charts()
        self.trend_status.set("Trend data cleared.")

    # ── TAB 2: ALGORITHM COMPARISON ───────────────

    def _build_compare_tab(self, parent):
        tk.Label(parent,
                 text="Compare Dijkstra (weighted shortest path) vs BFS (hop shortest path)",
                 bg=self.BG, fg=self.MUTED,
                 font=("Helvetica",10)).pack(pady=(16,8))

        tk.Button(parent, text="▶  Run Comparison on Current Network",
                  bg=self.PURPLE, fg="white",
                  font=("Helvetica",11,"bold"), relief="flat",
                  cursor="hand2", command=self._run_comparison
                  ).pack(pady=6, ipadx=12, ipady=8)

        # Result cards
        cards = tk.Frame(parent, bg=self.BG)
        cards.pack(fill="both", expand=True, padx=20, pady=10)

        # Dijkstra card
        dc = tk.Frame(cards, bg=self.CARD, bd=0)
        dc.pack(side="left", fill="both", expand=True, padx=(0,8))
        tk.Label(dc, text="DIJKSTRA  (Weighted)", bg=self.CARD,
                 fg="#00b894", font=("Helvetica",12,"bold")).pack(pady=(12,4))
        self.dijk_vars = {}
        for key in ["Path","Hops","Distance","Time (µs)"]:
            row = tk.Frame(dc, bg=self.CARD)
            row.pack(fill="x", padx=16, pady=3)
            tk.Label(row, text=key+":", bg=self.CARD, fg=self.MUTED,
                     font=("Helvetica",9), width=12, anchor="w").pack(side="left")
            v = tk.StringVar(value="—")
            self.dijk_vars[key] = v
            tk.Label(row, textvariable=v, bg=self.CARD, fg=self.TEXT,
                     font=("Helvetica",9,"bold"), anchor="w", wraplength=260).pack(side="left")

        # BFS card
        bc = tk.Frame(cards, bg=self.CARD, bd=0)
        bc.pack(side="left", fill="both", expand=True, padx=(8,0))
        tk.Label(bc, text="BFS  (Hop Count)", bg=self.CARD,
                 fg="#fdcb6e", font=("Helvetica",12,"bold")).pack(pady=(12,4))
        self.bfs_vars = {}
        for key in ["Path","Hops","Distance","Time (µs)"]:
            row = tk.Frame(bc, bg=self.CARD)
            row.pack(fill="x", padx=16, pady=3)
            tk.Label(row, text=key+":", bg=self.CARD, fg=self.MUTED,
                     font=("Helvetica",9), width=12, anchor="w").pack(side="left")
            v = tk.StringVar(value="—")
            self.bfs_vars[key] = v
            tk.Label(row, textvariable=v, bg=self.CARD, fg=self.TEXT,
                     font=("Helvetica",9,"bold"), anchor="w", wraplength=260).pack(side="left")

        # Verdict
        vf = tk.Frame(parent, bg=self.PANEL)
        vf.pack(fill="x", padx=20, pady=8)
        tk.Label(vf, text="VERDICT:", bg=self.PANEL, fg=self.ACCENT,
                 font=("Helvetica",10,"bold")).pack(side="left", padx=12, pady=10)
        self.verdict_var = tk.StringVar(value="Run comparison to see result")
        tk.Label(vf, textvariable=self.verdict_var, bg=self.PANEL,
                 fg=self.TEXT, font=("Helvetica",10),
                 wraplength=900, justify="left").pack(side="left", padx=6)

        # Visual comparison canvas
        self.cmp_fig, (self.ax_d, self.ax_b) = plt.subplots(1, 2, figsize=(10,3.5),
                                                               facecolor=self.BG)
        for a in (self.ax_d, self.ax_b):
            a.set_facecolor(self.BG)
        self.cmp_fig.tight_layout(pad=1.5)
        self.cmp_canvas = FigureCanvasTkAgg(self.cmp_fig, master=parent)
        self.cmp_canvas.get_tk_widget().configure(bg=self.BG)
        self.cmp_canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(0,10))

    # ── TAB 3: REROUTE HISTORY ────────────────────

    def _build_history_tab(self, parent):
        tk.Label(parent, text="Every reroute event is recorded here automatically.",
                 bg=self.BG, fg=self.MUTED,
                 font=("Helvetica",10)).pack(pady=(14,6))

        tk.Button(parent, text="🗑  Clear History",
                  bg=self.ACCENT, fg="white",
                  font=("Helvetica",10,"bold"), relief="flat",
                  cursor="hand2", command=self._clear_history
                  ).pack(anchor="e", padx=20, pady=(0,6))

        cols = ("#","Time","Failed Node(s)","Old Path","New Path","Hops Before","Hops After","Dist Before","Dist After")
        frame = tk.Frame(parent, bg=self.BG)
        frame.pack(fill="both", expand=True, padx=14, pady=(0,14))

        style = ttk.Style()
        style.configure("History.Treeview",
                        background=self.CARD,
                        foreground=self.TEXT,
                        fieldbackground=self.CARD,
                        rowheight=28,
                        font=("Helvetica",9))
        style.configure("History.Treeview.Heading",
                        background=self.PANEL,
                        foreground=self.ACCENT,
                        font=("Helvetica",9,"bold"))
        style.map("History.Treeview", background=[("selected","#0984e3")])

        self.hist_tree = ttk.Treeview(frame, columns=cols,
                                       show="headings",
                                       style="History.Treeview")
        widths = [30,70,110,200,200,90,90,90,90]
        for col, w in zip(cols, widths):
            self.hist_tree.heading(col, text=col)
            self.hist_tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(frame, orient="vertical",
                             command=self.hist_tree.yview)
        self.hist_tree.configure(yscrollcommand=vsb.set)
        hsb = ttk.Scrollbar(frame, orient="horizontal",
                             command=self.hist_tree.xview)
        self.hist_tree.configure(xscrollcommand=hsb.set)

        self.hist_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

    # ── TAB 4: DASHBOARD ─────────────────────────

    def _build_dashboard_tab(self, parent):
        tk.Label(parent,
                 text="Live network performance metrics — updates automatically after every action.",
                 bg=self.BG, fg=self.MUTED,
                 font=("Helvetica",10)).pack(pady=(14,8))

        cards = tk.Frame(parent, bg=self.BG)
        cards.pack(fill="x", padx=20, pady=6)

        self.dash_vars = {}
        metrics = [
            ("Network Health",  "health",  self.GREEN,  "%"),
            ("Packet Loss",     "pktloss", self.ACCENT, "%"),
            ("Path Efficiency", "effic",   self.BLUE,   "%"),
            ("Active Nodes",    "active",  self.YELLOW, ""),
            ("Path Hops",       "hops",    self.PURPLE, ""),
            ("Path Distance",   "dist",    "#00cec9",   " units"),
        ]
        for label, key, color, unit in metrics:
            c = tk.Frame(cards, bg=self.CARD, width=180, height=90)
            c.pack(side="left", fill="y", padx=6, pady=4)
            c.pack_propagate(False)
            tk.Label(c, text=label, bg=self.CARD, fg=self.MUTED,
                     font=("Helvetica",8)).pack(pady=(12,2))
            v = tk.StringVar(value="—")
            self.dash_vars[key] = v
            tk.Label(c, textvariable=v, bg=self.CARD, fg=color,
                     font=("Helvetica",22,"bold")).pack()
            tk.Label(c, text=unit, bg=self.CARD, fg=self.MUTED,
                     font=("Helvetica",8)).pack()

        # Health over time bar chart
        self.dash_fig, self.dash_ax = plt.subplots(figsize=(10,3),
                                                     facecolor=self.BG)
        self.dash_ax.set_facecolor(self.BG)
        self.dash_fig.tight_layout(pad=1.5)
        self.dash_canvas = FigureCanvasTkAgg(self.dash_fig, master=parent)
        self.dash_canvas.get_tk_widget().configure(bg=self.BG)
        self.dash_canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(4,12))

        self.health_history = []
        self.health_labels  = []

    # ────────────────────────────────────────────
    #  DRAW
    # ────────────────────────────────────────────

    def _draw(self, packet_pos=None, packet_color="#fdcb6e"):
        self.ax.clear()
        self.ax.set_facecolor(self.BG)
        self.fig.patch.set_facecolor(self.BG)

        G    = self.G
        pos  = nx.get_node_attributes(G, 'pos')
        path = self.current_path

        # Edge styling
        path_edges = set()
        if path:
            for i in range(len(path)-1):
                path_edges.add((path[i], path[i+1]))
                path_edges.add((path[i+1], path[i]))

        normal_edges, failed_edges = [], []
        e_colors, e_widths = [], []

        for u, v in G.edges():
            is_failed = (u,v) in self.failed_links or (v,u) in self.failed_links
            if is_failed:
                failed_edges.append((u, v))
            else:
                normal_edges.append((u, v))
                load = self.congestion.get((u,v), self.congestion.get((v,u), 0.0))
                if (u,v) in path_edges:
                    # Active path: colour shifts green->yellow->red with congestion
                    if load > 0.7:
                        e_colors.append("#e74c3c")
                        e_widths.append(4.5)
                    elif load > 0.4:
                        e_colors.append("#f39c12")
                        e_widths.append(4.0)
                    else:
                        e_colors.append("#00b894")
                        e_widths.append(3.5)
                else:
                    # Off-path: grey, but tinted orange if congested
                    if load > 0.7:
                        e_colors.append("#c0392b")
                        e_widths.append(1.8)
                    elif load > 0.4:
                        e_colors.append("#e67e22")
                        e_widths.append(1.4)
                    else:
                        e_colors.append("#2d4a6b")
                        e_widths.append(0.8)

        if normal_edges:
            nx.draw_networkx_edges(G, pos, ax=self.ax,
                                   edgelist=normal_edges,
                                   edge_color=e_colors, width=e_widths, alpha=0.9)
        if failed_edges:
            nx.draw_networkx_edges(G, pos, ax=self.ax,
                                   edgelist=failed_edges,
                                   edge_color="#e74c3c", width=2.5,
                                   style="dashed", alpha=0.85)
            for u, v in failed_edges:
                mx = (pos[u][0] + pos[v][0]) / 2
                my = (pos[u][1] + pos[v][1]) / 2
                self.ax.plot(mx, my, 'x', color="#e74c3c",
                             markersize=10, markeredgewidth=2.5, zorder=8)

        # Congestion load labels on active path edges
        if self.congestion and path:
            for i in range(len(path)-1):
                u, v = path[i], path[i+1]
                load = self.congestion.get((u,v), self.congestion.get((v,u), 0.0))
                if load > 0:
                    mx = (pos[u][0] + pos[v][0]) / 2
                    my = (pos[u][1] + pos[v][1]) / 2 + 2
                    col = "#e74c3c" if load>0.7 else "#f39c12" if load>0.4 else "#2ecc71"
                    self.ax.text(mx, my, f"{int(load*100)}%",
                                 fontsize=7, color=col, ha='center', va='bottom',
                                 bbox=dict(boxstyle="round,pad=0.15",
                                           fc=self.BG, ec="none", alpha=0.7))

        # Node styling
        n_colors, n_sizes, n_borders = [], [], []
        for n in G.nodes():
            if G.nodes[n]['failed']:
                n_colors.append("#e17055"); n_sizes.append(950); n_borders.append("#c0392b")
            elif path and n == path[0]:
                n_colors.append("#00b894"); n_sizes.append(1000); n_borders.append("#55efc4")
            elif path and n == path[-1]:
                n_colors.append("#fdcb6e"); n_sizes.append(1000); n_borders.append("#f9ca24")
            elif path and n in path:
                n_colors.append("#00cec9"); n_sizes.append(850);  n_borders.append("#00b894")
            elif n in self.selected_nodes:
                n_colors.append("#a29bfe"); n_sizes.append(850);  n_borders.append("#6c5ce7")
            else:
                n_colors.append("#576574"); n_sizes.append(700);  n_borders.append("#808e9b")

        nx.draw_networkx_nodes(G, pos, ax=self.ax,
                               node_color=n_colors, node_size=n_sizes,
                               edgecolors=n_borders, linewidths=2)

        nx.draw_networkx_labels(G, pos, ax=self.ax,
                                font_color="white", font_size=9, font_weight="bold")

        # Path edge weight labels
        if path:
            elabels = {}
            for i in range(len(path)-1):
                u,v = path[i], path[i+1]
                if G.has_edge(u,v):
                    elabels[(u,v)] = f"{G[u][v]['weight']:.0f}"
            nx.draw_networkx_edge_labels(G, pos, elabels, ax=self.ax,
                                          font_color="#00b894", font_size=7,
                                          bbox=dict(boxstyle="round,pad=0.2",
                                                    fc=self.BG, ec="none", alpha=0.7))

        # Animated packet dot — colour reflects QoS priority
        if packet_pos is not None:
            px, py = packet_pos
            qos_color = packet_color
            if packet_color == "#fdcb6e":   # only override if not flashing
                qos = getattr(self, 'qos_mode', 'normal')
                qos_color = {"normal":"#fdcb6e","high":"#f39c12","emergency":"#e74c3c"}.get(qos,"#fdcb6e")
            label_map = {"normal":"PKT","high":"HI","emergency":"SOS"}
            qos_label = label_map.get(getattr(self,'qos_mode','normal'), "PKT")
            self.ax.plot(px, py, 'o', color=qos_color,
                         markersize=16, zorder=10,
                         markeredgecolor="white", markeredgewidth=2)
            self.ax.text(px, py, qos_label, fontsize=6, color="white",
                         ha='center', va='center', zorder=11, fontweight='bold')
            self.ax.plot(px, py, 'o', color=qos_color,
                         markersize=24, zorder=9,
                         markeredgecolor=qos_color,
                         markeredgewidth=1.5,
                         alpha=0.25, fillstyle='none')

        self.ax.axis("off")
        self.mpl_canvas.draw()
        self._update_stats()
        self._update_dashboard()

    def _draw_comparison(self, d_path, b_path):
        pos = nx.get_node_attributes(self.G, 'pos')

        for ax, path, color, title in [
            (self.ax_d, d_path, "#00b894", "Dijkstra — Weighted Shortest"),
            (self.ax_b, b_path, "#fdcb6e", "BFS — Fewest Hops"),
        ]:
            ax.clear()
            ax.set_facecolor(self.BG)

            path_edges = set()
            if path:
                for i in range(len(path)-1):
                    path_edges.add((path[i], path[i+1]))
                    path_edges.add((path[i+1], path[i]))

            e_col = ["#00b894" if (u,v) in path_edges else "#2d4a6b"
                     for u,v in self.G.edges()]
            e_wid = [3 if (u,v) in path_edges else 0.7
                     for u,v in self.G.edges()]

            nx.draw_networkx_edges(self.G, pos, ax=ax,
                                   edge_color=e_col, width=e_wid, alpha=0.9)

            n_col = []
            for n in self.G.nodes():
                if path and n == path[0]:   n_col.append("#00b894")
                elif path and n == path[-1]: n_col.append("#fdcb6e")
                elif path and n in path:    n_col.append(color)
                else:                        n_col.append("#576574")

            nx.draw_networkx_nodes(self.G, pos, ax=ax,
                                   node_color=n_col, node_size=600,
                                   edgecolors="#808e9b", linewidths=1.5)
            nx.draw_networkx_labels(self.G, pos, ax=ax,
                                    font_color="white", font_size=8, font_weight="bold")
            ax.set_title(title, color=color, fontsize=10, fontweight="bold", pad=6)
            ax.axis("off")

        self.cmp_canvas.draw()

    # ────────────────────────────────────────────
    #  STATS & DASHBOARD
    # ────────────────────────────────────────────

    def _update_stats(self):
        G = self.G
        failed_list = [n for n in G.nodes() if G.nodes[n]['failed']]
        path = self.current_path
        health = network_health(G, self.failed_links)
        pktloss = packet_loss_percent(G, path)
        effic   = path_efficiency(G, path)

        self.svars["nodes"].set(str(G.number_of_nodes()))
        self.svars["edges"].set(str(G.number_of_edges()))
        self.svars["active"].set(str(G.number_of_nodes() - len(failed_list)))
        self.svars["failed"].set(", ".join(map(str,failed_list)) if failed_list else "None")
        fl = list(self.failed_links)
        self.svars["failedlinks"].set(str(len(fl)) + " link(s)" if fl else "None")
        cong_count = sum(1 for v in self.congestion.values() if v > 0.4)
        self.svars["conglinks"].set(f"{cong_count} link(s)" if cong_count else "None")
        qos_labels = {"normal":"Normal 🟦","high":"High 🟨","emergency":"Emergency 🟥"}
        self.svars["qos"].set(qos_labels.get(self.qos_mode, "Normal"))
        self.svars["src"].set(f"Node {self.src}" if self.src is not None else "—")
        self.svars["dst"].set(f"Node {self.dst}" if self.dst is not None else "—")
        self.svars["health"].set(f"{health}%")
        self.svars["pktloss"].set(f"{pktloss}%")
        self.svars["effic"].set(f"{effic}%")

        if path:
            self.svars["hops"].set(f"{len(path)-1} hops / {len(path)} nodes")
            self.svars["dist"].set(f"{path_distance(G, path)} units")
            if any(G.nodes[n]['failed'] for n in path):
                self.svars["status"].set("⚠ PATH BROKEN")
            elif failed_list:
                self.svars["status"].set("✔ Rerouted OK")
            else:
                self.svars["status"].set("✔ Active")
        else:
            self.svars["hops"].set("—")
            self.svars["dist"].set("—")
            self.svars["status"].set("No path")

    def _update_dashboard(self):
        G    = self.G
        path = self.current_path
        failed_list = [n for n in G.nodes() if G.nodes[n]['failed']]
        health  = network_health(G)
        pktloss = packet_loss_percent(G, path)
        effic   = path_efficiency(G, path)

        self.dash_vars["health"].set(f"{health}")
        self.dash_vars["pktloss"].set(f"{pktloss}")
        self.dash_vars["effic"].set(f"{effic}")
        self.dash_vars["active"].set(str(G.number_of_nodes()-len(failed_list)))
        self.dash_vars["hops"].set(str(len(path)-1) if path else "—")
        self.dash_vars["dist"].set(str(path_distance(G,path)) if path else "—")

        # Health over time chart
        ts = datetime.now().strftime("%H:%M:%S")
        self.health_history.append(health)
        self.health_labels.append(ts)
        if len(self.health_history) > 20:
            self.health_history.pop(0)
            self.health_labels.pop(0)

        self.dash_ax.clear()
        self.dash_ax.set_facecolor(self.BG)
        self.dash_fig.patch.set_facecolor(self.BG)

        xs = range(len(self.health_history))
        bar_colors = ["#e17055" if h < 70 else "#fdcb6e" if h < 90 else "#00b894"
                      for h in self.health_history]
        self.dash_ax.bar(xs, self.health_history, color=bar_colors, width=0.6)
        self.dash_ax.set_ylim(0, 110)
        self.dash_ax.set_xticks(list(xs))
        self.dash_ax.set_xticklabels(self.health_labels,
                                      rotation=35, fontsize=6, color=self.MUTED)
        self.dash_ax.set_ylabel("Health %", color=self.MUTED, fontsize=8)
        self.dash_ax.set_title("Network Health Over Time",
                                color=self.TEXT, fontsize=10)
        self.dash_ax.tick_params(colors=self.MUTED, labelsize=7)
        self.dash_ax.spines[:].set_visible(False)
        self.dash_ax.axhline(100, color="#2d4a6b", linewidth=0.5, linestyle="--")
        self.dash_canvas.draw()

    # ────────────────────────────────────────────
    #  LOGGING
    # ────────────────────────────────────────────

    def _log(self, msg, tag="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.configure(state="normal")
        self.log.insert("end", f"[{ts}] ", "time")
        self.log.insert("end", msg+"\n", tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    def _status(self, msg):
        self.status_var.set(msg)

    # ────────────────────────────────────────────
    #  BUTTON ACTIONS
    # ────────────────────────────────────────────

    def _new_network(self):
        self._stop_animation()
        self._status("Building network...")
        self.update()
        self.G, self.src, self.dst = create_network(n=12, range_val=55)
        self.current_path, _ = get_path_dijkstra(self.G, self.src, self.dst, self.failed_links, self.congestion, self.qos_mode)
        self.original_path   = self.current_path[:]
        self.selected_nodes  = []
        self.multi_failed    = []
        self.failed_links    = set()
        self.congestion      = {}
        self.qos_mode        = "normal"
        self.reroute_history = []
        self.health_history  = []
        self.health_labels   = []
        self._draw()
        path_str = " → ".join(map(str, self.current_path))
        self._log(f"Network created — {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges", "success")
        self._log(f"SRC=Node {self.src}   DST=Node {self.dst}", "info")
        self._log(f"Initial path: {path_str}", "info")
        self._status(f"Network ready  |  {path_str}")

    def _show_path(self):
        self._stop_animation()
        if not self.current_path:
            self._log("No active path.", "error"); return
        self._draw()
        self._log(f"Path: {' → '.join(map(str,self.current_path))}", "success")
        self._status(f"Active path: {' → '.join(map(str,self.current_path))}")

    def _fail_node(self):
        self._stop_animation()
        if not self.current_path:
            self._log("No path to fail a node on.", "error"); return
        if any(self.G.nodes[n]['failed'] for n in self.current_path[1:-1]):
            self._log("Node already failed. Reroute first.", "warn"); return
        node = fail_node_on_path(self.G, self.current_path)
        if node is None:
            self._log("No intermediate nodes to fail.", "error"); return
        self._draw()
        self._log(f"Node {node} FAILED!", "error")
        self._log(f"Broken path: {' → '.join(map(str,self.current_path))}", "warn")
        self._log("Click Reroute to find alternate path.", "warn")
        self._status(f"⚠ Node {node} failed — click Reroute")

    def _fail_multiple(self):
        self._stop_animation()
        if not self.current_path or len(self.current_path) < 4:
            self._log("Need a path with at least 3 intermediate nodes.", "warn"); return
        failed = fail_multiple_nodes(self.G, self.current_path, count=2)
        if not failed:
            self._log("Not enough nodes to fail.", "warn"); return
        self.multi_failed = failed
        self._draw()
        self._log(f"Multiple nodes FAILED: {failed}", "error")
        self._log("Click Reroute to find alternate path.", "warn")
        self._status(f"⚠ Nodes {failed} failed — click Reroute")

    def _reroute(self):
        self._stop_animation()
        if not self.current_path:
            self._log("No path to reroute.", "error"); return
        path_has_failure = (
            any(self.G.nodes[n]['failed'] for n in self.current_path) or
            any((self.current_path[i], self.current_path[i+1]) in self.failed_links or
                (self.current_path[i+1], self.current_path[i]) in self.failed_links
                for i in range(len(self.current_path)-1))
        )
        if not path_has_failure:
            self._log("No failure on path. Fail a node or link first.", "warn"); return

        old_path = self.current_path[:]
        new_path, new_cost = get_path_dijkstra(self.G, self.src, self.dst, self.failed_links, self.congestion, self.qos_mode)

        failed_nodes = [n for n in old_path if self.G.nodes[n]['failed']]
        failed_links_on_path = [(u,v) for u,v in zip(old_path,old_path[1:])
                                if (u,v) in self.failed_links or (v,u) in self.failed_links]
        if failed_links_on_path:
            failed_nodes += [f"link {u}↔{v}" for u,v in failed_links_on_path]

        if new_path:
            self.current_path = new_path
            self._draw()
            self._log("REROUTING...", "warn")
            self._log(f"Old: {' → '.join(map(str,old_path))}", "warn")
            self._log(f"New: {' → '.join(map(str,new_path))}", "success")
            self._status(f"✔ Rerouted → {' → '.join(map(str,new_path))}")

            # Record in history
            self._add_history(old_path, new_path, failed_nodes)
        else:
            self._log("No alternate path! Network partitioned.", "error")
            self._status("✘ No alternate path available!")

    def _fix_nodes(self):
        self._stop_animation()
        fix_all_nodes(self.G)
        self._draw()
        self._log("All failed nodes fixed — back online.", "success")
        self._log(f"Original path was : {' → '.join(map(str,self.original_path))}", "info")
        self._log(f"Still using       : {' → '.join(map(str,self.current_path))}", "success")
        self._log("Stays on rerouted path — NOT reverted.", "warn")
        self._status(f"Node(s) fixed — still using: {' → '.join(map(str,self.current_path))}")

    # ────────────────────────────────────────────
    #  PACKET ANIMATION  (failure-aware + auto-reroute)
    # ────────────────────────────────────────────

    def _fail_link(self):
        """Fail a random link (edge) on the current path."""
        self._stop_animation()
        if not self.current_path or len(self.current_path) < 2:
            self._log("No path to fail a link on.", "error"); return

        # Candidate edges: edges on path that are not already failed
        candidates = []
        for i in range(len(self.current_path) - 1):
            u, v = self.current_path[i], self.current_path[i+1]
            if (u,v) not in self.failed_links and (v,u) not in self.failed_links:
                candidates.append((u, v))

        if not candidates:
            self._log("All links on path already failed.", "warn"); return

        u, v = random.choice(candidates)
        self.failed_links.add((u, v))
        self._draw()
        self._log(f"Link {u} ↔ {v} has FAILED (shown as red dashed line with ✖)", "error")
        self._log("Click Reroute to find alternate path.", "warn")
        self._status(f"⚠ Link {u}↔{v} broken — click Reroute")

    def _fail_multiple_links(self):
        """Fail 2 random links on the current path."""
        self._stop_animation()
        if not self.current_path or len(self.current_path) < 3:
            self._log("Need a longer path to fail multiple links.", "warn"); return

        candidates = []
        for i in range(len(self.current_path) - 1):
            u, v = self.current_path[i], self.current_path[i+1]
            if (u,v) not in self.failed_links and (v,u) not in self.failed_links:
                candidates.append((u, v))

        if len(candidates) < 2:
            self._log("Not enough active links on path to fail multiple.", "warn"); return

        chosen = random.sample(candidates, min(2, len(candidates)))
        for u, v in chosen:
            self.failed_links.add((u, v))

        self._draw()
        failed_str = "  &  ".join([f"{u}↔{v}" for u,v in chosen])
        self._log(f"Multiple links FAILED: {failed_str}", "error")
        self._log("Click Reroute (Link) to find alternate path.", "warn")
        self._status(f"⚠ Links {failed_str} broken — click Reroute (Link)")

    def _fix_links(self):
        """Restore all failed links."""
        self._stop_animation()
        count = len(self.failed_links)
        self.failed_links = set()
        self._draw()
        self._log(f"All {count} failed link(s) restored.", "success")
        self._log(f"Still using rerouted path: {' → '.join(map(str,self.current_path))}", "warn")
        self._status(f"Links restored — still on rerouted path")

    def _save_network(self):
        """Save full network state to a JSON file."""
        if not self.G:
            self._log("No network to save.", "error"); return

        path = filedialog.asksaveasfilename(
            title="Save Network",
            defaultextension=".json",
            filetypes=[("JSON files","*.json"), ("All files","*.*")],
            initialfile="mesh_network.json"
        )
        if not path:
            return

        # Build serialisable state
        nodes = []
        for n, data in self.G.nodes(data=True):
            nodes.append({
                "id":     n,
                "pos":    list(data["pos"]),
                "failed": data["failed"]
            })

        edges = []
        for u, v, data in self.G.edges(data=True):
            edges.append({
                "u":      u,
                "v":      v,
                "weight": data["weight"]
            })

        state = {
            "nodes":         nodes,
            "edges":         edges,
            "src":           self.src,
            "dst":           self.dst,
            "current_path":  self.current_path,
            "original_path": self.original_path,
            "failed_links":  [list(lk) for lk in self.failed_links],
            "congestion":    {f"{u},{v}": load
                              for (u,v), load in self.congestion.items()},
            "qos_mode":      self.qos_mode,
            "reroute_history": [
                {
                    "old_path":    old,
                    "new_path":    new,
                    "failed_nodes": [str(x) for x in fn]
                }
                for old, new, fn in self.reroute_history
            ],
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        with open(path, "w") as f:
            json.dump(state, f, indent=2)

        self._log(f"Network saved → {path.split('/')[-1]}", "success")
        self._log(f"  Nodes: {len(nodes)}  Edges: {len(edges)}  "
                  f"Failed nodes: {sum(1 for n in nodes if n['failed'])}  "
                  f"Failed links: {len(self.failed_links)}", "info")
        self._status(f"✔ Saved: {path.split('/')[-1]}")

    def _load_network(self):
        """Load network state from a JSON file."""
        path = filedialog.askopenfilename(
            title="Load Network",
            filetypes=[("JSON files","*.json"), ("All files","*.*")]
        )
        if not path:
            return

        try:
            with open(path, "r") as f:
                state = json.load(f)

            # Rebuild graph
            self._stop_animation()
            G = nx.Graph()

            for n in state["nodes"]:
                G.add_node(n["id"],
                           pos=tuple(n["pos"]),
                           failed=n["failed"])

            for e in state["edges"]:
                G.add_edge(e["u"], e["v"], weight=e["weight"])

            self.G            = G
            self.src          = state["src"]
            self.dst          = state["dst"]
            self.current_path = state["current_path"]
            self.original_path= state.get("original_path", state["current_path"])
            self.failed_links = set(tuple(lk) for lk in state.get("failed_links", []))
            self.qos_mode     = state.get("qos_mode", "normal")
            self.qos_var.set(self.qos_mode)
            self.selected_nodes = []
            self.multi_failed   = []

            # Restore congestion
            self.congestion = {}
            for key, load in state.get("congestion", {}).items():
                u, v = map(int, key.split(","))
                self.congestion[(u, v)] = load

            # Restore reroute history table
            self.reroute_history = []
            for item in state.get("reroute_history", []):
                self._add_history(
                    item["old_path"],
                    item["new_path"],
                    item["failed_nodes"]
                )

            self._draw()
            saved_at = state.get("saved_at", "unknown")
            self._log(f"Network loaded ← {path.split('/')[-1]}", "success")
            self._log(f"  Saved at: {saved_at}", "info")
            self._log(f"  SRC=Node {self.src}  DST=Node {self.dst}", "info")
            self._log(f"  Path: {' → '.join(map(str, self.current_path))}", "info")
            failed_nodes = [n["id"] for n in state["nodes"] if n["failed"]]
            if failed_nodes:
                self._log(f"  Failed nodes: {failed_nodes}", "warn")
            if self.failed_links:
                self._log(f"  Failed links: {list(self.failed_links)}", "warn")
            self._status(f"✔ Loaded: {path.split('/')[-1]}  |  "
                         f"Path: {' → '.join(map(str, self.current_path))}")

        except Exception as e:
            self._log(f"Failed to load: {e}", "error")
            err_msg = f"Could not load network file.\n\nError: {e}"
            messagebox.showerror("Load Error", err_msg)

    def _reroute_link(self):
        """Find alternate path avoiding the failed link — immediately, no waiting."""
        self._stop_animation()
        if not self.current_path:
            self._log("No path to reroute.", "error"); return

        link_failed_on_path = any(
            (self.current_path[i], self.current_path[i+1]) in self.failed_links or
            (self.current_path[i+1], self.current_path[i]) in self.failed_links
            for i in range(len(self.current_path)-1)
        )
        if not link_failed_on_path:
            self._log("No failed link on current path. Fail a link first.", "warn"); return

        old_path = self.current_path[:]
        new_path, new_cost = get_path_dijkstra(
            self.G, self.src, self.dst,
            self.failed_links, self.congestion, self.qos_mode
        )
        if new_path:
            self.current_path = new_path
            self._draw()
            failed_lk = [(self.current_path[i],self.current_path[i+1])
                         for i in range(len(old_path)-1)
                         if (old_path[i],old_path[i+1]) in self.failed_links
                         or (old_path[i+1],old_path[i]) in self.failed_links]
            self._log("LINK REROUTE triggered.", "warn")
            self._log(f"Old path : {' → '.join(map(str,old_path))}", "warn")
            self._log(f"New path : {' → '.join(map(str,new_path))}", "success")
            self._log(f"Avoided failed link(s) — path distance: {new_cost} units", "info")
            self._status(f"✔ Link Rerouted → {' → '.join(map(str,new_path))}")
            self._add_history(old_path, new_path,
                              [f"link {u}↔{v}" for u,v in self.failed_links])
        else:
            self._log("No alternate path around failed link! Network partitioned.", "error")
            self._status("✘ No alternate path — link failure isolates route!")

    def _simulate_congestion(self):
        """Randomly assign congestion loads to edges — higher on active path for demo."""
        self._stop_animation()
        if not self.G:
            return
        self.congestion = {}
        path_edges = set()
        if self.current_path:
            for i in range(len(self.current_path)-1):
                path_edges.add((self.current_path[i], self.current_path[i+1]))

        for u, v in self.G.edges():
            if (u,v) in self.failed_links or (v,u) in self.failed_links:
                continue
            if (u,v) in path_edges or (v,u) in path_edges:
                # Path edges get higher congestion for visible demo
                load = round(random.uniform(0.3, 0.95), 2)
            else:
                load = round(random.uniform(0.0, 0.6), 2)
            self.congestion[(u,v)] = load

        congested = sum(1 for v in self.congestion.values() if v > 0.4)
        heavily    = sum(1 for v in self.congestion.values() if v > 0.7)

        # QoS-aware reroute: if priority is high/emergency, auto-reroute away from congestion
        old_path = self.current_path[:] if self.current_path else []
        new_path, new_cost = get_path_dijkstra(
            self.G, self.src, self.dst,
            self.failed_links, self.congestion, self.qos_mode
        )
        if new_path and new_path != old_path:
            self.current_path = new_path
            self._log(f"Congestion applied — {congested} congested, {heavily} heavily congested links.", "warn")
            if self.qos_mode in ("high","emergency"):
                self._log(f"QoS [{self.qos_mode.upper()}] auto-rerouted away from congestion.", "success")
                self._log(f"New path: {' → '.join(map(str,new_path))} ({new_cost} units)", "success")
                self._add_history(old_path, new_path, ["congestion"])
            self._status(f"⚠ Congestion active — {heavily} links overloaded")
        else:
            self._log(f"Congestion applied — {congested} links congested.", "warn")
            if self.qos_mode in ("high","emergency"):
                self._log(f"QoS [{self.qos_mode.upper()}] — current path is still best.", "info")
            self._status(f"⚠ Congestion active on network")

        self._draw()

    def _clear_congestion(self):
        """Remove all congestion."""
        self._stop_animation()
        self.congestion = {}
        self._draw()
        self._log("Congestion cleared — all links back to normal load.", "success")
        self._status("Congestion cleared")

    def _on_qos_change(self):
        """Called when QoS radio button changes."""
        self.qos_mode = self.qos_var.get()
        labels = {"normal":"Normal — best path by distance",
                  "high":"High Priority — avoids congested links (>80%)",
                  "emergency":"Emergency — avoids all congestion (>50%), shortest route"}
        self._log(f"QoS set to: {self.qos_mode.upper()}", "info")
        self._log(labels.get(self.qos_mode,""), "info")
        # Re-route with new QoS if congestion is active
        if self.congestion and self.current_path:
            old = self.current_path[:]
            new_path, cost = get_path_dijkstra(
                self.G, self.src, self.dst,
                self.failed_links, self.congestion, self.qos_mode
            )
            if new_path and new_path != old:
                self.current_path = new_path
                self._log(f"QoS reroute → {' → '.join(map(str,new_path))}", "success")
                self._add_history(old, new_path, [f"QoS-{self.qos_mode}"])
        self._draw()
        self._status(f"QoS: {self.qos_mode.upper()}")

    def _animate_packet(self):
        if not self.current_path or len(self.current_path) < 2:
            self._log("No path to animate.", "warn"); return

        self._stop_animation()
        self.anim_step      = 0
        self.anim_path      = self.current_path[:]   # snapshot path at start
        self.anim_flashing  = False
        self.anim_flash_ct  = 0
        self.anim_stuck_pos = None

        self._log(f"Packet sending: {' → '.join(map(str, self.anim_path))}", "info")
        self._status("▶ Packet in transit...")
        self._packet_step()

    def _packet_step(self):
        # ── Flashing phase: packet blinks red at failed node ──
        if self.anim_flashing:
            self.anim_flash_ct += 1
            color = "#e17055" if self.anim_flash_ct % 2 == 0 else "#fdcb6e"
            self._draw(packet_pos=self.anim_stuck_pos, packet_color=color)
            if self.anim_flash_ct >= 8:          # flash 4 times then reroute
                self.anim_flashing = False
                self._do_anim_reroute()
            else:
                self.packet_anim_id = self.after(120, self._packet_step)
            return

        path = self.anim_path
        if not path:
            return

        total_steps = (len(path) - 1) * 10
        if self.anim_step > total_steps:
            self._draw(packet_pos=None)
            self._log("✔ Packet delivered to destination!", "success")
            self._status(f"✔ Packet delivered to Node {self.dst}")
            return

        seg = self.anim_step // 10
        t   = (self.anim_step % 10) / 10.0

        if seg >= len(path) - 1:
            self._draw(packet_pos=None)
            return

        # ── Check congestion: slow down packet on congested edges ──
        next_node = path[seg + 1]
        load = self.congestion.get((path[seg], next_node),
               self.congestion.get((next_node, path[seg]), 0.0))
        # Emergency packets ignore congestion delay; normal packets slow down
        delay = 60
        if load > 0.7 and self.qos_mode == "normal":
            delay = 180    # heavy congestion slows normal packets 3x
        elif load > 0.4 and self.qos_mode == "normal":
            delay = 110    # moderate congestion slows 2x
        elif self.qos_mode == "emergency":
            delay = 35     # emergency packets move faster

        # ── Check if the LINK to next node has failed ──
        link_failed = ((path[seg], next_node) in self.failed_links or
                       (next_node, path[seg]) in self.failed_links)
        if link_failed:
            pos = nx.get_node_attributes(self.G, 'pos')
            x1, y1 = pos[path[seg]]
            x2, y2 = pos[next_node]
            stuck_x = x1 + (x2 - x1) * 0.5
            stuck_y = y1 + (y2 - y1) * 0.5
            self.anim_stuck_pos  = (stuck_x, stuck_y)
            self.anim_flashing   = True
            self.anim_flash_ct   = 0
            self._log(f"⚠ Packet blocked! Link {path[seg]}↔{next_node} has failed.", "error")
            self._status(f"⚠ Link {path[seg]}↔{next_node} broken — rerouting...")
            self.packet_anim_id = self.after(120, self._packet_step)
            return

        # ── Check if the NEXT NODE has failed ──
        if self.G.nodes[next_node]['failed']:
            # Packet reaches the edge just before the failed node and stops
            pos = nx.get_node_attributes(self.G, 'pos')
            x1, y1 = pos[path[seg]]
            x2, y2 = pos[next_node]
            # Stop packet at 85% along the edge — just before failed node
            stuck_x = x1 + (x2 - x1) * 0.85
            stuck_y = y1 + (y2 - y1) * 0.85
            self.anim_stuck_pos  = (stuck_x, stuck_y)
            self.anim_flashing   = True
            self.anim_flash_ct   = 0
            self._log(f"⚠ Packet blocked! Node {next_node} has failed.", "error")
            self._status(f"⚠ Packet blocked at Node {next_node} — rerouting...")
            self.packet_anim_id = self.after(120, self._packet_step)
            return

        # ── Also check current node ──
        cur_node = path[seg]
        if self.G.nodes[cur_node]['failed'] and cur_node not in (path[0], path[-1]):
            pos = nx.get_node_attributes(self.G, 'pos')
            self.anim_stuck_pos  = pos[cur_node]
            self.anim_flashing   = True
            self.anim_flash_ct   = 0
            self._log(f"⚠ Packet blocked! Node {cur_node} has failed.", "error")
            self.packet_anim_id = self.after(120, self._packet_step)
            return

        # ── Normal movement ──
        pos = nx.get_node_attributes(self.G, 'pos')
        x1, y1 = pos[path[seg]]
        x2, y2 = pos[path[seg + 1]]
        px = x1 + (x2 - x1) * t
        py = y1 + (y2 - y1) * t

        self._draw(packet_pos=(px, py))
        self.anim_step += 1
        self.packet_anim_id = self.after(delay, self._packet_step)

    def _do_anim_reroute(self):
        """Auto-reroute during animation — find new path and continue packet."""
        old_path = self.anim_path[:]

        # Find which segment the packet is currently on
        seg = self.anim_step // 10
        seg = min(seg, len(old_path) - 2)

        # Packet is currently at old_path[seg], reroute from there
        current_node = old_path[seg]
        new_path, _  = get_path_dijkstra(self.G, current_node, self.dst, self.failed_links, self.congestion, self.qos_mode)

        if new_path and len(new_path) >= 2:
            # Update global path too so the canvas shows the rerouted route
            self.current_path = new_path
            self._add_history(old_path, new_path,
                              [n for n in old_path if self.G.nodes[n]['failed']])
            self.anim_path = new_path
            self.anim_step = 0    # restart animation from new path beginning
            self._log(f"[REROUTE] New path: {' → '.join(map(str, new_path))}", "success")
            self._status(f"✔ Rerouted → {' → '.join(map(str, new_path))}")
            self.packet_anim_id = self.after(200, self._packet_step)
        else:
            self._draw(packet_pos=None)
            self._log("✘ No alternate path — packet dropped!", "error")
            self._status("✘ Packet dropped — network partitioned!")

    def _stop_animation(self):
        if self.packet_anim_id:
            self.after_cancel(self.packet_anim_id)
            self.packet_anim_id = None
        self.anim_flashing  = False
        self.anim_flash_ct  = 0
        self.anim_stuck_pos = None

    # ────────────────────────────────────────────
    #  ALGORITHM COMPARISON
    # ────────────────────────────────────────────

    def _run_comparison(self):
        if not self.G or self.src is None:
            messagebox.showinfo("Info", "Generate a network first."); return

        import time

        t0 = time.perf_counter()
        d_path, d_cost = get_path_dijkstra(self.G, self.src, self.dst, self.failed_links, self.congestion, self.qos_mode)
        d_time = round((time.perf_counter() - t0) * 1e6, 2)

        t0 = time.perf_counter()
        b_path, b_cost = get_path_bfs(self.G, self.src, self.dst)
        b_time = round((time.perf_counter() - t0) * 1e6, 2)

        d_str = " → ".join(map(str, d_path)) if d_path else "No path"
        b_str = " → ".join(map(str, b_path)) if b_path else "No path"

        self.dijk_vars["Path"].set(d_str)
        self.dijk_vars["Hops"].set(f"{len(d_path)-1}" if d_path else "—")
        self.dijk_vars["Distance"].set(f"{d_cost} units" if d_cost else "—")
        self.dijk_vars["Time (µs)"].set(f"{d_time} µs")

        self.bfs_vars["Path"].set(b_str)
        self.bfs_vars["Hops"].set(f"{len(b_path)-1}" if b_path else "—")
        self.bfs_vars["Distance"].set(f"{b_cost} units" if b_cost else "—")
        self.bfs_vars["Time (µs)"].set(f"{b_time} µs")

        # Verdict
        if d_path and b_path:
            same = d_path == b_path
            if same:
                verdict = "Both algorithms found the SAME path. In this topology, the fewest-hop route is also the shortest-distance route."
            elif d_cost < b_cost:
                saved = round(b_cost - d_cost, 2)
                verdict = (f"Dijkstra found a SHORTER path by {saved} distance units. "
                           f"BFS used fewer hops ({len(b_path)-1}) but longer total distance ({b_cost}). "
                           f"Dijkstra is better when link weights (distances) matter.")
            else:
                verdict = (f"BFS found fewer hops but Dijkstra's path is more optimal by weight. "
                           f"In mesh networks, Dijkstra is preferred as link quality/distance matters.")
        else:
            verdict = "One or both algorithms could not find a path."

        self.verdict_var.set(verdict)
        self._draw_comparison(d_path, b_path)
        self._log("Algorithm comparison completed.", "info")

    # ────────────────────────────────────────────
    #  REROUTE HISTORY
    # ────────────────────────────────────────────

    def _add_history(self, old_path, new_path, failed_nodes):
        idx = len(self.reroute_history) + 1
        ts  = datetime.now().strftime("%H:%M:%S")
        old_dist = path_distance(self.G, old_path)
        new_dist = path_distance(self.G, new_path)
        self.reroute_history.append((old_path, new_path, failed_nodes))
        self.hist_tree.insert("", "end", values=(
            idx, ts,
            ", ".join(map(str, failed_nodes)),
            " → ".join(map(str, old_path)),
            " → ".join(map(str, new_path)),
            len(old_path)-1,
            len(new_path)-1,
            old_dist,
            new_dist,
        ))

    def _clear_history(self):
        for row in self.hist_tree.get_children():
            self.hist_tree.delete(row)
        self.reroute_history = []
        self._log("Reroute history cleared.", "info")

    # ────────────────────────────────────────────
    #  CLICK-TO-SELECT SRC / DST
    # ────────────────────────────────────────────

    def _on_click(self, event):
        if event.inaxes is None: return
        pos = nx.get_node_attributes(self.G, 'pos')
        nearest, min_d = None, float('inf')
        for n,(x,y) in pos.items():
            d = math.sqrt((x-event.xdata)**2+(y-event.ydata)**2)
            if d < min_d:
                min_d = d; nearest = n
        if min_d > 8: return

        self.selected_nodes.append(nearest)
        if len(self.selected_nodes) == 1:
            self._log(f"SRC = Node {nearest}. Click destination.", "info")
            self._status(f"Node {nearest} selected as SOURCE")
            self._draw()
        elif len(self.selected_nodes) == 2:
            s, d = self.selected_nodes
            self.selected_nodes = []
            if s == d:
                self._log("Same node. Pick again.", "warn")
                self._draw(); return
            path, _ = get_path_dijkstra(self.G, s, d)
            if not path or len(path) < 4:
                self._log(f"Path too short. Pick farther nodes.", "warn")
                self._draw(); return
            self.src, self.dst = s, d
            self.current_path  = path
            self.original_path = path[:]
            self._draw()
            self._log(f"SRC=Node {s}  DST=Node {d}", "info")
            self._log(f"Path: {' → '.join(map(str,path))}", "success")
            self._status(f"Path: {' → '.join(map(str,path))}")


# ══════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = MeshNetworkApp()
    app.mainloop()
