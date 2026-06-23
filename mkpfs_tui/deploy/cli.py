"""The ``mkpfs-tui deploy`` CLI subcommand (shares run_deploy with the TUI)."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from mkpfs_tui.config import load
from mkpfs_tui.deploy.deployer import DeployOptions, run_deploy
from mkpfs_tui.deploy.ftp import FtpTarget


def deploy_argv_parser() -> argparse.ArgumentParser:
    """Build the argument parser for ``deploy`` (config supplies defaults)."""
    cfg = load()
    parser = argparse.ArgumentParser(
        prog="mkpfs-tui deploy",
        description="Push a file to a jailbroken PS5 over FTP (e.g. a built .exfat).",
    )
    parser.add_argument("file", type=Path, help="local file to upload")
    parser.add_argument("--host", default=cfg.host or None, help="PS5 IP/host")
    parser.add_argument("--port", type=int, default=cfg.port, help=f"FTP port (default {cfg.port})")
    parser.add_argument("--path", default=cfg.path, help=f"remote directory (default {cfg.path})")
    parser.add_argument("--user", default=cfg.user, help=f"FTP user (default {cfg.user})")
    parser.add_argument("--name", default=None, help="remote filename (default: same as the local basename)")
    return parser


def main(argv: list[str]) -> int:
    """Run deploy. Returns a process exit code (0 ok, 1 on failure/abort)."""
    args = deploy_argv_parser().parse_args(argv)
    if not args.host:
        print("No host given (pass --host or set one in the config).")
        return 1
    password = getpass.getpass("FTP password (blank for anonymous): ")
    target = FtpTarget(host=args.host, port=args.port, path=args.path, user=args.user, password=password)
    opts = DeployOptions(local_file=args.file, target=target, remote_name=args.name)
    result = run_deploy(opts)
    if result.needs_confirm:
        print(f"{result.remote_path} already exists on the remote.")
        answer = input("Overwrite? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted — remote file kept.")
            return 1
        result = run_deploy(DeployOptions(local_file=args.file, target=target, remote_name=args.name, overwrite=True))
    if result.ok:
        print(f"Deployed {result.remote_path} ({result.bytes_sent} bytes)")
        return 0
    if result.cancelled:
        print("Deploy cancelled.")
        return 1
    print(f"Deploy failed: {'; '.join(result.errors) or 'unknown error'}")
    return 1
