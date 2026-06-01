import os
import re

routes_file = 'scratch/routes.txt'
bruno_dir = 'bruno/Medi_Vision_AI_API'

def get_next_seq(collection_path):
    if not os.path.exists(collection_path):
        os.makedirs(collection_path)
        return 1
    files = os.listdir(collection_path)
    max_seq = 0
    for f in files:
        if f.endswith('.bru'):
            match = re.match(r'^(\d+)_', f)
            if match:
                max_seq = max(max_seq, int(match.group(1)))
    return max_seq + 1

def generate_bru(collection, name, method, url):
    collection_path = os.path.join(bruno_dir, collection)
    seq = get_next_seq(collection_path)
    
    # Format readable name
    safe_name = re.sub(r'[^a-zA-Z0-9]', '_', name)
    file_name = f"{seq:02d}_{safe_name}.bru"
    file_path = os.path.join(collection_path, file_name)
    
    # Replace parameters
    url = url.replace('<int:id>', '1')
    url = url.replace('<id>', '1')
    url = url.replace('<int:voucher_id>', '1')
    url = url.replace('<bill_id>', 'BILL-001')
    url = url.replace('<int:expense_id>', '1')
    url = url.replace('<int:staff_id>', '1')
    url = url.replace('<int:wanted_id>', '1')
    url = url.replace('<int:return_id>', '1')
    url = url.replace('<int:customer_id>', '1')
    
    body_type = "json" if method.lower() in ["post", "put", "patch"] else "none"

    content = f"""meta {{
  name: {name}
  type: http
  seq: {seq}
}}

{method.lower()} {{
  url: {{{{baseUrl}}}}{url}
  body: {body_type}
  auth: none
}}

vars:pre-request {{
  baseUrl: http://127.0.0.1:5001
}}
"""
    with open(file_path, 'w') as f:
        f.write(content)
    print(f"Created: {file_path}")

existing_endpoints = set()
for root, dirs, files in os.walk(bruno_dir):
    for file in files:
        if file.endswith('.bru'):
            with open(os.path.join(root, file), 'r') as f:
                content = f.read()
                # find method and url
                match_method = re.search(r'^(get|post|put|patch|delete) \{', content, re.MULTILINE)
                match_url = re.search(r'url:\s*\{\{baseUrl\}\}(/[^\n]*)', content)
                if match_method and match_url:
                    method = match_method.group(1).upper()
                    url = match_url.group(1).strip()
                    existing_endpoints.add(f"{method} {url}")

with open(routes_file, 'r') as f:
    for line in f:
        if not line.strip(): continue
        parts = line.strip().split(' | ')
        if len(parts) == 3:
            endpoint_name = parts[0]
            methods_str = parts[1]
            url = parts[2]
            
            # Filter strictly for /api/
            if not url.startswith('/api/'):
                continue
                
            # determine collection
            blueprint = endpoint_name.split('.')[0]
            collection_name = blueprint.capitalize()
            if collection_name == 'Wanted_list': collection_name = 'Wanted_List'
            
            # Form friendly name
            func_name = endpoint_name.split('.')[1] if '.' in endpoint_name else endpoint_name
            friendly_name = ' '.join(word.capitalize() for word in func_name.split('_'))
            
            test_url = url.replace('<int:id>', '1').replace('<id>', '1').replace('<int:voucher_id>', '1').replace('<bill_id>', 'BILL-001').replace('<int:expense_id>', '1').replace('<int:staff_id>', '1').replace('<int:wanted_id>', '1').replace('<int:return_id>', '1').replace('<int:customer_id>', '1')
            
            for method in methods_str.split(','):
                method = method.strip()
                if f"{method} {test_url}" not in existing_endpoints:
                    generate_bru(collection_name, friendly_name, method, url)
                    existing_endpoints.add(f"{method} {test_url}")
