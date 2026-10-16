# Modelversies (bevroren)

Elke map is een bevroren modelversie. De code is een kopie van de nodes in de n8n-workflow
"Stock Scanner - Live scan" op het moment van bevriezen. Een wijziging in de regels betekent
een NIEUWE versie (nieuwe map, nieuwe `model_version` in scanner_alerts), zodat de resultaten
van elke versie apart en zuiver gemeten blijven.

## 6.0-dip (bevroren op 14-10-2026)
Eerste live alerts: 14-10-2026 15:46 (STX, VRT, HWM, WDC, CAT).

- `score-alle-aandelen.js`: berekent de dip-positie per aandeel (gemiddelde percentielrang van z20, RSI14, afstand tot SMA50 en dd30 over de laatste 250 koersdagen).
- `dip-regels.js`: kwalificatie (dip <= 0,30, dd30 <= -8%, d52 <= -15%), kwaliteitsfilters (omzetgroei >= 10%, positieve kasstroom of strikt speculatief pad, geen Real Estate), selectie van maximaal 5 signalen en WATCH.
- `alert-beslissing.js`: bepaalt wanneer een signaal wordt opgeslagen.

Positiebeheer van het model (20% verkopen bij +10/25/50/100%, bijkopen bij -12%, terugkopen, altijd een restpositie) staat in `app/portfolio/positionEngine.js`.

Wijzigingen na bevriezing (bewust gedocumenteerd):
- Universum-opschoning (aandelen verwijderd uit de lijst) verandert de regels niet.

## 6.1-dip (15-10-2026)
Enige wijziging ten opzichte van 6.0: de voorwaarde over vrije kasstroom is verwijderd (ook het strenge "speculatieve" pad). Aandelen met negatieve vrije kasstroom kunnen nu gewoon een signaal worden. Overgebleven filters: omzetgroei >= 10% en geen Real Estate.
Reden: voor swingtrading is negatieve vrije kasstroom geen uitsluitingsgrond (beslissing Hugo). Alerts van 6.0 blijven onder 6.0 gemeten, nieuwe signalen krijgen model_version 6.1-dip.
Bekende kanttekening: negatieve kasstroom was in de historische test de riskantste groep (75% in winst, gem. +25%, gem. diepste daling -17%).


## 6.2-dip (16-10-2026)
Selectie en dip-regels zijn gelijk aan 6.1 (top 5 op diepte van de dip, omzetgroei minimaal 10%, geen vastgoed). Wat is nieuw:
- **Positiebeheer:** per trap 10% verkopen op +15/30/60/120% (was 20% op +10/25/50/100%). Bijkopen (-12%, max 3 eenheden), terugkopen (-12% onder laatste verkoop), altijd een restpositie en geen stops blijven gelijk. Posities die vóór 6.2 zijn geopend houden hun oude plan (`plan` ontbreekt = 6.1).
- **Waarschuwingen (geen filter):** aandeel-specifieke dip (markt zelf niet in een dip, aandeel 10 procentpunt zwakker dan de S&P 500 over 30 dagen) en dip binnen 10 dagen na kwartaalcijfers. Zichtbaar op de signaalkaart en opgeslagen in `scanner_alerts.context_facts`.
- `target_level` is nu +15% (eerste winstniveau).
- Reden en testen: zie project-docs (positiebeheer-varianten, verbeterpunten-test). Positiebeheer was het enige onderdeel met bewezen meerwaarde (ongeveer +4 procentpunt tegenover vasthouden); de waarschuwingen zijn suggestief maar niet significant.
- 6.0 en 6.1 blijven bevroren; 6.2 wordt apart gemeten (model_version `6.2-dip`).
