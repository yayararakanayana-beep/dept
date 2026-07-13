from __future__ import annotations
import argparse,json
from . import build_relation_field_prediction_p2_precursor_audit,validate_relation_field_prediction_p2_precursor_audit

def main()->int:
    parser=argparse.ArgumentParser(description="P2-4 continuous-coordinate precursor audit")
    sub=parser.add_subparsers(dest="command",required=True)
    build=sub.add_parser("build");build.add_argument("case_manifest");build.add_argument("output")
    validate=sub.add_parser("validate");validate.add_argument("audit_dir");validate.add_argument("case_manifest")
    args=parser.parse_args()
    if args.command=="build":print(build_relation_field_prediction_p2_precursor_audit(args.case_manifest,args.output))
    else:print(json.dumps(validate_relation_field_prediction_p2_precursor_audit(args.audit_dir,args.case_manifest),ensure_ascii=False,indent=2,sort_keys=True))
    return 0
if __name__=="__main__":raise SystemExit(main())
