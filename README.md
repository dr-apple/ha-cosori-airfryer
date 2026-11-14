# Cosori Airfryer für Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

Integration für Cosori-Heißluftfritteusen aus der **VeSync-App** – gebaut und getestet für die **Cosori Dual Blaze TwinFry 10 L (CAF-TF101S)** mit zwei Körben. Andere Cosori-Fritteusen, die [pyvesync](https://github.com/webdjoe/pyvesync) kennt (CAF-TF102S, CAF-DC111S, CS137/CS158, TurboBlaze, Dual Blaze), funktionieren mit derselben Integration.

> Die Fritteuse hat keine lokale Schnittstelle; sie spricht nur mit der VeSync-Cloud. Die Integration nutzt deshalb dein VeSync-Konto (Cloud-Polling: 15 s während des Garens, sonst 60 s).

*English summary below.*

## Einrichtung

1. HACS → Benutzerdefinierte Repositories → `https://github.com/dr-apple/ha-cosori-airfryer` (Typ *Integration*) hinzufügen und installieren.
2. Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → *Integration hinzufügen* → **Cosori Airfryer**, mit E-Mail und Passwort aus der VeSync-App anmelden (Ländercode z. B. `DE`).

## Entitäten (TwinFry)

| Entität | Beschreibung |
|---|---|
| `sensor.…_korb_1_status` / `korb_2_status` | Bereit, Gart, Pausiert, Korb herausgezogen, Fertig, Wartet (Sync) … |
| `sensor.…_korb_N_restzeit` | Restzeit bis zum Ende (inkl. Sync-Wartezeit) |
| `sensor.…_korb_N_fertig_um` | Uhrzeit, zu der der Korb fertig ist |
| `sensor.…_korb_N_programm` | Heißluft, Braten, Backen, Grillen, Aufwärmen, Trocknen |
| `sensor.…_korb_N_solltemperatur` / `eingestellte_garzeit` | aktuelle Einstellung |
| `binary_sensor.…_korb_N_gart` | an, solange der Korb heizt/gart |
| `sensor.…_aktiver_korb` | Korb 1, Korb 2, Ganzer Korb, Beide (Sync) |
| `binary_sensor.…_cloud_verbindung` | Fritteuse in der VeSync-Cloud online |
| `select.…_start_korb` | Korb 1 (links), Korb 2 (rechts), Ganzer Korb (ohne Trenner), Beide Körbe (Sync) |
| `select.…_start_programm` | Programm für den Start; setzt Temperatur/Zeit auf die App-Standardwerte |
| `number.…_start_temperatur` / `start_garzeit` | Grenzen folgen dem Programm (z. B. Grillen 205–240 °C) |
| `button.…_garen_starten` | startet mit den obigen Einstellungen |
| `button.…_korb_1_beenden` / `korb_2_beenden` / `alles_beenden` | beendet den Garvorgang |

Programme und Grenzen beim CAF-TF101S:

| Programm | Temperatur | Zeit |
|---|---|---|
| Heißluft (`airfry`) | 120–205 °C | 1–60 min |
| Braten (`roast`) | 120–205 °C | 1–240 min |
| Backen (`bake`) | 80–205 °C | 1–240 min |
| Grillen (`grill`) | 205–240 °C | 1–30 min |
| Aufwärmen (`reheat`) | 40–205 °C | 1–60 min |
| Trocknen (`dry`) | 35–95 °C | 30 min–48 h (30-min-Schritte) |

Pausieren geht beim TwinFry nicht über die Cloud – Korb herausziehen pausiert, wieder einschieben setzt fort (Status „Korb herausgezogen“).
„Beide Körbe (Sync)“ startet beide Körbe mit denselben Einstellungen; unterschiedliche Programme pro Korb lässt die TwinFry-API nur über die App bzw. das Gerät zu.

## Dienste

```yaml
action: cosori_airfryer.start_cooking
data:
  device_id: <Gerät>
  chamber: chamber_2      # chamber_1 | chamber_2 | whole | both
  mode: airfry            # airfry | roast | bake | grill | reheat | dry
  temperature: 190        # °C, wird auf die Programmgrenzen begrenzt
  duration: 15            # Minuten
```

```yaml
action: cosori_airfryer.end_cooking
data:
  device_id: <Gerät>
  chamber: both           # beendet alles
```

Beispiel-Benachrichtigung, wenn Korb 1 fertig ist:

```yaml
triggers:
  - trigger: state
    entity_id: sensor.airfryer_korb_1_status
    to: cook_end
actions:
  - action: notify.notify
    data:
      message: Korb 1 ist fertig.
```

## English

Cloud integration (VeSync account, via pyvesync ≥ 3.5.1) for Cosori air fryers, with full support for the dual-basket **Dual Blaze TwinFry (CAF-TF101S)**: per-basket status, remaining time, finish time, program and settings; start (basket 1, basket 2, whole basket, both in sync) with program/temperature/time; end per basket or all. Services `cosori_airfryer.start_cooking` and `cosori_airfryer.end_cooking`. Install via HACS custom repository, then add *Cosori Airfryer* and log in with your VeSync account.
