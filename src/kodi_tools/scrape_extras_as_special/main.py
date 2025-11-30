#!/usr/bin/env python3
"""
Kodi Custom Special Episodes Generator
Erstellt NFO-Dateien und Thumbnails für manuell verwaltete Special-Folgen (E10000+)
"""

import os
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re

try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


class CustomSpecialGenerator:
    def __init__(self, base_path: str, force_nfo: bool = False, force_thumb: bool = False,
                 add_labels: bool = True, dry_run: bool = False):
        self.base_path = Path(base_path)
        self.force_nfo = force_nfo
        self.force_thumb = force_thumb
        self.add_labels = add_labels
        self.dry_run = dry_run
        self.processed_files = []
        self.video_extensions = ['.mkv', '.mp4', '.avi', '.m4v', '.ts', '.mov']

        # Label-Keywords für Thumbnails
        self.label_keywords = {
            'trailer': 'TRAILER',
            'teaser': 'TEASER',
            'making of': 'MAKING OF',
            'interview': 'INTERVIEW',
            'behind the scenes': 'BEHIND THE SCENES',
            'deleted scene': 'DELETED SCENE',
            'gag reel': 'GAG REEL',
            'blooper': 'BLOOPERS',
            'featurette': 'FEATURETTE',
            'preview': 'PREVIEW',
            'special': 'SPECIAL'
        }

    def find_video_files(self) -> List[Path]:
        """Findet rekursiv alle Video-Dateien für Special-Folgen >= E10000"""
        video_files = []
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in self.video_extensions:
                    ep_info = self.parse_episode_info(file_path.stem)
                    if ep_info and ep_info[0] == 0 and ep_info[1] >= 10000:
                        video_files.append(file_path)
        return video_files

    def parse_episode_info(self, filename: str) -> Optional[Tuple[int, int, str]]:
        """
        Extrahiert Season, Episode und Titel aus Dateinamen
        Unterstützte Formate:
        - "Serienname - S00E10000 - Episode Titel"
        - "S00E10000 - Episode Titel" (ohne Serienname)
        - "Serie-mit-Bindestrichen - S00E10000 - Episode Titel"
        Returns: (season, episode, title) oder None
        """
        # Pattern 1: Mit Episode-Titel nach S00E10000
        # Suche nach S00E10000, dann optional " - " und danach der Titel
        match = re.search(r'[Ss](\d+)[Ee](\d+)(?:\s*-\s*(.+))?')

    def get_json_path(self, video_path: Path) -> Path:
        """Gibt den Pfad zur JSON-Metadaten-Datei zurück"""
        return video_path.with_suffix('.json')

    def get_nfo_path(self, video_path: Path) -> Path:
        """Gibt den Pfad zur NFO-Datei zurück"""
        return video_path.with_suffix('.nfo')

    def get_thumb_path(self, video_path: Path) -> Path:
        """Gibt den Pfad zum Thumbnail zurück"""
        return video_path.with_suffix('') / Path(video_path.stem + '-thumb.jpg')

    def load_json_metadata(self, json_path: Path) -> Optional[Dict]:
        """Lädt gespeicherte Metadaten aus JSON"""
        if json_path.exists():
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️  Fehler beim Laden von {json_path}: {e}")
        return None

    def save_json_metadata(self, json_path: Path, data: Dict):
        """Speichert Metadaten in JSON"""
        if self.dry_run:
            print(f"   [DRY-RUN] Würde speichern: {json_path}")
            return

        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"⚠️  Fehler beim Speichern von {json_path}: {e}")

    def create_nfo(self, nfo_path: Path, season: int, episode: int, title: str, metadata: Dict | None = None):
        """Erstellt eine NFO-Datei für die Episode"""
        if self.dry_run:
            print(f"   [DRY-RUN] Würde NFO erstellen: {nfo_path}")
            return

        # Root Element
        root = ET.Element('episodedetails')

        # Pflichtfelder aus Dateiname
        ET.SubElement(root, 'title').text = title
        ET.SubElement(root, 'season').text = str(season)
        ET.SubElement(root, 'episode').text = str(episode)

        # Zusätzliche Felder aus Metadaten (falls vorhanden)
        if metadata:
            if metadata.get('plot'):
                ET.SubElement(root, 'plot').text = metadata['plot']
            if metadata.get('aired'):
                ET.SubElement(root, 'aired').text = metadata['aired']
            if metadata.get('rating'):
                ET.SubElement(root, 'rating').text = str(metadata['rating'])
            if metadata.get('director'):
                ET.SubElement(root, 'director').text = metadata['director']
            if metadata.get('credits'):
                for writer in metadata['credits']:
                    ET.SubElement(root, 'credits').text = writer
            if metadata.get('actors'):
                for actor in metadata['actors']:
                    actor_elem = ET.SubElement(root, 'actor')
                    ET.SubElement(actor_elem, 'name').text = actor.get('name', '')
                    if actor.get('role'):
                        ET.SubElement(actor_elem, 'role').text = actor['role']

        # Erstelle Tree und speichere
        tree = ET.ElementTree(root)
        ET.indent(tree, space='  ')

        try:
            tree.write(nfo_path, encoding='utf-8', xml_declaration=True)
            print(f"   ✓ NFO erstellt: {nfo_path.name}")
        except Exception as e:
            print(f"   ⚠️  Fehler beim Erstellen der NFO: {e}")

    def detect_label(self, title: str) -> Optional[str]:
        """Erkennt ob der Titel ein Label-Keyword enthält"""
        title_lower = title.lower()
        for keyword, label in self.label_keywords.items():
            if keyword in title_lower:
                return label
        return None

    def add_label_to_thumbnail(self, thumb_path: Path, label: str) -> bool:
        """Fügt ein Label mit abgerundeten Ecken zum Thumbnail hinzu"""
        if not PILLOW_AVAILABLE:
            print(f"   ⚠️  Pillow nicht installiert, Label wird übersprungen")
            print(f"      Installation: pip install Pillow")
            return False

        if self.dry_run:
            print(f"   [DRY-RUN] Würde Label '{label}' hinzufügen")
            return True

        try:
            # Lade Bild
            img = Image.open(thumb_path)
            draw = ImageDraw.Draw(img, 'RGBA')

            # Versuche verschiedene Schriftgrößen
            font = None
            font_size = 48
            try:
                # Versuche System-Schrift zu laden
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", font_size)
                except:
                    try:
                        font = ImageFont.truetype("Arial.ttf", font_size)
                    except:
                        # Fallback auf Default-Font
                        font = ImageFont.load_default()

            # Berechne Textgröße
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]

            # Position und Größe des Labels (unten links)
            padding = 20
            margin = 30
            border_radius = 15

            # Box-Koordinaten
            box_x = margin
            box_y = img.height - text_height - (2 * padding) - margin
            box_width = text_width + (2 * padding)
            box_height = text_height + (2 * padding)

            # Erstelle abgerundetes Rechteck mit transparentem schwarzen Hintergrund
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)

            # Zeichne abgerundetes Rechteck
            overlay_draw.rounded_rectangle(
                [box_x, box_y, box_x + box_width, box_y + box_height],
                radius=border_radius,
                fill=(0, 0, 0, 200)  # Schwarz mit 78% Deckkraft
            )

            # Kombiniere Overlay mit Original
            img = Image.alpha_composite(img.convert('RGBA'), overlay)
            draw = ImageDraw.Draw(img)

            # Zeichne Text
            text_x = box_x + padding
            text_y = box_y + padding
            draw.text((text_x, text_y), label, font=font, fill=(255, 255, 255, 255))

            # Speichere
            img = img.convert('RGB')  # Zurück zu RGB für JPEG
            img.save(thumb_path, 'JPEG', quality=95)

            print(f"   ✓ Label '{label}' hinzugefügt")
            return True

        except Exception as e:
            print(f"   ⚠️  Fehler beim Hinzufügen des Labels: {e}")
            return False

    def create_thumbnail(self, video_path: Path, thumb_path: Path, timestamp: Optional[str] = None):
        """Erstellt ein Thumbnail mit ffmpeg aus der Mitte des Videos"""
        if self.dry_run:
            print(f"   [DRY-RUN] Würde Thumbnail erstellen: {thumb_path}")
            return True

        # Wenn kein Timestamp angegeben, berechne Mitte des Videos
        if timestamp is None:
            duration = self.get_video_duration(video_path)
            if duration:
                middle_seconds = duration / 2
                hours = int(middle_seconds // 3600)
                minutes = int((middle_seconds % 3600) // 60)
                seconds = int(middle_seconds % 60)
                timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                print(f"   Video-Dauer: {duration:.1f}s, Thumbnail bei: {timestamp}")
            else:
                # Fallback wenn Dauer nicht ermittelt werden kann
                timestamp = "00:00:05"
                print(f"   ⚠️  Dauer nicht ermittelbar, verwende Fallback: {timestamp}")

        # ffmpeg Kommando
        cmd = [
            'ffmpeg',
            '-ss', timestamp,
            '-i', str(video_path),
            '-vframes', '1',
            '-q:v', '2',
            '-y',  # Überschreiben ohne Nachfrage
            str(thumb_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30
            )

            if result.returncode == 0 and thumb_path.exists():
                print(f"   ✓ Thumbnail erstellt: {thumb_path.name}")
                return True
            else:
                print(f"   ⚠️  ffmpeg Fehler beim Erstellen des Thumbnails")
                return False

        except subprocess.TimeoutExpired:
            print(f"   ⚠️  ffmpeg Timeout beim Erstellen des Thumbnails")
            return False
        except FileNotFoundError:
            print(f"   ⚠️  ffmpeg nicht gefunden. Bitte installieren!")
            return False
        except Exception as e:
            print(f"   ⚠️  Fehler beim Erstellen des Thumbnails: {e}")
            return False

    def check_ffmpeg(self) -> bool:
        """Prüft ob ffmpeg und ffprobe verfügbar sind"""
        try:
            ffmpeg_result = subprocess.run(
                ['ffmpeg', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            ffprobe_result = subprocess.run(
                ['ffprobe', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            return ffmpeg_result.returncode == 0 and ffprobe_result.returncode == 0
        except:
            return False

    def process_video_file(self, video_path: Path):
        """Verarbeitet eine einzelne Video-Datei"""
        print(f"\n📹 {video_path.name}")

        # Parse Episode Info
        ep_info = self.parse_episode_info(video_path.stem)
        if not ep_info:
            print(f"   ⚠️  Konnte Episode-Info nicht parsen")
            return

        season, episode, title = ep_info
        print(f"   Season: {season}, Episode: {episode}")
        print(f"   Titel: {title}")

        # Pfade
        json_path = self.get_json_path(video_path)
        nfo_path = self.get_nfo_path(video_path)
        thumb_path = self.get_thumb_path(video_path)

        # Lade vorhandene JSON-Daten
        json_data = self.load_json_metadata(json_path)

        # Entscheide ob neu generiert werden soll
        needs_nfo = self.force_nfo or not nfo_path.exists()
        needs_thumb = self.force_thumb or not thumb_path.exists()

        if json_data and not self.force_nfo and not self.force_thumb:
            print(f"   📄 JSON-Metadaten gefunden")
            # Verwende Daten aus JSON
            metadata = json_data.get('metadata', {})
        else:
            # Erstelle neue Metadaten
            metadata = {
                'plot': '',  # Kann später manuell ergänzt werden
                'aired': datetime.now().strftime('%Y-%m-%d'),
            }

        # Erstelle/Aktualisiere NFO
        if needs_nfo:
            self.create_nfo(nfo_path, season, episode, title, metadata)
        else:
            print(f"   ✓ NFO existiert bereits: {nfo_path.name}")

        # Erstelle Thumbnail
        if needs_thumb:
            # Verwende Timestamp aus JSON falls vorhanden, sonst automatisch Mitte
            if json_data and json_data.get('thumbnail_timestamp'):
                timestamp = json_data['thumbnail_timestamp']
                print(f"   Verwende Timestamp aus JSON: {timestamp}")
            else:
                timestamp = None  # Automatisch Mitte berechnen

            success = self.create_thumbnail(video_path, thumb_path, timestamp)

            # Füge Label hinzu falls gewünscht und erkannt
            if success and self.add_labels:
                label = self.detect_label(title)
                if label:
                    self.add_label_to_thumbnail(thumb_path, label)

            # Speichere verwendeten Timestamp für nächstes Mal
            if success and timestamp is None:
                # Berechne tatsächlich verwendeten Timestamp
                duration = self.get_video_duration(video_path)
                if duration:
                    middle_seconds = duration / 2
                    hours = int(middle_seconds // 3600)
                    minutes = int((middle_seconds % 3600) // 60)
                    seconds = int(middle_seconds % 60)
                    timestamp = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    timestamp = "00:00:05"
        else:
            print(f"   ✓ Thumbnail existiert bereits: {thumb_path.name}")
            timestamp = json_data.get('thumbnail_timestamp') if json_data else None

        # Speichere/Aktualisiere JSON
        updated_json = {
            'video_file': video_path.name,
            'season': season,
            'episode': episode,
            'title': title,
            'metadata': metadata,
            'thumbnail_timestamp': timestamp if timestamp else json_data.get('thumbnail_timestamp') if json_data else None,
            'nfo_created': nfo_path.exists(),
            'thumb_created': thumb_path.exists(),
            'last_processed': datetime.now().isoformat()
        }

        self.save_json_metadata(json_path, updated_json)
        self.processed_files.append(video_path.name)

    def process_all(self):
        """Hauptfunktion: Verarbeitet alle Video-Dateien"""
        print(f"🔍 Suche Custom Special Episodes (>= E10000) in: {self.base_path}\n")

        # Zeige Modus an
        if self.force_nfo and self.force_thumb:
            print("📝 Modus: Alle NFO und Thumbnails neu generieren")
        elif self.force_nfo:
            print("📝 Modus: Nur NFO-Dateien neu generieren")
        elif self.force_thumb:
            print("🖼️  Modus: Nur Thumbnails neu generieren")
        else:
            print("📝 Modus: Nur fehlende Dateien erstellen")

        if self.add_labels:
            print("🏷️  Labels: Aktiviert (Trailer, Interview, etc.)")
        else:
            print("🏷️  Labels: Deaktiviert")

        print()

        # Prüfe ffmpeg
        if not self.check_ffmpeg():
            print("⚠️  WARNUNG: ffmpeg/ffprobe nicht gefunden!")
            print("   Thumbnails können nicht erstellt werden.")
            print("   Installation: https://ffmpeg.org/download.html\n")

        # Prüfe Pillow für Labels
        if self.add_labels and not PILLOW_AVAILABLE:
            print("⚠️  WARNUNG: Pillow nicht installiert!")
            print("   Labels können nicht hinzugefügt werden.")
            print("   Installation: pip install Pillow\n")

        video_files = self.find_video_files()

        if not video_files:
            print("ℹ️  Keine Custom Special Episodes gefunden")
            return

        print(f"✓ {len(video_files)} Video-Datei(en) gefunden\n")

        for video_path in video_files:
            self.process_video_file(video_path)

        print(f"\n{'='*60}")
        print(f"✅ Fertig! {len(self.processed_files)} Datei(en) verarbeitet")


    def get_video_duration(self, video_path: Path) -> Optional[float]:
        """Ermittelt die Dauer des Videos in Sekunden"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(video_path)
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10
            )

            if result.returncode == 0:
                duration = float(result.stdout.decode().strip())
                return duration
        except:
            pass

        return None

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Kodi Custom Special Episodes Generator - Erstellt NFO und Thumbnails für E10000+ Episoden',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Beispiele:
  # Nur fehlende Dateien erstellen
  python %(prog)s /pfad/zu/serien

  # Alle NFO-Dateien neu generieren
  python %(prog)s /pfad/zu/serien --force-nfo

  # Alle Thumbnails neu generieren
  python %(prog)s /pfad/zu/serien --force-thumb

  # Alles neu generieren (NFO + Thumbnails)
  python %(prog)s /pfad/zu/serien --force-all

  # Testlauf
  python %(prog)s /pfad/zu/serien --dry-run

Dateiformat:
  Video: "Serienname - S00E10001 - Episode Titel.mkv"
  NFO:   "Serienname - S00E10001 - Episode Titel.nfo"
  Thumb: "Serienname - S00E10001 - Episode Titel-thumb.jpg"
  JSON:  "Serienname - S00E10001 - Episode Titel.json"
        """
    )

    parser.add_argument('path', help='Basis-Pfad zum rekursiven Durchsuchen')

    force_group = parser.add_mutually_exclusive_group()
    force_group.add_argument('--force-nfo', action='store_true',
                            help='Alle NFO-Dateien neu generieren')
    force_group.add_argument('--force-thumb', action='store_true',
                            help='Alle Thumbnails neu generieren')
    force_group.add_argument('--force-all', action='store_true',
                            help='Alles neu generieren (NFO + Thumbnails)')

    parser.add_argument('--dry-run', action='store_true',
                       help='Testlauf ohne Änderungen')

    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"❌ Pfad existiert nicht: {args.path}")
        return

    # Bestimme welche Flags gesetzt werden
    force_nfo = args.force_nfo or args.force_all
    force_thumb = args.force_thumb or args.force_all

    generator = CustomSpecialGenerator(
        args.path,
        force_nfo=force_nfo,
        force_thumb=force_thumb,
        dry_run=args.dry_run
    )

    if args.dry_run:
        print("🧪 DRY-RUN Modus - Es werden keine Änderungen vorgenommen\n")

    generator.process_all()


if __name__ == '__main__':
    main()
