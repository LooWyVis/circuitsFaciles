# main.py
from tkinter import *
from tkinter import filedialog, messagebox
from itertools import product
from tkinter import ttk
import math

import portes
import saveAndLoad


PIN_R = 6
GATE_W, GATE_H = 90, 60

COLOR_UNDEF = "#888888"
COLOR_0 = "#000000"
COLOR_1 = "#cc0000"

INVERT_R = 6        # rayon de la bulle d'inversion
INVERT_OFFSET = 14 # distance bulle → vrai pin


def bool_to_color(v):
    if v is None:
        return COLOR_UNDEF
    return COLOR_1 if v else COLOR_0


class Pin:
    def __init__(self, owner, kind: str, index: int, x: int, y: int):
        self.owner = owner            # Gate instance
        self.kind = kind              # "in" or "out"
        self.index = index            # input index or output index (0)
        self.x = x
        self.y = y
        self.value = None             # None/False/True

        self.canvas_id = None
        self.label_id = None

    def hit_test(self, mx, my):
        return (mx - self.x) ** 2 + (my - self.y) ** 2 <= (PIN_R + 3) ** 2


class Wire:
    def __init__(self, src_pin: Pin, dst_pin: Pin):
        self.src = src_pin
        self.dst = dst_pin
        self.value = None
        self.canvas_id = None

    def as_dict(self):
        return {
            "src_gate": self.src.owner.gid,
            "src_pin": self.src.index,  # output index (0)
            "dst_gate": self.dst.owner.gid,
            "dst_pin": self.dst.index,  # input index
        }


class Gate:
    def __init__(self, gid: int, gtype: str, x: int, y: int):        
        self.gid = gid
        self.gtype = gtype
        self.x = x
        self.y = y

        self.inputs = []
        self.outputs = []
        self.value = None  # for Source mainly

        self.rect_id = None
        self.text_id = None
        self.led_id = None
        self.value_text_id = None

        self._build_pins()

    def _build_pins(self):
        # Pin layout: inputs on left, output on right (1 output) sauf OUT
        if self.gtype == "SRC":
            self.inputs = []
            self.outputs = [Pin(self, "out", 0, self.x + GATE_W, self.y + GATE_H // 2)]
            self.value = False

        elif self.gtype == "OUT":
            self.inputs = [Pin(self, "in", 0, self.x, self.y + GATE_H // 2)]
            self.outputs = []  # pas de sortie

        
        elif self.gtype == "NOT":
            self.inputs = [
                Pin(self, "in", 0, self.x, self.y + GATE_H // 2)
            ]
            self.outputs = [
                Pin(self, "out", 0, self.x + GATE_W + INVERT_OFFSET, self.y + GATE_H // 2)
            ]

        elif self.gtype == "NOR":
            self.inputs = [
                Pin(self, "in", 0, self.x, self.y + GATE_H // 3),
                Pin(self, "in", 1, self.x, self.y + 2 * GATE_H // 3)
            ]
            self.outputs = [
                Pin(self, "out", 0, self.x + GATE_W + INVERT_OFFSET, self.y + GATE_H // 2)
            ]

        else:
            # 2-input gates
            self.inputs = [
                Pin(self, "in", 0, self.x, self.y + GATE_H // 3),
                Pin(self, "in", 1, self.x, self.y + 2 * GATE_H // 3),
            ]
            self.outputs = [Pin(self, "out", 0, self.x + GATE_W, self.y + GATE_H // 2)]

    def update_pin_positions(self):
        # Recompute pin coordinates if gate moved (future-proof)
        if self.gtype == "SRC":
            self.outputs[0].x = self.x + GATE_W
            self.outputs[0].y = self.y + GATE_H // 2
        elif self.gtype == "OUT":
            self.inputs[0].x = self.x
            self.inputs[0].y = self.y + GATE_H // 2
        elif self.gtype == "NOT":
            self.inputs[0].x = self.x
            self.inputs[0].y = self.y + GATE_H // 2
            self.outputs[0].x = self.x + GATE_W + INVERT_OFFSET
            self.outputs[0].y = self.y + GATE_H // 2
        elif self.gtype == "NOR":
            self.inputs[0].x = self.x
            self.inputs[0].y = self.y + GATE_H // 3
            self.inputs[1].x = self.x
            self.inputs[1].y = self.y + 2 * GATE_H // 3
            self.outputs[0].x = self.x + GATE_W + INVERT_OFFSET
            self.outputs[0].y = self.y + GATE_H // 2
        else:
            self.inputs[0].x = self.x
            self.inputs[0].y = self.y + GATE_H // 3
            self.inputs[1].x = self.x
            self.inputs[1].y = self.y + 2 * GATE_H // 3
            self.outputs[0].x = self.x + GATE_W
            self.outputs[0].y = self.y + GATE_H // 2

    def compute(self):
        # Returns output value (bool) or None if undefined
        if self.gtype == "SRC":
            return self.value
        
        if self.gtype == "OUT":
            return None

        ins = [p.value for p in self.inputs]
        if any(v is None for v in ins):
            return None

        if self.gtype == "NOT":
            return portes.non(ins[0])
        if self.gtype == "AND":
            return portes.et(ins[0], ins[1])
        if self.gtype == "OR":
            return portes.ou(ins[0], ins[1])
        if self.gtype == "XOR":
            return portes.xor(ins[0], ins[1])
        if self.gtype == "NOR":
            return portes.nor(ins[0], ins[1])
        
        
        return None

    def title(self):
        return {
            "SRC": "Entree",
            "NOT": "1",
            "AND": "&",
            "OR": "≥1",
            "XOR": "=1",
            "NOR": "≥1",
            "OUT": "S",
        }.get(self.gtype, self.gtype)

    def as_dict(self):
        return {
            "gid": self.gid,
            "type": self.gtype,
            "x": self.x,
            "y": self.y,
            "value": self.value if self.gtype == "SRC" else None,
        }


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Circuits logiques (NSI)")

        self.left = Frame(root, width=180, padx=8, pady=8)
        self.left.pack(side=LEFT, fill=Y)
        self.left.pack_propagate(False)

        self.canvas = Canvas(root, bg="white")
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.mode = StringVar(value="select")
        self.pending_wire_src = None

        self.gates = []
        self.wires = []
        self.next_gid = 1

        self.invert_id = None

        self.drag_gate = None
        self.drag_dx = 0
        self.drag_dy = 0

        self.scale = 1.0
        self.scale_min = 0.5
        self.scale_max = 3.0

        self.cam_x = 0.0
        self.cam_y = 0.0
        self.panning = False
        self.pan_start = (0, 0)
        self.cam_start = (0.0, 0.0)
        self.space_down = False

        self._build_left_panel()
        self._bind_canvas()

    def _build_left_panel(self):
        Label(self.left, text="Circuits logiques", font=("Arial", 14, "bold")).pack(anchor="w")

        Label(self.left, text="_________________", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 10))

        Label(self.left, text="Outils", font=("Arial", 12, "bold")).pack(anchor="w")

        Button(self.left, text="Fil", command=lambda: self.set_mode("wire")).pack(fill=X, pady=(6, 0))
        Button(self.left, text="Sélection", command=lambda: self.set_mode("select")).pack(fill=X, pady=(6, 0))
        Button(self.left, text="Suppression", command=lambda: self.set_mode("delete")).pack(fill=X, pady=(4, 10))

        Label(self.left, text="Composants", font=("Arial", 12, "bold")).pack(anchor="w")

        Button(self.left, text="Entrée", command=lambda: self.set_mode("place:SRC")).pack(fill=X, pady=(6, 0))
        Button(self.left, text="NON", command=lambda: self.set_mode("place:NOT")).pack(fill=X, pady=(4, 0))
        Button(self.left, text="ET", command=lambda: self.set_mode("place:AND")).pack(fill=X, pady=(4, 0))
        Button(self.left, text="OU", command=lambda: self.set_mode("place:OR")).pack(fill=X, pady=(4, 0))
        Button(self.left, text="XOR", command=lambda: self.set_mode("place:XOR")).pack(fill=X, pady=(4, 0))
        Button(self.left, text="NOR", command=lambda: self.set_mode("place:NOR")).pack(fill=X, pady=(4, 0))
        Button(self.left, text="Sortie (LED)", command=lambda: self.set_mode("place:OUT")).pack(fill=X, pady=(4, 10))

        Label(self.left, text="Actions", font=("Arial", 12, "bold")).pack(anchor="w")
        # Button(self.left, text="Simuler", command=self.simulate).pack(fill=X, pady=(6, 0))
        Button(self.left, text="Table de vérité", command=self.show_truth_table).pack(fill=X, pady=(4, 0))
        Button(self.left, text="Sauvegarder…", command=self.save_file).pack(fill=X, pady=(4, 0))
        Button(self.left, text="Nouveau (vierge)", command=self.new_circuit).pack(fill=X, pady=(4, 0))
        Button(self.left, text="Charger…", command=self.load_file).pack(fill=X, pady=(4, 0))

        self.status = Label(
            self.left,
            text="Mode: sélection",
            fg="#444",
            justify="left",
            anchor="w",
            wraplength=160  # largeur de retour à la ligne (en pixels)
        )
        self.status.pack(fill=X, pady=(12, 0))

    def set_mode(self, m: str):
        self.mode.set(m)
        self.pending_wire_src = None
        if m == "wire":
            self.status.config(text="Mode: fil (clic sortie → clic entrée)")
        elif m == "select":
            self.status.config(text="Mode: sélection (double-clic SRC pour changer l'entrée)")
        elif m.startswith("place:"):
            self.status.config(text=f"Mode: placer {m.split(':', 1)[1]} (clic sur le canvas)")
        elif m == "delete":
            self.status.config(text="Mode: suppression (clic sur fil ou composant)")
        else:
            self.status.config(text=f"Mode: {m}")

    def _bind_canvas(self):
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)

        # Zoom
        self.canvas.bind("<MouseWheel>", self.on_zoom_wheel)      # Windows/Mac
        self.canvas.bind("<Button-4>", lambda e: self.on_zoom(1, e))  # Linux
        self.canvas.bind("<Button-5>", lambda e: self.on_zoom(-1, e)) # Linux
        self.root.bind("<Control-plus>", lambda e: self.on_zoom(1))
        self.root.bind("<Control-minus>", lambda e: self.on_zoom(-1))
        self.root.bind("<Control-0>", self.on_zoom_reset)
        self.root.bind("<Control-equal>", lambda e: self.on_zoom(1))


        self.root.bind("<KeyPress-space>", lambda e: self._set_space(True))
        self.root.bind("<KeyRelease-space>", lambda e: self._set_space(False))

        self.root.bind("<Left>",  lambda e: self._pan_key(-40, 0))
        self.root.bind("<Right>", lambda e: self._pan_key(40, 0))
        self.root.bind("<Up>",    lambda e: self._pan_key(0, -40))
        self.root.bind("<Down>",  lambda e: self._pan_key(0, 40))

    def add_gate(self, gtype: str, x: int, y: int):
        g = Gate(self.next_gid, gtype, x, y)
        self.next_gid += 1
        self.gates.append(g)
        self.draw_gate(g)
        return g

    def draw_gate(self, g: Gate):
        # Body (scaled)
        x1, y1 = self.w2c(g.x, g.y)
        x2, y2 = self.w2c(g.x + GATE_W, g.y + GATE_H)

        g.rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline="#333", width=2, fill="#f7f7f7"
        )

        g.text_id = self.canvas.create_text(
            (x1 + x2) / 2,
            (y1 + y2) / 2,
            text=g.title(),
            font=("Arial", 12, "bold"),
            fill="black"
        )

        # --- Bulle inversion (NOT/NOR) ---
        if g.gtype in ("NOT", "NOR"):
            cxw = g.x + GATE_W + INVERT_R
            cyw = g.y + GATE_H // 2
            cx, cy = self.w2c(cxw, cyw)
            r = INVERT_R * self.scale
            g.invert_id = self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                outline="black", width=2, fill="white"
            )
        else:
            g.invert_id = None

        # Pins (scaled)
        for p in g.inputs + g.outputs:
            cx, cy = self.w2c(p.x, p.y)
            r = PIN_R * self.scale
            p.canvas_id = self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                outline="#222", width=2, fill=bool_to_color(p.value)
            )

        # SRC / OUT texts (scaled position, font stays same size)
        if g.gtype == "SRC":
            tx, ty = self.w2c(g.x + GATE_W // 2, g.y + GATE_H - 12)
            g.value_text_id = self.canvas.create_text(tx, ty, text="0", font=("Arial", 11), fill="black")
            g.led_id = None

        elif g.gtype == "OUT":
            cxw, cyw = g.x + GATE_W - 18, g.y + GATE_H // 2
            cx, cy = self.w2c(cxw, cyw)
            rr = 10 * self.scale
            g.led_id = self.canvas.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, width=2)

            tx, ty = self.w2c(g.x + 20, g.y + GATE_H - 12)
            g.value_text_id = self.canvas.create_text(tx, ty, text="?", font=("Arial", 11), fill="black")

        else:
            g.value_text_id = None
            g.led_id = None

    def redraw_all(self):
        self.canvas.delete("all")
        # re-draw gates
        for g in self.gates:
            g.update_pin_positions()
            self.draw_gate(g)
        # re-draw wires
        for w in self.wires:
            self.draw_wire(w)
        self.update_colors()

    def draw_wire(self, w: Wire):
        x1, y1 = self.w2c(w.src.x, w.src.y)
        x2, y2 = self.w2c(w.dst.x, w.dst.y)
        width = max(1, int(3 * self.scale))
        w.canvas_id = self.canvas.create_line(x1, y1, x2, y2, width=width, fill=bool_to_color(w.value))

    def update_colors(self):
        # pins
        for g in self.gates:
            for p in g.inputs + g.outputs:
                self.canvas.itemconfig(p.canvas_id, fill=bool_to_color(p.value))
            if g.gtype == "SRC" and g.value_text_id is not None:
                self.canvas.itemconfig(
                    g.value_text_id,
                    text="1" if g.value else "0",
                    fill="black"
                )
            if g.gtype == "OUT":
                v = g.inputs[0].value
                # texte
                self.canvas.itemconfig(g.value_text_id, text="?" if v is None else ("1" if v else "0"))
                # "LED" colorée
                self.canvas.itemconfig(g.led_id, outline=bool_to_color(v), fill=bool_to_color(v))

            if g.gtype in ("NOT", "NOR") and g.invert_id is not None:
                v = g.outputs[0].value
                self.canvas.itemconfig(g.invert_id, outline=bool_to_color(v))

        # wires
        for w in self.wires:
            self.canvas.itemconfig(w.canvas_id, fill=bool_to_color(w.value))

    def find_pin_at(self, x, y):
        for g in reversed(self.gates):  # topmost first
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
            # priorité : fil puis composant
            w = self.find_wire_at(wx, wy)
            if w is not None:
                self.delete_wire(w)
                self.simulate()
                return

            g = self.find_gate_at(wx, wy)
            if g is not None:
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
            if pin is None:
                return

            if self.pending_wire_src is None:
                if pin.kind != "out":
                    return
                self.pending_wire_src = pin
                self.status.config(text="Fil: maintenant clique une entrée")
            else:
                if pin.kind != "in":
                    return
                # create wire
                w = Wire(self.pending_wire_src, pin)
                self.wires.append(w)
                self.draw_wire(w)
                self.pending_wire_src = None
                self.status.config(text="Mode: fil (clic sortie → clic entrée)")
                self.simulate()
            return

        # select mode: nothing for now (future: drag/drop)

    def on_double_click(self, event):
        wx, wy = self.c2w(event.x, event.y)
        # double click on SRC toggles value
        g = self.find_gate_at(wx, wy)
        if g and g.gtype == "SRC":
            g.value = not g.value
            self.simulate()

    def simulate(self):
        # reset all pin values (except SRC output)
        for g in self.gates:
            for p in g.inputs + g.outputs:
                p.value = None

        # set SRC outputs
        for g in self.gates:
            if g.gtype == "SRC":
                g.outputs[0].value = g.value

        # iterative relaxation (enough for acyclic circuits; for loops it stabilizes or stays None)
        for _ in range(30):
            changed = False

            # propagate wires src -> dst
            for w in self.wires:
                newv = w.src.value
                if w.value != newv:
                    w.value = newv
                    changed = True
                if w.dst.value != newv:
                    w.dst.value = newv
                    changed = True

            # compute each gate output from its inputs
            for g in self.gates:
                if g.gtype in ("SRC", "OUT"):
                    continue
                out = g.compute()
                if g.outputs and g.outputs[0].value != out:
                    g.outputs[0].value = out
                    changed = True

            if not changed:
                break

        self.update_colors()

    def save_file(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Circuit JSON", "*.json")]
        )
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
        path = filedialog.askopenfilename(
            filetypes=[("Circuit JSON", "*.json")]
        )
        if not path:
            return
        data = saveAndLoad.load(path)

        # rebuild
        self.gates = []
        self.wires = []
        self.next_gid = data.get("next_gid", 1)

        gid_to_gate = {}
        for gd in data.get("gates", []):
            g = Gate(gd["gid"], gd["type"], gd["x"], gd["y"])
            if g.gtype == "SRC":
                g.value = bool(gd.get("value", False))
            self.gates.append(g)
            gid_to_gate[g.gid] = g

        for wd in data.get("wires", []):
            sg = gid_to_gate[wd["src_gate"]]
            dg = gid_to_gate[wd["dst_gate"]]
            src_pin = sg.outputs[wd["src_pin"]]
            dst_pin = dg.inputs[wd["dst_pin"]]
            self.wires.append(Wire(src_pin, dst_pin))

        self.redraw_all()
        self.simulate()

    
    def overline(self, s: str) -> str:
        # Ajoute une barre au-dessus de chaque caractère
        return "".join(ch + "\u0305" for ch in s)

    def _get_io(self):
        """Retourne (src_gates, out_gates) triés par gid."""
        srcs = sorted([g for g in self.gates if g.gtype == "SRC"], key=lambda g: g.gid)
        outs = sorted([g for g in self.gates if g.gtype == "OUT"], key=lambda g: g.gid)
        return srcs, outs

    def _build_dst_to_src(self):
        """
        Construit un mapping: (dst_gate_gid, dst_input_index) -> (src_gate_gid, src_output_index)
        """
        m = {}
        for w in self.wires:
            m[(w.dst.owner.gid, w.dst.index)] = (w.src.owner.gid, w.src.index)
        return m

    def _gate_by_gid(self):
        return {g.gid: g for g in self.gates}

    def _var_names(self, n):
        # A, B, C, ... (simple pour NSI)
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if n <= len(letters):
            return list(letters[:n])
        # au-delà, A0, A1, ...
        return [f"A{i}" for i in range(n)]

    def _expr_for_gate_out(
        self,
        gate_gid,
        dst_to_src,
        gid_map,
        src_name_by_gid,
        visiting,
        memo
    ):
        if gate_gid in memo:
            return memo[gate_gid]

        if gate_gid in visiting:
            return ("?", 0)

        visiting.add(gate_gid)
        g = gid_map[gate_gid]

        # SRC
        if g.gtype == "SRC":
            e = (src_name_by_gid[gate_gid], 3)
            memo[gate_gid] = e
            visiting.remove(gate_gid)
            return e

        def get(i):
            key = (gate_gid, i)
            if key not in dst_to_src:
                return ("Ø", 3)
            src_gid, _ = dst_to_src[key]
            return self._expr_for_gate_out(
                src_gid, dst_to_src, gid_map, src_name_by_gid, visiting, memo
            )

        # NOT
        if g.gtype == "NOT":
            a, pa = get(0)
            if pa < 3:
                a = f"({a})"
            e = (self.overline(a), 3)

        # AND
        elif g.gtype == "AND":
            (a, pa), (b, pb) = get(0), get(1)
            if pa < 2:
                a = f"({a})"
            if pb < 2:
                b = f"({b})"
            e = (f"{a}.{b}", 2)

        # OR
        elif g.gtype == "OR":
            (a, pa), (b, pb) = get(0), get(1)
            if pa < 1:
                a = f"({a})"
            if pb < 1:
                b = f"({b})"
            e = (f"{a} + {b}", 1)

        # XOR
        elif g.gtype == "XOR":
            (a, pa), (b, pb) = get(0), get(1)
            if pa < 1:
                a = f"({a})"
            if pb < 1:
                b = f"({b})"
            e = (f"{a} ⊕ {b}", 1)

        # NOR
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
        """
        Évalue la sortie d'une gate (bool ou None) pour une affectation des SRC,
        en remontant les fils. Gestion cycles -> None.
        """
        if gate_gid in memo:
            return memo[gate_gid]

        if gate_gid in visiting:
            return None  # cycle
        visiting.add(gate_gid)

        g = gid_map[gate_gid]

        if g.gtype == "SRC":
            v = assignment_by_gid.get(gate_gid, False)
            memo[gate_gid] = v
            visiting.remove(gate_gid)
            return v

        def val_of_input(i):
            key = (gate_gid, i)
            if key not in dst_to_src:
                return None
            src_gid, _src_pin = dst_to_src[key]
            return self._value_for_gate_out(src_gid, assignment_by_gid, dst_to_src, gid_map, visiting, memo)

        if g.gtype == "NOT":
            a = val_of_input(0)
            v = None if a is None else portes.non(a)
        elif g.gtype == "AND":
            a, b = val_of_input(0), val_of_input(1)
            v = None if (a is None or b is None) else portes.et(a, b)
        elif g.gtype == "OR":
            a, b = val_of_input(0), val_of_input(1)
            v = None if (a is None or b is None) else portes.ou(a, b)
        elif g.gtype == "XOR":
            a, b = val_of_input(0), val_of_input(1)
            v = None if (a is None or b is None) else portes.xor(a, b)
        elif g.gtype == "NOR":
            a, b = val_of_input(0), val_of_input(1)
            v = None if (a is None or b is None) else portes.nor(a, b)
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

        # (sécurité UX) limite pour éviter explosion combinatoire
        if len(srcs) > 8:
            messagebox.showwarning(
                "Table de vérité",
                "Trop d'entrées (SRC) pour afficher une table complète (max conseillé : 8)."
            )
            return

        gid_map = self._gate_by_gid()
        dst_to_src = self._build_dst_to_src()

        order = self._topological_gates(dst_to_src, gid_map)

        # noms A, B, C... associés aux SRC dans l'ordre
        var_names = self._var_names(len(srcs))
        src_name_by_gid = {srcs[i].gid: var_names[i] for i in range(len(srcs))}

        intermediate = []
        for gid in order:
            g = gid_map[gid]
            if g.gtype not in ("SRC", "OUT"):
                expr, _ = self._expr_for_gate_out(
                    gid, dst_to_src, gid_map, src_name_by_gid, set(), {}
                )
                intermediate.append((gid, expr))

        # expressions des OUT (on remonte depuis l'entrée de OUT)
        out_exprs = []

        single_output = (len(outs) == 1)

        for i, outg in enumerate(outs):
            out_name = "S" if single_output else f"OUT{outg.gid}"
            key = (outg.gid, 0)

            if key not in dst_to_src:
                out_exprs.append((out_name, "Ø"))
            else:
                src_gid, _ = dst_to_src[key]
                expr, _ = self._expr_for_gate_out(
                    src_gid, dst_to_src, gid_map, src_name_by_gid, set(), {}
                )
                out_exprs.append((out_name, expr))

        # Fenêtre
        win = Toplevel(self.root)
        win.title("Table de vérité")
        win.geometry("900x600")

        # Expressions (en haut)
        expr_frame = Frame(win, padx=10, pady=10)
        expr_frame.pack(fill=X)

        Label(expr_frame, text="Expression(s) booléenne(s) :", font=("Arial", 12, "bold")).pack(anchor="w")

        expr_text = Text(expr_frame, height=min(6, 2 + len(out_exprs)), wrap="word")
        expr_text.pack(fill=X, pady=(6, 0))
        expr_text.insert("end", "\n".join([f"{name} = {expr}" for name, expr in out_exprs]))
        expr_text.config(state="disabled")

        # Table (Treeview)
        table_frame = Frame(win, padx=10, pady=10)
        table_frame.pack(fill=BOTH, expand=True)

        cols = (
            var_names +
            [expr for _, expr in intermediate] +
            [name for name, _ in out_exprs]
        )
        tree = ttk.Treeview(table_frame, columns=cols, show="headings")
        tree.pack(side=LEFT, fill=BOTH, expand=True)

        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=70, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        tree.configure(yscrollcommand=scrollbar.set)

        # Remplissage truth table
        # On évalue chaque OUT en remontant le graphe, pas besoin d'appeler simulate()
        for bits in product([0, 1], repeat=len(srcs)):
            assignment_by_gid = {srcs[i].gid: bool(bits[i]) for i in range(len(srcs))}
            row = list(bits)

            # --- ÉTAPE 6a : sous-expressions ---
            for gid, _expr in intermediate:
                v = self._value_for_gate_out(
                    gid, assignment_by_gid, dst_to_src, gid_map, set(), {}
                )
                row.append("?" if v is None else ("1" if v else "0"))

            # --- ÉTAPE 6b : sorties ---
            for outg in outs:
                key = (outg.gid, 0)
                if key not in dst_to_src:
                    row.append("?")
                else:
                    src_gid, _ = dst_to_src[key]
                    v = self._value_for_gate_out(
                        src_gid, assignment_by_gid, dst_to_src, gid_map, set(), {}
                    )
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
        # Optionnel : demander confirmation si quelque chose existe
        if self.gates or self.wires:
            ok = messagebox.askyesno(
                "Nouveau circuit",
                "Repartir sur un circuit vierge ?\nLes modifications non sauvegardées seront perdues."
            )
            if not ok:
                return

        self.gates = []
        self.wires = []
        self.next_gid = 1
        self.pending_wire_src = None

        self.canvas.delete("all")
        self.set_mode("select")   # remet aussi le texte de statut


    def on_press(self, event):
        m = self.mode.get()

        wx, wy = self.c2w(event.x, event.y)

        if m == "delete":
            w = self.find_pin_at(wx, wy)
            if w is not None:
                self.delete_wire(w)
                self.simulate()
                return
            g = self.find_gate_at(wx, wy)
            if g is not None:
                self.delete_gate(g)
                self.simulate()
            return

        # Si on est en mode placement ou fil, on garde le comportement actuel
        # Pan si :
        # - on est en mode select
        # - et (on clique dans le vide) OU (on tient Espace)
        if m == "select":
            wx, wy = self.c2w(event.x, event.y)

            pin = self.find_pin_at(wx, wy)
            g = self.find_gate_at(wx, wy)

            if self.space_down or (pin is None and g is None):
                self.panning = True
                self.pan_start = (event.x, event.y)     # coords canvas (pixels)
                self.cam_start = (self.cam_x, self.cam_y)
                return

        # En mode select : si on clique sur un pin, ne pas déplacer (utile pour éviter conflits)
        pin = self.find_pin_at(wx, wy)
        if pin is not None:
            return

        g = self.find_gate_at(wx, wy)
        if g is None:
            return

        self.drag_gate = g
        
        wx, wy = self.c2w(event.x, event.y)
        self.drag_dx = wx - g.x
        self.drag_dy = wy - g.y


    def on_drag(self, event):

        if self.panning:
            dx_pix = event.x - self.pan_start[0]
            dy_pix = event.y - self.pan_start[1]

            # conversion pixels -> monde
            dx_w = dx_pix / self.scale
            dy_w = dy_pix / self.scale

            # on déplace la caméra dans le sens inverse du drag
            self.cam_x = self.cam_start[0] - dx_w
            self.cam_y = self.cam_start[1] - dy_w

            self.redraw_all()
            self.update_colors()
            return


        if self.mode.get() != "select":
            return
        
        if self.drag_gate is None:
            return
        g = self.drag_gate


        wx, wy = self.c2w(event.x, event.y)
        g.x = wx - self.drag_dx
        g.y = wy - self.drag_dy
        g.update_pin_positions()
        self.redraw_all()
        self.update_colors()
        self._update_gate_drawing(g)
        self._update_wires_drawing()


    def on_release(self, event):
        self.drag_gate = None
        self.panning = False

    
    def _update_gate_drawing(self, g: Gate):
        # rectangle
        self.canvas.coords(g.rect_id, g.x, g.y, g.x + GATE_W, g.y + GATE_H)

        # titre
        self.canvas.coords(g.text_id, g.x + GATE_W // 2, g.y + GATE_H // 2)

        # pins
        for p in g.inputs + g.outputs:
            self.canvas.coords(
                p.canvas_id,
                p.x - PIN_R, p.y - PIN_R,
                p.x + PIN_R, p.y + PIN_R
            )

        # bulle inversion (NOT / NOR)
        if getattr(g, "invert_id", None) is not None:
            cx = g.x + GATE_W + INVERT_R
            cy = g.y + GATE_H // 2
            self.canvas.coords(
                g.invert_id,
                cx - INVERT_R, cy - INVERT_R,
                cx + INVERT_R, cy + INVERT_R
            )

        # LED (OUT)
        if getattr(g, "led_id", None) is not None:
            cx, cy = g.x + GATE_W - 18, g.y + GATE_H // 2
            self.canvas.coords(g.led_id, cx - 10, cy - 10, cx + 10, cy + 10)

        # texte valeur (SRC / OUT)
        if getattr(g, "value_text_id", None) is not None:
            if g.gtype == "SRC":
                self.canvas.coords(g.value_text_id, g.x + GATE_W // 2, g.y + GATE_H - 12)
            elif g.gtype == "OUT":
                self.canvas.coords(g.value_text_id, g.x + 20, g.y + GATE_H - 12)


    def _update_wires_drawing(self):
        for w in self.wires:
            x1, y1 = self.w2c(w.src.x, w.src.y)
            x2, y2 = self.w2c(w.dst.x, w.dst.y)
            self.canvas.coords(w.canvas_id, x1, y1, x2, y2)

    
    def _dist_point_to_segment(self, px, py, x1, y1, x2, y2):
        # distance d'un point à un segment
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)

        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        cx = x1 + t * dx
        cy = y1 + t * dy
        return math.hypot(px - cx, py - cy)

    def find_wire_at(self, x, y, threshold=8):
        threshold = threshold / self.scale
        # on teste du plus récent au plus ancien (comme pour les portes)
        for w in reversed(self.wires):
            d = self._dist_point_to_segment(x, y, w.src.x, w.src.y, w.dst.x, w.dst.y)
            if d <= threshold:
                return w
        return None
    
    def delete_wire(self, w: Wire):
        # effacer canvas
        if w.canvas_id is not None:
            self.canvas.delete(w.canvas_id)
        # retirer de la liste
        if w in self.wires:
            self.wires.remove(w)

    def delete_gate(self, g: Gate):
        # supprimer les fils connectés
        to_remove = [w for w in self.wires if (w.src.owner == g or w.dst.owner == g)]
        for w in to_remove:
            self.delete_wire(w)

        # supprimer les éléments canvas de la gate
        if g.rect_id is not None:
            self.canvas.delete(g.rect_id)
        if g.text_id is not None:
            self.canvas.delete(g.text_id)

        for p in g.inputs + g.outputs:
            if p.canvas_id is not None:
                self.canvas.delete(p.canvas_id)

        # bulle inversion
        if getattr(g, "invert_id", None) is not None:
            self.canvas.delete(g.invert_id)

        # LED
        if getattr(g, "led_id", None) is not None:
            self.canvas.delete(g.led_id)

        # texte valeur
        if getattr(g, "value_text_id", None) is not None:
            self.canvas.delete(g.value_text_id)

        # retirer de la liste
        if g in self.gates:
            self.gates.remove(g)

        # sécurité : si on avait commencé un fil depuis cette gate
        if self.pending_wire_src is not None and self.pending_wire_src.owner == g:
            self.pending_wire_src = None

    def w2c(self, x, y):
        # World -> Canvas
        return (x - self.cam_x) * self.scale, (y - self.cam_y) * self.scale

    def c2w(self, x, y):
        # Canvas -> World
        return x / self.scale + self.cam_x, y / self.scale + self.cam_y
    
    def on_zoom_wheel(self, event):
        # event.delta > 0 zoom in, < 0 zoom out
        direction = 1 if event.delta > 0 else -1
        self.on_zoom(direction, event)

    def on_zoom(self, direction, event=None):
        factor = 1.1 if direction > 0 else 1/1.1
        new_scale = self.scale * factor
        new_scale = max(self.scale_min, min(self.scale_max, new_scale))

        if abs(new_scale - self.scale) < 1e-9:
            return

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
        self.update_colors()


def main_ui():
    root = Tk()
    root.geometry("1000x650")
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main_ui()