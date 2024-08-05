import os
import xml.etree.ElementTree as ET
import json
from collections import defaultdict
import lxml.etree as lxml_ET

def detect_language(root):
    # Check for a French property
    french_properties = get_properties_to_delete("French")
    for prop in french_properties:
        if root.find(f".//PropertyDefinition/Name[.='{prop}']") is not None:
            print("French")
            return "French"
    print("English")
    return "English"

def get_properties_to_delete(language):
    if language == "English":
        return ["Position ArchiCAD - IsExternal", "Structural Function ArchiCAD - IsLoadBearing", "IFC renovation status"]
    else:  # French
        return ["Position ArchiCAD - Est extérieur", "Fonction structurelle ArchiCAD - Est porteur", "État de rénovation (Espace et Zone)"]

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

def get_properties(root):
    properties = defaultdict(set)
    for prop_def in root.findall('.//PropertyDefinition'):
        name_elem = prop_def.find('Name')
        if name_elem is not None:
            prop_name = name_elem.text
            for class_id in prop_def.findall('.//ClassificationID/ItemID'):
                if class_id is not None:
                    item_id = class_id.text
                    properties[item_id].add(prop_name)
    return properties

def assign_properties(tree, properties):
    def recursive_assign(node, parent_properties=None):
        if parent_properties is None:
            parent_properties = set()

        #print(f"Processing node: {node['name']} (ID: {node['id']})")

        # Assign properties from the properties dictionary
        if node['id'] in properties:
            node['properties'] = set(properties[node['id']])
        else:
            node['properties'] = set()

        #print(f"  Initial properties: {node['properties']}")

        # Inherit properties from parent
        node['properties'].update(parent_properties)
        #print(f"  After inheriting from parent: {node['properties']}")

        children_with_properties = [child for child in node['children'] if properties.get(child['id'])]
        #if children_with_properties:
        #    print(f"  Children with properties: {[child['id'] for child in children_with_properties]}")
        
        # Handle cases where parent has no original properties but children do
        if not properties.get(node['id']) and children_with_properties:
            #print(f"  Parent {node['id']} has no properties but children do")
            child_property_sets = [set(properties[child['id']]) for child in children_with_properties]
            
            if all(prop_set == child_property_sets[0] for prop_set in child_property_sets):
                #print(f"  All children have the same properties. Updating parent and siblings.")
                node['properties'].update(child_property_sets[0])
                #print(f"Update parent: {node['id']}")
                #print(node['properties'])
                for child in node['children']:
                    child['properties'] = set(node['properties'])
            elif node['id'] in ['Covering', 'Revêtement']:
                handle_covering_case(node, properties)
            elif node['id'] not in ['Chimney', 'Cheminée']:
                print(f"  Warning: {node['id']} has no properties, and its children have different properties")
                # Merge all child properties into the parent
                for prop_set in child_property_sets:
                    node['properties'].update(prop_set)
                # Update children without properties
                for child in node['children']:
                    if not properties.get(child['id']):
                        child['properties'] = set(node['properties'])

        #print(f"  Final properties: {node['properties']}")

        # Recursively process children
        for child in node['children']:
            recursive_assign(child, node['properties'])

    for node in tree:
        recursive_assign(node)

def handle_covering_case(node, properties):
    covering_children = ['Ceiling', 'Revêtement de plafond', 'Cladding', 'Revêtement de paroi', 
                         'Flooring', 'Revêtement de sol', 'Roofing', 'Couverture de toiture']
    all_properties = set()
    for child in node['children']:
        if child['id'] in covering_children and properties.get(child['id']):
            all_properties.update(properties[child['id']])
    
    if all_properties:
        node['properties'].update(all_properties)
        for child in node['children']:
            if not properties.get(child['id']):
                child['properties'] = set(all_properties)


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

    loopNum = 0
    prevProps = None
    prevTree = None
    element_tree = build_element_tree(root)
    properties = get_properties(root)
    while properties != prevProps or element_tree != prevTree or not prevProps or not prevTree:
        prevProps = properties
        prevTree = element_tree
        loopNum += 1
        print(f"loop {loopNum}")
        assign_properties(element_tree, properties)
        
        #element_tree = build_element_tree(root)
        properties = get_properties(root)

    # Update XML with new properties
    update_xml_properties(root, element_tree)
    tree.write(output_path, encoding='UTF-8', xml_declaration=True, pretty_print=True)
    print(f"Updated XML saved to {output_path}")

    return element_tree

def update_xml_properties(root, element_tree):
    prop_def_groups = root.find('.//PropertyDefinitionGroups')
    if prop_def_groups is None:
        print("Error: No PropertyDefinitionGroups found in the XML.")
        return

    property_classes = {}
    def collect_properties(node):
        for prop in node['properties']:
            if prop not in property_classes:
                property_classes[prop] = set()
            property_classes[prop].add(node['id'])
        for child in node['children']:
            collect_properties(child)

    for root_node in element_tree:
        collect_properties(root_node)

    prop_def_groups.clear()
    new_group = lxml_ET.SubElement(prop_def_groups, 'PropertyDefinitionGroup')
    lxml_ET.SubElement(new_group, 'Name').text = 'Updated Properties'
    lxml_ET.SubElement(new_group, 'Description')
    prop_defs = lxml_ET.SubElement(new_group, 'PropertyDefinitions')

    for prop_name, class_ids in property_classes.items():
        new_prop_def = lxml_ET.SubElement(prop_defs, 'PropertyDefinition')
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
        for class_id in class_ids:
            class_id_elem = lxml_ET.SubElement(class_ids_elem, 'ClassificationID')
            lxml_ET.SubElement(class_id_elem, 'ItemID').text = class_id
            lxml_ET.SubElement(class_id_elem, 'SystemIDName').text = 'ARCHICAD Classification'
            lxml_ET.SubElement(class_id_elem, 'SystemIDVersion').text = 'v 2.0'


input_folder = 'inputs'
output_folder = 'outputs'

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

for filename in os.listdir(input_folder):
    if filename.endswith('.xml'):
        input_path = os.path.join(input_folder, filename)
        output_filename = f"{os.path.splitext(filename)[0]}_processed.xml"
        output_path = os.path.join(output_folder, output_filename)
        
        element_tree = process_xml_file(input_path, output_path)

print("All XML files processed.")


def xml_to_json(output_folder):
    json_folder = os.path.join(output_folder, 'json')
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

    for filename in os.listdir(output_folder):
        if filename.endswith('_processed.xml'):
            input_path = os.path.join(output_folder, filename)
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

    print("All processed XML files have been converted to JSON.")

#xml_to_json(output_folder)

#### THIS IS SLOW, ONLY UNCOMMENT IF YOU RUN INTO ISSUES!!!