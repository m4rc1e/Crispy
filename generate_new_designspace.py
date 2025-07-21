import csv
import os
import shutil
from fontTools.designspaceLib import DesignSpaceDocument, AxisDescriptor, SourceDescriptor
from lxml import etree

# Print current working directory for debugging
print(f"Current working directory: {os.getcwd()}")

# CONFIGURABLE PATHS (relative to /sources)
CSV_PATH = 'sources/mapping.csv'  # Only used for new axis min/max
DESIGNSPACE_PATH = 'master_ufo/Crispy.designspace'
UFO_SOURCE_DIR = 'master_ufo'
UFO_OUTPUT_DIR = 'master_ufo'
INSTANCE_UFO_DIR = 'instance_ufo'
OUTPUT_DESIGNSPACE = os.path.join(UFO_OUTPUT_DIR, 'Crispy-updated.designspace')

# 1. Parse CSV for -e axes and build StyleName lookup
def get_e_axes_and_lookup(csv_path):
    print(f"Parsing CSV for -e axes and StyleName lookup: {csv_path}")
    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        if reader.fieldnames is None:
            print("Error: CSV file is empty or malformed. No headers found.")
            exit(1)
        e_axes = [h for h in reader.fieldnames if '-e' in h]
        rows = list(reader)
        # Build StyleName lookup for all axes
        style_lookup = {}
        for row in rows:
            style = row['Instance'].strip()
            style_lookup[style] = {k: float(v) for k, v in row.items() if k != 'Instance' and v}
        # Get min/max for each -e axis
        axis_minmax = {}
        for axis in e_axes:
            values = [float(row[axis]) for row in rows if axis in row and row[axis]]
            axis_minmax[axis] = {'min': min(values), 'max': max(values)}
        print(f"-e axes: {e_axes}")
        print(f"Axis min/max: {axis_minmax}")
        print(f"StyleName lookup: {style_lookup}")
        return e_axes, axis_minmax, style_lookup, rows

# 2. Update designspace axes
def ensure_e_axes(doc, e_axes, axis_minmax):
    print(f"Ensuring all -e axes are present in designspace...")
    existing_axis_names = [a.name for a in doc.axes]
    for axis in e_axes:
        if axis not in existing_axis_names:
            ad = AxisDescriptor()
            ad.name = axis
            ad.tag = axis[:4]
            ad.minimum = axis_minmax[axis]['min']
            ad.maximum = axis_minmax[axis]['max']
            ad.default = axis_minmax[axis]['min']
            doc.axes.append(ad)
            print(f"Added new axis: {axis}")
        else:
            print(f"Axis '{axis}' already exists in designspace.")

# 3. Duplicate UFOs and add new sources
def duplicate_sources_and_update_designspace(doc, e_axes, axis_minmax):
    print("Duplicating master UFOs and updating designspace sources...")
    new_sources = []
    for source in doc.sources:
        # Set all -e axes to min for original
        for axis in e_axes:
            source.location[axis] = axis_minmax[axis]['min']
        # Duplicate UFO for max value
        orig_ufo_path = os.path.join(UFO_SOURCE_DIR, os.path.basename(source.filename))
        ufo_base, ufo_ext = os.path.splitext(os.path.basename(source.filename))
        new_ufo_name = f"{ufo_base}-{'-'.join([a+'Max' for a in e_axes])}{ufo_ext}"
        new_ufo_path = os.path.join(UFO_OUTPUT_DIR, new_ufo_name)
        print(f"Duplicating {orig_ufo_path} -> {new_ufo_path} (overwrite if exists)")
        if os.path.exists(new_ufo_path):
            shutil.rmtree(new_ufo_path)
        if not os.path.exists(orig_ufo_path):
            print(f"WARNING: Source UFO not found: {orig_ufo_path}. Skipping.")
            continue
        shutil.copytree(orig_ufo_path, new_ufo_path)
        # Add new source for duplicate
        new_source = SourceDescriptor()
        new_source.filename = os.path.relpath(new_ufo_path, os.path.dirname(OUTPUT_DESIGNSPACE))
        new_source.name = f"{ufo_base}-{'-'.join([a+'Max' for a in e_axes])}"
        new_source.familyName = getattr(source, 'familyName', 'Crispy')
        new_source.styleName = f"{getattr(source, 'styleName', ufo_base)}-{'-'.join([a+'Max' for a in e_axes])}"
        new_source.location = dict(source.location)
        for axis in e_axes:
            new_source.location[axis] = axis_minmax[axis]['max']
        new_sources.append(new_source)
        print(f"Added new source: {new_source.filename} with location {new_source.location}")
    doc.sources.extend(new_sources)

# 4. Update all instances to have the -e axis value from CSV or default
def update_instances_with_e_axes(doc, e_axes, axis_minmax, style_lookup):
    print("Updating instances with new -e axis values...")
    for instance in doc.instances:
        style_name = getattr(instance, 'styleName', None)
        for axis in e_axes:
            default_value = (axis_minmax[axis]['min'] + axis_minmax[axis]['max']) / 2
            if style_name and style_name in style_lookup:
                axis_value = style_lookup[style_name].get(axis, default_value)
                print(f"Instance '{style_name}': matched CSV, setting {axis}={axis_value}")
            else:
                axis_value = default_value
                print(f"Instance '{style_name}': not found in CSV, setting {axis} to default {axis_value}")
            if not hasattr(instance, 'location') or instance.location is None:
                instance.location = {}
            instance.location[axis] = axis_value

# 5. Set axis defaults to the minimum value among all sources
def set_axis_defaults_to_minimums(output_path, doc):
    print("Setting axis defaults to the minimum value among all sources...")
    # Gather all axis names
    axis_names = [a.name for a in doc.axes]
    # Build a dict of min values for each axis
    min_values = {axis: float('inf') for axis in axis_names}
    for source in doc.sources:
        for axis in axis_names:
            if axis in source.location:
                min_values[axis] = min(min_values[axis], source.location[axis])
    print(f"Axis minimums: {min_values}")
    # Update axis defaults in XML
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(output_path, parser)
    root = tree.getroot()
    axis_elems = root.findall('axes/axis')
    for axis_elem in axis_elems:
        axis_name = axis_elem.get('name')
        if axis_name in min_values:
            axis_elem.set('default', str(min_values[axis_name]))
    tree.write(output_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')
    print(f"Axis defaults set to minimums: {min_values}")

# 6. Save updated designspace
def save_designspace(doc, output_path):
    print(f"Saving updated designspace to {output_path}")
    doc.write(output_path)
    print("Done.")

def main():
    e_axes, axis_minmax, style_lookup, rows = get_e_axes_and_lookup(CSV_PATH)
    doc = DesignSpaceDocument.fromfile(DESIGNSPACE_PATH)
    ensure_e_axes(doc, e_axes, axis_minmax)
    duplicate_sources_and_update_designspace(doc, e_axes, axis_minmax)
    update_instances_with_e_axes(doc, e_axes, axis_minmax, style_lookup)
    save_designspace(doc, OUTPUT_DESIGNSPACE)
    set_axis_defaults_to_minimums(OUTPUT_DESIGNSPACE, doc)

if __name__ == "__main__":
    main() 