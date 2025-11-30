#!/usr/bin/env python3
"""
Kodi Special Episodes NFO Manager
Sortiert Special-Folgen chronologisch zwischen normale Folgen basierend auf Ausstrahlungsdatum
"""

import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Tuple, Optional
import re


class SpecialEpisodeManager:
    def __init__(self, base_path: str, dry_run: bool = False):
        self.base_path = Path(base_path)
        self.dry_run = dry_run
        self.processed_episodes = []

    def find_nfo_files(self) -> List[Path]:
        """Findet rekursiv alle NFO-Dateien"""
        nfo_files = []
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                if file.endswith('.nfo'):
                    nfo_files.append(Path(root) / file)
        return nfo_files

    def parse_episode_info(self, filename: str) -> Optional[Tuple[int, int]]:
        """Extrahiert Season und Episode aus Dateinamen (z.B. S00E05 -> (0, 5))"""
        match = re.search(r'[Ss](\d+)[Ee](\d+)', filename)
        if match:
            season = int(match.group(1))
            episode = int(match.group(2))
            return (season, episode)
        return None

    def get_json_path(self, nfo_path: Path) -> Path:
        """Gibt den Pfad zur JSON-Backup-Datei zurück"""
        return nfo_path.with_suffix('.nfo.json')

    def load_json_backup(self, json_path: Path) -> Optional[Dict]:
        """Lädt gespeicherte Einstellungen aus JSON"""
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Fehler beim Laden von {json_path}: {e}")
        return None

    def save_json_backup(self, json_path: Path, data: Dict):
        """Speichert Einstellungen in JSON"""
        if self.dry_run:
            print(f"   [DRY-RUN] Würde speichern: {json_path}")
            return

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Fehler beim Speichern von {json_path}: {e}")

    def parse_nfo(self, nfo_path: Path) -> Optional[ET.ElementTree]:
        """Lädt und parsed eine NFO-Datei"""
        try:
            tree: Any = ET.parse(nfo_path)
            return tree
        except Exception as e:
            print(f"⚠️  Fehler beim Parsen von {nfo_path}: {e}")
            return None

    def get_aired_date(self, tree: ET.ElementTree) -> Optional[datetime]:
        """Extrahiert das Ausstrahlungsdatum aus der NFO"""
        root: ET.Element[str] | None = tree.getroot()
        if root is None:
            return None
        aired = root.find('aired')
        if aired is not None and aired.text:
            try:
                return datetime.strptime(aired.text, '%Y-%m-%d')
            except ValueError:
                pass
        return None

    def get_season_episode(self, tree: ET.ElementTree) -> Optional[Tuple[int, int]]:
        """Extrahiert Season und Episode aus NFO"""
        root: ET.Element[str] | None = tree.getroot()
        if root is None:
            return None
        season_elem: ET.Element[str] | None = root.find('season')
        episode_elem: ET.Element[str] | None = root.find('episode')

        if season_elem is not None and episode_elem is not None and season_elem.text and episode_elem.text:
            try:
                return (int(season_elem.text), int(episode_elem.text))
            except (ValueError, TypeError):
                pass
        return None

    def set_display_tags(self, tree: ET.ElementTree, display_season: int, display_episode: int):
        """Setzt oder aktualisiert displayseason und displayepisode Tags"""
        root: ET.Element[str] | None = tree.getroot()
        if root is None:
            return

        # displayseason
        ds_elem = root.find('displayseason')
        if ds_elem is None:
            ds_elem = ET.SubElement(root, 'displayseason')
        ds_elem.text = str(display_season)

        # displayepisode
        de_elem = root.find('displayepisode')
        if de_elem is None:
            de_elem = ET.SubElement(root, 'displayepisode')
        de_elem.text = str(display_episode)

    def save_nfo(self, tree: ET.ElementTree, nfo_path: Path):
        """Speichert die geänderte NFO-Datei"""
        if self.dry_run:
            print(f"   [DRY-RUN] Würde speichern: {nfo_path}")
            return

        try:
            tree.write(nfo_path, encoding='utf-8', xml_declaration=True)
        except Exception as e:
            print(f"⚠️  Fehler beim Speichern von {nfo_path}: {e}")

    def process_special_episodes(self):
        """Hauptfunktion: Verarbeitet alle Special-Folgen"""
        print(f"🔍 Suche NFO-Dateien in: {self.base_path}")
        nfo_files = self.find_nfo_files()
        print(f"✓ {len(nfo_files)} NFO-Dateien gefunden\n")

        # Sammle alle Folgen (normale + specials)
        all_episodes = []
        specials_to_process = []

        for nfo_path in nfo_files:
            # Prüfe ob es eine Episode ist
            ep_info = self.parse_episode_info(nfo_path.name)
            if not ep_info:
                continue

            season, episode = ep_info

            # Parse NFO
            tree: ET.ElementTree[ET.Element[str] | None] | None = self.parse_nfo(nfo_path)
            if not tree:
                continue

            aired = self.get_aired_date(tree)

            # Prüfe JSON-Backup für Specials
            json_path = self.get_json_path(nfo_path)
            json_data = self.load_json_backup(json_path)

            if season == 0:
                # Ignoriere Folgen >= E10000
                if episode >= 10000:
                    print(f"⏭️  Überspringe {nfo_path.name} (Episode >= 10000)")
                    continue

                if not aired:
                    print(f"⚠️  Kein Ausstrahlungsdatum für Special: {nfo_path.name}")
                    continue

                # Special-Folge
                if json_data:
                    print(f"📄 Lade Special aus JSON: {nfo_path.name}")
                    specials_to_process.append({
                        'path': nfo_path,
                        'season': season,
                        'episode': episode,
                        'aired': datetime.strptime(json_data['aired'], '%Y-%m-%d'),
                        'tree': tree,
                        'is_special': True,
                        'from_json': True,
                        'json_data': json_data
                    })
                else:
                    specials_to_process.append({
                        'path': nfo_path,
                        'season': season,
                        'episode': episode,
                        'aired': aired,
                        'tree': tree,
                        'is_special': True,
                        'from_json': False
                    })
            else:
                # Normale Folge
                if not aired:
                    print(f"⚠️  Kein Ausstrahlungsdatum für normale Episode: {nfo_path.name}")
                    continue

                all_episodes.append({
                    'path': nfo_path,
                    'season': season,
                    'episode': episode,
                    'aired': aired,
                    'tree': tree,
                    'is_special': False
                })

        if not specials_to_process:
            print("ℹ️  Keine Special-Folgen zum Verarbeiten gefunden")
            return

        # Füge Specials zu allen Episoden hinzu
        all_episodes.extend(specials_to_process)

        # Sortiere alle Folgen nach Ausstrahlungsdatum
        all_episodes.sort(key=lambda x: (x['aired'] if x['aired'] else datetime.max, x['season'], x['episode']))

        print(f"\n📺 Verarbeite {len(specials_to_process)} Special-Folgen zwischen {len(all_episodes) - len(specials_to_process)} normalen Folgen\n")

        # Gruppiere nach Staffeln und weise Display-Nummern zu
        current_season = None
        episode_counter = 0

        for ep in all_episodes:
            # Wenn wir zu einer neuen Staffel wechseln (nur bei normalen Folgen)
            if not ep['is_special'] and ep['season'] != current_season:
                current_season = ep['season']
                episode_counter = 0

            if not current_season:
                continue

            episode_counter += 1

            # Nur Specials bearbeiten
            if ep['is_special']:
                nfo_path = ep['path']
                tree = ep['tree']
                if not tree:
                    continue

                # Wenn aus JSON geladen und sich nichts geändert hat, überspringe
                if ep['from_json']:
                    old_display_season = ep['json_data'].get('display_season')
                    old_display_episode = ep['json_data'].get('display_episode')

                    if old_display_season == current_season and old_display_episode == episode_counter:
                        print(f"✓ {nfo_path.name} (bereits korrekt: S{current_season:02d}E{episode_counter:02d})")
                        continue

                print(f"✏️  {nfo_path.name}")
                print(f"   Original: S{ep['season']:02d}E{ep['episode']:02d}")
                print(f"   Ausgestrahlt: {ep['aired'].strftime('%Y-%m-%d')}")
                print(f"   → Display: S{current_season:02d}E{episode_counter:02d}")

                # Setze Tags
                self.set_display_tags(tree, current_season, episode_counter)
                self.save_nfo(tree, nfo_path)

                # Speichere JSON-Backup
                json_data = {
                    'original_season': ep['season'],
                    'original_episode': ep['episode'],
                    'aired': ep['aired'].strftime('%Y-%m-%d'),
                    'display_season': current_season,
                    'display_episode': episode_counter,
                    'last_modified': datetime.now().isoformat()
                }
                self.save_json_backup(self.get_json_path(nfo_path), json_data)

                self.processed_episodes.append(nfo_path.name)
                print()
            else:
                # Normale Folge - nur zur Info
                print(f"   S{ep['season']:02d}E{ep['episode']:02d} → Display: S{current_season:02d}E{episode_counter:02d} ({ep['aired'].strftime('%Y-%m-%d')})")

        print(f"\n✅ Fertig! {len(self.processed_episodes)} Special-Folgen verarbeitet")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Kodi Special Episodes NFO Manager - Sortiert Specials chronologisch zwischen normale Folgen'
    )
    parser.add_argument('path', help='Basis-Pfad zum rekursiven Durchsuchen')
    parser.add_argument('--dry-run', action='store_true', help='Testlauf ohne Änderungen')

    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"❌ Pfad existiert nicht: {args.path}")
        return

    manager = SpecialEpisodeManager(args.path, dry_run=args.dry_run)

    if args.dry_run:
        print("🧪 DRY-RUN Modus - Es werden keine Änderungen vorgenommen\n")

    manager.process_special_episodes()


if __name__ == '__main__':
    main()
