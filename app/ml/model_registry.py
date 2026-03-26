# app/ml/model_registry.py
from __future__ import annotations

import json
import re
import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import joblib


# ============================================================
# Katalogi modeli (zgodnie z ustaleniami)
# ============================================================

def project_root() -> Path:
    # .../app/ml/model_registry.py -> parents[0]=ml, [1]=app, [2]=root
    return Path(__file__).resolve().parents[2]


def models_root() -> Path:
    return project_root() / "app" / "ml" / "models"


def dir_test() -> Path:
    return models_root() / "test"


def dir_prd() -> Path:
    return models_root() / "prd"


def dir_prezentation() -> Path:
    return models_root() / "prezentation"


def ensure_dirs() -> None:
    for d in (dir_test(), dir_prd(), dir_prezentation()):
        d.mkdir(parents=True, exist_ok=True)


# ============================================================
# Nazwa pliku (krótka + komentarz + limit długości)
# ============================================================

def _sanitize_comment(comment: str, max_len: int = 24) -> str:
    """
    Komentarz użytkownika do filename:
    - tylko [a-zA-Z0-9_-]
    - spacje -> '-'
    - limit długości
    """
    if not comment:
        return ""
    s = comment.strip().replace(" ", "-")
    s = re.sub(r"[^a-zA-Z0-9_\-]+", "", s)
    return s[:max_len]


def _short_model_name(model_name: str) -> str:
    """
    Krótki kod modelu do nazwy pliku (żeby filename nie puchł).
    """
    m = (model_name or "").strip().lower()
    mapping = {
        "logistic regression": "LR",
        "random forest": "RF",
        "gradient boosting": "GB",
        "dummy": "DUMMY",
    }
    return mapping.get(m, (model_name[:10] if model_name else "MODEL").upper().replace(" ", ""))


def filters_hash(filters_active: Dict[str, bool], min_conditions: Optional[int]) -> str:
    """
    Do filename dajemy tylko hash filtrów, bo lista będzie rosła i filename ma być krótki.
    Pełna informacja i tak jest w JSON i w tabeli.
    """
    payload = {
        "filters_active": {k: bool(v) for k, v in sorted(filters_active.items())},
        "min_conditions": min_conditions,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:8]


def build_model_filename(
    *,
    model_name: str,
    target_shortcode: str,
    window_sessions: Optional[int],
    max_signals: Optional[int],
    top_score_pct: Optional[float],
    filters_h: str,
    comment: str,
    ts: Optional[datetime] = None,
    max_total_len: int = 120,
) -> str:
    """
    Format (krótki, ale informacyjny):
    YYYYMMDD_HHMM__<MODEL>__y=<T>__w=<w>__k=<k>__p=<pct>__f=<hash>__c=<comment>.joblib

    Jeśli brakuje w/k/p (np. user nie wybierał w tab2) -> wpisujemy 'na'.
    """
    ts = ts or datetime.now()
    dt = ts.strftime("%Y%m%d_%H%M")
    m = _short_model_name(model_name)
    c = _sanitize_comment(comment)

    w = "na" if window_sessions is None else str(int(window_sessions))
    k = "na" if max_signals is None else str(int(max_signals))
    p = "na" if top_score_pct is None else (f"{top_score_pct:g}".replace(".", "_"))

    base = f"{dt}__{m}__y={target_shortcode}__w={w}__k={k}__p={p}__f={filters_h}"
    if c:
        base += f"__c={c}"
    fname = base + ".joblib"

    # Twardy limit długości (żeby Windows/FS nie bolało i żeby UX był czytelny)
    if len(fname) > max_total_len:
        # obcinamy komentarz jako pierwszy
        if c:
            overflow = len(fname) - max_total_len
            c2 = c[:-overflow] if overflow < len(c) else ""
            base2 = f"{dt}__{m}__y={target_shortcode}__w={w}__k={k}__p={p}__f={filters_h}"
            if c2:
                base2 += f"__c={c2}"
            fname = base2 + ".joblib"
        # jeśli nadal za długie (skrajne) -> obcinamy model
        if len(fname) > max_total_len:
            m2 = m[:6]
            base3 = f"{dt}__{m2}__y={target_shortcode}__w={w}__k={k}__p={p}__f={filters_h}"
            if c:
                base3 += f"__c={_sanitize_comment(comment, max_len=12)}"
            fname = (base3 + ".joblib")[:max_total_len]

    return fname


# ============================================================
# Zapis artefaktów (joblib + json)
# ============================================================

def save_model_and_meta(
    *,
    out_dir: Path,
    filename_joblib: str,
    model_obj: Any,
    meta: Dict[str, Any],
) -> Tuple[Path, Path]:
    """
    Zapisuje:
    - out_dir/<filename_joblib>  (joblib)
    - out_dir/<stem>.json        (metadata)

    WAŻNE:
    - w JSON zapisujemy ścieżki względne względem katalogu projektu,
      żeby artefakty działały po wdrożeniu (np. w chmurze / na innym serwerze).
    """
    ensure_dirs()
    out_dir.mkdir(parents=True, exist_ok=True)

    fp_model = out_dir / filename_joblib
    fp_meta = fp_model.with_suffix(".json")

    # 1) Zapis modelu
    joblib.dump(model_obj, fp_model)

    # 2) Ścieżki względne (platform-independent)
    root = project_root()
    try:
        rel_model = fp_model.resolve().relative_to(root.resolve())
        rel_meta = fp_meta.resolve().relative_to(root.resolve())
    except Exception:
        # Fallback: gdyby relative_to nie zadziałało (np. różne dyski), użyjemy relpath.
        # W praktyce w projekcie powinno zadziałać relative_to.
        import os
        rel_model = Path(os.path.relpath(fp_model.resolve(), root.resolve()))
        rel_meta = Path(os.path.relpath(fp_meta.resolve(), root.resolve()))

    # Zapisujemy POSIX-like, żeby JSON był przenośny (Windows/Linux)
    rel_model_str = rel_model.as_posix()
    rel_meta_str = rel_meta.as_posix()

    # 3) Zapis metadanych
    meta = dict(meta)
    meta["model_file"] = rel_model_str
    meta["meta_file"] = rel_meta_str

    fp_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    return fp_model, fp_meta


# ============================================================
# Listowanie modeli (tabela dla UI)
# ============================================================

@dataclass(frozen=True)
class ModelCatalog:
    key: str
    label: str
    path: Path


def available_catalogs() -> List[ModelCatalog]:
    return [
        ModelCatalog("test", "TEST (robocze)", dir_test()),
        ModelCatalog("prd", "PRD (produkcyjne)", dir_prd()),
        ModelCatalog("prezentation", "PREZENTATION (git)", dir_prezentation()),
    ]


def _load_meta(fp_json: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(fp_json.read_text(encoding="utf-8"))
    except Exception:
        return None


def list_models_from_dir(d: Path) -> List[Dict[str, Any]]:
    """
    Zwraca listę metadanych z plików *.json.
    """
    if not d.exists():
        return []
    out: List[Dict[str, Any]] = []
    for fp in sorted(d.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        meta = _load_meta(fp)
        if meta is None:
            continue
        meta["_meta_fp"] = str(fp)
        out.append(meta)
    return out


def models_table(metas: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Buduje płaską tabelę do Streamlit.
    Dynamiczne kolumny filtrów: każdy filtr jako kolumna, w wierszu "X"/"".
    """
    rows: List[Dict[str, Any]] = []
    all_filter_keys: List[str] = []

    # zbierz pełny zestaw filtrów z metadanych (żeby kolumny były dynamiczne)
    for m in metas:
        fq = (m.get("quality_filters") or {})
        for k in fq.keys():
            if k not in all_filter_keys:
                all_filter_keys.append(k)

    for m in metas:
        r: Dict[str, Any] = {}
        r["created_at"] = m.get("created_at")
        r["filename"] = Path(m.get("model_file", "")).name if m.get("model_file") else ""
        r["comment"] = m.get("comment", "")
        r["model_name"] = m.get("model_name")
        r["target"] = m.get("target")
        rp = m.get("rank_params") or {}
        r["w"] = rp.get("window_sessions")
        r["k"] = rp.get("max_signals")
        r["p"] = rp.get("top_score_pct")
        r["min_conditions"] = (m.get("min_conditions") if m.get("min_conditions") is not None else "")

        # VAL ex-post (żebyś widział, jaki był efekt przy zapisie)
        vm = m.get("val_summary") or {}
        r["val_prec"] = vm.get("precision")
        r["val_n"] = vm.get("n_selected")
        r["val_ret20"] = vm.get("avg_ret_20")
        r["val_ret60"] = vm.get("avg_ret_60")
        r["val_ret120"] = vm.get("avg_ret_120")

        # dynamiczne filtry jako kolumny (wariant B)
        qf = (m.get("quality_filters") or {})
        for fk in all_filter_keys:
            r[f"F:{fk}"] = "X" if bool(qf.get(fk)) else ""

        r["_meta_fp"] = m.get("_meta_fp", "")
        rows.append(r)

    df = pd.DataFrame(rows)
    return df