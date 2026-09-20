"""
Traceability final check — ensures every REQ in BUILD_STATE has test and doc.
Part of P21 audit prep.
"""
import json
import pathlib
from typing import Dict, Any, List

def check_traceability(build_state_path: str = "BUILD_STATE.json") -> Dict[str,Any]:
    p = pathlib.Path(build_state_path)
    if not p.exists():
        return {"ok": False, "missing": ["BUILD_STATE.json not found"]}
    data = json.loads(p.read_text())
    reqs = data.get("requirements", {})
    missing_tests=[]
    missing_evidence=[]
    unverified=[]
    for rid, info in reqs.items():
        tests = info.get("tests", [])
        evidence = info.get("evidence", "")
        status = info.get("status","")
        if not tests or tests == ["TBD"]:
            missing_tests.append(rid)
        if not evidence:
            missing_evidence.append(rid)
        if status != "CODE_VERIFIED":
            unverified.append(rid)
    ok = not missing_tests and not missing_evidence and not unverified
    return {
        "ok": ok,
        "total_reqs": len(reqs),
        "missing_tests": missing_tests,
        "missing_evidence": missing_evidence,
        "unverified": unverified,
        "note": "Traceability per 13.5: every REQ needs at least one test and evidence path"
    }

def generate_feature_status_stub() -> str:
    """
    Stub generator for FEATURE_STATUS.md: lists CODE_VERIFIED count.
    Real generator uses scripts but here we provide simplified check.
    """
    check = check_traceability()
    total = check["total_reqs"]
    unverified = len(check["unverified"])
    verified = total - unverified
    return f"FEATURE_STATUS: {verified}/{total} CODE_VERIFIED, {unverified} remaining"
