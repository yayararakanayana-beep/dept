from __future__ import annotations
import argparse
import json
from . import build_relation_field_prediction_coordinates, validate_relation_field_prediction_coordinates


def main() -> int:
    parser=argparse.ArgumentParser(description="P2-2 continuous relation-field coordinates")
    sub=parser.add_subparsers(dest="command",required=True)
    build=sub.add_parser("build");build.add_argument("p1_series");build.add_argument("output")
    validate=sub.add_parser("validate");validate.add_argument("p2_series");validate.add_argument("p1_series")
    args=parser.parse_args()
    if args.command=="build":
        print(build_relation_field_prediction_coordinates(args.p1_series,args.output))
    else:
        print(json.dumps(validate_relation_field_prediction_coordinates(args.p2_series,args.p1_series),ensure_ascii=False,indent=2,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
