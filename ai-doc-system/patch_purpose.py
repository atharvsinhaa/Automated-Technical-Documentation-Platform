with open("backend/document_generator/lld_generator.py", "r") as f:
    code = f.read()

old_logic = """            purpose = getattr(comp, 'purpose', '').strip().replace("\\n", " ")
            if not purpose:
                purpose = "Internal component."
                
            # If the purpose is too long, we extract a concise sentence.
            sentences = [s.strip() for s in purpose.split(".") if s.strip()]
            concise_purpose = sentences[0] + "." if sentences else purpose"""

new_logic = """            purpose = getattr(comp, 'purpose', '').strip().replace("\\n", " ")
            
            # Check if purpose is missing or generic
            generic_terms = ["internal component", "core component", "utility component", "infrastructure component", "generic component", "core service", "utility module"]
            is_generic = not purpose or any(purpose.lower().startswith(t) for t in generic_terms)
            
            if is_generic:
                # Synthesize from evidence
                name_low = comp.name.lower()
                consumes = getattr(comp, 'consumes', [])
                produces = getattr(comp, 'produces', [])
                deps = getattr(comp, 'depends_on', [])
                
                # Role inference
                role = "Manages"
                if "ast" in name_low or "parser" in name_low: role = "Parses"
                elif "extract" in name_low: role = "Extracts"
                elif "graph" in name_low or "store" in name_low or "repo" in name_low: role = "Stores"
                elif "ir" in name_low or "semantic" in name_low: role = "Converts"
                elif "intell" in name_low or "analyz" in name_low: role = "Infers"
                elif "build" in name_low or "combin" in name_low: role = "Builds"
                elif "generat" in name_low: role = "Produces"
                elif "diagram" in name_low: role = "Generates"
                elif "docx" in name_low or "service" in name_low: role = "Renders"
                elif "orchestrator" in name_low: role = "Orchestrates"
                
                # Known system components
                if "ast engine" in name_low or "universal ast" in name_low:
                    purpose = "Parses source code into a normalized language-agnostic AST representation."
                elif "dependency extractor" in name_low:
                    purpose = "Extracts imports, calls, and structural relationships from parsed code."
                elif "knowledge graph" in name_low:
                    purpose = "Stores code entities and relationships as a graph model for analysis."
                elif "semantic ir" in name_low:
                    purpose = "Converts graph data into a normalized semantic representation."
                elif "architecture intelligence" in name_low:
                    purpose = "Infers architecture patterns, capabilities, and system characteristics."
                elif "aim" in name_low or "combiner" in name_low:
                    purpose = "Builds the Architecture Intelligence Model (AIM) from analyzed artifacts."
                elif "hld" in name_low or "document generator" in name_low:
                    purpose = "Produces high-level architecture and technical design documentation."
                elif "lld" in name_low:
                    purpose = "Produces low-level technical design documentation."
                elif "diagram" in name_low:
                    purpose = "Generates Mermaid-based architecture and design diagrams."
                elif "docx" in name_low:
                    purpose = "Renders documentation into Word documents."
                elif "context builder" in name_low:
                    purpose = "Builds execution context from repository artifacts and dependencies."
                elif "comment engine" in name_low:
                    purpose = "Generates semantic documentation and code comments for parsed artifacts."
                elif "semantic bridge" in name_low:
                    purpose = "Bridges structural dependencies with semantic models for analysis."
                elif "llm orchestrator" in name_low:
                    purpose = "Orchestrates LLM inference tasks across the generation pipeline."
                elif "object model extractor" in name_low:
                    purpose = "Extracts object-oriented structures and relationships from code."
                else:
                    # Dynamic synthesis if not hardcoded
                    if role == "Parses" and produces: purpose = f"Parses input into {produces[0]} representations."
                    elif role == "Extracts" and consumes: purpose = f"Extracts artifacts from {consumes[0]}."
                    elif role == "Produces" and produces: purpose = f"Produces {produces[0]} documentation."
                    else: purpose = "Purpose could not be confidently determined."
                    
            # If the purpose is too long, we extract a concise sentence.
            sentences = [s.strip() for s in purpose.split(".") if s.strip()]
            concise_purpose = sentences[0] + "." if sentences else purpose
            
            # Enforce fallback if empty or still generic
            if concise_purpose.lower() in generic_terms or not concise_purpose:
                concise_purpose = "Purpose could not be confidently determined." """

code = code.replace(old_logic, new_logic)

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code)

print("Patched component purposes.")
