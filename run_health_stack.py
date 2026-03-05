"""
FinWell Health Stack Launcher
Starts all health agents in separate processes so they can communicate locally.
"""
import subprocess
import sys
import os
import time

VENV_PYTHON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "venv", "Scripts", "python.exe")
if not os.path.exists(VENV_PYTHON):
    VENV_PYTHON = sys.executable

HEALTH_AGENTS = [
    ("ASI1 Wrapper Agent (port 8009)", "health/asi1_wrapper_agent.py"),
    ("Collector Agent (port 8005)",    "health/collector_agent.py"),
    ("Analyser Agent (port 8006)",     "health/analyser_agent.py"),
    ("Insurance Agent (port 8010)",    "health/insurance_agent.py"),
]

CLI_AGENT = ("Health CLI (port 8000)", "health/main.py")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    processes = []

    print("=" * 60)
    print("  FinWell Health Stack Launcher")
    print("=" * 60)
    print()

    # Start background agents first
    for name, script in HEALTH_AGENTS:
        script_path = os.path.join(base_dir, script)
        log_name = os.path.basename(script).replace(".py", "")
        stdout_log = open(os.path.join(log_dir, f"{log_name}_out.log"), "w")
        stderr_log = open(os.path.join(log_dir, f"{log_name}_err.log"), "w")

        print(f"  Starting {name}...")
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.Popen(
            [VENV_PYTHON, script_path],
            cwd=base_dir,
            stdout=stdout_log,
            stderr=stderr_log,
            env=env,
        )
        processes.append((name, proc, stdout_log, stderr_log))
        time.sleep(2)  # Stagger startup

    print()
    print("  ⏳ Waiting 8 seconds for agents to fully initialize...")
    time.sleep(8)

    # Check if any background agents crashed
    all_ok = True
    for name, proc, _, stderr_log in processes:
        if proc.poll() is not None:
            stderr_log.flush()
            err_path = stderr_log.name
            stderr_log.close()
            with open(err_path, 'r') as f:
                err = f.read().strip()
            print(f"  ❌ {name} crashed (exit code {proc.returncode})")
            if err:
                # Show last 3 lines of error
                lines = err.split('\n')
                for line in lines[-3:]:
                    print(f"     {line}")
            all_ok = False
        else:
            print(f"  ✅ {name} — running (PID {proc.pid})")

    if not all_ok:
        print("\n  ⚠️  Some agents failed. Check logs/ folder for details.")
        cleanup(processes)
        return

    print()
    print("=" * 60)
    print("  All agents running! Starting Health CLI...")
    print("  Type your symptoms below. Type 'exit' to quit.")
    print("=" * 60)
    print()

    # Run the CLI agent in the foreground (interactive)
    cli_path = os.path.join(base_dir, CLI_AGENT[1])
    try:
        cli_proc = subprocess.Popen(
            [VENV_PYTHON, cli_path],
            cwd=base_dir,
        )
        cli_proc.wait()
    except KeyboardInterrupt:
        print("\n\n  👋 Shutting down all agents...")
    finally:
        cleanup(processes)


def cleanup(processes):
    """Terminate all background agent processes."""
    for name, proc, stdout_log, stderr_log in processes:
        stdout_log.close()
        stderr_log.close()
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
                print(f"  🛑 Stopped {name}")
            except Exception:
                proc.kill()
                print(f"  🛑 Force-killed {name}")
    print("\n  ✅ All agents stopped. Goodbye!")


if __name__ == "__main__":
    main()
