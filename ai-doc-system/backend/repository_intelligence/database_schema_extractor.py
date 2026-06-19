"""
repository_intelligence/database_schema_extractor.py
────────────────────────────────────────────────────────────────
Extracts database schemas and data models from source code.

Supports:
  - SQLAlchemy       (Column, relationship, Base subclasses)
  - Django ORM       (models.Model subclasses, fields)
  - TypeORM          (@Entity, @Column decorators)
  - SQL DDL          (CREATE TABLE statements)
  - MongoDB/Mongoose (new Schema, createCollection)

Output:
  List[DatabaseNode] — table/collection definitions
  List[DataModel]    — ORM model definitions
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class ColumnDef:
    """A single column/field definition."""
    name: str
    data_type: str = ""
    nullable: bool = True
    primary_key: bool = False
    foreign_key: Optional[str] = None  # "table.column"
    default: Optional[str] = None
    indexed: bool = False


@dataclass
class DatabaseNode:
    """A database table or collection."""
    name: str
    store_type: str = "sql_table"   # sql_table / mongo_collection
    columns: List[ColumnDef] = field(default_factory=list)
    primary_keys: List[str] = field(default_factory=list)
    foreign_keys: List[str] = field(default_factory=list)
    indexes: List[str] = field(default_factory=list)
    source_file: str = ""
    line_number: int = 0
    framework: str = ""             # sqlalchemy / django / typeorm / ddl / mongoose


@dataclass
class DataModel:
    """An ORM data model class."""
    class_name: str
    table_name: str = ""
    fields: List[ColumnDef] = field(default_factory=list)
    relationships: List[str] = field(default_factory=list)
    source_file: str = ""
    line_number: int = 0
    framework: str = ""


class DatabaseSchemaExtractor:
    """
    Static analysis extractor for database schemas.

    Usage:
        extractor = DatabaseSchemaExtractor()
        tables, models = extractor.extract_from_directory("/path/to/repo")
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

        # ── SQLAlchemy patterns ──────────────────────────────
        self._sqla_class = re.compile(
            r'class\s+(\w+)\s*\(.*?(?:Base|Model|db\.Model)',
        )
        self._sqla_tablename = re.compile(
            r'__tablename__\s*=\s*["\'](\w+)["\']',
        )
        self._sqla_column = re.compile(
            r'(\w+)\s*=\s*(?:db\.)?Column\s*\(\s*'
            r'(?:db\.)?(\w+)',
        )
        self._sqla_fk = re.compile(
            r'ForeignKey\s*\(\s*["\']([^"\']+)["\']',
        )
        self._sqla_relationship = re.compile(
            r'(\w+)\s*=\s*(?:db\.)?relationship\s*\(\s*'
            r'["\'](\w+)["\']',
        )

        # ── Django ORM patterns ──────────────────────────────
        self._django_class = re.compile(
            r'class\s+(\w+)\s*\(\s*models\.Model\s*\)',
        )
        self._django_field = re.compile(
            r'(\w+)\s*=\s*models\.(\w+Field)\s*\(',
        )
        self._django_fk = re.compile(
            r'(\w+)\s*=\s*models\.ForeignKey\s*\(\s*'
            r'["\']?(\w+)["\']?',
        )
        self._django_meta_table = re.compile(
            r'db_table\s*=\s*["\'](\w+)["\']',
        )

        # ── TypeORM patterns ─────────────────────────────────
        self._typeorm_entity = re.compile(
            r'@Entity\s*\(\s*(?:["\'](\w+)["\'])?\s*\)',
        )
        self._typeorm_column = re.compile(
            r'@Column\s*\((?:\s*\{[^}]*type\s*:\s*["\'](\w+)["\'])?',
        )
        self._typeorm_pk = re.compile(
            r'@PrimaryGeneratedColumn',
        )

        # ── SQL DDL patterns ─────────────────────────────────
        self._ddl_create = re.compile(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?'
            r'["`]?(\w+)["`]?\s*\(',
            re.IGNORECASE,
        )
        self._ddl_column = re.compile(
            r'^\s*["`]?(\w+)["`]?\s+'
            r'(INT|INTEGER|BIGINT|SMALLINT|SERIAL|'
            r'VARCHAR|CHAR|TEXT|NVARCHAR|'
            r'BOOLEAN|BOOL|'
            r'DATE|DATETIME|TIMESTAMP|TIME|'
            r'FLOAT|DOUBLE|DECIMAL|NUMERIC|REAL|'
            r'BLOB|BINARY|BYTEA|JSON|JSONB|UUID)',
            re.IGNORECASE,
        )
        self._ddl_pk = re.compile(
            r'PRIMARY\s+KEY',
            re.IGNORECASE,
        )
        self._ddl_fk_ref = re.compile(
            r'REFERENCES\s+["`]?(\w+)["`]?\s*\(\s*["`]?(\w+)["`]?',
            re.IGNORECASE,
        )

        # ── Mongoose patterns ────────────────────────────────
        self._mongoose_schema = re.compile(
            r'(?:const|let|var)\s+(\w+)\s*=\s*new\s+(?:mongoose\.)?Schema\s*\(',
        )
        self._mongoose_model = re.compile(
            r'mongoose\.model\s*\(\s*["\'](\w+)["\']',
        )

    def extract_from_directory(
        self, repo_path: str,
    ) -> tuple:
        """
        Scan a repository and extract database schemas.

        Returns:
            (List[DatabaseNode], List[DataModel])
        """
        tables: List[DatabaseNode] = []
        models: List[DataModel] = []

        for dirpath, _, filenames in os.walk(repo_path):
            rel_dir = os.path.relpath(dirpath, repo_path)
            if any(
                skip in rel_dir
                for skip in (
                    "node_modules", "venv", ".git",
                    "__pycache__", "dist", "build",
                    "migrations",
                )
            ):
                continue

            for fname in filenames:
                if not self._is_relevant_file(fname):
                    continue

                filepath = os.path.join(dirpath, fname)
                rel_path = os.path.relpath(filepath, repo_path)

                try:
                    with open(
                        filepath, "r",
                        encoding="utf-8", errors="ignore",
                    ) as f:
                        source = f.read()

                    ft, fm = self._extract_from_source(
                        source, rel_path,
                    )
                    tables.extend(ft)
                    models.extend(fm)

                except Exception:
                    pass

        if self.verbose:
            print(
                f"[db-extractor] Found {len(tables)} tables, "
                f"{len(models)} ORM models"
            )

        return tables, models

    def _extract_from_source(
        self,
        source: str,
        file_path: str,
    ) -> tuple:
        """Extract from a single source file."""
        tables: List[DatabaseNode] = []
        models: List[DataModel] = []

        # Detect ORM type
        if "from sqlalchemy" in source or "import sqlalchemy" in source:
            t, m = self._extract_sqlalchemy(source, file_path)
            tables.extend(t)
            models.extend(m)

        if "from django" in source and "models" in source:
            t, m = self._extract_django(source, file_path)
            tables.extend(t)
            models.extend(m)

        if "@Entity" in source and "@Column" in source:
            t, m = self._extract_typeorm(source, file_path)
            tables.extend(t)
            models.extend(m)

        if "CREATE TABLE" in source.upper():
            tables.extend(
                self._extract_ddl(source, file_path)
            )

        if "mongoose" in source.lower() or "Schema(" in source:
            t, m = self._extract_mongoose(source, file_path)
            tables.extend(t)
            models.extend(m)

        return tables, models

    # ── SQLAlchemy ───────────────────────────────────────────

    def _extract_sqlalchemy(
        self, source: str, file_path: str,
    ) -> tuple:
        tables, models = [], []
        lines = source.split("\n")

        i = 0
        while i < len(lines):
            m = self._sqla_class.search(lines[i])
            if m:
                class_name = m.group(1)
                table_name = ""
                columns = []
                relationships = []
                fks = []

                # Scan class body
                for j in range(i + 1, min(i + 100, len(lines))):
                    line = lines[j]

                    # End of class
                    if (
                        line.strip()
                        and not line.startswith(" ")
                        and not line.startswith("\t")
                        and j > i + 1
                    ):
                        break

                    # Table name
                    tm = self._sqla_tablename.search(line)
                    if tm:
                        table_name = tm.group(1)

                    # Columns
                    cm = self._sqla_column.search(line)
                    if cm:
                        col_name = cm.group(1)
                        col_type = cm.group(2)
                        is_pk = "primary_key=True" in line
                        fk_match = self._sqla_fk.search(line)
                        fk = fk_match.group(1) if fk_match else None

                        columns.append(ColumnDef(
                            name=col_name,
                            data_type=col_type,
                            primary_key=is_pk,
                            foreign_key=fk,
                            nullable="nullable=False" not in line,
                        ))
                        if fk:
                            fks.append(fk)

                    # Relationships
                    rm = self._sqla_relationship.search(line)
                    if rm:
                        relationships.append(rm.group(2))

                if not table_name:
                    table_name = class_name.lower() + "s"

                tables.append(DatabaseNode(
                    name=table_name,
                    store_type="sql_table",
                    columns=columns,
                    primary_keys=[
                        c.name for c in columns if c.primary_key
                    ],
                    foreign_keys=fks,
                    source_file=file_path,
                    line_number=i + 1,
                    framework="sqlalchemy",
                ))

                models.append(DataModel(
                    class_name=class_name,
                    table_name=table_name,
                    fields=columns,
                    relationships=relationships,
                    source_file=file_path,
                    line_number=i + 1,
                    framework="sqlalchemy",
                ))

            i += 1

        return tables, models

    # ── Django ───────────────────────────────────────────────

    def _extract_django(
        self, source: str, file_path: str,
    ) -> tuple:
        tables, models = [], []
        lines = source.split("\n")

        i = 0
        while i < len(lines):
            m = self._django_class.search(lines[i])
            if m:
                class_name = m.group(1)
                table_name = ""
                columns = []
                fks = []

                for j in range(i + 1, min(i + 100, len(lines))):
                    line = lines[j]

                    if (
                        line.strip()
                        and not line.startswith(" ")
                        and not line.startswith("\t")
                        and j > i + 1
                    ):
                        break

                    # Meta db_table
                    mt = self._django_meta_table.search(line)
                    if mt:
                        table_name = mt.group(1)

                    # Fields
                    fm = self._django_field.search(line)
                    if fm:
                        columns.append(ColumnDef(
                            name=fm.group(1),
                            data_type=fm.group(2),
                        ))

                    # ForeignKey
                    fkm = self._django_fk.search(line)
                    if fkm:
                        fks.append(fkm.group(2))
                        columns.append(ColumnDef(
                            name=fkm.group(1),
                            data_type="ForeignKey",
                            foreign_key=fkm.group(2),
                        ))

                if not table_name:
                    table_name = class_name.lower()

                tables.append(DatabaseNode(
                    name=table_name,
                    columns=columns,
                    foreign_keys=fks,
                    source_file=file_path,
                    line_number=i + 1,
                    framework="django",
                ))

                models.append(DataModel(
                    class_name=class_name,
                    table_name=table_name,
                    fields=columns,
                    source_file=file_path,
                    line_number=i + 1,
                    framework="django",
                ))

            i += 1

        return tables, models

    # ── TypeORM ──────────────────────────────────────────────

    def _extract_typeorm(
        self, source: str, file_path: str,
    ) -> tuple:
        tables, models = [], []
        lines = source.split("\n")

        i = 0
        while i < len(lines):
            m = self._typeorm_entity.search(lines[i])
            if m:
                table_name = m.group(1) or ""
                columns = []

                # Find class name
                class_name = ""
                for j in range(i + 1, min(i + 3, len(lines))):
                    cm = re.search(
                        r'(?:export\s+)?class\s+(\w+)', lines[j],
                    )
                    if cm:
                        class_name = cm.group(1)
                        break

                if not table_name:
                    table_name = class_name.lower() + "s" if class_name else ""

                # Scan for columns
                for j in range(i + 1, min(i + 60, len(lines))):
                    if self._typeorm_pk.search(lines[j]):
                        # Next line is the field
                        if j + 1 < len(lines):
                            field_m = re.search(
                                r'(\w+)\s*:', lines[j + 1],
                            )
                            if field_m:
                                columns.append(ColumnDef(
                                    name=field_m.group(1),
                                    data_type="auto",
                                    primary_key=True,
                                ))

                    col_m = self._typeorm_column.search(lines[j])
                    if col_m:
                        col_type = col_m.group(1) or "string"
                        if j + 1 < len(lines):
                            field_m = re.search(
                                r'(\w+)\s*:', lines[j + 1],
                            )
                            if field_m:
                                columns.append(ColumnDef(
                                    name=field_m.group(1),
                                    data_type=col_type,
                                ))

                if table_name:
                    tables.append(DatabaseNode(
                        name=table_name,
                        columns=columns,
                        source_file=file_path,
                        line_number=i + 1,
                        framework="typeorm",
                    ))

                if class_name:
                    models.append(DataModel(
                        class_name=class_name,
                        table_name=table_name,
                        fields=columns,
                        source_file=file_path,
                        line_number=i + 1,
                        framework="typeorm",
                    ))

            i += 1

        return tables, models

    # ── SQL DDL ──────────────────────────────────────────────

    def _extract_ddl(
        self, source: str, file_path: str,
    ) -> List[DatabaseNode]:
        tables = []

        for m in self._ddl_create.finditer(source):
            table_name = m.group(1)
            start = m.end()

            # Find matching closing paren
            depth = 1
            end = start
            for k in range(start, len(source)):
                if source[k] == "(":
                    depth += 1
                elif source[k] == ")":
                    depth -= 1
                    if depth == 0:
                        end = k
                        break

            body = source[start:end]
            columns = []
            pks = []
            fks = []

            for line in body.split("\n"):
                line = line.strip().rstrip(",")

                cm = self._ddl_column.match(line)
                if cm:
                    col_name = cm.group(1)
                    col_type = cm.group(2).upper()
                    is_pk = bool(self._ddl_pk.search(line))

                    fk_m = self._ddl_fk_ref.search(line)
                    fk = (
                        f"{fk_m.group(1)}.{fk_m.group(2)}"
                        if fk_m else None
                    )

                    columns.append(ColumnDef(
                        name=col_name,
                        data_type=col_type,
                        primary_key=is_pk,
                        foreign_key=fk,
                        nullable="NOT NULL" not in line.upper(),
                    ))

                    if is_pk:
                        pks.append(col_name)
                    if fk:
                        fks.append(fk)

            line_num = source[:m.start()].count("\n") + 1

            tables.append(DatabaseNode(
                name=table_name,
                store_type="sql_table",
                columns=columns,
                primary_keys=pks,
                foreign_keys=fks,
                source_file=file_path,
                line_number=line_num,
                framework="ddl",
            ))

        return tables

    # ── Mongoose ─────────────────────────────────────────────

    def _extract_mongoose(
        self, source: str, file_path: str,
    ) -> tuple:
        tables, models = [], []

        # Find schema definitions
        for m in self._mongoose_schema.finditer(source):
            schema_var = m.group(1)

            # Find the model name
            model_match = self._mongoose_model.search(source)
            collection_name = (
                model_match.group(1) if model_match
                else schema_var.replace("Schema", "")
            )

            line_num = source[:m.start()].count("\n") + 1

            tables.append(DatabaseNode(
                name=collection_name,
                store_type="mongo_collection",
                source_file=file_path,
                line_number=line_num,
                framework="mongoose",
            ))

            models.append(DataModel(
                class_name=collection_name,
                table_name=collection_name,
                source_file=file_path,
                line_number=line_num,
                framework="mongoose",
            ))

        return tables, models

    # ── Helpers ──────────────────────────────────────────────

    def _is_relevant_file(self, filename: str) -> bool:
        """Check if file might contain schema definitions."""
        name_lower = filename.lower()

        # Direct SQL files
        if name_lower.endswith((".sql", ".ddl")):
            return True

        # Source files with model/schema/entity hints
        if name_lower.endswith((
            ".py", ".js", ".ts", ".java", ".kt",
        )):
            # Prefer files with model/schema/entity in the name
            return True

        return False
