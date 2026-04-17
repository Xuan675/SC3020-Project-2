import io
import tkinter as tk
from tkinter import messagebox, ttk
import re
import textwrap

try:
    from PIL import Image, ImageTk
    import networkx as nx
    import plotly.graph_objects as go
except ImportError:
    Image = None
    ImageTk = None
    nx = None
    go = None
# tkinter interface
class Interface:
    def __init__(self, schemas, pipeline=None):
        self.root = tk.Tk()
        self.root.title("Database Selector")
        self.root.geometry("1600x900")
        self.schemas = schemas
        self.schema = tk.StringVar()
        self.conn = None
        self.pipeline = pipeline

        self.root.columnconfigure(0, weight=1)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(1, weight=1)

        # create select schema component
        self._select_schema()
        self._query_annotation_panel()
        self._query_plan_display()

    # selects database schema
    def _select_schema(self):
        # parent
        select = tk.LabelFrame(self.root)
        select.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5)
        select.columnconfigure(1, weight=1)
        # label for the dropdown
        label = tk.Label(select, text="Choose schema:")
        label.grid(row=0, column=0, padx=5)

        # dropdown component
        dropdown = ttk.Combobox(select, textvariable=self.schema, state="readonly", values=self.schemas)
        dropdown.grid(row=0, column=1, sticky="ew", padx=5)

        # confirm button
        confirm = tk.Button(select, text="confirm", command=self._schema_callback)
        confirm.grid(row=0, column=2, padx=5)
    def _schema_callback(self):
        if not self.schema.get():
            messagebox.showwarning("Schema required", "Please choose a schema first.")
            return
        messagebox.showinfo("Schema selected", f"Using schema/database: {self.schema.get()}")

    def _query_annotation_panel(self):
        self.left = tk.LabelFrame(self.root, text="SQL Query Annotation")
        self.left.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.left.rowconfigure(1, weight=1)
        self.left.rowconfigure(4, weight=1)
        self.left.columnconfigure(0, weight=1)

        tk.Label(self.left, text="Input SQL Query").grid(row=0, column=0, sticky="w", padx=5, pady=(5, 0))
        self.query_text = tk.Text(self.left, height=10, wrap="word")
        self.query_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.query_text.insert(
            "1.0",
            "SELECT * FROM customer c, orders o WHERE c.c_custkey = o.o_custkey",
        )

        run_button = tk.Button(self.left, text="Run Annotation", command=self._run_query_callback)
        run_button.grid(row=2, column=0, sticky="ew", padx=5, pady=5)

        tk.Label(self.left, text="Annotated Output").grid(row=3, column=0, sticky="w", padx=5, pady=(5, 0))
        self.output_text = tk.Text(self.left, height=18, wrap="word")
        self.output_text.grid(row=4, column=0, sticky="nsew", padx=5, pady=5)

    def _run_query_callback(self):
        query = self.query_text.get("1.0", "end").strip()
        if not query:
            messagebox.showwarning("Query required", "Please enter a SQL query.")
            return
        if self.pipeline is None:
            messagebox.showerror("Pipeline missing", "The annotation pipeline is not connected.")
            return

        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", "Running annotation...")
        self.root.update_idletasks()

        try:
            result = self.pipeline(query)
        except Exception as exc:
            self.output_text.delete("1.0", "end")
            self.output_text.insert("1.0", f"Error:\n{exc}")
            return

        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", result["annotated_query"])
        self._try_show_default_plan(result.get("qep"))

    def _try_show_default_plan(self, qep):
        if not qep:
            return
        try:
            self._load_image_callback(self.img, qep)
            self.right.grid()
        except Exception:
            # Annotation output is the core deliverable; plan rendering is optional.
            self.right.grid_remove()

    def _query_plan_display(self):
        # parent
        self.right = tk.LabelFrame(self.root, text="Query Plan Comparison")
        self.right.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        canvas = tk.Canvas(self.right, bg="white", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.right, orient="vertical", command=canvas.yview)
        scroll_content = tk.Frame(canvas, bg="white")
        scroll_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # default img frame
        tk.Label(scroll_content, text="Default plan").pack()
        self.img = tk.Label(scroll_content)
        self.img.pack(fill="x", expand=False, padx=5)

        # merge join frame
        # SET enable_hashjoin = off;
        tk.Label(scroll_content, text="Merge Join").pack()
        self.merge_img = tk.Label(scroll_content)
        self.merge_img.pack(fill="x", expand=False, padx=5)

        # nlj join frame
        # SET enable_hashjoin = off; SET enable_mergejoin = off;
        tk.Label(scroll_content, text="Nested Loop").pack()
        self.nlj_img = tk.Label(scroll_content)
        self.nlj_img.pack(fill="x", expand=False, padx=5)

        self.right.grid_remove()

    def _load_image_callback(self, ref, response):
        render = TreeRender(response)
        img = render.get_img()
        if img == None:
            return

        # convert tree render img to pil then load into the query plan display
        pil_image = Image.open(io.BytesIO(img))
        tk_image = ImageTk.PhotoImage(pil_image)
        ref.config(image=tk_image)
        ref.image = tk_image

    def run(self):
        self.root.mainloop()

# the code below is to generate the execution plans
TREE_LAYOUT = go.Layout(
    showlegend=False,
    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, autorange="reversed"),
    plot_bgcolor='white'
) if go else None
class TreeRender:
    def __init__(self, data):
        if nx is None or go is None:
            raise ImportError("Install Pillow, networkx, plotly, and kaleido to render plan images.")
        # directed graph
        self.graph = nx.DiGraph()

        # always add EXPLAIN (FORMAT JSON)
        self.data = data[0]

        # need labels for nodes
        self.labels = {}
        self.depth = 0
    
    def _clean_condition_label(self, text):
        if not text:
            return ""
        text = re.sub(r'::[\w\s]+', '', text)
        text = re.sub(r'\(([^()]+)\)\s*=\s*\(([^()]+)\)', r'\1 = \2', text)
        lines = text.split(' AND ')
        wrapped_lines = []
        for line in lines:
            wrapped_lines.append("<br>".join(textwrap.wrap(line, width=25)))
        
        return " AND <br>".join(wrapped_lines)

    def _get_label(self, node):
        ntype = "unkown type"
        if "Node Type" in node:
            ntype = node["Node Type"]
        cost = 0
        if "Total Cost" in node:
            cost = node["Total Cost"]
        rows = 1
        if "Plan Rows" in node:
            rows = node["Plan Rows"]
        relation = ""
        if "Relation Name" in node:
            relation = node["Relation Name"]
            
        string = f"{ntype}<br>"
        if relation:
            string += f"Relation: <br>{relation}<br>"
        string += f"Rows: {rows}<br>"
        string += f"Cost: {cost} ms<br>"
        string += "<br>"
        if "Hash Cond" in node:
            string += f"Cond:<br> {self._clean_condition_label(node['Hash Cond'])}<br>"
        if "Index Cond" in node:
            string += f"Cond:<br> {self._clean_condition_label(node['Index Cond'])}<br>"
        if "Filter" in node:
            string += f"Filter<br>: {self._clean_condition_label(node['Filter'])}<br>"
        return {
            "label": string,
        }
    def _dfs(self, node, parent=None, depth=0):
        nid = str(id(node))
        plans = []
        if "Plans" in node:
            plans = node["Plans"]
    
        # connect current node to parent
        self.labels[nid] = self._get_label(node)
        # depth is for the networkx graph to show different levels
        self.graph.add_node(nid, subset=depth)
        if depth > self.depth:
            self.depth = depth
        if parent:
            self.graph.add_edge(nid, parent)
        
        # recurse through all children
        for c in plans:
            self._dfs(c, nid, depth + 1)

        if "InitPlan" in node:
            # mutliple init plans
            if isinstance(node["InitPlan"], list):
                for p in node["InitPlan"]:
                    self._dfs(p, nid, depth + 1)
            else:
                # 1 init plan
                self._dfs(node["InitPlan"], nid, depth + 1)
        
        if "SubPlan" in node:
            # mutliple subplans plans
            if isinstance(node["SubPlan"], list):
                for p in node["SubPlan"]:
                    self._dfs(p, nid, depth + 1)
            else:
                # 1 subplans 
                self._dfs(node["SubPlan"], nid, depth + 1)
    def _create_row_border(self, y_position):
        rects = []
        y_list = list(set(y_position))
        y_list.sort()
        for d in range(len(y_list) - 1):
            rects.append({
                "type": "line",
                "xref": "paper",
                "yref": "y",
                "x0": 0,
                "x1": 1,
                "y0": (y_list[d] + y_list[d+1]) / 2,
                "y1": (y_list[d] + y_list[d+1]) / 2,
                "line": {
                    "dash": "dot"
                },
                "layer": "below"
            })
        return rects

    def _generate_diagram(self):
        p = nx.multipartite_layout(self.graph)
        edges = []
        # plot edge lines
        for edge in self.graph.edges():
            xf = p[edge[0]][1]
            yf = p[edge[0]][0]
            xt = p[edge[1]][1]
            yt = p[edge[1]][0]
            line = go.Scatter(x=[xf, xt], y=[yf, yt], mode="lines")
            edges.append(line)
        # render nodes
        x_list = []
        y_list = []
        label_list = []
        size_list = []
        for nid in self.graph.nodes():
            x_list.append(p[nid][1])
            y_list.append(p[nid][0])
            label_list.append(self.labels[nid]["label"])
            # make the node dynamic for better ux
            size_list.append(10 + (self.labels[nid]["label"].count('<br>') + 1) * 10)
        vertices = go.Scatter(x=x_list, 
                              y=y_list, 
                              mode="markers+text", 
                              text=label_list, 
                              textposition="middle center", 
                              hoverinfo="none",
                              textfont={
                                "size": 8
                              },
                              marker={
                                "symbol": "square",
                                "size": size_list,
                                "color": "white",
                                "opacity": 1,
                                "line": {
                                    "color": "black",
                                    "width": 1
                                }
                              }
                            )

        # edge first then nodes (plotly format)
        combined = []
        for line in edges:
            combined.append(line)
        combined.append(vertices)
        fig = go.Figure(data=combined, layout=TREE_LAYOUT)
        border = self._create_row_border(vertices["y"])
        fig.update_layout(shapes=border)
        return fig
    
    def _load(self):
        if "Plan" not in self.data:
            return 
        root = self.data["Plan"]
        if root:
            self._dfs(root)
    
    def _render(self):
        self._load()
        return self._generate_diagram()
    
    def get_img(self):
        if Image is None or ImageTk is None:
            raise ImportError("Install Pillow to load rendered plan images.")
        fig = self._render()
        img = fig.to_image(format="png", scale=1, width=900, height= 506.25)
        return img
