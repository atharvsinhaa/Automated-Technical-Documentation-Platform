import os
import shutil
import subprocess
import tempfile

def test_sql():
    with tempfile.TemporaryDirectory() as td:
        repo_dir = os.path.join(td, "sql_repo")
        os.makedirs(repo_dir)
        with open(os.path.join(repo_dir, "proc1.sql"), "w") as f:
            f.write("CREATE DEFINER=`testuser`@`%` PROCEDURE `sample_proc`(IN p1 VARCHAR(50))\nBEGIN\n  INSERT INTO sample_table (col1, col2) VALUES (p1, NOW());\nEND;\n")
            
        output_dir = os.path.join(td, "outputs")
        subprocess.run(["python3", "pipeline.py", repo_dir, "--output", output_dir])
        
        print("\n--- LLD.md Content ---")
        lld_path = os.path.join(output_dir, "lld", "LLD.md")
        if os.path.exists(lld_path):
            with open(lld_path, "r") as f:
                content = f.read()
                print("\n# Class Inventory\n", content.split('## Class Inventory')[1].split('### Method Inventory')[0])
                print("\n# ERD\n", content.split('## Entity Relationship Diagram')[1].split('## Layered')[0])

if __name__ == "__main__":
    test_sql()
