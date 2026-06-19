"""
combiner — Component 2: Simple Code Combiner
Airtel Enterprise AI Documentation System
"""
from .combiner import SimpleCodeCombiner
from .models import CombinedProject, Dependency, SQLTable, NormalizedSymbol
from .exporter import export_xml

__all__ = [
    "SimpleCodeCombiner",
    "CombinedProject", "Dependency", "SQLTable", "NormalizedSymbol",
    "export_xml",
]
__version__ = "1.0.0"
