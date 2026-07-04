import os
import xml.etree.ElementTree as ET
import base64
import urllib.request
import urllib.error
import json
import sys

def execute_azure_command(command_str):
    publish_settings_path = 'aiemagazine.PublishSettings'
    if not os.path.exists(publish_settings_path):
        return "PublishSettings file not found!"

    try:
        tree = ET.parse(publish_settings_path)
        root = tree.getroot()
    except Exception as e:
        return f"Error parsing PublishSettings: {e}"

    zip_profile = None
    for profile in root.findall('.//publishProfile'):
        if profile.attrib.get('publishMethod') == 'ZipDeploy':
            zip_profile = profile
            break
    if not zip_profile:
        for profile in root.findall('.//publishProfile'):
            zip_profile = profile
            break

    if not zip_profile:
        return "No publish profile found!"

    username = zip_profile.attrib.get('userName')
    password = zip_profile.attrib.get('userPWD')
    publish_url = zip_profile.attrib.get('publishUrl')

    scm_host = publish_url.split(':')[0]
    url = f"https://{scm_host}/api/command"

    auth_str = f"{username}:{password}"
    auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')

    body = {
        "command": command_str,
        "dir": "/home/site/wwwroot"
    }
    
    req = urllib.request.Request(
        url, 
        data=json.dumps(body).encode('utf-8'),
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth_b64}'
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            res_data = response.read().decode('utf-8')
            res_json = json.loads(res_data)
            return res_json
    except urllib.error.HTTPError as e:
        return f"HTTP Error: {e.code} {e.reason}\n{e.read().decode('utf-8', errors='replace')}"
    except Exception as e:
        return f"Error: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python kudu_exec.py \"<command>\"")
        sys.exit(1)
    
    command = " ".join(sys.argv[1:])
    result = execute_azure_command(command)
    if isinstance(result, dict):
        sys.stdout.buffer.write(b"--- STDOUT ---\n")
        stdout_val = result.get('Output') or ""
        sys.stdout.buffer.write(stdout_val.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(b"\n--- STDERR ---\n")
        stderr_val = result.get('Error') or ""
        sys.stdout.buffer.write(stderr_val.encode('utf-8', errors='replace'))
        sys.stdout.buffer.write(f"\nExit Code: {result.get('ExitCode')}\n".encode('utf-8'))
    else:
        sys.stdout.buffer.write(str(result).encode('utf-8', errors='replace'))
