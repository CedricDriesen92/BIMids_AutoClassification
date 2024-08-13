import os
import xml.etree.ElementTree as ET
import json
from collections import defaultdict
import lxml.etree as lxml_ET

def detect_language(root):
    # Check for a French property
    french_properties = get_properties_to_delete("French")
    for prop in [french_properties[1], french_properties[2]]:
        if root.find(f".//PropertyDefinition/Name[.='{prop}']") is not None:
            print("French")
            return "French"
    print("English")
    return "English"

def get_properties_to_delete(language):
    if language == "English":
        return ["Position", "IsLoadBearing", "Renovation Status"]
    else:  # French
        return ["Position", "Fonction structurelle", "État de rénovation"]

def remove_properties_from_tree(root, properties_to_delete):
    for prop in properties_to_delete:
        for elem in root.findall(f".//PropertyDefinition[Name='{prop}']"):
            elem.getparent().remove(elem)

def build_element_tree(root):
    def recursive_build(element):
        if element.tag != 'Item':
            return None
        
        item_id = element.find('ID').text
        name = element.find('Name').text
        
        children = []
        for child in element.find('Children') or []:
            child_tree = recursive_build(child)
            if child_tree:
                children.append(child_tree)
        
        return {
            'id': item_id,
            'children': children,
            'properties': set()
        }

    tree = []
    for item in root.find('.//Items'):
        item_tree = recursive_build(item)
        if item_tree:
            tree.append(item_tree)
    
    return tree

def get_properties(root, element_tree):
    def find_node(tree, item_id):
        for node in tree:
            if node['id'] == item_id:
                return node
            result = find_node(node['children'], item_id)
            if result:
                return result
        return None

    for prop_def in root.findall('.//PropertyDefinition'):
        name_elem = prop_def.find('Name')
        if name_elem is not None:
            prop_name = name_elem.text
            for class_id in prop_def.findall('.//ClassificationID/ItemID'):
                if class_id is not None:
                    item_id = class_id.text
                    node = find_node(element_tree, item_id)
                    if node:
                        node['properties'].add(prop_name)
                        #print(f"Added property '{prop_name}' to node '{item_id}'")
    
    return element_tree

def assign_properties(tree):
    def recursive_assign(node, parent_properties=None):
        if parent_properties is None:
            parent_properties = set()

        children_with_properties = [child for child in node['children'] if child['properties']]
        children_with_children = [child for child in node['children'] if child['children']]
        overlap = [child for child in children_with_properties if child in children_with_children]
        
        # Handle child-to-parent propagation, only if parent has no properties
        if not node['properties'] and children_with_properties:
            child_property_sets = [set(child['properties']) for child in children_with_properties]
            if all(prop_set == child_property_sets[0] for prop_set in child_property_sets) and (not overlap or len(overlap) == 0):
                node['properties'] = child_property_sets[0]
                for child in node['children']:
                    if not child['properties']:
                        #print(f"Node {child['id']} got properties from siblings")
                        child['properties'] = set(node['properties'])
            elif node['id'] in ['Covering', 'Revêtement']:
                handle_covering_case(node)
            elif node['id'] not in ['Chimney', 'Cheminée']:
                print(f"Warning: Children of {node['id']} have different properties")

        # Handle parent-to-child propagation
        elif node['properties']:
            for child in node['children']:
                if not child['properties']:
                    #print(f"Node {child['id']} got properties from parent {node['id']}")
                    child['properties'] = set(node['properties'])

        #print(f"Final properties for {node['id']}: {node['properties']}")

        # Recursively process children
        for child in node['children']:
            recursive_assign(child, node['properties'])

    for node in tree:
        recursive_assign(node)
    
    return tree

def handle_covering_case(node):
    covering_children = ['Ceiling', 'Revêtement de plafond', 'Cladding', 'Revêtement de paroi', 
                         'Flooring', 'Revêtement de sol', 'Roofing', 'Couverture de toiture']
    common_properties = set()
    for child in node['children']:
        if child['id'] in covering_children and child['properties']:
            if not common_properties:
                common_properties = child['properties']
            else:
                common_properties.intersection_update(child['properties'])
    
    if common_properties:
        node['properties'] = common_properties
        for child in node['children']:
            if not child['properties']:
                child['properties'] = common_properties


def sets_to_lists(obj):
    if isinstance(obj, dict):
        return {k: sets_to_lists(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sets_to_lists(v) for v in obj]
    elif isinstance(obj, set):
        return list(obj)
    else:
        return obj
    
    
def export_config_prev(element_tree):
    def recursive_export(node, parent_properties=None):
        if parent_properties is None:
            parent_properties = set()

        config_node = {
            'id': node['id']
        }

        not_inherited = parent_properties - node['properties']
        if not_inherited and len(node['properties']) > 0:
            config_node['not_inherited_from'] = not_inherited

        new_props = node['properties'] - parent_properties
        if new_props and node['properties'] != parent_properties:
            config_node['new_properties'] = new_props

        children = []
        for child in node['children']:
            child_config = recursive_export(child, node['properties'])
            if child_config:
                children.append(child_config)

        if children:
            config_node['children'] = children

        if node['children']:
            never_inherit = node['properties'] - set().union(*(child['properties'] for child in node['children']))
            if never_inherit:
                config_node['never_inherit_to'] = never_inherit

        return config_node if len(config_node) > 1 else None

    config_prev = []
    for root_node in element_tree:
        root_config = recursive_export(root_node)
        if root_config:
            config_prev.append(root_config)

    return config_prev

def clean_and_convert(obj):
    if isinstance(obj, dict):
        return {k: clean_and_convert(v) for k, v in obj.items() if v}
    elif isinstance(obj, list):
        return [clean_and_convert(v) for v in obj if v]
    elif isinstance(obj, set):
        return list(obj) if obj else None
    else:
        return obj
    
# Function to convert sets to lists for JSON serialization
def sets_to_lists(obj):
    if isinstance(obj, dict):
        return {k: sets_to_lists(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sets_to_lists(v) for v in obj]
    elif isinstance(obj, set):
        return list(obj)
    else:
        return obj
    

def apply_new_config(element_tree, new_config):
    def find_config_node(config, node_id):
        for item in config:
            if item['id'] == node_id:
                return item
            if 'children' in item:
                result = find_config_node(item['children'], node_id)
                if result:
                    return result
        return None

    def process_node(node, parent_properties=None):
        if parent_properties is None:
            parent_properties = set()

        config_node = find_config_node(new_config, node['id'])

        node['properties'] = set(parent_properties)

        if config_node:
            if 'not_inherited_from' in config_node:
                node['properties'] -= set(config_node['not_inherited_from'])
            if 'new_properties' in config_node:
                node['properties'] |= set(config_node['new_properties'])

        for child in node['children']:
            process_node(child, node['properties'])

        if config_node and 'never_inherit_to' in config_node:
            for child in node['children']:
                child['properties'] -= set(config_node['never_inherit_to'])

    for root_node in element_tree:
        process_node(root_node)


def process_xml_file(input_path, output_path):
    parser = lxml_ET.XMLParser(remove_blank_text=True)
    tree = lxml_ET.parse(input_path, parser)
    root = tree.getroot()

    language = detect_language(root)
    properties_to_delete = get_properties_to_delete(language)
    remove_properties_from_tree(root, properties_to_delete)

    element_tree = build_element_tree(root)
    element_tree = get_properties(root, element_tree)
    element_tree = assign_properties(element_tree)

    # Update XML with new properties
    updated_element_tree = update_xml_properties(root, element_tree, language)
    tree.write(output_path, encoding='UTF-8', xml_declaration=True, pretty_print=True)
    print(f"Updated XML saved to {output_path}")

    return updated_element_tree

def update_xml_properties(root, element_tree, language):
    syst = root.find('.//System')
    print(syst)
    systemname = syst.find('Name').text
    systemversion = syst.find('EditionVersion').text
    print(systemname)
    print(systemversion)
    prop_def_groups = root.find('.//PropertyDefinitionGroups')
    if prop_def_groups is None:
        print("Error: No PropertyDefinitionGroups found in the XML.")
        return element_tree

    # Create a mapping of element IDs to their nodes in the element_tree
    element_map = {}
    def build_element_map(node):
        element_map[node['id']] = node
        for child in node['children']:
            build_element_map(child)

    for root_node in element_tree:
        build_element_map(root_node)

    #print("Element map after building:")
    #for element_id, node in element_map.items():
    #    print(f"{element_id}: {node['properties']}")

    # Update ClassificationIDs for all property definitions and update element_tree
    for prop_def_group in prop_def_groups.findall('PropertyDefinitionGroup'):
        for prop_def in prop_def_group.findall('.//PropertyDefinition'):
            prop_name = prop_def.find('Name').text
            class_ids_elem = prop_def.find('ClassificationIDs')
            if class_ids_elem is not None:
                class_ids_elem.clear()
            else:
                class_ids_elem = lxml_ET.SubElement(prop_def, 'ClassificationIDs')

            for element_id, node in element_map.items():
                if prop_name in node['properties']:
                    class_id_elem = lxml_ET.SubElement(class_ids_elem, 'ClassificationID')
                    lxml_ET.SubElement(class_id_elem, 'ItemID').text = element_id
                    lxml_ET.SubElement(class_id_elem, 'SystemIDName').text = systemname
                    lxml_ET.SubElement(class_id_elem, 'SystemIDVersion').text = systemversion

    # Add any new properties to the XML
    for element_id, node in element_map.items():
        for prop_name in node['properties']:
            prop_def = None
            for pd in prop_def_groups.findall('.//PropertyDefinition'):
                if pd.find('Name').text == prop_name:
                    prop_def = pd
                    break

            if prop_def is None:
                # Create a new PropertyDefinition
                new_prop_def = lxml_ET.SubElement(prop_def_groups[0], 'PropertyDefinition')
                lxml_ET.SubElement(new_prop_def, 'Name').text = prop_name
                lxml_ET.SubElement(new_prop_def, 'Description')
                value_desc = lxml_ET.SubElement(new_prop_def, 'ValueDescriptor', Type="SingleValueDescriptor")
                lxml_ET.SubElement(value_desc, 'ValueType').text = 'String'
                lxml_ET.SubElement(new_prop_def, 'MeasureType').text = 'Default'
                default_value = lxml_ET.SubElement(new_prop_def, 'DefaultValue')
                lxml_ET.SubElement(default_value, 'DefaultValueType').text = 'Basic'
                variant = lxml_ET.SubElement(default_value, 'Variant', Type="StringVariant")
                lxml_ET.SubElement(variant, 'Status').text = 'UserUndefined'
                class_ids_elem = lxml_ET.SubElement(new_prop_def, 'ClassificationIDs')
                class_id_elem = lxml_ET.SubElement(class_ids_elem, 'ClassificationID')
                lxml_ET.SubElement(class_id_elem, 'ItemID').text = element_id
                lxml_ET.SubElement(class_id_elem, 'SystemIDName').text = systemname
                lxml_ET.SubElement(class_id_elem, 'SystemIDVersion').text = systemversion
            else:
                # Add the element ID to the existing PropertyDefinition
                class_ids_elem = prop_def.find('ClassificationIDs')
                if class_ids_elem is None:
                    class_ids_elem = lxml_ET.SubElement(prop_def, 'ClassificationIDs')
                class_id_elem = lxml_ET.SubElement(class_ids_elem, 'ClassificationID')
                lxml_ET.SubElement(class_id_elem, 'ItemID').text = element_id
                lxml_ET.SubElement(class_id_elem, 'SystemIDName').text = systemname
                lxml_ET.SubElement(class_id_elem, 'SystemIDVersion').text = systemversion

    return element_tree

def xml_to_json(folder, is_input=True):
    json_folder = os.path.join('temp', 'input_json' if is_input else 'output_json')
    if not os.path.exists(json_folder):
        os.makedirs(json_folder)

    def parse_element(element):
        result = {
            'id': element.find('ID').text if element.find('ID') is not None else None,
            'properties': [],
            'children': []
        }

        # Get properties
        for prop_def in root.findall('.//PropertyDefinition'):
            prop_name = prop_def.find('Name').text
            class_ids = [class_id.find('ItemID').text for class_id in prop_def.findall('.//ClassificationID')]
            if result['id'] in class_ids:
                result['properties'].append(prop_name)

        # Process children
        children = element.find('Children')
        if children is not None:
            for child in children:
                if child.tag == 'Item':
                    result['children'].append(parse_element(child))

        return result

    for filename in os.listdir(folder):
        if filename.endswith('.xml'):
            input_path = os.path.join(folder, filename)
            output_filename = f"{os.path.splitext(filename)[0]}.json"
            output_path = os.path.join(json_folder, output_filename)

            tree = lxml_ET.parse(input_path)
            root = tree.getroot()

            items = root.find('.//Items')
            if items is None:
                print(f"Warning: No Items found in {filename}")
                continue

            result = []
            for item in items:
                if item.tag == 'Item':
                    result.append(parse_element(item))

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print(f"Processed {filename} -> {output_filename}")

    print(f"All XML files have been converted to JSON in {json_folder}.")

def element_tree_to_json(element_tree, filename):
    json_folder = os.path.join('temp', 'element_tree_json')
    if not os.path.exists(json_folder):
        os.makedirs(json_folder)

    def convert_node(node):
        return {
            'id': node['id'],
            'properties': list(node['properties']),
            'children': [convert_node(child) for child in node['children']]
        }

    result = [convert_node(root_node) for root_node in element_tree]

    output_filename = f"element_tree_{os.path.splitext(filename)[0]}.json"
    output_path = os.path.join(json_folder, output_filename)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Element tree JSON saved to {output_path}")

def print_element_tree(element_tree, indent=""):
    for node in element_tree:
        print(f"{indent}{node['id']}: {node['properties']}")
        print_element_tree(node['children'], indent + "  ")

# Main execution
input_folder = 'inputs'
output_folder = 'outputs'

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

if not os.path.exists('temp'):
    os.makedirs('temp')

# Generate JSON for input XML files
xml_to_json(input_folder, is_input=True)

for filename in os.listdir(input_folder):
    if filename.endswith('.xml'):
        input_path = os.path.join(input_folder, filename)
        output_filename = f"{os.path.splitext(filename)[0]}_processed.xml"
        output_path = os.path.join(output_folder, output_filename)
        
        element_tree = process_xml_file(input_path, output_path)
        
        # Generate JSON for the element tree
        element_tree_to_json(element_tree, filename)

# Generate JSON for output XML files
xml_to_json(output_folder, is_input=False)

print("All XML files processed and additional JSON files generated.")

#### THIS IS SLOW, ONLY UNCOMMENT IF YOU RUN INTO ISSUES!!!