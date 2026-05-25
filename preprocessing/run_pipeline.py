"""
Master pipeline runner.

Usage:
  python run_pipeline.py --comunas PENALOLEN SANTIAGO --cargos concejal alcalde
  python run_pipeline.py --all    # process everything (slow)

Steps:
  1. Build locales index from TODOSLOCALES.csv
  2. Build manzana→local weights per commune (centroid method)
  3. Distribute votes to manzanas per commune × cargo
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def run(script: str, extra_args: list[str] = []):
    cmd = [sys.executable, str(HERE / script)] + extra_args
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print('='*60)
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"ERROR: {script} failed with code {result.returncode}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Electoral preprocessing pipeline")
    parser.add_argument("--comunas", nargs="*", help="Communes to process")
    parser.add_argument("--cargos", nargs="*",
                        choices=["concejal", "core", "alcalde", "diputado"],
                        help="Cargo types (default: all)")
    parser.add_argument("--all", action="store_true", help="Process all communes")
    parser.add_argument("--skip-locales", action="store_true",
                        help="Skip step 1 (locales already built)")
    parser.add_argument("--skip-pesos", action="store_true",
                        help="Skip step 2 (pesos already built)")
    args = parser.parse_args()

    if not args.skip_locales:
        run("01_build_locales.py")

    peso_args = []
    if args.comunas:
        peso_args = args.comunas
    if not args.skip_pesos:
        run("02_build_pesos.py", peso_args)

    votos_args = []
    if args.comunas:
        votos_args += ["--comunas"] + args.comunas
    if args.cargos:
        votos_args += ["--cargos"] + args.cargos
    run("03_build_votos.py", votos_args)

    # Steps 4-6: metadata + D'Hondt winners (no per-commune args)
    run("04_build_insights.py")
    run("05_build_distritos.py")
    run("06_build_electos.py")

    print("\n✓ Pipeline complete.")


if __name__ == "__main__":
    main()
