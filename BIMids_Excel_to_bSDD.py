import pandas as pd
import os
import json
from datetime import datetime

def process_class_properties(excel_file, sheet_name, class_code, dic_ver):
    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
    properties = []
    property_section = False
    excluded_properties = ['Object name', 'IFC Type', 'IFC Object Type', 'Classification', 'Numerical identifier', 'PROPERTY']
    used_codes = set()

    for _, row in df.iterrows():
        if 'ALPHANUMERICAL INFORMATION' in str(row[0]):
            property_section = True
            continue
        
        if property_section and pd.notna(row[0]) and pd.notna(row[49]):  # Column AX is index 49
            if row[0] not in excluded_properties:
                uri_code = str(row[49]).lower().replace(' ', '').replace('/', '_')
                property_code = str(row[0]).lower().replace(' ', '').replace('/', '_')
                property_name = str(row[0])
                
                uri_code_short = uri_code.split('.')[-1]  # Get the part after the last dot
                uri_code_short = ''.join([i for i in uri_code_short if not i.isdigit()])  # Remove numbers
                
                # Determine the property type and generate the appropriate URI
                if uri_code.startswith('pset_'):
                    uri = f"https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3/prop/{uri_code_short}"
                elif uri_code.startswith('bimids_'):
                    uri_code = ''.join([i for i in property_code if not i.isdigit()])
                    uri = f"https://identifier.buildingsmart.org/uri/bw/bimids/{dic_ver}/prop/{uri_code_short}"
                else:
                    uri = f"https://identifier.buildingsmart.org/uri/bw/bimids/{dic_ver}/prop/{uri_code_short}"


                if property_code not in used_codes:
                    used_codes.add(property_code)
                    properties.append({
                        "Code": property_code,
                        "Name": property_name,
                        "PropertyUri": uri
                    })
                    if uri_code.startswith('bimids_'):
                        properties.append({"PropertyCode": property_code})
        elif property_section and pd.isna(row[0]):
            break

    return properties

def excel_to_bsdd_json(excel_file):
    try:
        full_path = os.path.abspath(excel_file)
        print(f"Attempting to open file: {full_path}")

        props_df = pd.read_excel(full_path, sheet_name='Property definitions', header=None)
        classes_df = pd.read_excel(full_path, sheet_name='IFC mapping', header=None)
        
        used_class_codes = []
        used_property_codes = []
        dic_ver = "0.2"

        bsdd_json = {
            "OrganizationCode": "bw",
            "DictionaryCode": "BIMids",
            "DictionaryVersion": dic_ver,
            "DictionaryName": "BIMids",
            "ReleaseDate": datetime.now().isoformat(),
            "Status": "Preview",
            "ChangeRequestEmailAddress": "louis.casteleyn@buildwise.be",
            "LanguageIsoCode": "EN",
            "License": "CC BY-ND 4.0",
            "LicenseUrl": "https://creativecommons.org/licenses/by-nd/4.0/legalcode",
            "QualityAssuranceProcedure": "This content is in draft and still under development. Do not use this as final content",
            "ModelVersion": "2.0",
            "Classes": [],
            "Properties": []
        }

        for _, row in props_df.iterrows():
            if pd.notna(row[0]) and pd.notna(row[2]) and row[2] != "VALUE":
                code = str(row[0]).lower().replace(' ', '').replace('/', '')
                if code not in used_property_codes:
                    prop = {
                        "Code": code,
                        "Name": str(row[0]),
                        "Definition": str(row[2])
                    }
                    bsdd_json['Properties'].append(prop)
                    used_property_codes.append(code)

        for _, row in classes_df.iterrows():
            if pd.notna(row[0]) and pd.notna(row[4]) and row[0] not in ["ELEMENT", 'GROUP']:
                class_name = row[0]
                ifc_class = row[4]
                code = str(row[0]).lower().replace(' ', '').replace('/', '')
                if code not in used_class_codes:
                    class_obj = {
                        "Code": code,
                        "Name": class_name,
                        "ClassType": "Class",
                        "Definition": f"Represents a {class_name.lower()}.",
                        "CreatorLanguageIsoCode": "EN",
                        "RelatedIfcEntityNamesList": [ifc_class.split('.')[0]],
                        "ClassRelations": [
                            {
                                "RelationType": "IsEqualTo",
                                "RelatedClassUri": f"https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3/class/{ifc_class.replace('.', '')}"
                            }
                        ],
                        "ClassProperties": []
                    }

                    # Process properties for this class
                    try:
                        class_properties = process_class_properties(full_path, class_name.replace('/', ''), code, dic_ver)
                        class_obj["ClassProperties"] = class_properties
                    except Exception as e:
                        print(f"Error processing properties for {class_name}: {str(e)}")

                    bsdd_json['Classes'].append(class_obj)
                    used_class_codes.append(code)

        output_file = 'bsdd_output.json'
        with open(output_file, 'w') as f:
            json.dump(bsdd_json, f, indent=2)

        print(f"bSDD JSON file has been generated: {output_file}")

    except Exception as e:
        print(f"An error occurred: {str(e)}")

# Usage
excel_file = '240912_EIR_AR-MEP-ST_multiple use-cases_HDWI.xlsx'
excel_to_bsdd_json(excel_file)


# BASE_URL = "https://api.bsdd.buildingsmart.org"

# def search_term(term: str, type_filter: str = "All", dictionary_uris: List[str] = None) -> List[Dict]:
#     """
#     Search for a term across specified dictionaries or all dictionaries if none specified.
#     """
#     endpoint = f"{BASE_URL}/api/TextSearch/v1"
#     params = {
#         "SearchText": term,
#         "TypeFilter": type_filter,
#         "Limit": 10
#     }
#     if dictionary_uris:
#         params["DictionaryUris"] = dictionary_uris

#     response = requests.get(endpoint, params=params)
#     response.raise_for_status()
    
#     return response.json().get("classes", []) + response.json().get("properties", [])

# def process_term_list(terms: List[str], type_filter: str = "All", dictionary_uris: List[str] = None) -> Dict[str, List[Dict]]:
#     """
#     Process a list of terms, searching for each in the specified dictionaries.
#     """
#     results = {}
#     for term in terms:
#         matches = search_term(term, type_filter, dictionary_uris)
#         results[term] = matches
    
#     return results

# def print_results(results: Dict[str, List[Dict]]):
#     """
#     Print the results in a formatted way.
#     """
#     for term, matches in results.items():
#         print(f"\nResults for '{term}':")
#         if matches:
#             for match in matches:
#                 try:
#                     print(f"  - Found in {match['dictionaryName']} ({match['dictionaryUri']})")
#                     print(f"    Name: {match['name']}")
#                     print(f"    URI: {match['uri']}")
#                     print(f"    Type: {match['classType']}")
#                     if 'parentClassName' in match:
#                         print(f"    Parent: {match['parentClassName']}")
#                     if 'relatedIfcEntityNames' in match:
#                         print(f"    Related IFC Entities: {', '.join(match['relatedIfcEntityNames'])}")
#                     print()
#                 except:
#                     print(f"Error with match {match['name']}")
#         else:
#             print("  No matches found")

# def main():
#     # Example usage
#     class_terms = ["wall", "door", "window", "roof", "floor"]
#     property_terms = ["width"]
#     dictionary_uris = [
#         "https://identifier.buildingsmart.org/uri/buildingsmart/ifc/4.3",
#     ]
#     excel_file = 'BIMids_Excel_to_bSDD.xlsx'

#     # Load the Excel file
#     df = pd.read_excel(excel_file)
    
#     results = process_term_list(class_terms, "Classes")
#     results.update(process_term_list(property_terms, "Properties"))
    
#     print_results(results)

# if __name__ == "__main__":
#     main()

