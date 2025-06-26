import sys
import logging
import subprocess
import shutil
from pathlib import Path
import uharfbuzz as hb
from vanilla import Window, List, Button, TextBox, EditText
from AppKit import NSApplication
from fontTools.ttLib import TTFont

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

def measure_text_width(font, text):
    """Measure text advance width using HarfBuzz shaping engine."""
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    
    features = {"kern": True, "liga": True}
    hb.shape(font, buf, features)
    
    positions = buf.glyph_positions
    total_width = sum(pos.x_advance for pos in positions)
    return total_width

def extract_axes_from_otf(otf_path):
    """Extract available axes and values from an OTF font file."""
    axes = {}
    try:
        ttfont = TTFont(otf_path)
        if 'fvar' in ttfont:
            for axis in ttfont['fvar'].axes:
                axes[axis.axisTag] = None  # Initialize with None
            
            # Extract named instance coordinates
            for instance in ttfont['fvar'].instances:
                name_table = ttfont['name']
                instance_name = name_table.getDebugName(instance.subfamilyNameID)
                
                # Build dictionary with axis values for this instance
                instance_axes = {axis.axisTag: instance.coordinates[i] for i, axis in enumerate(ttfont['fvar'].axes)}
                
                # Store per-instance values
                axes[instance_name] = instance_axes
    except Exception as e:
        logging.warning(f"Could not extract axes from {otf_path}: {e}")
    return axes

def process_instances_with_harfbuzz(glyphs_file_path, text="H"):
    """Process a .glyphs file to generate instances and measure text width."""
    export_dir = Path("export")
    export_dir.mkdir(exist_ok=True)
    
    results = []
    all_axes = set()

    try:
        logging.info(f"Generating OTF instances from {glyphs_file_path}...")
        subprocess.run([
            "fontmake",
            "-g", str(glyphs_file_path),
            "-i",  
            "-o", "otf",  
            "--output-dir", str(export_dir)
        ], check=True)
        
        otf_files = list(export_dir.glob("*.otf"))
        
        if not otf_files:
            logging.error("No OTF files generated.")
            return results, []
        
        logging.info(f"Generated {len(otf_files)} instance files")
        
        for otf_path in otf_files:
            instance_name = otf_path.stem
            logging.info(f"Processing instance: {instance_name}")
            
            blob = hb.Blob.from_file_path(str(otf_path))
            face = hb.Face(blob)
            font = hb.Font(face)
            
            width = measure_text_width(font, text)
            logging.info(f"{text} width in '{instance_name}': {width}")
            
            # Extract axis values from the instance
            axes_data = extract_axes_from_otf(otf_path)
            
            # Get the axes values for this specific instance
            instance_axes = axes_data.get(instance_name, {})
            all_axes.update(instance_axes.keys())

            # Ensure all axes exist before adding row data
            result = {"Instance": instance_name}
            for axis in all_axes:
                result[axis] = instance_axes.get(axis, "-")  # Default to "-"
            result[f"{text} Width"] = width

            results.append(result)
            
    except subprocess.CalledProcessError as e:
        logging.error(f"fontmake failed: {e}")
    except Exception as e:
        logging.error(f"Error during processing: {e}")
    
    return results, sorted(all_axes)

class InspectorUI:
    """UI for font width inspection using HarfBuzz."""
    
    def __init__(self, glyphs_file_path):
        self.export_dir = Path("export")
        self.glyphs_file_path = glyphs_file_path

        self.w = Window((900, 500), "HarfBuzz Font Width Inspector")

        self.w.textLabel = TextBox((10, 10, 40, 20), "Text:")
        self.w.text = EditText((50, 10, 150, 20), "H", callback=None)

        self.w.button = Button((210, 10, 100, 20), "Run Check", callback=self.run_check)
        self.w.status = TextBox((320, 10, -10, 20), "Ready")

        self.w.list = List(
            (10, 40, -10, -40),
            [],
            columnDescriptions=[{"title": "Instance"}]  # Default column setup
        )

        self.w.info = TextBox((10, -30, -10, 20), "This tool measures text advance width using HarfBuzz shaping engine.")

        self.w.open()
    
    def run_check(self, sender):
        """Run width check when button is pressed."""
        text = str(self.w.text.get()).strip() or "H"
        
        self.w.status.set("Running...")
        
        try:
            results, axis_names = process_instances_with_harfbuzz(self.glyphs_file_path, text)
            
            if not results:
                self.w.status.set("No data found.")
                return
            
            # Define column descriptions dynamically
            columns = [{"title": "Instance"}] + [{"title": axis} for axis in axis_names] + [{"title": f"{text} Width"}]

            # Apply column descriptions **before** setting data
            self.w.list.columnDescriptions = columns  
            self.w.list.set([])  # Clear previous data
            self.w.list.set(results)  # Set new data

            count = len(results)
            self.w.status.set(f"Completed: {count} instances measured")
        except Exception as e:
            logging.error(f"Error during checking: {e}")
            self.w.status.set(f"Error: {str(e)[:50]}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python harfbuzz_inspector.py path/to/font.glyphs")
        sys.exit(1)

    glyphs_file_path = Path(sys.argv[1])
    if not glyphs_file_path.exists():
        print(f"Error: File not found: {glyphs_file_path}")
        sys.exit(1)
        
    logging.info(f"Starting HarfBuzz Font Width Inspector with {glyphs_file_path}")

    app = NSApplication.sharedApplication()
    inspector = InspectorUI(glyphs_file_path)

    try:
        app.run()
    finally:
        shutil.rmtree("export", ignore_errors=True)
        logging.info("Export folder cleaned up.")
