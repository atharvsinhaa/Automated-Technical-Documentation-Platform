import os
import re

from backend.semantic_ir.models import IRComponent, IRDataStore, IRRelationship

class SQLExtractor:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def extract_from_directory(self, repo_path: str, ir):
        source_exts = {".sql", ".txt", ""}
        skip_dirs = {"__pycache__", ".git", "venv", ".venv", "node_modules", "dist", "build", "outputs"}
        
        proc_pattern = re.compile(r'CREATE\s+(?:DEFINER\s*=\s*\S+\s+)?(?:OR\s+REPLACE\s+)?(?:PROCEDURE|FUNCTION)\s+`?([a-zA-Z0-9_]+)`?\s*\((.*?)\)', re.IGNORECASE | re.DOTALL)
        table_pattern = re.compile(r'(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|FROM|JOIN)\s+`?([a-zA-Z0-9_]+)`?', re.IGNORECASE)

        added_procs = 0
        added_tables = 0

        if "sql_procedures" not in ir.metadata:
            ir.metadata["sql_procedures"] = []

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            for fname in files:
                ext = os.path.splitext(fname)[1].lower()
                if ext not in source_exts:
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    if ext in (".txt", ""):
                        if not re.search(r'\b(?:CREATE\s+(?:DEFINER|OR\s+REPLACE|PROCEDURE|FUNCTION)|BEGIN|DELIMITER|INSERT\s+INTO)\b', content, re.IGNORECASE):
                            continue
                    
                    procs_in_file = []
                    for match in proc_pattern.finditer(content):
                        proc_name = match.group(1).replace('`', '')
                        params_str = match.group(2).replace('`', '')
                        procs_in_file.append(proc_name)
                        
                        ir.components.append(IRComponent(
                            name=proc_name,
                            component_type="SQL Procedure",
                            description=f"Stored Procedure: {proc_name} ({params_str.strip()[:50]})",
                            files=[os.path.relpath(fpath, repo_path)],
                            key_classes=[proc_name],
                            key_functions=[proc_name],
                            layer="Data",
                            confidence="high"
                        ))
                        
                        ir.metadata["sql_procedures"].append({
                            "name": proc_name,
                            "params": params_str.strip(),
                            "file": os.path.relpath(fpath, repo_path)
                        })
                        added_procs += 1

                    for match in table_pattern.finditer(content):
                        table_name = match.group(1).replace('`', '')
                        if table_name.lower() in ("select", "from", "where", "join", "on", "and", "or", "order", "group", "by", "in", "is", "not", "null"):
                            continue
                        
                        existing = [ds for ds in ir.data_stores if ds.name.upper() == table_name.upper()]
                        if not existing:
                            ir.data_stores.append(IRDataStore(
                                name=table_name,
                                store_type="SQL Table",
                                accessed_by=["SQL Procedures"],
                                operations=["CRUD"]
                            ))
                            added_tables += 1
                        
                        for proc in procs_in_file:
                            ir.relationships.append(IRRelationship(
                                source=proc,
                                target=table_name,
                                relationship_type="DEPENDS_ON",
                                evidence=f"Table accessed in {proc}"
                            ))

                except Exception as e:
                    if self.verbose:
                        print(f"[SQLExtractor] Error processing {fpath}: {e}")
        
        if self.verbose:
            print(f"[enrich] Added {added_procs} SQL procedures and {added_tables} SQL tables")
            
        if added_procs > 0 or added_tables > 0:
            if "SQL" not in ir.languages:
                ir.languages.append("SQL")
