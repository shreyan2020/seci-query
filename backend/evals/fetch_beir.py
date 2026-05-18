from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict


BEIR_BASE_URL = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets"
KNOWN_MD5 = {
    "scifact": "5f7d1de60b170fc8027bb7898e2efca1",
    "trec-covid": "ce62140cb23feb9becf6270d0d1fe6d1",
    "nfcorpus": "a89dba18a62ef92f7d323ec890a0d38d",
}


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_beir_dataset(dataset: str, output_root: str | Path, force: bool = False, verify_md5: bool = True) -> Dict[str, str]:
    dataset_name = dataset.strip()
    if not dataset_name:
        raise ValueError("Dataset name cannot be empty.")
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    target_dir = root / dataset_name
    zip_path = root / f"{dataset_name}.zip"
    if target_dir.exists() and not force:
        return {"dataset": dataset_name, "status": "exists", "path": str(target_dir)}

    url = f"{BEIR_BASE_URL}/{dataset_name}.zip"
    print(json.dumps({"event": "download_start", "dataset": dataset_name, "url": url, "zip_path": str(zip_path)}))
    urllib.request.urlretrieve(url, zip_path)

    expected_md5 = KNOWN_MD5.get(dataset_name)
    if verify_md5 and expected_md5:
        actual_md5 = _md5(zip_path)
        if actual_md5 != expected_md5:
            raise ValueError(f"MD5 mismatch for {dataset_name}: expected {expected_md5}, got {actual_md5}")

    if target_dir.exists() and force:
        shutil.rmtree(target_dir)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(root)
    if not target_dir.exists():
        raise FileNotFoundError(f"Expected extracted dataset directory was not created: {target_dir}")
    return {"dataset": dataset_name, "status": "downloaded", "path": str(target_dir), "zip_path": str(zip_path)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download public BEIR benchmark datasets into the local benchmark layout.")
    parser.add_argument("--datasets", nargs="+", default=["scifact"], help="BEIR dataset names, e.g. scifact trec-covid nfcorpus.")
    parser.add_argument("--output-root", default="data/benchmarks/beir", help="Directory where datasets should be extracted.")
    parser.add_argument("--force", action="store_true", help="Re-download and replace existing dataset directories.")
    parser.add_argument("--skip-md5", action="store_true", help="Skip MD5 verification for known datasets.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    results = [
        fetch_beir_dataset(dataset, args.output_root, force=args.force, verify_md5=not args.skip_md5)
        for dataset in args.datasets
    ]
    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()
