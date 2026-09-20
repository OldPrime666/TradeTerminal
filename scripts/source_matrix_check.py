#!/usr/bin/env python3
"""
scripts/source_matrix_check.py — Appendix A matrix verifier (FBK-01..10, CAP-01..20)
- Reads config/sources.yaml (single source of truth per Appendix A).
- Verifies per-capability: PRIMARY + >=3 free fallbacks, V/U tags, keyless-complete (FBK-07).
- Optional live probing (checks TLS reachability, V->expected ok) — but never circumvents blocks.
- Generates DATA_SOURCE_MATRIX.md if --generate-md.
"""
import argparse, sys, yaml, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_YAML = ROOT / "config" / "sources.yaml"
MD_OUT = ROOT / "DATA_SOURCE_MATRIX.md"

def load_yaml():
    with open(SRC_YAML, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def check_cap(cap_id: str, cap: dict, min_fallbacks: int):
    errors = []
    primary = cap.get("primary")
    fallbacks = cap.get("fallbacks", [])
    chain = cap.get("chain", [])
    if not primary:
        errors.append(f"{cap_id}: missing primary")
    if len(fallbacks) < min_fallbacks:
        errors.append(f"{cap_id}: only {len(fallbacks)} fallbacks, need >= {min_fallbacks} (FBK-01)")
    for i, entry in enumerate(chain):
        if "tag" not in entry:
            errors.append(f"{cap_id} chain[{i}]: missing tag V/U")
        elif entry["tag"] not in ("V","U"):
            errors.append(f"{cap_id} chain[{i}]: invalid tag {entry['tag']}")
    has_keyless = any((e.get("auth") is False) or (e.get("auth") is None) or (str(e.get("auth")).lower()=="false") for e in chain)
    if not has_keyless and chain:
        has_keyless = any(e.get("auth") not in ("key","token","webhook") for e in chain)
    if not has_keyless:
        errors.append(f"{cap_id}: no keyless path — violates FBK-07 (must work without keys)")
    return errors

def probe_live(data, timeout=4):
    import ssl, urllib.request, urllib.error
    results = {}
    venues = {v["id"]: v for v in data.get("venues", [])}
    for vid, v in venues.items():
        base = v.get("rest_base") or v.get("ws_base") or ""
        host = base.replace("https://","").replace("wss://","").split("/")[0].split(":")[0]
        if not host:
            results[vid] = "no_host"
            continue
        try:
            ctx = ssl.create_default_context()
            url = v.get("rest_base","")
            if not url:
                results[vid] = "no_rest_base"
                continue
            req = urllib.request.Request(url, headers={"User-Agent":"GCIS-probe/1.0"})
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                code = resp.getcode()
                results[vid] = f"reachable:{code}"
        except urllib.error.HTTPError as e:
            if e.code in (451,403):
                results[vid] = f"RESTRICTED_{e.code}"
            else:
                results[vid] = f"http_{e.code}"
        except Exception as e:
            results[vid] = f"probe_failed:{type(e).__name__}"
    return results

def generate_md(data, probe_results=None):
    lines = []
    lines.append("# DATA_SOURCE_MATRIX — Appendix A (Generated)")
    lines.append("")
    lines.append(f"_Generated: {datetime.datetime.now(datetime.timezone.utc).isoformat()} from `config/sources.yaml` (single source of truth). Tags V=verified 2026-09-20, U=unverified/candidate. FBK-07 keyless-complete._")
    lines.append("")
    lines.append("| Capability | Primary | Fallbacks (free, ranked) | Keyless? | Tag chain | Notes |")
    lines.append("|---|---|---|---|---|---|")
    caps = data.get("capabilities", {})
    for cap_id, cap in sorted(caps.items()):
        primary = cap.get("primary","—")
        fallbacks = ", ".join(str(x) for x in cap.get("fallbacks",[]))
        # include endpoint/method/file for auditability
        parts = []
        for e in cap.get("chain",[]):
            prov = e.get('provider','?')
            tag = e.get('tag','?')
            detail = e.get('endpoint') or e.get('method') or e.get('path') or e.get('file') or e.get('feeds') or ""
            if detail:
                parts.append(f"{prov}:{tag} ({detail})")
            else:
                parts.append(f"{prov}:{tag}")
        chain_tags = ", ".join(parts)
        has_keyless = any(e.get("auth") is False or e.get("auth") is None for e in cap.get("chain",[]))
        keyless_str = "YES (FBK-07)" if has_keyless else "NO — violation"
        notes = ""
        if probe_results:
            pr = probe_results.get(primary, "")
            if pr:
                notes = pr
        lines.append(f"| {cap_id} | {primary} | {fallbacks} | {keyless_str} | {chain_tags} | {notes} |")
    lines.append("")
    lines.append("## Venues")
    lines.append("")
    lines.append("| Venue | REST base | WS base | Limits | Tag |")
    lines.append("|---|---|---|---|---|")
    for v in data.get("venues",[]):
        lines.append(f"| {v.get('id')} | {v.get('rest_base','—')} | {v.get('ws_base','—')} | {v.get('limits','—')} | {v.get('tag','—')} |")
    lines.append("")
    lines.append("## Infrastructure fallbacks")
    infra = data.get("infrastructure",{})
    for k, lst in infra.items():
        lines.append(f"- **{k}**: " + " → ".join(str(x) for x in lst))
    lines.append("")
    lines.append("## Candidate pool (replacements if a free source dies)")
    lines.append("")
    for c in data.get("candidate_pool",[]):
        lines.append(f"- {c}")
    lines.append("")
    lines.append("> Rule: never circumvent geo-block (INV-14/SEC-09). If primary returns 451/403 → status RESTRICTED, automatic failover after hysteresis (FBK-05). Every day `source_matrix_check` reprobes V/U (FBK-10).")
    return "\n".join(lines)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assert-min-fallbacks", type=int, default=3)
    ap.add_argument("--generate-md", action="store_true")
    ap.add_argument("--probe-live", action="store_true")
    args = ap.parse_args()

    data = load_yaml()
    caps = data.get("capabilities", {})
    all_errors = []
    for cap_id, cap in caps.items():
        errs = check_cap(cap_id, cap, args.assert_min_fallbacks)
        all_errors.extend(errs)
        status = "OK" if not errs else "FAIL"
        tag_chain = ", ".join(e.get("tag","?") for e in cap.get("chain",[]))
        keyless_ok = not any('keyless' in e for e in errs)
        print(f"[{status}] {cap_id}: primary={cap.get('primary')} fallbacks={len(cap.get('fallbacks',[]))} tags=[{tag_chain}] keyless={'yes' if keyless_ok else 'no'}")
        for e in errs:
            print(f"  - {e}")

    probe_results = None
    if args.probe_live:
        print("\nProbing live venues (honest, no circumvention)...")
        probe_results = probe_live(data)
        for k,v in probe_results.items():
            print(f"  {k}: {v}")

    md = generate_md(data, probe_results)
    MD_OUT.write_text(md, encoding="utf-8")
    print(f"\nWrote {MD_OUT}")
    if args.generate_md:
        # already wrote
        pass

    if all_errors:
        print(f"\nFAILED — {len(all_errors)} violation(s) (FBK-01/07). Fix config/sources.yaml.")
        sys.exit(1)
    else:
        print(f"\nPASSED — all {len(caps)} capabilities have >= {args.assert_min_fallbacks} free fallbacks and keyless path (FBK-01/07).")

if __name__ == "__main__":
    main()
