"""
repository_intelligence/java_source_scanner.py
────────────────────────────────────────────────────────────────
Static regex-based scanner for Java/Kotlin/Spring repositories.

Extracts architecture, classes, interfaces, modules, annotations,
dependency chains and entity relationships WITHOUT requiring the
AST engine or tree-sitter.

This is the fallback path when the AST engine cannot parse the
repository (e.g. Java repos with a Python-only AST engine).

Output dataclasses are lightweight and mapped into SemanticIR
components/relationships by the IRBuilder enrichment pipeline.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


# ═══════════════════════════════════════════════════════════════
#  DATA CLASSES
# ═══════════════════════════════════════════════════════════════

@dataclass
class JavaField:
    name: str
    field_type: str
    annotations: List[str] = field(default_factory=list)
    is_injected: bool = False  # @Autowired / constructor injection

@dataclass
class JavaMethod:
    name: str
    return_type: str = "void"
    parameters: List[str] = field(default_factory=list)
    annotations: List[str] = field(default_factory=list)
    http_method: str = ""      # GET/POST/PUT/DELETE if mapped
    http_path: str = ""        # endpoint path if mapped

@dataclass
class JavaClass:
    name: str
    file_path: str
    package: str = ""
    stereotype: str = ""       # Entity, Service, Controller, Repository, Component, Configuration, FeignClient
    annotations: List[str] = field(default_factory=list)
    extends: str = ""
    implements: List[str] = field(default_factory=list)
    fields: List[JavaField] = field(default_factory=list)
    methods: List[JavaMethod] = field(default_factory=list)
    is_interface: bool = False
    base_path: str = ""        # @RequestMapping base path

@dataclass
class JavaModule:
    name: str                  # e.g. "vets-service"
    directory: str             # e.g. "spring-petclinic-vets-service"
    classes: List[str] = field(default_factory=list)
    has_main: bool = False
    spring_annotations: List[str] = field(default_factory=list)

@dataclass
class JavaScanResult:
    classes: List[JavaClass] = field(default_factory=list)
    interfaces: List[JavaClass] = field(default_factory=list)
    modules: List[JavaModule] = field(default_factory=list)
    architecture_pattern: str = "Unknown"
    architecture_confidence: str = "Low"
    architecture_evidence: str = ""
    frameworks: List[str] = field(default_factory=list)
    entity_relationships: List[Tuple[str, str, str]] = field(default_factory=list)  # (from, to, type)
    dependency_chains: List[Tuple[str, str, str]] = field(default_factory=list)     # (from, to, rel_type)


# ═══════════════════════════════════════════════════════════════
#  COMPILED REGEX PATTERNS
# ═══════════════════════════════════════════════════════════════

_RE_PACKAGE = re.compile(r'^\s*package\s+([\w.]+)\s*;')
_RE_CLASS = re.compile(
    r'(?:public\s+)?(?:abstract\s+)?class\s+(\w+)'
    r'(?:\s+extends\s+(\w+))?'
    r'(?:\s+implements\s+([\w,\s]+))?'
)
_RE_INTERFACE = re.compile(
    r'(?:public\s+)?interface\s+(\w+)'
    r'(?:\s+extends\s+([\w,\s]+))?'
)
_RE_ANNOTATION = re.compile(r'@(\w+)(?:\(([^)]*)\))?')
_RE_FIELD = re.compile(
    r'(?:private|protected|public)\s+'
    r'(?:final\s+)?(?:static\s+)?'
    r'([\w<>,\s\[\]?]+?)\s+(\w+)\s*[;=]'
)
_RE_METHOD = re.compile(
    r'(?:public|protected|private)\s+'
    r'(?:static\s+)?(?:final\s+)?'
    r'([\w<>,\[\]?]+)\s+(\w+)\s*\(([^)]*)\)'
)
_RE_MAPPING = re.compile(
    r'@(Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*'
    r'(?:value\s*=\s*)?["\']([^"\']+)["\']'
    r'(?:.*?method\s*=\s*RequestMethod\.(\w+))?'
)
_RE_FEIGN = re.compile(r'@FeignClient\s*\(.*?(?:name|value)\s*=\s*["\']([^"\']+)["\']')
_RE_ENTITY_REL = re.compile(r'@(ManyToOne|OneToMany|ManyToMany|OneToOne)')
_RE_JOIN_COLUMN = re.compile(r'@JoinColumn\s*\(.*?name\s*=\s*["\']([^"\']+)["\']')
_RE_TABLE = re.compile(r'@Table\s*\(.*?name\s*=\s*["\']([^"\']+)["\']')

_SKIP_DIRS = {
    "__pycache__", ".git", "venv", ".venv", "node_modules",
    "dist", "build", ".gradle", ".idea", ".mvn", "target",
    "outputs", ".pytest_cache",
}

_STEREOTYPE_MAP = {
    "Entity": "Entity",
    "Table": "Entity",
    "Document": "Entity",
    "MappedSuperclass": "Entity",
    "Service": "Service",
    "Component": "Component",
    "RestController": "Controller",
    "Controller": "Controller",
    "Repository": "Repository",
    "Configuration": "Configuration",
    "SpringBootApplication": "Application",
    "EnableConfigServer": "ConfigServer",
    "EnableEurekaServer": "DiscoveryServer",
    "EnableDiscoveryClient": "DiscoveryClient",
    "EnableAdminServer": "AdminServer",
    "FeignClient": "FeignClient",
}


# ═══════════════════════════════════════════════════════════════
#  SCANNER
# ═══════════════════════════════════════════════════════════════

class JavaSourceScanner:
    """
    Scans a repository for Java/Kotlin source files and extracts
    structural information using regex-based static analysis.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def scan(self, repo_path: str) -> JavaScanResult:
        """Scan the repo and return structured results."""
        result = JavaScanResult()

        java_files = self._find_java_files(repo_path)
        if not java_files:
            return result

        if self.verbose:
            print(f"[java-scanner] Found {len(java_files)} Java/Kotlin files")

        # Pass 1: Parse all files
        for fpath in java_files:
            rel_path = os.path.relpath(fpath, repo_path)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()
                parsed = self._parse_file(source, rel_path)
                for cls in parsed:
                    if cls.is_interface:
                        result.interfaces.append(cls)
                    else:
                        result.classes.append(cls)
            except Exception:
                pass

        # Pass 2: Detect modules from directory structure
        result.modules = self._detect_modules(repo_path, result.classes + result.interfaces)

        # Pass 3: Detect architecture pattern
        arch, conf, evidence = self._detect_architecture(result)
        result.architecture_pattern = arch
        result.architecture_confidence = conf
        result.architecture_evidence = evidence

        # Pass 4: Detect frameworks
        result.frameworks = self._detect_frameworks(result)

        # Pass 5: Extract entity relationships
        result.entity_relationships = self._extract_entity_relationships(result.classes)

        # Pass 6: Extract dependency chains (Controller→Service→Repository)
        result.dependency_chains = self._extract_dependency_chains(result.classes)

        if self.verbose:
            print(f"[java-scanner] Classes: {len(result.classes)}, "
                  f"Interfaces: {len(result.interfaces)}, "
                  f"Modules: {len(result.modules)}")
            print(f"[java-scanner] Architecture: {result.architecture_pattern} "
                  f"({result.architecture_confidence})")

        return result

    # ───────────────────────────────────────────────────────────
    #  FILE DISCOVERY
    # ───────────────────────────────────────────────────────────

    def _find_java_files(self, repo_path: str) -> List[str]:
        """Find all Java/Kotlin source files, excluding tests."""
        files = []
        for root, dirs, fnames in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
            rel = os.path.relpath(root, repo_path)
            # Skip test directories
            if "/test/" in rel or "\\test\\" in rel:
                continue
            for fname in fnames:
                if fname.endswith((".java", ".kt")):
                    files.append(os.path.join(root, fname))
        return files

    # ───────────────────────────────────────────────────────────
    #  FILE PARSING
    # ───────────────────────────────────────────────────────────

    def _parse_file(self, source: str, file_path: str) -> List[JavaClass]:
        """Parse a single Java file and return classes/interfaces found."""
        results = []
        lines = source.split("\n")

        # Extract package
        package = ""
        for line in lines[:20]:
            m = _RE_PACKAGE.match(line)
            if m:
                package = m.group(1)
                break

        # Collect annotations that precede a class/interface declaration
        pending_annotations: List[str] = []
        pending_annotation_args: Dict[str, str] = {}
        base_path = ""

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Collect annotations
            ann_match = _RE_ANNOTATION.search(stripped)
            if ann_match and not stripped.startswith("//"):
                ann_name = ann_match.group(1)
                ann_args = ann_match.group(2) or ""
                pending_annotations.append(ann_name)
                pending_annotation_args[ann_name] = ann_args

                # Extract base path from @RequestMapping on class
                if ann_name == "RequestMapping":
                    path_match = re.search(r'["\']([^"\']+)["\']', ann_args)
                    if path_match:
                        base_path = path_match.group(1)

                # FeignClient name
                if ann_name == "FeignClient":
                    fm = _RE_FEIGN.search(stripped)
                    if fm:
                        pending_annotation_args["FeignClient"] = fm.group(1)

                continue

            # Interface declaration
            iface_match = _RE_INTERFACE.search(stripped)
            if iface_match:
                name = iface_match.group(1)
                extends_str = iface_match.group(2) or ""
                extends_list = [e.strip() for e in extends_str.split(",") if e.strip()]

                stereotype = ""
                for ann in pending_annotations:
                    if ann in _STEREOTYPE_MAP:
                        stereotype = _STEREOTYPE_MAP[ann]

                cls = JavaClass(
                    name=name,
                    file_path=file_path,
                    package=package,
                    stereotype=stereotype or "Interface",
                    annotations=list(pending_annotations),
                    implements=extends_list,
                    is_interface=True,
                    base_path=base_path,
                )

                # Parse methods inside
                cls.methods = self._parse_methods(lines, i)
                results.append(cls)
                pending_annotations = []
                pending_annotation_args = {}
                base_path = ""
                continue

            # Class declaration
            cls_match = _RE_CLASS.search(stripped)
            if cls_match:
                name = cls_match.group(1)
                extends = cls_match.group(2) or ""
                implements_str = cls_match.group(3) or ""
                implements_list = [e.strip() for e in implements_str.split(",") if e.strip()]

                stereotype = ""
                for ann in pending_annotations:
                    if ann in _STEREOTYPE_MAP:
                        stereotype = _STEREOTYPE_MAP[ann]

                cls = JavaClass(
                    name=name,
                    file_path=file_path,
                    package=package,
                    stereotype=stereotype,
                    annotations=list(pending_annotations),
                    extends=extends,
                    implements=implements_list,
                    base_path=base_path,
                )

                # Parse fields and methods inside
                cls.fields = self._parse_fields(lines, i)
                cls.methods = self._parse_methods(lines, i)

                # Mark injected fields
                for fld in cls.fields:
                    if any(a in fld.annotations for a in ("Autowired", "Inject", "Value")):
                        fld.is_injected = True

                results.append(cls)
                pending_annotations = []
                pending_annotation_args = {}
                base_path = ""
                continue

            # Reset annotations if we hit a non-annotation, non-class line
            if stripped and not stripped.startswith("//") and not stripped.startswith("/*") and not stripped.startswith("*"):
                if not ann_match and not stripped.startswith("@") and not stripped.startswith("import"):
                    pending_annotations = []
                    pending_annotation_args = {}

        return results

    def _parse_fields(self, lines: List[str], class_start: int) -> List[JavaField]:
        """Parse fields inside a class body."""
        fields = []
        brace_depth = 0
        started = False
        pending_annotations: List[str] = []

        for i in range(class_start, min(class_start + 300, len(lines))):
            line = lines[i].strip()
            brace_depth += line.count("{") - line.count("}")

            if "{" in lines[class_start] or (i > class_start and brace_depth > 0):
                started = True

            if started and brace_depth <= 0 and i > class_start:
                break

            # Collect field-level annotations
            ann_match = _RE_ANNOTATION.search(line)
            if ann_match and not line.startswith("//"):
                pending_annotations.append(ann_match.group(1))

            # Match fields
            fm = _RE_FIELD.search(line)
            if fm and started and brace_depth == 1:
                ftype = fm.group(1).strip()
                fname = fm.group(2).strip()
                fields.append(JavaField(
                    name=fname,
                    field_type=ftype,
                    annotations=list(pending_annotations),
                ))
                pending_annotations = []
            elif not line.startswith("@"):
                if fm is None and not line.startswith("//"):
                    pending_annotations = []

        return fields

    def _parse_methods(self, lines: List[str], class_start: int) -> List[JavaMethod]:
        """Parse methods inside a class/interface body."""
        methods = []
        brace_depth = 0
        started = False
        pending_annotations: List[str] = []
        pending_http_method = ""
        pending_http_path = ""

        for i in range(class_start, min(class_start + 500, len(lines))):
            line = lines[i].strip()
            brace_depth += line.count("{") - line.count("}")

            if "{" in lines[class_start] or (i > class_start and brace_depth > 0):
                started = True

            if started and brace_depth <= 0 and i > class_start:
                break

            # Collect method-level annotations
            ann_match = _RE_ANNOTATION.search(line)
            if ann_match and not line.startswith("//"):
                ann_name = ann_match.group(1)
                pending_annotations.append(ann_name)

                # HTTP mapping
                mapping_match = _RE_MAPPING.search(line)
                if mapping_match:
                    mtype = mapping_match.group(1)
                    mpath = mapping_match.group(2)
                    explicit = mapping_match.group(3)
                    if explicit:
                        pending_http_method = explicit.upper()
                    elif mtype == "Request":
                        pending_http_method = "GET"
                    else:
                        pending_http_method = mtype.upper()
                    pending_http_path = mpath

            # Match methods
            mm = _RE_METHOD.search(line)
            if mm and started:
                ret_type = mm.group(1).strip()
                mname = mm.group(2).strip()
                params_str = mm.group(3).strip()
                params = [p.strip() for p in params_str.split(",") if p.strip()] if params_str else []

                methods.append(JavaMethod(
                    name=mname,
                    return_type=ret_type,
                    parameters=params,
                    annotations=list(pending_annotations),
                    http_method=pending_http_method,
                    http_path=pending_http_path,
                ))
                pending_annotations = []
                pending_http_method = ""
                pending_http_path = ""
            elif not line.startswith("@"):
                if mm is None and not line.startswith("//"):
                    pending_annotations = []
                    pending_http_method = ""
                    pending_http_path = ""

        return methods

    # ───────────────────────────────────────────────────────────
    #  MODULE DETECTION
    # ───────────────────────────────────────────────────────────

    def _detect_modules(self, repo_path: str, all_classes: List[JavaClass]) -> List[JavaModule]:
        """Detect modules from directory structure (multi-module Maven/Gradle projects)."""
        modules: Dict[str, JavaModule] = {}

        for cls in all_classes:
            # e.g. file_path = "spring-petclinic-vets-service/src/main/java/.../VetResource.java"
            parts = cls.file_path.replace("\\", "/").split("/")
            if len(parts) >= 2:
                mod_dir = parts[0]
            else:
                mod_dir = "root"

            if mod_dir not in modules:
                # Clean name: "my-service" → "My Service"
                name = mod_dir
                if name.startswith("spring-"):
                    name = name[len("spring-"):]
                name = name.replace("-", " ").replace("_", " ").title()
                if not name:
                    name = mod_dir.replace("-", " ").title()

                modules[mod_dir] = JavaModule(name=name, directory=mod_dir)

            mod = modules[mod_dir]
            mod.classes.append(cls.name)
            mod.spring_annotations.extend(cls.annotations)

            if cls.stereotype == "Application":
                mod.has_main = True

        # Deduplicate annotations
        for mod in modules.values():
            mod.spring_annotations = list(set(mod.spring_annotations))

        return list(modules.values())

    # ───────────────────────────────────────────────────────────
    #  ARCHITECTURE DETECTION
    # ───────────────────────────────────────────────────────────

    def _detect_architecture(self, result: JavaScanResult) -> Tuple[str, str, str]:
        """Detect architecture pattern from structural signals."""
        signals: Dict[str, int] = {
            "spring_cloud": 0,
            "microservices": 0,
            "mvc": 0,
            "layered": 0,
            "hexagonal": 0,
            "clean": 0,
        }
        evidence: List[str] = []

        all_classes = result.classes + result.interfaces
        all_annotations = set()
        all_stereotypes = set()
        for cls in all_classes:
            all_annotations.update(cls.annotations)
            if cls.stereotype:
                all_stereotypes.add(cls.stereotype)

        # Spring Cloud signals
        has_config_server = any(c.stereotype == "ConfigServer" for c in all_classes)
        has_discovery = any(c.stereotype in ("DiscoveryServer", "DiscoveryClient") for c in all_classes)
        has_gateway = any("Gateway" in c.name or "gateway" in c.file_path.lower() for c in all_classes)
        has_feign = any(c.stereotype == "FeignClient" for c in all_classes)

        if has_config_server:
            signals["spring_cloud"] += 3
            evidence.append("Config Server detected (@EnableConfigServer)")
        if has_discovery:
            signals["spring_cloud"] += 3
            evidence.append("Discovery Server detected (@EnableEurekaServer/@EnableDiscoveryClient)")
        if has_gateway:
            signals["spring_cloud"] += 2
            evidence.append("API Gateway detected")
        if has_feign:
            signals["spring_cloud"] += 2
            evidence.append("FeignClient inter-service communication detected")

        # Multi-module = microservices
        main_modules = [m for m in result.modules if m.has_main]
        if len(main_modules) >= 3:
            signals["microservices"] += 3
            evidence.append(f"{len(main_modules)} independently deployable modules detected")
        elif len(main_modules) >= 2:
            signals["microservices"] += 1

        # MVC signals
        has_controllers = "Controller" in all_stereotypes
        has_services = "Service" in all_stereotypes
        has_repos = "Repository" in all_stereotypes
        has_entities = "Entity" in all_stereotypes

        if has_controllers and has_services and has_repos:
            signals["mvc"] += 3
            signals["layered"] += 2
            evidence.append("Controller → Service → Repository layering detected")

        if has_entities:
            signals["mvc"] += 1
            evidence.append("JPA Entities detected")

        # Hexagonal signals
        has_ports = any("Port" in c.name or "port" in c.file_path.lower() for c in all_classes)
        has_adapters = any("Adapter" in c.name or "adapter" in c.file_path.lower() for c in all_classes)
        if has_ports and has_adapters:
            signals["hexagonal"] += 4
            evidence.append("Port/Adapter pattern detected (Hexagonal Architecture)")

        # Clean architecture signals
        has_usecase = any("UseCase" in c.name or "usecase" in c.file_path.lower() for c in all_classes)
        if has_usecase:
            signals["clean"] += 3
            evidence.append("Use Case layer detected (Clean Architecture)")

        # Pick winner
        winner = max(signals, key=signals.get)
        max_score = signals[winner]

        if max_score == 0:
            return ("Unknown", "Low", "Insufficient structural signals")

        confidence = "High" if max_score >= 5 else "Medium" if max_score >= 3 else "Low"

        # Combine patterns
        if signals["spring_cloud"] >= 5:
            pattern = "Spring Cloud Microservices"
        elif signals["spring_cloud"] >= 3 and signals["microservices"] >= 2:
            pattern = "Spring Cloud Microservices"
        elif winner == "microservices":
            pattern = "Microservices"
        elif winner == "hexagonal":
            pattern = "Hexagonal Architecture"
        elif winner == "clean":
            pattern = "Clean Architecture"
        elif winner == "mvc":
            pattern = "MVC (Spring)"
        elif winner == "layered":
            pattern = "Layered Architecture"
        else:
            pattern = "Modular Monolith"

        return (pattern, confidence, " | ".join(evidence))

    # ───────────────────────────────────────────────────────────
    #  FRAMEWORK DETECTION
    # ───────────────────────────────────────────────────────────

    def _detect_frameworks(self, result: JavaScanResult) -> List[str]:
        frameworks: Set[str] = set()
        all_annotations = set()
        for cls in result.classes + result.interfaces:
            all_annotations.update(cls.annotations)

        if any(a in all_annotations for a in ("SpringBootApplication", "EnableAutoConfiguration")):
            frameworks.add("Spring Boot")
        if any(a in all_annotations for a in ("RestController", "Controller", "RequestMapping")):
            frameworks.add("Spring MVC")
        if any(a in all_annotations for a in ("EnableConfigServer",)):
            frameworks.add("Spring Cloud Config")
        if any(a in all_annotations for a in ("EnableEurekaServer", "EnableDiscoveryClient")):
            frameworks.add("Spring Cloud Netflix (Eureka)")
        if any(a in all_annotations for a in ("FeignClient",)):
            frameworks.add("Spring Cloud OpenFeign")
        if any(a in all_annotations for a in ("Entity", "Table", "MappedSuperclass")):
            frameworks.add("Spring Data JPA")
        if any(a in all_annotations for a in ("Document",)):
            frameworks.add("Spring Data MongoDB")
        if any(a in all_annotations for a in ("EnableAdminServer",)):
            frameworks.add("Spring Boot Admin")

        return sorted(frameworks)

    # ───────────────────────────────────────────────────────────
    #  ENTITY RELATIONSHIPS
    # ───────────────────────────────────────────────────────────

    def _extract_entity_relationships(self, classes: List[JavaClass]) -> List[Tuple[str, str, str]]:
        """Extract @ManyToOne / @OneToMany / etc. relationships between entities."""
        rels: List[Tuple[str, str, str]] = []
        entity_names = {c.name for c in classes if c.stereotype == "Entity"}

        for cls in classes:
            if cls.stereotype != "Entity":
                continue
            for fld in cls.fields:
                rel_anns = [a for a in fld.annotations if a in ("ManyToOne", "OneToMany", "ManyToMany", "OneToOne")]
                if rel_anns:
                    # Target type is the field type (strip generics)
                    target = re.sub(r'<.*>', '', fld.field_type).strip()
                    target = re.sub(r'(List|Set|Collection|Iterable)\s*', '', target).strip()
                    if target in entity_names:
                        rels.append((cls.name, target, rel_anns[0]))

        return rels

    # ───────────────────────────────────────────────────────────
    #  DEPENDENCY CHAINS
    # ───────────────────────────────────────────────────────────

    def _extract_dependency_chains(self, classes: List[JavaClass]) -> List[Tuple[str, str, str]]:
        """
        Extract Controller→Service→Repository dependency chains
        from field injection / constructor injection.
        """
        chains: List[Tuple[str, str, str]] = []
        class_by_name = {c.name: c for c in classes}
        class_by_type = {}
        for c in classes:
            class_by_type[c.name] = c
            # Also map interface implementations
            for iface in c.implements:
                class_by_type[iface] = c

        for cls in classes:
            for fld in cls.fields:
                target_type = re.sub(r'<.*>', '', fld.field_type).strip()
                target_cls = class_by_name.get(target_type)
                if not target_cls:
                    continue

                # Determine relationship type
                if cls.stereotype in ("Controller",) and target_cls.stereotype in ("Service",):
                    chains.append((cls.name, target_cls.name, "CALLS"))
                elif cls.stereotype in ("Service",) and target_cls.stereotype in ("Repository",):
                    chains.append((cls.name, target_cls.name, "CALLS"))
                elif cls.stereotype in ("Service",) and target_cls.stereotype in ("Service",):
                    chains.append((cls.name, target_cls.name, "DEPENDS_ON"))
                elif fld.is_injected:
                    chains.append((cls.name, target_cls.name, "DEPENDS_ON"))

        return chains
