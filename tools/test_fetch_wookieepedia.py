import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("wp", ROOT / "tools/fetch-wookieepedia.py")
wp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wp)

WIKITEXT = """{{Top|legends=}}
{{Update|[[Star Wars: The Old Republic: Onslaught]]}}
{{CelestialBody
|image=[[File:Eriadu_TEA.jpg]]
|name=Eriadu
|region=*[[Outer Rim Territories/Legends|Outer Rim Territories]]<ref name="EAOC">{{SW|url=x|text=''Atlas''}}</ref>
*[[Trailing Sectors/Legends|Trailing Sectors]]<ref name="Region">''[[The Essential Atlas]]'' &mdash; map</ref>
|sector=[[Seswenna sector/Legends|Seswenna sector]]<ref name="EAOC" />
|routes=*[[Hydian Way/Legends|Hydian Way]]<ref name="EA" />
*[[Rimma Trade Route/Legends|Rimma Trade Route]]<ref name="EA" />
|atmosphere=[[Atmosphere/Legends#Type I|Type I]] {{C|breathable}}<ref name="GORW" />
|terrain=*Industrial cityscape<ref name="GORW" />
*Waste zones<ref name="GORW" />
|population=22 billion<ref name="GORW" />
|affiliation=*[[Galactic Republic/Legends|Galactic Republic]]
*[[Galactic Empire/Legends|Galactic Empire]]
}}
{{Quote|Eriadu is a wretched hive.|Someone|Book}}
'''Eriadu''' was a [[planet/Legends|planet]] in the [[Seswenna sector/Legends|Seswenna sector]] of the [[Outer Rim Territories/Legends|Outer Rim]].<ref name="EA" /> It was the homeworld of [[Wilhuff Tarkin]] and an industrial powerhouse, located at the junction of the [[Hydian Way/Legends|Hydian Way]] and the [[Rimma Trade Route/Legends|Rimma Trade Route]]. Over the centuries it grew rich and polluted.

==History==
Later text that is not the lead.
"""


def test_facts_render_lists_links_refs_and_comment_templates():
    facts = wp.parse_facts(WIKITEXT)
    assert facts["region"] == "Outer Rim Territories, Trailing Sectors"
    assert facts["sector"] == "Seswenna sector"
    assert facts["routes"] == "Hydian Way, Rimma Trade Route"
    assert facts["terrain"] == "Industrial cityscape, Waste zones"
    assert facts["population"] == "22 billion"
    assert facts["affiliation"] == "Galactic Republic, Galactic Empire"
    assert "atmosphere" not in facts  # not a fact key we keep
    assert "<ref" not in str(facts) and "[[" not in str(facts)


def test_lead_is_first_prose_paragraph_without_markup():
    lead = wp.parse_lead(WIKITEXT)
    assert lead.startswith("Eriadu was a planet in the Seswenna sector of the Outer Rim.")
    assert "Wilhuff Tarkin" in lead and "wretched hive" not in lead
    assert "[[" not in lead and "{{" not in lead and "<ref" not in lead
    assert "Later text" not in lead


def test_lead_is_capped_at_a_sentence_boundary():
    long = "{{Box|name=X}}\n'''X''' was a world. " + ("It had many things to say about itself. " * 40)
    lead = wp.parse_lead(long)
    assert len(lead) <= wp.LEAD_MAX and lead.endswith(".")


def test_infobox_image_and_title_candidates():
    assert wp.infobox_image(WIKITEXT) == "Eriadu_TEA.jpg"
    assert wp.title_candidates("Brentaal") == ["Brentaal/Legends", "Brentaal"]
    assert wp.title_candidates("Brentaal", "Brentaal IV/Legends") == ["Brentaal IV/Legends"]


def test_clean_handles_comment_template_and_entities():
    assert wp.clean("[[Atmosphere/Legends#Type I|Type I]] {{C|breathable}}<ref name=\"x\" />") == "Type I (breathable)"
    assert wp.clean("''Atlas'' &mdash; map") == "Atlas — map"
