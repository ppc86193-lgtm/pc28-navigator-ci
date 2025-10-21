#!/usr/bin/env python3
import argparse
import asyncio


def _run_async(async_fn):
    return asyncio.run(async_fn())


def main():
    parser = argparse.ArgumentParser(
        prog="pc28-deploy",
        description="PC28 deployment orchestrator (consolidated CLI)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("prepare", help="Prepare Google Cloud resources")
    sub.add_parser("cloudbuild", help="Build & deploy via Cloud Build")
    sub.add_parser("cloudbuild-fix", help="Apply Cloud Build fixes flow")
    sub.add_parser("real", help="Real end-to-end cloud deployment")
    sub.add_parser("immediate", help="Immediate minimal deployment")
    sub.add_parser("master", help="Master controller deployment flow")

    args = parser.parse_args()

    if args.cmd == "prepare":
        from google_cloud_ai_deployment import main as gcloud_prep

        gcloud_prep()
        return

    if args.cmd == "cloudbuild":
        from cloud_build_deployer import main as cloudbuild_main

        _run_async(cloudbuild_main)
        return

    if args.cmd == "cloudbuild-fix":
        from cloud_build_fix_agent import main as cloudbuild_fix

        _run_async(cloudbuild_fix)
        return

    if args.cmd == "real":
        from real_cloud_deployer import main as real_deploy

        _run_async(real_deploy)
        return

    if args.cmd == "immediate":
        from immediate_google_deployment import main as immediate_deploy

        _run_async(immediate_deploy)
        return

    if args.cmd == "master":
        from cloud_deployment_master import main as master_flow

        _run_async(master_flow)
        return


if __name__ == "__main__":
    main()
