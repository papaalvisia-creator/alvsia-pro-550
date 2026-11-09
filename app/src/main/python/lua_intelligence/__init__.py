"""ALVSIA Program Intelligence core.

Static, file-backed analysis primitives for recursive Lua/program research.
No unknown input is executed by this package.
"""
from .core import IntelligenceEngine, IntelligenceConfig, analyze_file
from .model import LayerArtifact, AnalysisEvidence, AnalysisResult

__all__ = [
    "IntelligenceEngine", "IntelligenceConfig", "analyze_file",
    "LayerArtifact", "AnalysisEvidence", "AnalysisResult",
]
