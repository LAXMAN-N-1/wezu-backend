import subprocess
import sys

def run_command(command):
    try:
        result = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True
        )
        print(f"Command '{command}' succeeded.")
        print("STDOUT:", result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Command '{command}' failed with return code {e.returncode}.")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    print("Running migration revision...")
    run_command("alembic revision --autogenerate -m \"Add Warehouse module\"")
    
    print("\nRunning migration upgrade...")
    run_command("alembic upgrade head")
