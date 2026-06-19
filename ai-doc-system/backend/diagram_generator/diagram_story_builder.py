"""
diagram_generator/diagram_story_builder.py
────────────────────────────────────────────────────────────────
Diagram Intelligence Layer.
Converts the Architecture Intelligence Model (AIM) into 
cohesive, narrative-driven Mermaid diagrams with visual hierarchy.
"""

import re

MERMAID_INIT = (
    '%%{init: {"theme": "base", "themeVariables": {'
    '"fontSize": "12px", "fontFamily": "Arial, sans-serif",'
    '"primaryColor": "#E3F2FD", "lineColor": "#555555",'
    '"edgeLabelBackground": "#ffffff"}}}%%\n'
)

class DiagramStoryBuilder:
    def __init__(self, aim):
        self.aim = aim

    def _safe_id(self, text: str) -> str:
        if not text:
            return "unknown"
        return re.sub(r"[^a-zA-Z0-9_]", "_", text)

    def _rank_and_filter(self, items: list, limit: int, key_func=None) -> list:
        if not items:
            return []
        if key_func:
            return sorted(items, key=key_func, reverse=True)[:limit]
        return items[:limit]

    def build_executive_story(self) -> str:
        lines = ["flowchart LR", ""]
        
        # 1. Actors Subgraph
        actors = ["User"]
        if self.aim and hasattr(self.aim, 'domain') and hasattr(self.aim.domain, 'user_personas') and self.aim.domain.user_personas:
            actors = self.aim.domain.user_personas
            
        lines.append('    subgraph Actors ["External Actors"]')
        lines.append('        direction TB')
        actor_ids = []
        for a in actors[:3]:
            aid = self._safe_id(a)
            actor_ids.append(aid)
            lines.append(f'        {aid}["{a}"]:::actor')
        lines.append('    end')
        lines.append('')
        
        # 2. Platform Subgraph
        core_name = "Core Platform"
        if self.aim and hasattr(self.aim, 'domain') and getattr(self.aim.domain, 'primary_domain', None):
            core_name = self.aim.domain.primary_domain
        core_id = self._safe_id(core_name)
        lines.append(f'    subgraph Core ["{core_name}"]')
        engine_label = f"{core_name} Engine" if core_name != "Core Platform" else "Platform Engine"
        lines.append(f'        {core_id}["{engine_label}"]:::core')
        lines.append('    end')
        lines.append('')

        # Add Data Store node
        infra = getattr(getattr(self.aim, 'deployment', None), 'infrastructure_components', []) or []
        db_infra = [i for i in infra if any(kw in i.lower() for kw in ["db", "database", "postgres", "sql", "mongo"])]
        store_label = db_infra[0] if db_infra else "Data Store"
        store_id = self._safe_id(store_label)
        lines.append(f'    {store_id}[("{store_label}")]:::store')
        lines.append('')

        # 3. Outputs Subgraph
        _DOMAIN_OUTCOMES = {
            "E-Commerce":              "Orders Fulfilled",
            "Financial Services":      "Transactions Processed",
            "Healthcare IT":           "Care Delivered",
            "CRM & Sales":             "Deals Closed",
            "Logistics & Supply Chain":"Shipments Delivered",
            "Telecom":                 "Services Activated",
            "Insurance":               "Claims Resolved",
            "Data Platform":           "Insights Delivered",
            "AI & ML Platform":        "Documentation Generated",
            "Developer Platform":      "Software Deployed",
            "Enterprise Application":  "Workflows Completed",
        }

        domain_name = getattr(getattr(self.aim, 'domain', None), 'primary_domain', '')
        biz_funcs   = getattr(getattr(self.aim, 'domain', None), 'business_functions', []) or []
        outcome = _DOMAIN_OUTCOMES.get(domain_name, biz_funcs[-1] if biz_funcs else "Business Value")

        out_id = self._safe_id(outcome)
        lines.append('    subgraph Outcomes ["Business Outputs"]')
        lines.append(f'        {out_id}["{outcome}"]:::output')
        lines.append('    end')
        lines.append('')

        # Edges
        lines.append(f"    {actor_ids[0]} -->|Interacts with| {core_id}")
        lines.append(f"    {core_id} -->|Persists to| {store_id}")
        lines.append(f"    {core_id} -->|Generates| {out_id}")
        lines.append('')

        # Styling
        lines.append("    classDef actor fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#4a148c")
        lines.append("    classDef core fill:#e3f2fd,stroke:#1976d2,stroke-width:3px,color:#0d47a1")
        lines.append("    classDef store fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20")
        lines.append("    classDef output fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100")
        lines.append("    classDef cluster fill:#f8f9fa,stroke:#dee2e6,stroke-width:2px,stroke-dasharray: 5 5")
        lines.append("")
        lines.append("    class Actors,Core,Outcomes cluster")
        
        return MERMAID_INIT + "\n".join(lines)

    def build_business_process_story(self) -> str:
        """
        Business Capability Map: Core capabilities in one subgraph,
        supporting capabilities in another, with an enabling edge between.
        """
        if not self.aim:
            return ""

        core_caps = getattr(self.aim.capabilities, 'core_capabilities', []) or []
        supp_caps = getattr(self.aim.capabilities, 'supporting_capabilities', []) or []

        if not core_caps and not supp_caps:
            return ""

        lines = ["flowchart LR", ""]
        lines.append("    classDef core    fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1")
        lines.append("    classDef support fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20")
        lines.append("    classDef cluster fill:#f8f9fa,stroke:#dee2e6,stroke-dasharray:5 5")
        lines.append("")

        core_ids = []
        if core_caps:
            lines.append('    subgraph CoreCaps ["Core Capabilities"]')
            lines.append('        direction LR')
            for cap in core_caps[:4]:
                cid = self._safe_id(cap.name)
                lines.append(f'        {cid}["{cap.name}"]:::core')
                core_ids.append(cid)
                
            if len(core_ids) == 1 and not supp_caps:
                init_id = f"init_{core_ids[0]}"
                comp_id = f"comp_{core_ids[0]}"
                lines.append(f'        {init_id}["Initialize {core_caps[0].name}"]:::core')
                lines.append(f'        {comp_id}["Complete {core_caps[0].name}"]:::core')
                lines.append(f'        {init_id} --> {core_ids[0]}')
                lines.append(f'        {core_ids[0]} --> {comp_id}')
            else:
                for i in range(len(core_ids) - 1):
                    lines.append(f'        {core_ids[i]} --> {core_ids[i+1]}')
                    
            lines.append('    end')
            lines.append('    class CoreCaps cluster')
            lines.append('')

        supp_ids = []
        if supp_caps:
            lines.append('    subgraph SuppCaps ["Supporting Capabilities"]')
            lines.append('        direction LR')
            for cap in supp_caps[:2]:
                sid = self._safe_id(cap.name)
                lines.append(f'        {sid}["{cap.name}"]:::support')
                supp_ids.append(sid)
            lines.append('    end')
            lines.append('    class SuppCaps cluster')
            lines.append('')

        # Cross-subgraph enabling edge
        if supp_ids and core_ids:
            lines.append(f'    {supp_ids[0]} -.->|Enables| {core_ids[0]}')

        return MERMAID_INIT + "\n".join(lines)

    _TRANSITION_VERBS = {
        ("Product Catalog", "Shopping Cart"):     "Selected into",
        ("Shopping Cart", "Customer Order"):      "Converted to",
        ("Customer Order", "Payment Transaction"): "Triggers",
        ("Payment Transaction", "Inventory Record"): "Updates",
        ("Account", "Transaction"):               "Generates",
        ("Transaction", "Ledger"):                "Posted to",
        ("Ledger", "Statement"):                  "Summarized in",
        ("Patient Record", "Encounter"):          "Linked to",
        ("Encounter", "Prescription"):            "Results in",
    }

    def _get_transition_verb(self, from_stage: str, to_stage: str) -> str:
        key = (from_stage, to_stage)
        if key in self._TRANSITION_VERBS:
            return self._TRANSITION_VERBS[key]
        f, t = from_stage.lower(), to_stage.lower()
        if any(w in t for w in ["order", "request", "booking"]): return "Creates"
        if any(w in t for w in ["payment", "transaction"]):       return "Triggers"
        if any(w in t for w in ["record", "log", "history"]):     return "Recorded in"
        if any(w in f for w in ["cart", "basket"]):               return "Submitted as"
        return "Flows to"

    def build_information_flow_story(self) -> str:
        flows = []
        if self.aim and hasattr(self.aim, 'information'):
            flows = getattr(self.aim.information, 'primary_data_flows', []) or []
        if not flows:
            return ""

        flow = flows[0]
        stages = getattr(flow, 'stages', []) or []
        if len(stages) < 2:
            return ""

        # Use a meaningful flow name
        flow_name = getattr(flow, 'name', '') or ''
        if not flow_name or flow_name in ("Primary Processing Pipeline", "Primary Processing Flow"):
            domain = getattr(getattr(self.aim, 'domain', None), 'primary_domain', 'Business')
            flow_name = f"{domain} Information Flow"

        lines = ["flowchart LR", ""]
        lines.append(f'    subgraph InfoFlow ["{flow_name}"]')
        lines.append('        direction LR')

        prev_id, prev_name = None, None
        for step in stages[:6]:
            if not step:
                continue
            aid = self._safe_id(step)
            lines.append(f'        {aid}["{step}"]:::asset')
            if prev_id and prev_name:
                verb = self._get_transition_verb(prev_name, step)
                lines.append(f'        {prev_id} -->|{verb}| {aid}')
            prev_id, prev_name = aid, step

        lines.append('    end')
        lines.append('')
        lines.append("    classDef asset fill:#fff3e0,stroke:#f57c00,stroke-width:2px,color:#e65100")
        lines.append("    classDef cluster fill:#f8f9fa,stroke:#dee2e6,stroke-dasharray:5 5")
        lines.append("    class InfoFlow cluster")
        return MERMAID_INIT + "\n".join(lines)

    def build_deployment_story(self) -> str:
        """
        Deployment topology: Client → App Server → Data Tier.
        Shows infrastructure components, NOT services.
        """
        if not self.aim:
            return ""

        infra = getattr(self.aim.deployment, 'infrastructure_components', []) or []
        domain_name = getattr(getattr(self.aim, 'domain', None), 'primary_domain', '')
        hosting = getattr(self.aim.deployment, 'hosting_model', 'Local') or 'Local'

        lines = ["flowchart LR", ""]
        lines.append("    classDef client  fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#4a148c")
        lines.append("    classDef server  fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1")
        lines.append("    classDef store   fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20")
        lines.append("    classDef cluster fill:#f8f9fa,stroke:#dee2e6,stroke-dasharray:5 5")
        lines.append("")

        protocol = "CLI" if domain_name in ("AI & ML Platform", "Developer Platform") else "HTTPS"

        # Client
        lines.append('    Client["Client"]:::client')

        # Application tier
        app_name = f"{domain_name} Application" if domain_name else "Application Server"
        app_id = self._safe_id(app_name)
        lines.append(f'    {app_id}["{app_name}"]:::server')

        # Data stores from infrastructure
        db_infra = [i for i in infra if any(
            kw in i.lower() for kw in ["db", "database", "sql", "postgres", "mysql", "mongo", "redis", "neo4j", "sqlite"]
        )]
        non_db_infra = [i for i in infra if i not in db_infra]

        store_ids = []
        for db in db_infra[:3]:
            did = self._safe_id(db)
            lines.append(f'    {did}[("{db}")]:::store')
            store_ids.append(did)

        queue_ids = []
        for ndb in non_db_infra[:2]:
            qid = self._safe_id(ndb)
            lines.append(f'    {qid}["{ndb}"]:::server')
            queue_ids.append(qid)

        lines.append("")
        lines.append(f'    Client -->|{protocol}| {app_id}')
        for sid in store_ids:
            lines.append(f'    {app_id} --> {sid}')
        for qid in queue_ids:
            lines.append(f'    {app_id} -.-> {qid}')

        # If no infra found, add a generic database node so diagram has edges
        if not store_ids and not queue_ids:
            lines.append('    DB[("Database")]:::store')
            lines.append(f'    {app_id} --> DB')

        return MERMAID_INIT + "\n".join(lines)

    def _classify_service_tier(self, service_name: str) -> str:
        name_lower = service_name.lower()
        if any(kw in name_lower for kw in ["gpu", "model", "inference", "bert", "embedding", "vector"]):
            return "gpu"
        if any(kw in name_lower for kw in ["db", "database", "sql", "mongo", "redis", "elastic", "neo4j", "blob", "cache", "store", "vector"]):
            return "store"
        if any(kw in name_lower for kw in ["infrastructure", "support", "update", "backend", "admin", "monitor", "dashboard"]):
            return "ops"
        return "service"

    def _build_annotation_box(self, steps: list) -> str:
        if not steps:
            return ""
        lines = []
        lines.append('    subgraph QuestionAnsweringFlow ["Request Processing Flow"]')
        lines.append('        direction TB')
        for i, step in enumerate(steps, 1):
            step_clean = step.replace('"', "'")
            lines.append(f'        Step{i}["{i}. {step_clean}"]:::note')
            
        for i in range(1, len(steps)):
            lines.append(f'        Step{i} -.-> Step{i+1}')
            
        lines.append('    end')
        return "\n".join(lines)

    def build_architecture_story(self) -> str:
        """
        Zone-based System Context Diagram:
        Actors (left) -> DMZ -> Core Platform -> Backend Ops -> Outputs.
        """
        if not self.aim:
            return ""

        lines = ["flowchart LR", ""]
        
        # Style Definitions
        lines.append("    classDef actor    fill:#f3e5f5,stroke:#ab47bc,stroke-width:2px,color:#4a148c")
        lines.append("    classDef dmz      fill:#fce4ec,stroke:#e57373,stroke-width:2px,stroke-dasharray:5 5")
        lines.append("    classDef service  fill:#e3f2fd,stroke:#1976d2,stroke-width:2px,color:#0d47a1")
        lines.append("    classDef gpu      fill:#fff3e0,stroke:#f57c00,stroke-width:3px,color:#e65100")
        lines.append("    classDef store    fill:#e8f5e9,stroke:#388e3c,stroke-width:2px,color:#1b5e20")
        lines.append("    classDef ops      fill:#e0f2f1,stroke:#00897b,stroke-width:2px,color:#004d40")
        lines.append("    classDef output   fill:#f1f8e9,stroke:#7cb342,stroke-width:2px,color:#33691e")
        lines.append("    classDef note     fill:#fafafa,stroke:#bdbdbd,stroke-width:1px,color:#424242")
        lines.append("")
        
        # Zone styling using subgraph styling
        lines.append("    style Zone1 fill:none,stroke:#ab47bc,stroke-width:2px,stroke-dasharray: 5 5")
        lines.append("    style Zone2 fill:#fce4ec,stroke:#e57373,stroke-width:2px,stroke-dasharray: 5 5")
        lines.append("    style Zone3 fill:none,stroke:#1976d2,stroke-width:2px")
        lines.append("    style Zone4 fill:none,stroke:#00897b,stroke-width:2px")
        lines.append("    style Zone5 fill:none,stroke:#7cb342,stroke-width:2px")
        lines.append("")

        total_nodes = 0
        MAX_NODES = 22

        # ZONE 1 — "External Users"
        lines.append('    subgraph Zone1 ["External Users"]')
        lines.append('        direction TB')
        
        personas = getattr(self.aim.domain, 'user_personas', []) or []
        primary_domain = getattr(self.aim.domain, 'primary_domain', '')
        if primary_domain in ("AI & ML Platform", "Developer Platform") and "Developer / Admin" not in personas:
            personas.append("Developer / Admin")
        if not personas:
            personas = ["End Users"]
            
        actor_ids = []
        for p in personas[:3]:
            if total_nodes >= MAX_NODES: break
            aid = self._safe_id(p)
            lines.append(f'        {aid}["{p}"]:::actor')
            actor_ids.append(aid)
            total_nodes += 1
            
        lines.append('    end')
        lines.append("")

        # ZONE 2 — "DMZ / Security Perimeter"
        lines.append('    subgraph Zone2 ["DMZ / Security Perimeter"]')
        lines.append('        direction TB')
        
        waf_id = "WAF_Node"
        lines.append(f'        {waf_id}["Web Application Firewall (WAF)"]:::dmz')
        total_nodes += 1
        
        infra = getattr(self.aim.deployment, 'infrastructure_components', []) or []
        api_gw_label = "API Gateway (HTTP)"
        for i in infra:
            if "gateway" in i.lower() or "api" in i.lower() or "." in i:
                api_gw_label = f"API Gateway ({i})"
                break
        
        gw_id = "API_GW"
        lines.append(f'        {gw_id}["{api_gw_label}"]:::dmz')
        lines.append(f'        DMZ_Note["All external traffic enters here"]:::note')
        lines.append(f'        DMZ_Note -.-> {gw_id}')
        total_nodes += 2
        
        lines.append('    end')
        lines.append("")
        
        # ZONE 3 — "Core Platform / NON-DMZ"
        lines.append('    subgraph Zone3 ["Core Platform / NON-DMZ"]')
        lines.append('        direction TB')
        
        # Row A - Processing Services
        lines.append('        subgraph RowA ["Processing Services"]')
        lines.append('            direction LR')
        
        services = self.aim.services.services or []
        proc_svcs = [s for s in services if s.service_type in ["Domain", "Application", "Analysis"]]
        if not proc_svcs:
            proc_svcs = [s for s in services][:6]
            
        svc_ids = []
        gpu_svcs = []
        regular_svcs = []
        
        for s in proc_svcs[:6]:
            if self._classify_service_tier(s.name) == "gpu":
                gpu_svcs.append(s)
            else:
                regular_svcs.append(s)
                
        for s in regular_svcs:
            if total_nodes >= MAX_NODES: break
            sid = self._safe_id(s.name)
            short_name = s.name.replace(" Service", "")
            lines.append(f'            {sid}["{short_name}"]:::service')
            svc_ids.append(sid)
            total_nodes += 1
            
        if gpu_svcs and total_nodes < MAX_NODES:
            lines.append('            subgraph GPU_Tier ["GPU / ML Inference Tier"]')
            lines.append('                style GPU_Tier fill:#fff3e0,stroke:#f57c00')
            for s in gpu_svcs:
                if total_nodes >= MAX_NODES: break
                sid = self._safe_id(s.name)
                short_name = s.name.replace(" Service", "")
                lines.append(f'                {sid}["{short_name}"]:::gpu')
                svc_ids.append(sid)
                total_nodes += 1
            lines.append('            end')
            
        lines.append('        end')
        
        # Row B - Data Layer
        lines.append('        subgraph RowB ["Data Layer"]')
        lines.append('            direction LR')
        
        db_infra = [i for i in infra if any(kw in i.lower() for kw in ["db", "database", "sql", "mysql", "mongo", "redis", "elastic", "neo4j", "blob", "cache", "vector", "postgres"])]
        
        store_ids = []
        grouped_stores = {
            "Search & Index": [d for d in db_infra if "elastic" in d.lower() or "vector" in d.lower()],
            "Document Store": [d for d in db_infra if "mongo" in d.lower() or "doc" in d.lower()],
            "Relational": [d for d in db_infra if "sql" in d.lower() or "postgres" in d.lower()],
            "Cache": [d for d in db_infra if "redis" in d.lower() or "cache" in d.lower()],
            "Object Storage": [d for d in db_infra if "blob" in d.lower() or "s3" in d.lower()]
        }
        
        assigned_dbs = set()
        for group, dbs in grouped_stores.items():
            if not dbs: continue
            grp_id = self._safe_id(group)
            lines.append(f'            subgraph {grp_id} ["{group}"]')
            for db in dbs:
                if db in assigned_dbs: continue
                if total_nodes >= MAX_NODES: break
                did = self._safe_id(db)
                lines.append(f'                {did}[("{db}")]:::store')
                store_ids.append(did)
                assigned_dbs.add(db)
                total_nodes += 1
            lines.append('            end')
            
        unassigned_dbs = [d for d in db_infra if d not in assigned_dbs]
        if unassigned_dbs:
            lines.append('            subgraph Generic_Stores ["Persistent Data Stores"]')
            for db in unassigned_dbs:
                if total_nodes >= MAX_NODES: break
                did = self._safe_id(db)
                lines.append(f'                {did}[("{db}")]:::store')
                store_ids.append(did)
                total_nodes += 1
            lines.append('            end')
            
        # Add fallback database if no data layer found
        if not store_ids and total_nodes < MAX_NODES:
            fallback_db_id = "Fallback_DB"
            lines.append(f'            {fallback_db_id}[("Primary Database")]:::store')
            store_ids.append(fallback_db_id)
            total_nodes += 1
            
        lines.append('        end')
        lines.append('    end')
        lines.append("")

        # ZONE 4 — "Backend Operations"
        ops_svcs = [s for s in services if s.service_type in ["Infrastructure", "Support", "Update", "Backend"]]
        ops_ids = []
        if ops_svcs and total_nodes < MAX_NODES:
            lines.append('    subgraph Zone4 ["Backend Operations"]')
            lines.append('        direction TB')
            for s in ops_svcs[:3]:
                if total_nodes >= MAX_NODES: break
                oid = self._safe_id(s.name)
                short_name = s.name.replace(" Service", "")
                lines.append(f'        {oid}["{short_name}"]:::ops')
                ops_ids.append(oid)
                total_nodes += 1
            lines.append('    end')
            lines.append("")

        # ZONE 5 — "Outputs / Business Value"
        lines.append('    subgraph Zone5 ["Outputs / Business Value"]')
        lines.append('        direction TB')
        
        output_label = "Generated Output"
        try:
            if getattr(self.aim, 'information', None) and getattr(self.aim.information, 'primary_data_flows', None):
                flow = self.aim.information.primary_data_flows[0]
                if getattr(flow, 'outcome', None):
                    output_label = flow.outcome
                elif getattr(flow, 'stages', None):
                    output_label = flow.stages[-1]
        except Exception:
            pass
            
        out_id = self._safe_id(output_label)
        lines.append(f'        {out_id}["{output_label}"]:::output')
        lines.append('    end')
        lines.append("")
        
        # Edges
        # Zone 1 -> Zone 2
        for aid in actor_ids:
            lines.append(f"    {aid} --> {waf_id}")
            
        lines.append(f"    {waf_id} -- \"①\" --> {gw_id}")
        
        # Zone 2 -> Zone 3 Row A
        circle_numbers = ["②", "③", "④", "⑤", "⑥", "⑦"]
        if svc_ids:
            for i, sid in enumerate(svc_ids):
                circ = circle_numbers[i] if i < len(circle_numbers) else "→"
                lines.append(f"    {gw_id} -- \"{circ}\" --> {sid}")
                
        # Zone 3 Row A -> Row B
        if svc_ids and store_ids:
            for sid in svc_ids:
                sid_lower = sid.lower()
                mapped = False
                for store_id in store_ids:
                    store_lower = store_id.lower()
                    if "search" in sid_lower and ("elastic" in store_lower or "vector" in store_lower):
                        lines.append(f"    {sid} --> {store_id}")
                        mapped = True
                    elif "doc" in sid_lower and "mongo" in store_lower:
                        lines.append(f"    {sid} --> {store_id}")
                        mapped = True
                if not mapped:
                    lines.append(f"    {sid} --> {store_ids[0]}")
                    
        # Zone 3 -> Zone 4
        if svc_ids and ops_ids:
            lines.append(f"    {ops_ids[0]} -.-> {svc_ids[0]}")
            
        # Zone 3 -> Zone 5
        if svc_ids:
            lines.append(f"    {svc_ids[-1]} --> {out_id}")
        else:
            lines.append(f"    {gw_id} --> {out_id}")
            
        lines.append("")
        
        # Annotation Box
        narrative = getattr(self.aim, 'narrative', None)
        exec_summary = getattr(narrative, 'executive_summary', '') if narrative else ''
        
        steps = []
        if exec_summary and "1." in exec_summary:
            import re
            step_matches = re.findall(r'\d+\.\s+([^\n]+)', exec_summary)
            if step_matches:
                steps = step_matches[:5]
                
        if not steps:
            primary_svc = svc_ids[0] if svc_ids else "Primary Service"
            store_name = store_ids[0] if store_ids else "Database"
            sec_svc = svc_ids[1] if len(svc_ids) > 1 else ""
            
            steps.append("User sends request to API Gateway")
            steps.append(f"API Gateway routes to {primary_svc.replace('_', ' ')}")
            steps.append(f"{primary_svc.replace('_', ' ')} queries {store_name.replace('_', ' ')}")
            if sec_svc:
                steps.append(f"Response enriched by {sec_svc.replace('_', ' ')}")
            steps.append("Result returned to user")
            
        lines.append(self._build_annotation_box(steps))

        return MERMAID_INIT + "\n".join(lines)
