with open("backend/document_generator/lld_generator.py", "r") as f:
    code = f.read()

old_snap = """        lines.append("| Dimension | Value |")
        lines.append("|---|---|")
        lines.append(f"| Repository | {repo_name} |")
        lines.append(f"| Language(s) | {lang_str} |")
        lines.append(f"| Architecture | **{arch_str}** |")
        lines.append(f"| Arch Confidence | {arch_conf} |")
        lines.append(f"| Arch Evidence | {arch_ev} |")
        lines.append(f"| Modules | {modules} |")
        lines.append(f"| Core Classes | {core_classes} |")
        lines.append(f"| External Services | {ext_str} |")
        lines.append(f"| Entry Point | {entry} |")
        lines.append(f"| Circular Deps | {circular} detected |")
        lines.append("")"""

new_snap = """        lines.append("| Dimension | Value |")
        lines.append("|---|---|")
        lines.append(f"| Repository | {repo_name} |")
        lines.append(f"| Language(s) | {lang_str} |")
        lines.append(f"| Modules | {modules} |")
        lines.append(f"| Core Classes | {core_classes} |")
        lines.append(f"| External Services | {ext_str} |")
        lines.append(f"| Entry Point | {entry} |")
        lines.append(f"| Circular Deps | {circular} detected |")
        lines.append("")
        
        lines.append("### Architecture Classification")
        lines.append("")
        if not arch_ev or "No structural evidence" in arch_ev:
            lines.append("**Architecture:** Unknown")
        else:
            lines.append(f"**Architecture:** {arch_str}")
            lines.append(f"**Confidence:** {arch_conf}")
            lines.append("")
            lines.append("**Evidence:**")
            for ev in arch_ev.split(","):
                ev = ev.strip()
                if ev:
                    lines.append(f"- {ev}")
        lines.append("")"""

code = code.replace(old_snap, new_snap)

with open("backend/document_generator/lld_generator.py", "w") as f:
    f.write(code)

print("Patched snapshot.")
