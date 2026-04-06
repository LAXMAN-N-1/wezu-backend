import os

def scan_debug_log():
    log_path = 'tmp/debug_sql_output.txt'
    if not os.path.exists(log_path):
        print("Log file not found.")
        return
        
    try:
        content = open(log_path, 'rb').read().decode('utf-16le', 'ignore')
        lines = content.splitlines()
        
        found_insert = False
        for i, line in enumerate(lines):
            if 'INSERT INTO audit_logs' in line:
                print("\n--- FAILING SQL ---")
                print(line)
                # Print next 5 lines for parameters
                for j in range(1, 10):
                    if i + j < len(lines):
                        print(lines[i+j])
                found_insert = True
                break
        
        if not found_insert:
            print("No INSERT statement found in log.")
            # Print last 20 lines anyway
            print("\n--- LAST 20 LINES OF LOG ---")
            for line in lines[-20:]:
                print(line)

    except Exception as e:
        print(f"Error reading log: {e}")

if __name__ == "__main__":
    scan_debug_log()
