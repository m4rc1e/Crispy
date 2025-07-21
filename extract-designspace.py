from fontTools.ttLib import TTFont
from fontTools.varLib import designspace_lib
import argparse
import os

def extract_designspace(ttf_path, output_path=None):
    # Load the variable font
    font = TTFont(ttf_path)

    # Extract designspace object
    designspace = designspace_lib.from_variable_font(font)

    # Determine output path if not provided
    if output_path is None:
        base_name = os.path.splitext(os.path.basename(ttf_path))[0]
        output_path = f"{base_name}.designspace"

    # Write to file
    designspace.write(output_path)
    print(f"Designspace saved to: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract .designspace file from a variable TTF font.")
    parser.add_argument("ttf_path", help="Path to the variable TTF font file")
    parser.add_argument("--output", "-o", help="Output .designspace file path (optional)")
    args = parser.parse_args()

    extract_designspace(args.ttf_path, args.output)
