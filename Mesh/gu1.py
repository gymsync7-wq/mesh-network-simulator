import tkinter as tk
from tkinter import ttk, messagebox
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

def get_path_dijkstra(G, src, dst):
    G2 = G.copy()
    for n in list(G2.nodes()):
        if G2.nodes[n]['failed']:
            G2.remove_node(n)
    try:
        path = nx.dijkstra_path(G2, src, dst)
        cost = nx.dijkstra_path_length(G2, src, dst, weight='weight')
        return path, round(cost, 2)
    except:
        return None, None

def get_path_bfs(G, src, dst):
    G2 = G.copy()
    for n in list(G2.nodes()):
        if G2.nodes[n]['failed']:
            G2.remove_node(n)
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

def network_health(G):
    total = G.number_of_nodes()
    failed = sum(1 for n in G.nodes() if G.nodes[n]['failed'])
    if total == 0:
        return 0
    return round(((total - failed) / total) * 100, 1)

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
        self.geometry("1340x780")
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

    # ── TAB 1: SIMULATOR ──────────────────────────

    def _build_sim_tab(self, parent):
        body = tk.Frame(parent, bg=self.BG)
        body.pack(fill="both", expand=True, padx=8, pady=6)

        # Left control panel
        left = tk.Frame(body, bg=self.PANEL, width=270)
        left.pack(side="left", fill="y", padx=(0,8))
        left.pack_propagate(False)
        self._build_controls(left)

        # Right canvas
        right = tk.Frame(body, bg=self.BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_canvas(right)

    def _build_controls(self, parent):
        def section(text):
            tk.Frame(parent, bg=self.MUTED, height=1).pack(fill="x", padx=12, pady=8)
            tk.Label(parent, text=text, bg=self.PANEL, fg=self.ACCENT,
                     font=("Helvetica",9,"bold")).pack(anchor="w", padx=14, pady=(0,4))

        tk.Label(parent, text="CONTROLS", bg=self.PANEL, fg=self.ACCENT,
                 font=("Helvetica",9,"bold")).pack(anchor="w", padx=14, pady=(16,4))

        btns = [
            ("🔄  New Network",           self.BLUE,   self._new_network),
            ("📡  Show Current Path",      self.GREEN,  self._show_path),
            ("💥  Fail Node on Path",      self.ACCENT, self._fail_node),
            ("💣  Fail Multiple Nodes",    "#c0392b",   self._fail_multiple),
            ("🔀  Reroute",                self.PURPLE, self._reroute),
            ("🔧  Fix All Failed Nodes",   "#e67e22",   self._fix_nodes),
            ("▶  Animate Packet",          "#00cec9",   self._animate_packet),
        ]
        for label, color, cmd in btns:
            tk.Button(parent, text=label, bg=color, fg="white",
                      font=("Helvetica",10,"bold"), relief="flat",
                      cursor="hand2", activebackground=color,
                      activeforeground="white", command=cmd
                      ).pack(fill="x", padx=14, pady=3, ipady=7)

        section("NETWORK STATS")
        self.svars = {}
        rows = [
            ("Total Nodes",   "nodes"),
            ("Total Edges",   "edges"),
            ("Active Nodes",  "active"),
            ("Failed Nodes",  "failed"),
            ("Source",        "src"),
            ("Destination",   "dst"),
            ("Path Hops",     "hops"),
            ("Path Distance", "dist"),
            ("Network Health","health"),
            ("Packet Loss",   "pktloss"),
            ("Path Efficiency","effic"),
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
                 ("● Failed","#e17055"),("━ Active Path","#00b894")]
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

        e_colors, e_widths = [], []
        for u,v in G.edges():
            if (u,v) in path_edges:
                e_colors.append("#00b894")
                e_widths.append(3.5)
            else:
                e_colors.append("#2d4a6b")
                e_widths.append(0.8)

        nx.draw_networkx_edges(G, pos, ax=self.ax,
                               edge_color=e_colors, width=e_widths, alpha=0.9)

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

        # Animated packet dot
        if packet_pos is not None:
            px, py = packet_pos
            self.ax.plot(px, py, 'o', color=packet_color,
                         markersize=14, zorder=10,
                         markeredgecolor="white", markeredgewidth=2)
            # Ripple ring around packet
            self.ax.plot(px, py, 'o', color=packet_color,
                         markersize=22, zorder=9,
                         markeredgecolor=packet_color,
                         markeredgewidth=1.5,
                         alpha=0.3, fillstyle='none')

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
        health = network_health(G)
        pktloss = packet_loss_percent(G, path)
        effic   = path_efficiency(G, path)

        self.svars["nodes"].set(str(G.number_of_nodes()))
        self.svars["edges"].set(str(G.number_of_edges()))
        self.svars["active"].set(str(G.number_of_nodes() - len(failed_list)))
        self.svars["failed"].set(", ".join(map(str,failed_list)) if failed_list else "None")
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
        self.current_path, _ = get_path_dijkstra(self.G, self.src, self.dst)
        self.original_path   = self.current_path[:]
        self.selected_nodes  = []
        self.multi_failed    = []
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
        if not any(self.G.nodes[n]['failed'] for n in self.current_path):
            self._log("No failure on path. Fail a node first.", "warn"); return

        old_path = self.current_path[:]
        new_path, new_cost = get_path_dijkstra(self.G, self.src, self.dst)

        failed_nodes = [n for n in old_path if self.G.nodes[n]['failed']]

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

        # ── Check if the NEXT node in path has failed ──
        next_node = path[seg + 1]
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
        self.packet_anim_id = self.after(60, self._packet_step)

    def _do_anim_reroute(self):
        """Auto-reroute during animation — find new path and continue packet."""
        old_path = self.anim_path[:]

        # Find which segment the packet is currently on
        seg = self.anim_step // 10
        seg = min(seg, len(old_path) - 2)

        # Packet is currently at old_path[seg], reroute from there
        current_node = old_path[seg]
        new_path, _  = get_path_dijkstra(self.G, current_node, self.dst)

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
        d_path, d_cost = get_path_dijkstra(self.G, self.src, self.dst)
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
