from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "tpch-tools" / "dbgen"
FILES = [
    "customer.tbl",
    "lineitem.tbl",
    "nation.tbl",
    "orders.tbl",
    "part.tbl",
    "partsupp.tbl",
    "region.tbl",
    "supplier.tbl",
]


def convert_tbl_to_csv(input_file: Path, output_file: Path) -> None:
    with input_file.open("r", encoding="utf-8") as fin, output_file.open(
        "w", encoding="utf-8", newline=""
    ) as fout:
        for line in fin:
            if line.endswith("|\n"):
                fout.write(line[:-2] + "\n")
            elif line.endswith("|"):
                fout.write(line[:-1])
            else:
                fout.write(line)


def main() -> None:
    missing_files = [name for name in FILES if not (DATA_DIR / name).exists()]
    if missing_files:
        missing = ", ".join(missing_files)
        raise FileNotFoundError(
            f"Missing .tbl files in {DATA_DIR}: {missing}. "
            "Generate the TPC-H data first before running this script."
        )

    for name in FILES:
        input_file = DATA_DIR / name
        output_file = DATA_DIR / name.replace(".tbl", ".csv")
        convert_tbl_to_csv(input_file, output_file)

    print(f"Converted {len(FILES)} files in {DATA_DIR}")


if __name__ == "__main__":
    main()
