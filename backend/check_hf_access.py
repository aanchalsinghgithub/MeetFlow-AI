"""Run this with the SAME .venv your backend uses, from the backend/ folder:

    python check_hf_access.py

It isolates exactly one question: can your HF_TOKEN download the gated
pyannote diarization model right now? Everything else (torchcodec
warnings, Whisper, the rest of the app) is irrelevant to this check.
"""
import os
import sys

REPO = "pyannote/speaker-diarization-community-1"
FILE = "plda/xvec_transform.npz"  # the exact file that 403'd in your log


def main() -> None:
    # Mirrors how the app loads it (python-dotenv if present, else raw env var).
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    token = os.environ.get("HF_TOKEN")

    print(f"HF_TOKEN found in environment: {'yes' if token else 'NO'}")
    if token:
        print(f"HF_TOKEN preview: {token[:6]}...{token[-4:]} (length {len(token)})")
    else:
        print(
            "\n>>> HF_TOKEN is not set in this environment.\n"
            "    Check that backend/.env has a line like:\n"
            "    HF_TOKEN=hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\n"
            "    and that you're running this from the backend/ folder\n"
            "    (so python-dotenv can find the .env file), or export it:\n"
            "    (PowerShell)  $env:HF_TOKEN=\"hf_...\"\n"
        )
        sys.exit(1)

    # Who does this token actually belong to?
    try:
        from huggingface_hub import HfApi
        who = HfApi().whoami(token=token)
        print(f"Token belongs to HF account: {who.get('name')}")
    except Exception as e:
        print(f"\n>>> Token rejected by Hugging Face outright: {e}")
        print("    This token is invalid/expired. Generate a new READ token at")
        print("    https://huggingface.co/settings/tokens and update backend/.env")
        sys.exit(1)

    # The actual test: can this token pull the specific gated file?
    print(f"\nAttempting to download {REPO}/{FILE} ...")
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(repo_id=REPO, filename=FILE, token=token)
        print(f"\n✅ SUCCESS — downloaded to {path}")
        print("Your token has access. Diarization should work after a backend restart.")
        print("If it still shows 'Unknown' after restarting, the issue is something")
        print("else (check the backend logs for a different error message) —")
        print("come back and paste the new error.")
    except Exception as e:
        msg = str(e)
        print(f"\n❌ FAILED: {msg}")
        if "403" in msg or "gated" in msg.lower() or "authorized" in msg.lower():
            print(
                f"\n>>> Your token IS valid, but this account hasn't accepted the\n"
                f"    repo's access conditions yet. Fix:\n"
                f"    1. Go to https://huggingface.co/{REPO} while logged in as the\n"
                f"       SAME account shown above.\n"
                f"    2. Click 'Agree and access repository'.\n"
                f"    3. Re-run this script to confirm it now succeeds.\n"
                f"    4. Restart your backend (uvicorn) — it caches a failed load\n"
                f"       for the rest of the process, so it won't retry on its own.\n"
            )
        elif "401" in msg:
            print(
                "\n>>> Token was rejected (401) for this specific request — it may\n"
                "    lack read scope. Generate a fresh READ token at\n"
                "    https://huggingface.co/settings/tokens\n"
            )
        else:
            print(
                "\n>>> This doesn't look like a token/gate problem — could be a\n"
                "    network/proxy/firewall issue reaching huggingface.co instead.\n"
            )
        sys.exit(1)


if __name__ == "__main__":
    main()
