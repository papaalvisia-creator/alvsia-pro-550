from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
VAULT = (ROOT / "app/src/main/java/com/alvsia/pro/panel/Vault.kt").read_text(encoding="utf-8")
XML = (ROOT / "app/src/main/res/xml/network_security_config.xml").read_text(encoding="utf-8")
PYTHON = (ROOT / "app/src/main/python/pinned_http.py").read_text(encoding="utf-8")

def test_panel_pin_sets_are_identical_across_all_clients():
    kotlin_pins = set(re.findall(r'sha256/([A-Za-z0-9+/=]+)', VAULT))
    xml_pins = set(re.findall(r'<pin digest="SHA-256">([^<]+)</pin>', XML))
    python_pins = set(re.findall(r'"([A-Za-z0-9+/=]{43}=)"', PYTHON))
    assert len(kotlin_pins) == 3
    assert kotlin_pins == xml_pins == python_pins

def test_only_active_unaux_panel_host_is_configured():
    assert 'PANEL_ORIGIN = "https://alvsiapanel.unaux.com"' in VAULT
    assert '<domain includeSubdomains="true">alvsiapanel.unaux.com</domain>' in XML
    assert 'PANEL_HOSTS = frozenset(("alvsiapanel.unaux.com",))' in PYTHON
    assert "alvsiapro.cc.cd" not in VAULT + XML + PYTHON

def test_tls_remains_fail_closed_and_cleartext_disabled():
    assert 'cleartextTrafficPermitted="false"' in XML
    assert '.certificatePinner(Vault.certPinner())' in (
        ROOT / "app/src/main/java/com/alvsia/pro/panel/PanelClient.kt"
    ).read_text(encoding="utf-8")
    assert 'kwargs["verify"] = True' in PYTHON
