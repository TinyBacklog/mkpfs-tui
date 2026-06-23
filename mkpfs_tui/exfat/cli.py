"""The ``mkpfs-tui build-exfat`` CLI subcommand (shares run_build with the TUI)."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from mkpfs_tui.config import load
from mkpfs_tui.deploy.deployer import DeployOptions, run_deploy
from mkpfs_tui.deploy.ftp import FtpTarget
from mkpfs_tui.exfat.builder import BuildOptions, run_build
from mkpfs_tui.exfat.naming import PRESETS, read_param, suggest_filename, suggest_label
from mkpfs_tui.exfat.sizing import CLUSTER_CHOICES
from mkpfs_tui.exfat.tools import preflight


def build_argv_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``build-exfat``."""
    cfg = load()
    parser = argparse.ArgumentParser(
        prog="mkpfs-tui build-exfat",
        description="Build a PS5 dump folder into an exFAT image for ShadowMountPlus.",
    )
    parser.add_argument("dump", type=Path, help="dump folder (its contents go to the image root)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="output .exfat path (default: derived from param.json + preset, next to the dump)",
    )
    parser.add_argument(
        "--cluster",
        choices=list(CLUSTER_CHOICES),
        default="auto",
        help="cluster size (default: auto — 32K for small files, else 64K)",
    )
    parser.add_argument("--label", default=None, help="volume label (default: derived from param.json)")
    parser.add_argument(
        "--preset", choices=list(PRESETS), default="version", help="filename preset (default: version)"
    )
    parser.add_argument("--lower", action="store_true", help="lowercase the derived filename")
    parser.add_argument("--no-verify", dest="verify", action="store_false", help="skip the fsck.exfat check")
    parser.add_argument("--deploy", action="store_true", help="after building, upload the image to a PS5 over FTP")
    parser.add_argument("--host", default=cfg.host or None, help="PS5 IP/host (with --deploy)")
    parser.add_argument("--port", type=int, default=cfg.port, help="FTP port (with --deploy)")
    parser.add_argument("--path", default=cfg.path, help="remote directory (with --deploy)")
    parser.add_argument("--user", default=cfg.user, help="FTP user (with --deploy)")
    return parser


def _deploy_after_build(args: argparse.Namespace, output: Path) -> int:
    """Upload a freshly built image; returns an exit code."""
    if not args.host:
        print("Built, but --deploy needs --host (or a configured host).")
        return 1
    password = getpass.getpass("FTP password (blank for anonymous): ")
    target = FtpTarget(host=args.host, port=args.port, path=args.path, user=args.user, password=password)
    result = run_deploy(DeployOptions(local_file=output, target=target, overwrite=True))
    if result.ok:
        print(f"Deployed {result.remote_path} ({result.bytes_sent} bytes)")
        return 0
    print(f"Deploy failed: {'; '.join(result.errors) or 'unknown error'}")
    return 1


def main(argv: list[str]) -> int:
    """Run build-exfat (optionally chaining a deploy). Returns 0 on success, else 1."""
    args = build_argv_parser().parse_args(argv)
    missing = preflight(verify=args.verify)
    if missing:
        print("Missing required tools:")
        for line in missing:
            print(f"  - {line}")
        return 1
    info = read_param(args.dump)
    output = args.output or (
        args.dump.parent / suggest_filename(info, args.dump, preset=args.preset, lowercase=args.lower)
    )
    label = args.label if args.label is not None else suggest_label(info, args.dump)
    opts = BuildOptions(
        dump=args.dump,
        output=output,
        label=label,
        cluster_override=CLUSTER_CHOICES[args.cluster],
        verify=args.verify,
    )
    result = run_build(opts)
    if not result.ok:
        print(f"Build failed: {'; '.join(result.errors)}")
        return 1
    print(
        f"Built {result.output_path} "
        f"({result.size_mb} MB, cluster {result.cluster_bytes // 1024}K, label {result.label})"
    )
    if args.deploy:
        return _deploy_after_build(args, output)
    return 0
