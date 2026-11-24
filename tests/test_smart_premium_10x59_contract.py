from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/SMART_PREMIUM_10X59_UI_CONTRACT.md"

def test_contract_defines_exactly_ten_main_menus_and_fifty_nine_submenus():
    text = CONTRACT.read_text(encoding="utf-8")
    sections = re.findall(r"(?m)^### (\d{2}) — (.+?) \((\d+)\)$", text)
    assert len(sections) == 10
    assert [int(number) for number, _, _ in sections] == list(range(1, 11))
    declared_counts = [int(count) for _, _, count in sections]
    assert declared_counts == [6, 7, 5, 9, 6, 6, 6, 5, 5, 4]
    assert sum(declared_counts) == 59

    catalog_section = text.split("## Main menu and submenu target", 1)[1].split("**Count check:**", 1)[0]
    numbered = [int(number) for number in re.findall(r"(?m)^(\d+)\. ", catalog_section)]
    assert numbered == list(range(1, 60))
    assert len(set(numbered)) == 59

def test_contract_preserves_task_workflow_and_truthful_backend_rules():
    text = CONTRACT.read_text(encoding="utf-8")
    for phrase in (
        "Preserve all working legacy operations",
        "Combine PAK and UnPAK",
        "Never overwrite source inputs by default",
        "Each visible operation must map to one Smart Engine workflow",
        "ARM64 acceptance evidence",
    ):
        assert phrase in text
