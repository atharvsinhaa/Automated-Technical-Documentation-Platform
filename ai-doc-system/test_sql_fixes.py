import os
import shutil
import subprocess
import tempfile

def test_sql():
    with tempfile.TemporaryDirectory() as td:
        repo_dir = os.path.join(td, "sql_repo")
        os.makedirs(repo_dir)
        with open(os.path.join(repo_dir, "proc1.sql"), "w") as f:
            f.write("CREATE PROCEDURE get_users(p_status VARCHAR)\nBEGIN\n  SELECT * FROM users WHERE status = p_status;\nEND;\n")
        with open(os.path.join(repo_dir, "proc2.txt"), "w") as f:
            f.write("CREATE PROCEDURE update_status(p_id INT)\nBEGIN\n  UPDATE orders SET status = 'DONE' WHERE id = p_id;\nEND;\n")
            
        output_dir = os.path.join(td, "outputs")
        subprocess.run(["python3", "pipeline.py", repo_dir, "--output", output_dir])
        
        print("\n--- LLD.md Content ---")
        lld_path = os.path.join(output_dir, "lld", "LLD.md")
        if os.path.exists(lld_path):
            with open(lld_path, "r") as f:
                content = f.read()
                print("\n# LLD Content\n", content)
        hld_path = os.path.join(output_dir, "hld", "HLD.md")
        if os.path.exists(hld_path):
            with open(hld_path, "r") as f:
                content = f.read()
                print("\n# HLD Architecture\n")
                if '## System Architecture' in content:
                    print(content.split('## System Architecture')[1].split('## Modules')[0])
                else:
                    print("NOT FOUND")

if __name__ == "__main__":
    test_sql()
