from datetime import datetime
from pathlib import Path
from hashlib import sha256
from tempfile import TemporaryDirectory
import tarfile, os
from bson import ObjectId
from app.database.collections import (
    col_rule_sets,
    col_rule_set_items,
    col_rule_items,
)

# Store rules in app/data directory
_APP_DIR = Path(__file__).parent.parent
RULE_BASE_DIR = os.getenv("RULE_BASE_DIR")
RULE_ENGINE = os.getenv("RULE_ENGINE", "snort3")
def _compute_sha256(path: Path) -> str:
    h = sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def build_files_for_rule_set(version: str, engine: str | None = None) -> dict:
    """
    Tìm rule_set theo version, lấy rule_set_items + rule_items,
    build file .tgz rồi UPDATE document rule_sets.
    """
    engine = engine or RULE_ENGINE

    rs = col_rule_sets.find_one({"version": version})
    if not rs:
        raise ValueError("rule_set not found")

    # 1) lấy danh sách rule_item_id từ rule_set_items
    set_items = list(
        col_rule_set_items.find(
            {"rule_set_id": rs["_id"]}, {"rule_item_id": 1, "_id": 0}
        )
    )
    rule_item_ids = [si["rule_item_id"] for si in set_items]

    # 2) build file console.rules tạm
    with TemporaryDirectory() as tmpdir:
        rules_file = Path(tmpdir) / "console.rules"
        with open(rules_file, "w", encoding="utf-8") as f:
            cursor = col_rule_items.find(
                {"_id": {"$in": rule_item_ids}}, {"rule_text": 1}
            )
            for doc in cursor:
                text = (doc.get("rule_text") or "").strip()
                if text:
                    f.write(text + "\n")

        # 3) nén thành snort3_<version>.tgz
        out_dir = Path(RULE_BASE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        tgz_path = out_dir / f"{engine}_{version}.tgz"
        with tarfile.open(tgz_path, mode="w:gz") as tar:
            tar.add(rules_file, arcname="console.rules")

    # 4) sha256
    digest = _compute_sha256(tgz_path)

    # 5) update rule_sets
    update = {
        "build_time": datetime.utcnow(),
        "files": {
            "tar": {
                "path": str(tgz_path),
                "sha256": digest,
            }
        },
        "active": False,          # mới build, chưa deploy
        "status": "built",        
    }
    col_rule_sets.update_one({"_id": rs["_id"]}, {"$set": update})
    rs.update(update)
    return rs