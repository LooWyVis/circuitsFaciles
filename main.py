from tkinter import *
from tkinter import filedialog, messagebox, simpledialog, ttk
from itertools import product
from collections import deque
import math

import portes
import saveAndLoad


PIN_R = 6
GATE_W, GATE_H = 90, 60

COLOR_UNDEF = "#888888"
COLOR_0 = "#000000"
COLOR_1 = "#cc0000"

INVERT_R = 6
INVERT_OFFSET = 14


def bool_to_color(v):
    return COLOR_1 if v else COLOR_0 if v is not None else COLOR_UNDEF


class Pin:
    __slots__ = ('owner', 'kind', 'index', 'x', 'y', 'value', 'canvas_id', 'label_id')
    
    def __init__(self, owner, kind: str, index: int, x: int, y: int):
        self.owner = owner
        self.kind = kind
        self.index = index
        self.x = x
        self.y = y
        self.value = None
        self.canvas_id = None
        self.label_id = None

    def hit_test(self, mx, my):
        dx, dy = mx - self.x, my - self.y
        return dx * dx + dy * dy <= (PIN_R + 3) ** 2


class Wire:
    __slots__ = ('src', 'dst', 'value', 'canvas_id')
    
    def __init__(self, src_pin: Pin, dst_pin: Pin):
        self.src = src_pin
        self.dst = dst_pin
        self.value = None
        self.canvas_id = None

    def as_dict(self):
        return {
            "src_gate": self.src.owner.gid,
            "src_pin": self.src.index,
            "dst_gate": self.dst.owner.gid,
            "dst_pin": self.dst.index,
        }


class Gate:
    __slots__ = ('gid', 'gtype', 'x', 'y', 'name', 'inputs', 'outputs', 'value',
                 'rect_id', 'text_id', 'led_id', 'value_text_id', 'invert_id')
    
    # Configuration statique des pins par type
    PIN_CONFIGS = {
        'SRC': {'in': 0, 'out': 1},
        'OUT': {'in': 1, 'out': 0},
        'NOT': {'in': 1, 'out': 1, 'invert': True},
        'NOR': {'in': 2, 'out': 1, 'invert': True},
        'AND': {'in': 2, 'out': 1},
        'OR': {'in': 2, 'out': 1},
        'XOR': {'in': 2, 'out': 1},
    }
    
    # Fonctions de calcul par type
    COMPUTE_FUNCS = {
        'NOT': lambda ins: portes.non(ins[0]),
        'AND': lambda ins: portes.et(ins[0], ins[1]),
        'OR': lambda ins: portes.ou(ins[0], ins[1]),
        'XOR': lambda ins: portes.xor(ins[0], ins[1]),
        'NOR': lambda ins: portes.nor(ins[0], ins[1]),
    }
    
    # Titres des gates
    TITLES = {
        'NOT': '1',
        'AND': '&',
        'OR': '≥1',
        'XOR': '=1',
        'NOR': '≥1',
        'OUT': 'S',
    }

    def __init__(self, gid: int, gtype: str, x: int, y: int, name: str | None = None):
        self.gid = gid
        self.gtype = gtype
        self.x = x
        self.y = y
        self.name = name
        self.inputs = []
        self.outputs = []
        self.value = False if gtype == "SRC" else None
        
        # Canvas IDs
        self.rect_id = None
        self.text_id = None
        self.led_id = None
        self.value_text_id = None
        self.invert_id = None
        
        self._build_pins()

    def _build_pins(self):
        config = self.PIN_CONFIGS.get(self.gtype, {'in': 2, 'out': 1})
        n_in = config['in']
        n_out = config['out']
        
        # Créer les inputs
        if n_in == 1:
            self.inputs = [Pin(self, "in", 0, self.x, self.y + GATE_H // 2)]
        elif n_in == 2:
            self.inputs = [
                Pin(self, "in", 0, self.x, self.y + GATE_H // 3),
                Pin(self, "in", 1, self.x, self.y + 2 * GATE_H // 3)
            ]
        
        # Créer les outputs
        if n_out == 1:
            offset = INVERT_OFFSET if config.get('invert') else 0
            self.outputs = [Pin(self, "out", 0, self.x + GATE_W + offset, self.y + GATE_H // 2)]

    def update_pin_positions(self):
        config = self.PIN_CONFIGS.get(self.gtype, {'in': 2, 'out': 1})
        
        # Update inputs
        if len(self.inputs) == 1:
            self.inputs[0].x = self.x
            self.inputs[0].y = self.y + GATE_H // 2
        elif len(self.inputs) == 2:
            self.inputs[0].x = self.x
            self.inputs[0].y = self.y + GATE_H // 3
            self.inputs[1].x = self.x
            self.inputs[1].y = self.y + 2 * GATE_H // 3
        
        # Update outputs
        if self.outputs:
            offset = INVERT_OFFSET if config.get('invert') else 0
            self.outputs[0].x = self.x + GATE_W + offset
            self.outputs[0].y = self.y + GATE_H // 2

    def compute(self):
        if self.gtype == "SRC":
            return self.value
        if self.gtype == "OUT":
            return None
        
        ins = [p.value for p in self.inputs]
        if None in ins:
            return None
        
        compute_func = self.COMPUTE_FUNCS.get(self.gtype)
        return compute_func(ins) if compute_func else None

    def title(self):
        if self.gtype == "SRC":
            return f"Entrée {self.name}" if self.name else "Entrée"
        return self.TITLES.get(self.gtype, self.gtype)

    def as_dict(self):
        return {
            "gid": self.gid,
            "type": self.gtype,
            "x": self.x,
            "y": self.y,
            "value": self.value if self.gtype == "SRC" else None,
            "name": self.name if self.gtype == "SRC" else None,
        }


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Circuits logiques (NSI)")

        # Frames
        self.left = Frame(root, width=180, padx=8, pady=8)
        self.left.pack(side=LEFT, fill=Y)
        self.left.pack_propagate(False)

        self.canvas = Canvas(root, bg="white")
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)

        # État
        self.mode = StringVar(value="select")
        self.pending_wire_src = None
        self.gates = []
        self.wires = []
        self.next_gid = 1
        
        # Cache pour optimisation
        self.gate_by_gid = {}
        self.topo_order = []
        self.topo_dirty = True

        # Drag & pan
        self.drag_gate = None
        self.drag_dx = 0
        self.drag_dy = 0
        self.panning = False
        self.pan_start = (0, 0)
        self.cam_start = (0.0, 0.0)
        self.space_down = False

        # Zoom & caméra
        self.scale = 1.0
        self.scale_min = 0.5
        self.scale_max = 3.0
        self.cam_x = 0.0
        self.cam_y = 0.0

        self._build_left_panel()
        self._bind_canvas()

    def _build_left_panel(self):
        Label(self.left, text="Circuits logiques", font=("Arial", 14, "bold")).pack(anchor="w")
        Label(self.left, text="_________________", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 10))

        # Outils
        Label(self.left, text="Outils", font=("Arial", 12, "bold")).pack(anchor="w")
        for text, mode in [("Fil", "wire"), ("Sélection", "select"), ("Suppression", "delete")]:
            Button(self.left, text=text, command=lambda m=mode: self.set_mode(m)).pack(fill=X, pady=(6 if text == "Fil" else 4, 0))

        # Composants
        Label(self.left, text="Composants", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10, 0))
        for text, gtype in [("Entrée", "SRC"), ("NON", "NOT"), ("ET", "AND"), 
                            ("OU", "OR"), ("XOR", "XOR"), ("NOR", "NOR"), ("Sortie (LED)", "OUT")]:
            Button(self.left, text=text, command=lambda g=gtype: self.set_mode(f"place:{g}")).pack(fill=X, pady=(6 if text == "Entrée" else 4, 0))

        # Actions
        Label(self.left, text="Actions", font=("Arial", 12, "bold")).pack(anchor="w", pady=(10, 0))
        actions = [
            ("Table de vérité", self.show_truth_table),
            ("Expression → Circuit", self.expression_to_circuit),
            ("Sauvegarder…", self.save_file),
            ("Nouveau (vierge)", self.new_circuit),
            ("Charger…", self.load_file),
        ]
        for i, (text, cmd) in enumerate(actions):
            Button(self.left, text=text, command=cmd).pack(fill=X, pady=(4, 0))

        self.status = Label(self.left, text="Mode: sélection", fg="#444", justify="left", anchor="w", wraplength=160)
        self.status.pack(fill=X, pady=(12, 0))

    def set_mode(self, m: str):
        self.mode.set(m)
        self.pending_wire_src = None
        
        messages = {
            "wire": "Mode: fil (clic sortie → clic entrée)",
            "select": "Mode: sélection (double-clic SRC pour changer l'entrée)",
            "delete": "Mode: suppression (clic sur fil ou composant)"
        }
        
        if m in messages:
            self.status.config(text=messages[m])
        elif m.startswith("place:"):
            self.status.config(text=f"Mode: placer {m.split(':', 1)[1]} (clic sur le canvas)")
        else:
            self.status.config(text=f"Mode: {m}")

    def _bind_canvas(self):
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        # Zoom
        self.canvas.bind("<MouseWheel>", self.on_zoom_wheel)
        self.canvas.bind("<Button-4>", lambda e: self.on_zoom(1, e))
        self.canvas.bind("<Button-5>", lambda e: self.on_zoom(-1, e))
        self.root.bind("<Control-plus>", lambda e: self.on_zoom(1))
        self.root.bind("<Control-minus>", lambda e: self.on_zoom(-1))
        self.root.bind("<Control-equal>", lambda e: self.on_zoom(1))
        self.root.bind("<Control-0>", self.on_zoom_reset)

        # Pan
        self.root.bind("<KeyPress-space>", lambda e: self._set_space(True))
        self.root.bind("<KeyRelease-space>", lambda e: self._set_space(False))
        self.root.bind("<Left>", lambda e: self._pan_key(-40, 0))
        self.root.bind("<Right>", lambda e: self._pan_key(40, 0))
        self.root.bind("<Up>", lambda e: self._pan_key(0, -40))
        self.root.bind("<Down>", lambda e: self._pan_key(0, 40))

    def add_gate(self, gtype: str, x: int, y: int, name=None, ask_name=True):
        if gtype == "SRC":
            if name is not None:
                name = str(name).strip() or None
            elif ask_name:
                name = simpledialog.askstring("Nom de l'entrée", "Nom de l'entrée (ex: A, B, EN, CLK...) :")
                name = name.strip() if name else None

        g = Gate(self.next_gid, gtype, x, y, name=name)
        self.next_gid += 1
        self.gates.append(g)
        self.gate_by_gid[g.gid] = g
        self.topo_dirty = True
        self.draw_gate(g)
        return g

    def draw_gate(self, g: Gate):
        x1, y1 = self.w2c(g.x, g.y)
        x2, y2 = self.w2c(g.x + GATE_W, g.y + GATE_H)

        g.rect_id = self.canvas.create_rectangle(x1, y1, x2, y2, outline="#333", width=2, fill="#f7f7f7")
        g.text_id = self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=g.title(), font=("Arial", 12, "bold"), fill="black")

        # Bulle inversion
        if g.gtype in ("NOT", "NOR"):
            cxw = g.x + GATE_W + INVERT_R
            cyw = g.y + GATE_H // 2
            cx, cy = self.w2c(cxw, cyw)
            r = INVERT_R * self.scale
            g.invert_id = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline="black", width=2, fill="white")

        # Pins
        for p in g.inputs + g.outputs:
            cx, cy = self.w2c(p.x, p.y)
            r = PIN_R * self.scale
            p.canvas_id = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#222", width=2, fill=bool_to_color(p.value))

        # Textes/LED spécifiques
        if g.gtype == "SRC":
            tx, ty = self.w2c(g.x + GATE_W // 2, g.y + GATE_H - 12)
            g.value_text_id = self.canvas.create_text(tx, ty, text="0", font=("Arial", 11), fill="black")
        elif g.gtype == "OUT":
            cxw, cyw = g.x + GATE_W - 18, g.y + GATE_H // 2
            cx, cy = self.w2c(cxw, cyw)
            rr = 10 * self.scale
            g.led_id = self.canvas.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, width=2)
            tx, ty = self.w2c(g.x + 20, g.y + GATE_H - 12)
            g.value_text_id = self.canvas.create_text(tx, ty, text="?", font=("Arial", 11), fill="black")

    def redraw_all(self):
        self.canvas.delete("all")
        for g in self.gates:
            g.update_pin_positions()
            self.draw_gate(g)
        for w in self.wires:
            self.draw_wire(w)
        self.update_colors()

    def draw_wire(self, w: Wire):
        x1, y1 = self.w2c(w.src.x, w.src.y)
        x2, y2 = self.w2c(w.dst.x, w.dst.y)
        width = max(1, int(3 * self.scale))
        w.canvas_id = self.canvas.create_line(x1, y1, x2, y2, width=width, fill=bool_to_color(w.value))

    def update_colors(self):
        for g in self.gates:
            for p in g.inputs + g.outputs:
                self.canvas.itemconfig(p.canvas_id, fill=bool_to_color(p.value))
            
            if g.gtype == "SRC" and g.value_text_id:
                self.canvas.itemconfig(g.value_text_id, text="1" if g.value else "0", fill="black")
            elif g.gtype == "OUT":
                v = g.inputs[0].value
                self.canvas.itemconfig(g.value_text_id, text="?" if v is None else ("1" if v else "0"))
                self.canvas.itemconfig(g.led_id, outline=bool_to_color(v), fill=bool_to_color(v))
            
            if g.gtype in ("NOT", "NOR") and g.invert_id:
                v = g.outputs[0].value
                self.canvas.itemconfig(g.invert_id, outline=bool_to_color(v))

        for w in self.wires:
            self.canvas.itemconfig(w.canvas_id, fill=bool_to_color(w.value))

    def find_pin_at(self, x, y):
        for g in reversed(self.gates):
            for p in g.inputs + g.outputs:
                if p.hit_test(x, y):
                    return p
        return None

    def find_gate_at(self, x, y):
        for g in reversed(self.gates):
            if g.x <= x <= g.x + GATE_W and g.y <= y <= g.y + GATE_H:
                return g
        return None

    def on_click(self, event):
        m = self.mode.get()
        wx, wy = self.c2w(event.x, event.y)

        if m == "delete":
            w = self.find_wire_at(wx, wy)
            if w:
                self.delete_wire(w)
                self.simulate()
                return
            g = self.find_gate_at(wx, wy)
            if g:
                self.delete_gate(g)
                self.simulate()
            return

        if m.startswith("place:"):
            gtype = m.split(":", 1)[1]
            self.add_gate(gtype, wx, wy)
            self.simulate()
            return

        if m == "wire":
            pin = self.find_pin_at(wx, wy)
            if not pin:
                return

            if not self.pending_wire_src:
                if pin.kind == "out":
                    self.pending_wire_src = pin
                    self.status.config(text="Fil: maintenant clique une entrée")
            else:
                if pin.kind == "in":
                    w = Wire(self.pending_wire_src, pin)
                    self.wires.append(w)
                    self.draw_wire(w)
                    self.pending_wire_src = None
                    self.topo_dirty = True
                    self.status.config(text="Mode: fil (clic sortie → clic entrée)")
                    self.simulate()

    def on_double_click(self, event):
        wx, wy = self.c2w(event.x, event.y)
        g = self.find_gate_at(wx, wy)
        if g and g.gtype == "SRC":
            g.value = not g.value
            self.simulate()

    def _build_topo_order(self):
        """Construit un ordre topologique des gates pour simulation optimisée"""
        if not self.topo_dirty:
            return
        
        # Construire le graphe de dépendances
        in_degree = {g.gid: 0 for g in self.gates}
        adjacency = {g.gid: [] for g in self.gates}
        
        for w in self.wires:
            src_gid = w.src.owner.gid
            dst_gid = w.dst.owner.gid
            adjacency[src_gid].append(dst_gid)
            in_degree[dst_gid] += 1
        
        # Kahn's algorithm
        queue = deque([gid for gid, deg in in_degree.items() if deg == 0])
        order = []
        
        while queue:
            gid = queue.popleft()
            order.append(gid)
            
            for neighbor in adjacency[gid]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        self.topo_order = order
        self.topo_dirty = False

    def simulate(self):
        # Reset pin values
        for g in self.gates:
            for p in g.inputs + g.outputs:
                p.value = None

        # Set SRC outputs
        for g in self.gates:
            if g.gtype == "SRC":
                g.outputs[0].value = g.value

        # Build topological order for efficient propagation
        self._build_topo_order()

        # Propagate in topological order (maximum 30 iterations for cycles)
        for iteration in range(30):
            changed = False

            # Propagate wires
            for w in self.wires:
                newv = w.src.value
                if w.value != newv:
                    w.value = newv
                    w.dst.value = newv
                    changed = True

            # Compute gates in topological order
            for gid in self.topo_order:
                g = self.gate_by_gid.get(gid)
                if not g or g.gtype in ("SRC", "OUT"):
                    continue
                
                out = g.compute()
                if g.outputs and g.outputs[0].value != out:
                    g.outputs[0].value = out
                    changed = True

            if not changed:
                break

        self.update_colors()

    def save_file(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Circuit JSON", "*.json")])
        if not path:
            return
        
        data = {
            "gates": [g.as_dict() for g in self.gates],
            "wires": [w.as_dict() for w in self.wires],
            "next_gid": self.next_gid,
        }
        saveAndLoad.save(path, data)
        messagebox.showinfo("Sauvegarde", "Circuit sauvegardé.")

    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("Circuit JSON", "*.json")])
        if not path:
            return
        
        data = saveAndLoad.load(path)
        self.gates = []
        self.wires = []
        self.gate_by_gid = {}
        self.next_gid = data.get("next_gid", 1)
        self.topo_dirty = True

        for gd in data.get("gates", []):
            g = Gate(gd["gid"], gd["type"], gd["x"], gd["y"], name=gd.get("name"))
            if g.gtype == "SRC":
                g.value = bool(gd.get("value", False))
            self.gates.append(g)
            self.gate_by_gid[g.gid] = g

        for wd in data.get("wires", []):
            sg = self.gate_by_gid[wd["src_gate"]]
            dg = self.gate_by_gid[wd["dst_gate"]]
            src_pin = sg.outputs[wd["src_pin"]]
            dst_pin = dg.inputs[wd["dst_pin"]]
            self.wires.append(Wire(src_pin, dst_pin))

        self.redraw_all()
        self.simulate()

    def overline(self, s: str) -> str:
        return "".join(ch + "\u0305" for ch in s)

    def _get_io(self):
        srcs = sorted([g for g in self.gates if g.gtype == "SRC"], key=lambda g: g.gid)
        outs = sorted([g for g in self.gates if g.gtype == "OUT"], key=lambda g: g.gid)
        return srcs, outs

    def _build_dst_to_src(self):
        return {(w.dst.owner.gid, w.dst.index): (w.src.owner.gid, w.src.index) for w in self.wires}

    def _var_names(self, n):
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        return list(letters[:n]) if n <= len(letters) else [f"A{i}" for i in range(n)]

    def _expr_for_gate_out(self, gate_gid, dst_to_src, gid_map, src_name_by_gid, visiting, memo):
        if gate_gid in memo:
            return memo[gate_gid]
        if gate_gid in visiting:
            return ("?", 0)

        visiting.add(gate_gid)
        g = gid_map[gate_gid]

        if g.gtype == "SRC":
            e = (src_name_by_gid[gate_gid], 3)
        else:
            def get(i):
                key = (gate_gid, i)
                if key not in dst_to_src:
                    return ("Ø", 3)
                src_gid, _ = dst_to_src[key]
                return self._expr_for_gate_out(src_gid, dst_to_src, gid_map, src_name_by_gid, visiting, memo)

            if g.gtype == "NOT":
                a, pa = get(0)
                a = f"({a})" if pa < 3 else a
                e = (self.overline(a), 3)
            elif g.gtype == "AND":
                (a, pa), (b, pb) = get(0), get(1)
                a = f"({a})" if pa < 2 else a
                b = f"({b})" if pb < 2 else b
                e = (f"{a}.{b}", 2)
            elif g.gtype == "OR":
                (a, pa), (b, pb) = get(0), get(1)
                a = f"({a})" if pa < 1 else a
                b = f"({b})" if pb < 1 else b
                e = (f"{a} + {b}", 1)
            elif g.gtype == "XOR":
                (a, pa), (b, pb) = get(0), get(1)
                a = f"({a})" if pa < 1 else a
                b = f"({b})" if pb < 1 else b
                e = (f"{a} ⊕ {b}", 1)
            elif g.gtype == "NOR":
                (a, pa), (b, pb) = get(0), get(1)
                inner = f"{a} + {b}"
                if pa < 1 or pb < 1:
                    inner = f"({inner})"
                e = (self.overline(inner), 3)
            else:
                e = ("?", 0)

        memo[gate_gid] = e
        visiting.remove(gate_gid)
        return e

    def _value_for_gate_out(self, gate_gid, assignment_by_gid, dst_to_src, gid_map, visiting, memo):
        if gate_gid in memo:
            return memo[gate_gid]
        if gate_gid in visiting:
            return None

        visiting.add(gate_gid)
        g = gid_map[gate_gid]

        if g.gtype == "SRC":
            v = assignment_by_gid.get(gate_gid, False)
        else:
            def val_of_input(i):
                key = (gate_gid, i)
                if key not in dst_to_src:
                    return None
                src_gid, _ = dst_to_src[key]
                return self._value_for_gate_out(src_gid, assignment_by_gid, dst_to_src, gid_map, visiting, memo)

            compute_func = Gate.COMPUTE_FUNCS.get(g.gtype)
            if compute_func:
                inputs = [val_of_input(i) for i in range(len(g.inputs))]
                v = None if None in inputs else compute_func(inputs)
            else:
                v = None

        memo[gate_gid] = v
        visiting.remove(gate_gid)
        return v

    def show_truth_table(self):
        srcs, outs = self._get_io()
        if not srcs:
            messagebox.showwarning("Table de vérité", "Aucune entrée (SRC) dans le circuit.")
            return
        if not outs:
            messagebox.showwarning("Table de vérité", "Aucune sortie (OUT) dans le circuit.")
            return
        if len(srcs) > 8:
            messagebox.showwarning("Table de vérité", "Trop d'entrées (SRC) pour afficher une table complète (max conseillé : 8).")
            return

        gid_map = self.gate_by_gid
        dst_to_src = self._build_dst_to_src()
        order = self._topological_gates(dst_to_src, gid_map)

        fallback = self._var_names(len(srcs))
        var_names = [(g.name or "").strip() or fallback[i] for i, g in enumerate(srcs)]
        src_name_by_gid = {srcs[i].gid: var_names[i] for i in range(len(srcs))}

        intermediate = []
        for gid in order:
            g = gid_map[gid]
            if g.gtype not in ("SRC", "OUT"):
                expr, _ = self._expr_for_gate_out(gid, dst_to_src, gid_map, src_name_by_gid, set(), {})
                intermediate.append((gid, expr))

        single_output = len(outs) == 1
        out_exprs = []
        for i, outg in enumerate(outs):
            out_name = "S" if single_output else f"OUT{outg.gid}"
            key = (outg.gid, 0)
            if key not in dst_to_src:
                out_exprs.append((out_name, "Ø"))
            else:
                src_gid, _ = dst_to_src[key]
                expr, _ = self._expr_for_gate_out(src_gid, dst_to_src, gid_map, src_name_by_gid, set(), {})
                out_exprs.append((out_name, expr))

        # Fenêtre
        win = Toplevel(self.root)
        win.title("Table de vérité")
        win.geometry("900x600")

        expr_frame = Frame(win, padx=10, pady=10)
        expr_frame.pack(fill=X)
        Label(expr_frame, text="Expression(s) booléenne(s) :", font=("Arial", 12, "bold")).pack(anchor="w")
        
        expr_text = Text(expr_frame, height=min(6, 2 + len(out_exprs)), wrap="word")
        expr_text.pack(fill=X, pady=(6, 0))
        expr_text.insert("end", "\n".join([f"{name} = {expr}" for name, expr in out_exprs]))
        expr_text.config(state="disabled")

        table_frame = Frame(win, padx=10, pady=10)
        table_frame.pack(fill=BOTH, expand=True)

        cols = var_names + [expr for _, expr in intermediate] + [name for name, _ in out_exprs]
        tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        tree.pack(side=LEFT, fill=BOTH, expand=True)

        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=70, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        tree.configure(yscrollcommand=scrollbar.set)

        for bits in product([0, 1], repeat=len(srcs)):
            assignment_by_gid = {srcs[i].gid: bool(bits[i]) for i in range(len(srcs))}
            row = list(bits)

            for gid, _ in intermediate:
                v = self._value_for_gate_out(gid, assignment_by_gid, dst_to_src, gid_map, set(), {})
                row.append("?" if v is None else ("1" if v else "0"))

            for outg in outs:
                key = (outg.gid, 0)
                if key not in dst_to_src:
                    row.append("?")
                else:
                    src_gid, _ = dst_to_src[key]
                    v = self._value_for_gate_out(src_gid, assignment_by_gid, dst_to_src, gid_map, set(), {})
                    row.append("?" if v is None else ("1" if v else "0"))

            tree.insert("", "end", values=row)

    def _topological_gates(self, dst_to_src, gid_map):
        visited = set()
        order = []

        def dfs(gid):
            if gid in visited:
                return
            visited.add(gid)
            g = gid_map[gid]
            for i in range(len(g.inputs)):
                key = (gid, i)
                if key in dst_to_src:
                    src_gid, _ = dst_to_src[key]
                    dfs(src_gid)
            order.append(gid)

        for g in self.gates:
            if g.gtype == "OUT":
                dfs(g.gid)
        return order

    def new_circuit(self):
        if self.gates or self.wires:
            ok = messagebox.askyesno("Nouveau circuit", "Repartir sur un circuit vierge ?\nLes modifications non sauvegardées seront perdues.")
            if not ok:
                return -1

        self.gates = []
        self.wires = []
        self.gate_by_gid = {}
        self.next_gid = 1
        self.pending_wire_src = None
        self.topo_dirty = True
        self.canvas.delete("all")
        self.set_mode("select")

    def on_press(self, event):
        m = self.mode.get()
        
        if m in ("wire", "delete") or m.startswith("place:"):
            self.on_click(event)
            return

        wx, wy = self.c2w(event.x, event.y)

        if m == "select":
            pin = self.find_pin_at(wx, wy)
            g = self.find_gate_at(wx, wy)

            if self.space_down or (pin is None and g is None):
                self.panning = True
                self.pan_start = (event.x, event.y)
                self.cam_start = (self.cam_x, self.cam_y)
                return

            if pin:
                return

            if g:
                self.drag_gate = g
                self.drag_dx = wx - g.x
                self.drag_dy = wy - g.y

    def on_drag(self, event):
        if self.panning:
            dx_pix = event.x - self.pan_start[0]
            dy_pix = event.y - self.pan_start[1]
            dx_w = dx_pix / self.scale
            dy_w = dy_pix / self.scale
            self.cam_x = self.cam_start[0] - dx_w
            self.cam_y = self.cam_start[1] - dy_w
            self.redraw_all()
            return

        if self.mode.get() != "select" or not self.drag_gate:
            return

        wx, wy = self.c2w(event.x, event.y)
        self.drag_gate.x = wx - self.drag_dx
        self.drag_gate.y = wy - self.drag_dy
        self.drag_gate.update_pin_positions()
        self.redraw_all()

    def on_release(self, event):
        self.drag_gate = None
        self.panning = False

    def _dist_point_to_segment(self, px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

    def find_wire_at(self, x, y, threshold=8):
        threshold /= self.scale
        for w in reversed(self.wires):
            if self._dist_point_to_segment(x, y, w.src.x, w.src.y, w.dst.x, w.dst.y) <= threshold:
                return w
        return None

    def delete_wire(self, w: Wire):
        if w.canvas_id:
            self.canvas.delete(w.canvas_id)
        if w in self.wires:
            self.wires.remove(w)
        self.topo_dirty = True

    def delete_gate(self, g: Gate):
        for w in [w for w in self.wires if w.src.owner == g or w.dst.owner == g]:
            self.delete_wire(w)

        for item_id in [g.rect_id, g.text_id, g.invert_id, g.led_id, g.value_text_id]:
            if item_id:
                self.canvas.delete(item_id)

        for p in g.inputs + g.outputs:
            if p.canvas_id:
                self.canvas.delete(p.canvas_id)

        if g in self.gates:
            self.gates.remove(g)
        if g.gid in self.gate_by_gid:
            del self.gate_by_gid[g.gid]

        if self.pending_wire_src and self.pending_wire_src.owner == g:
            self.pending_wire_src = None
        
        self.topo_dirty = True

    def w2c(self, x, y):
        return (x - self.cam_x) * self.scale, (y - self.cam_y) * self.scale

    def c2w(self, x, y):
        return x / self.scale + self.cam_x, y / self.scale + self.cam_y

    def on_zoom_wheel(self, event):
        self.on_zoom(1 if event.delta > 0 else -1, event)

    def on_zoom(self, direction, event=None):
        factor = 1.1 if direction > 0 else 1 / 1.1
        new_scale = max(self.scale_min, min(self.scale_max, self.scale * factor))
        if abs(new_scale - self.scale) > 1e-9:
            self.scale = new_scale
            self.status.config(text=f"Mode: {self.mode.get()} | Zoom: {int(self.scale*100)} %")
            self.redraw_all()

    def on_zoom_reset(self, event=None):
        self.scale = 1.0
        self.redraw_all()

    def _set_space(self, v: bool):
        self.space_down = v

    def _pan_key(self, dx_pix, dy_pix):
        self.cam_x += dx_pix / self.scale
        self.cam_y += dy_pix / self.scale
        self.redraw_all()

    def _tokenize_expr(self, s: str):
        s = s.replace(" ", "")
        tokens = []
        i = 0
        while i < len(s):
            c = s[i]
            if c.isalpha() or c == "_":
                j = i + 1
                while j < len(s) and (s[j].isalnum() or s[j] == "_"):
                    j += 1
                tokens.append(("ID", s[i:j]))
                i = j
            elif c in ("!", ".", "+", "^", "(", ")"):
                tokens.append((c, c))
                i += 1
            else:
                raise ValueError(f"Caractère invalide: {c}")
        return tokens

    def _to_rpn(self, tokens):
        prec = {"!": 3, ".": 2, "^": 1, "+": 0}
        right_assoc = {"!"}
        out = []
        ops = []

        def pop_ops(min_prec):
            while ops and ops[-1] != "(":
                ptop = prec[ops[-1]]
                if ptop > min_prec or (ptop == min_prec and ops[-1] not in right_assoc):
                    out.append(("OP", ops.pop()))
                else:
                    break

        prev_was_value = False
        for typ, val in tokens:
            if typ == "ID":
                out.append(("ID", val))
                prev_was_value = True
            elif val == "(":
                ops.append("(")
                prev_was_value = False
            elif val == ")":
                while ops and ops[-1] != "(":
                    out.append(("OP", ops.pop()))
                if not ops or ops[-1] != "(":
                    raise ValueError("Parenthèses non équilibrées")
                ops.pop()
                prev_was_value = True
            else:
                if val == "!":
                    ops.append("!")
                    prev_was_value = False
                else:
                    if not prev_was_value:
                        raise ValueError(f"Opérateur '{val}' placé au mauvais endroit")
                    pop_ops(prec[val])
                    ops.append(val)
                    prev_was_value = False

        while ops:
            if ops[-1] == "(":
                raise ValueError("Parenthèses non équilibrées")
            out.append(("OP", ops.pop()))
        return out

    def _rpn_to_ast(self, rpn):
        st = []
        for typ, val in rpn:
            if typ == "ID":
                st.append(("ID", val))
            else:
                if val == "!":
                    if not st:
                        raise ValueError("NOT sans opérande")
                    st.append(("NOT", st.pop()))
                else:
                    if len(st) < 2:
                        raise ValueError(f"Opérateur '{val}' sans 2 opérandes")
                    b, a = st.pop(), st.pop()
                    node = {".": "AND", "+": "OR", "^": "XOR"}[val]
                    st.append((node, a, b))
        if len(st) != 1:
            raise ValueError("Expression invalide")
        return st[0]

    def expression_to_circuit(self):
        if self.new_circuit() == -1:
            return

        expr = simpledialog.askstring("Expression → circuit", "Expression (ex: !(A.B) + C)\nOpérateurs: ! (NON), . (ET), + (OU), ^ (XOR)")
        if not expr:
            return

        try:
            tokens = self._tokenize_expr(expr)
            rpn = self._to_rpn(tokens)
            ast = self._rpn_to_ast(rpn)
        except Exception as e:
            messagebox.showerror("Erreur", f"Expression invalide :\n{e}")
            return

        self.new_circuit()
        src_by_name = {}
        x0, y0 = 80, 80
        y_step = 90
        gate_x_step = 160

        def get_src(name, x, y):
            if name not in src_by_name:
                src_by_name[name] = self.add_gate("SRC", x, y, name=name, ask_name=False)
            return src_by_name[name]

        def build(node, depth=0, y=0):
            kind = node[0]
            if kind == "ID":
                return get_src(node[1], x0, y0 + y * y_step), y

            if kind == "NOT":
                child_gate, cy = build(node[1], depth + 1, y)
                g = self.add_gate("NOT", x0 + (depth + 1) * gate_x_step, y0 + cy * y_step - 20)
                self.wires.append(Wire(child_gate.outputs[0], g.inputs[0]))
                return g, cy

            left, right = node[1], node[2]
            gl, yl = build(left, depth + 1, y)
            gr, yr = build(right, depth + 1, y + 1)
            midy = (yl + yr) / 2.0
            g = self.add_gate(kind, x0 + (depth + 1) * gate_x_step, y0 + midy * y_step - 20)
            self.wires.append(Wire(gl.outputs[0], g.inputs[0]))
            self.wires.append(Wire(gr.outputs[0], g.inputs[1]))
            return g, midy

        root_gate, midy = build(ast, depth=0, y=0)
        out = self.add_gate("OUT", x0 + 4 * gate_x_step, y0 + midy * y_step - 20)
        self.wires.append(Wire(root_gate.outputs[0], out.inputs[0]))
        self.topo_dirty = True
        self.redraw_all()
        self.simulate()


def main_ui():
    root = Tk()
    try:
        from PIL import Image, ImageTk
        ico = Image.open('logo.png')
        photo = ImageTk.PhotoImage(ico)
        root.wm_iconphoto(False, photo)
    except:
        pass

    root.geometry("1000x650")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main_ui()