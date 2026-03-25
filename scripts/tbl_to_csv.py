from pathlib import Path

data_dir = Path(r"C:\Dev\sc3020-project-2\tpch-tools\dbgen")

files = [
    "customer.tbl",
    "lineitem.tbl",
    "nation.tbl",
    "orders.tbl",
    "part.tbl",
    "partsupp.tbl",
    "region.tbl",
    "supplier.tbl"
]

for file in files:
    input_file = data_dir / file
    output_file = data_dir / file.replace(".tbl", ".csv")

    with open(input_file, "r", encoding="utf-8") as fin, open(output_file, "w", encoding="utf-8", newline="") as fout:
        for line in fin:
            if line.endswith("|\n"):
                fout.write(line[:-2] + "\n")
            elif line.endswith("|"):
                fout.write(line[:-1])
            else:
                fout.write(line)

print("Done.")